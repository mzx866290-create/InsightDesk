"""Helpers for promoting panel answers within a chat session."""

from __future__ import annotations

import sqlite3
import time
from typing import Any, Callable, Optional

from backend.core.storage_runtime import app_database_path
from backend.stores.chat_schema import init_messages_table, init_session_panels_table
from backend.stores.chat_serialization import normalize_token_usage, parse_json_list
from backend.stores.sqlite_runtime import connect_sqlite

DB_PATH = app_database_path()


def promote_panel_answer(
    session_id: str,
    answer_group_id: str,
    source_panel_id: str,
    db_path: str = DB_PATH,
    *,
    connect_sqlite_fn: Callable[[str | None], sqlite3.Connection] = connect_sqlite,
) -> Optional[dict[str, Any]]:
    with connect_sqlite_fn(db_path) as conn:
        init_messages_table(conn)
        init_session_panels_table(conn)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT panel_id
            FROM session_panels
            WHERE session_id = ?
            ORDER BY is_primary DESC, display_order ASC, updated_at ASC
            LIMIT 1
            """,
            (session_id,),
        )
        primary_row = cursor.fetchone()
        target_panel_id = (
            str(primary_row[0]).strip() if primary_row and primary_row[0] else ""
        )
        if not target_panel_id:
            target_panel_id = source_panel_id

        cursor.execute(
            """
            SELECT id, content, model_id, sources_json, workflow_json, token_usage_json, task_id, task_type
            FROM messages
            WHERE session_id = ?
              AND type = 'ai'
              AND COALESCE(panel_id, '') = ?
              AND COALESCE(answer_group_id, '') = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (session_id, source_panel_id, answer_group_id),
        )
        source_row = cursor.fetchone()
        if not source_row:
            return None

        source_content = str(source_row[1] or "")
        source_model_id = str(source_row[2] or "")
        source_sources_json = str(source_row[3] or "")
        source_workflow_json = str(source_row[4] or "")
        source_token_usage_json = str(source_row[5] or "")
        source_task_id = str(source_row[6] or "")
        source_task_type = str(source_row[7] or "")

        cursor.execute(
            """
            SELECT id
            FROM messages
            WHERE session_id = ?
              AND type = 'ai'
              AND COALESCE(panel_id, '') = ?
              AND COALESCE(answer_group_id, '') = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (session_id, target_panel_id, answer_group_id),
        )
        target_row = cursor.fetchone()
        if target_row:
            cursor.execute(
                """
                UPDATE messages
                SET content = ?, model_id = ?, sources_json = ?, workflow_json = ?, token_usage_json = ?, task_id = ?, task_type = ?
                WHERE id = ?
                """,
                (
                    source_content,
                    source_model_id,
                    source_sources_json,
                    source_workflow_json,
                    source_token_usage_json,
                    source_task_id,
                    source_task_type,
                    int(target_row[0]),
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO messages (
                    session_id, type, content, timestamp, model_id, panel_id, answer_group_id,
                    sources_json, workflow_json, token_usage_json, task_id, task_type
                )
                VALUES (?, 'ai', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    source_content,
                    time.time(),
                    source_model_id,
                    target_panel_id,
                    answer_group_id,
                    source_sources_json,
                    source_workflow_json,
                    source_token_usage_json,
                    source_task_id,
                    source_task_type,
                ),
            )

        cursor.execute(
            "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
            (time.time(), session_id),
        )
        conn.commit()
        return {
            "target_panel_id": target_panel_id,
            "source_panel_id": source_panel_id,
            "answer_group_id": answer_group_id,
            "content": source_content,
            "model_id": source_model_id,
            "sources": parse_json_list(source_sources_json),
            "workflow_nodes": parse_json_list(source_workflow_json),
            "token_usage": normalize_token_usage(source_token_usage_json),
            "task_id": source_task_id,
            "task_type": source_task_type,
        }


__all__ = ["promote_panel_answer"]
