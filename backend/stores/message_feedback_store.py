"""AI message feedback helpers for SQLite and PostgreSQL runtimes."""

from __future__ import annotations

import sqlite3
from typing import Any, Callable, Optional, cast

from backend.core.storage_runtime import (
    DATABASE_PROVIDER_POSTGRES,
    app_database_path,
    database_provider,
)
from backend.stores.chat_normalization import normalize_message_feedback_value
from backend.stores.chat_schema import init_messages_table, init_sessions_table
from backend.stores.sqlite_runtime import connect_sqlite

DB_PATH = app_database_path()


def _should_use_postgres_store(db_path: str | None = None) -> bool:
    normalized_db_path = str(db_path or "").strip()
    return database_provider() == DATABASE_PROVIDER_POSTGRES and normalized_db_path in {
        "",
        DB_PATH,
    }


def set_message_feedback(
    session_id: str,
    *,
    feedback_value: int,
    message_id: Optional[int] = None,
    panel_id: str = "",
    answer_group_id: str = "",
    db_path: str | None = None,
    connect_sqlite_fn: Callable[[str | None], sqlite3.Connection] = connect_sqlite,
) -> Optional[dict[str, Any]]:
    normalized_feedback_value = normalize_message_feedback_value(feedback_value)
    normalized_panel_id = str(panel_id or "").strip()
    normalized_answer_group_id = str(answer_group_id or "").strip()

    if _should_use_postgres_store(db_path):
        from backend.stores.factory import create_chat_message_history

        history = create_chat_message_history(session_id)
        return cast(
            Optional[dict[str, Any]],
            history.set_message_feedback(
                feedback_value=normalized_feedback_value,
                message_id=message_id,
                panel_id=normalized_panel_id,
                answer_group_id=normalized_answer_group_id,
            ),
        )

    with connect_sqlite_fn(db_path) as conn:
        init_messages_table(conn)
        init_sessions_table(conn)
        cursor = conn.cursor()

        target_row: tuple[Any, ...] | None = None
        if message_id is not None:
            cursor.execute(
                """
                SELECT id, COALESCE(panel_id, ''), COALESCE(answer_group_id, '')
                FROM messages
                WHERE session_id = ?
                  AND id = ?
                  AND type = 'ai'
                LIMIT 1
                """,
                (session_id, int(message_id)),
            )
            target_row = cursor.fetchone()
        else:
            if not normalized_answer_group_id:
                raise ValueError("answer_group_id is required when message_id is missing")
            cursor.execute(
                """
                SELECT id, COALESCE(panel_id, ''), COALESCE(answer_group_id, '')
                FROM messages
                WHERE session_id = ?
                  AND type = 'ai'
                  AND COALESCE(panel_id, '') = ?
                  AND COALESCE(answer_group_id, '') = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (session_id, normalized_panel_id, normalized_answer_group_id),
            )
            target_row = cursor.fetchone()

        if not target_row:
            return None

        resolved_message_id = int(target_row[0])
        resolved_panel_id = str(target_row[1] or "")
        resolved_answer_group_id = str(target_row[2] or "")

        cursor.execute(
            "UPDATE messages SET feedback_value = ? WHERE id = ?",
            (normalized_feedback_value, resolved_message_id),
        )
        conn.commit()

    return {
        "message_id": resolved_message_id,
        "panel_id": resolved_panel_id,
        "answer_group_id": resolved_answer_group_id,
        "feedback_value": normalized_feedback_value,
    }


__all__ = ["set_message_feedback"]
