"""PostgreSQL retrieval feedback store adapter."""

from __future__ import annotations

import time
from typing import Any, Callable

from backend.chat_store import (
    _build_retrieval_source_key,
    _normalize_content,
    _normalize_message_feedback_value,
)
from backend.stores.pg_base import PostgresStoreMixin


class PostgresRetrievalFeedbackStore(PostgresStoreMixin):
    """Persist per-source retrieval feedback in PostgreSQL."""

    def __init__(
        self,
        dsn: str | None = None,
        *,
        connection_factory: Callable[..., Any] | None = None,
    ) -> None:
        PostgresStoreMixin.__init__(self, dsn, connection_factory=connection_factory)
        self.db_path = self.dsn
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS retrieval_feedback (
                        id BIGSERIAL PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        panel_id TEXT NOT NULL,
                        answer_group_id TEXT NOT NULL,
                        source_key TEXT NOT NULL,
                        source_type TEXT DEFAULT '',
                        source_title TEXT DEFAULT '',
                        source_url TEXT DEFAULT '',
                        feedback_value INTEGER NOT NULL DEFAULT 0,
                        created_at DOUBLE PRECISION NOT NULL,
                        updated_at DOUBLE PRECISION NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_retrieval_feedback_unique
                    ON retrieval_feedback(session_id, panel_id, answer_group_id, source_key)
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_retrieval_feedback_lookup
                    ON retrieval_feedback(session_id, answer_group_id, panel_id, updated_at DESC)
                    """
                )
            conn.commit()

    def set_retrieval_feedback(
        self,
        session_id: str,
        *,
        panel_id: str,
        answer_group_id: str,
        source: dict[str, Any],
        feedback_value: int,
    ) -> dict[str, Any]:
        normalized_feedback_value = _normalize_message_feedback_value(feedback_value)
        normalized_panel_id = str(panel_id or "").strip()
        normalized_answer_group_id = str(answer_group_id or "").strip()
        if not normalized_panel_id:
            raise ValueError("必须提供 panel_id")
        if not normalized_answer_group_id:
            raise ValueError("必须提供 answer_group_id")

        source_key = _build_retrieval_source_key(source)
        source_type = str(source.get("type") or "").strip().lower()
        source_title = _normalize_content(source.get("title", "")).strip()
        source_url = _normalize_content(source.get("url", "")).strip()
        now = time.time()

        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM sessions WHERE session_id = %s LIMIT 1",
                    (session_id,),
                )
                if not cursor.fetchone():
                    raise ValueError("未找到会话")
                cursor.execute(
                    """
                    INSERT INTO retrieval_feedback (
                        session_id, panel_id, answer_group_id, source_key,
                        source_type, source_title, source_url,
                        feedback_value, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(session_id, panel_id, answer_group_id, source_key)
                    DO UPDATE SET
                        source_type = EXCLUDED.source_type,
                        source_title = EXCLUDED.source_title,
                        source_url = EXCLUDED.source_url,
                        feedback_value = EXCLUDED.feedback_value,
                        updated_at = EXCLUDED.updated_at
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
        self,
        session_id: str,
        *,
        panel_id: str,
        answer_group_id: str,
    ) -> list[dict[str, Any]]:
        normalized_panel_id = str(panel_id or "").strip()
        normalized_answer_group_id = str(answer_group_id or "").strip()
        if not normalized_panel_id:
            raise ValueError("必须提供 panel_id")
        if not normalized_answer_group_id:
            raise ValueError("必须提供 answer_group_id")

        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT source_key, feedback_value, updated_at
                    FROM retrieval_feedback
                    WHERE session_id = %s
                      AND panel_id = %s
                      AND answer_group_id = %s
                    ORDER BY updated_at DESC
                    """,
                    (session_id, normalized_panel_id, normalized_answer_group_id),
                )
                rows = cursor.fetchall()
        return [
            {
                "source_key": str(self._row_value(row, 0, "source_key") or ""),
                "feedback_value": _normalize_message_feedback_value(
                    self._row_value(row, 1, "feedback_value")
                ),
                "updated_at": float(self._row_value(row, 2, "updated_at") or 0),
            }
            for row in rows
        ]

    def aggregate_retrieval_feedback_by_source(
        self,
        *,
        source_type: str | None = None,
    ) -> list[dict[str, Any]]:
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
            query += " AND source_type = %s"
            params.append(normalized_source_type)
        query += """
            GROUP BY source_type, source_title, source_url
            ORDER BY net_feedback DESC, positive_count DESC, negative_count ASC, last_updated_at DESC
        """
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
        return [
            {
                "source_type": str(self._row_value(row, 0, "source_type") or "").strip().lower(),
                "source_title": str(self._row_value(row, 1, "source_title") or "").strip(),
                "source_url": str(self._row_value(row, 2, "source_url") or "").strip(),
                "positive_count": int(self._row_value(row, 3, "positive_count") or 0),
                "negative_count": int(self._row_value(row, 4, "negative_count") or 0),
                "net_feedback": int(self._row_value(row, 5, "net_feedback") or 0),
                "total_count": int(self._row_value(row, 6, "total_count") or 0),
                "last_updated_at": float(self._row_value(row, 7, "last_updated_at") or 0),
            }
            for row in rows
        ]
