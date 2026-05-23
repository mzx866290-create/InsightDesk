"""Retrieval source feedback helpers for SQLite and PostgreSQL runtimes."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Optional

from backend.core.storage_runtime import (
    DATABASE_PROVIDER_POSTGRES,
    app_database_path,
    database_provider,
)
from backend.stores.chat_messages import build_retrieval_source_key
from backend.stores.chat_normalization import normalize_message_feedback_value
from backend.stores.chat_schema import (
    init_retrieval_feedback_table,
    init_sessions_table,
)
from backend.stores.chat_serialization import normalize_content
from backend.stores.sqlite_runtime import connect_sqlite

DB_PATH = app_database_path()

if TYPE_CHECKING:
    from backend.stores.protocols import RetrievalFeedbackStore


def _should_use_postgres_store(db_path: str | None = None) -> bool:
    normalized_db_path = str(db_path or "").strip()
    return database_provider() == DATABASE_PROVIDER_POSTGRES and normalized_db_path in {
        "",
        DB_PATH,
    }


def _retrieval_feedback_store() -> "RetrievalFeedbackStore":
    from backend.stores.factory import create_retrieval_feedback_store

    return create_retrieval_feedback_store()


def set_retrieval_feedback(
    session_id: str,
    *,
    panel_id: str,
    answer_group_id: str,
    source: dict[str, Any],
    feedback_value: int,
    db_path: str | None = None,
) -> dict[str, Any]:
    if _should_use_postgres_store(db_path):
        return _retrieval_feedback_store().set_retrieval_feedback(
            session_id,
            panel_id=panel_id,
            answer_group_id=answer_group_id,
            source=source,
            feedback_value=feedback_value,
        )

    normalized_feedback_value = normalize_message_feedback_value(feedback_value)
    normalized_panel_id = str(panel_id or "").strip()
    normalized_answer_group_id = str(answer_group_id or "").strip()
    if not normalized_panel_id:
        raise ValueError("panel_id is required")
    if not normalized_answer_group_id:
        raise ValueError("answer_group_id is required")

    source_key = build_retrieval_source_key(source)
    source_type = str(source.get("type") or "").strip().lower()
    source_title = normalize_content(source.get("title", "")).strip()
    source_url = normalize_content(source.get("url", "")).strip()
    now = time.time()

    with connect_sqlite(db_path) as conn:
        init_sessions_table(conn)
        init_retrieval_feedback_table(conn)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM sessions WHERE session_id = ? LIMIT 1",
            (session_id,),
        )
        if not cursor.fetchone():
            raise ValueError("Session not found")

        cursor.execute(
            """
            INSERT INTO retrieval_feedback (
                session_id,
                panel_id,
                answer_group_id,
                source_key,
                source_type,
                source_title,
                source_url,
                feedback_value,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id, panel_id, answer_group_id, source_key)
            DO UPDATE SET
                source_type = excluded.source_type,
                source_title = excluded.source_title,
                source_url = excluded.source_url,
                feedback_value = excluded.feedback_value,
                updated_at = excluded.updated_at
            """,
            (
                session_id,
                normalized_panel_id,
                normalized_answer_group_id,
                source_key,
                source_type,
                source_title,
                source_url,
                normalized_feedback_value,
                now,
                now,
            ),
        )
        conn.commit()

    return {
        "session_id": session_id,
        "panel_id": normalized_panel_id,
        "answer_group_id": normalized_answer_group_id,
        "source_key": source_key,
        "feedback_value": normalized_feedback_value,
        "updated_at": now,
    }


def list_retrieval_feedback(
    session_id: str,
    *,
    panel_id: str,
    answer_group_id: str,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    if _should_use_postgres_store(db_path):
        return _retrieval_feedback_store().list_retrieval_feedback(
            session_id,
            panel_id=panel_id,
            answer_group_id=answer_group_id,
        )

    normalized_panel_id = str(panel_id or "").strip()
    normalized_answer_group_id = str(answer_group_id or "").strip()
    if not normalized_panel_id:
        raise ValueError("panel_id is required")
    if not normalized_answer_group_id:
        raise ValueError("answer_group_id is required")

    with connect_sqlite(db_path) as conn:
        init_retrieval_feedback_table(conn)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                source_key,
                feedback_value,
                updated_at
            FROM retrieval_feedback
            WHERE session_id = ?
              AND panel_id = ?
              AND answer_group_id = ?
            ORDER BY updated_at DESC
            """,
            (session_id, normalized_panel_id, normalized_answer_group_id),
        )
        rows = cursor.fetchall()

    return [
        {
            "source_key": str(row[0] or ""),
            "feedback_value": normalize_message_feedback_value(row[1]),
            "updated_at": float(row[2] or 0),
        }
        for row in rows
    ]


def aggregate_retrieval_feedback_by_source(
    *,
    source_type: Optional[str] = None,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    if _should_use_postgres_store(db_path):
        return _retrieval_feedback_store().aggregate_retrieval_feedback_by_source(
            source_type=source_type,
        )

    normalized_source_type = str(source_type or "").strip().lower()

    query = """
        SELECT
            source_type,
            source_title,
            source_url,
            SUM(CASE WHEN feedback_value = 1 THEN 1 ELSE 0 END) AS positive_count,
            SUM(CASE WHEN feedback_value = -1 THEN 1 ELSE 0 END) AS negative_count,
            SUM(feedback_value) AS net_feedback,
            COUNT(*) AS total_count,
            MAX(updated_at) AS last_updated_at
        FROM retrieval_feedback
        WHERE feedback_value != 0
    """
    params: list[Any] = []
    if normalized_source_type:
        query += " AND source_type = ?"
        params.append(normalized_source_type)
    query += """
        GROUP BY source_type, source_title, source_url
        ORDER BY net_feedback DESC, positive_count DESC, negative_count ASC, last_updated_at DESC
    """

    with connect_sqlite(db_path) as conn:
        init_retrieval_feedback_table(conn)
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

    return [
        {
            "source_type": str(row[0] or "").strip().lower(),
            "source_title": str(row[1] or "").strip(),
            "source_url": str(row[2] or "").strip(),
            "positive_count": int(row[3] or 0),
            "negative_count": int(row[4] or 0),
            "net_feedback": int(row[5] or 0),
            "total_count": int(row[6] or 0),
            "last_updated_at": float(row[7] or 0),
        }
        for row in rows
    ]


__all__ = [
    "aggregate_retrieval_feedback_by_source",
    "list_retrieval_feedback",
    "set_retrieval_feedback",
]
