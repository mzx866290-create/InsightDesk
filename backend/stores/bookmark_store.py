"""Bookmark persistence helpers for chat messages."""

from __future__ import annotations

import sqlite3
import time
import uuid
from typing import Any, Optional

from backend.stores.chat_normalization import normalize_bookmark_role
from backend.stores.chat_rows import row_to_bookmark
from backend.stores.chat_schema import (
    init_bookmarks_table,
    init_messages_table,
    init_sessions_table,
)
from backend.stores.chat_serialization import normalize_content
from backend.stores.sqlite_runtime import connect_sqlite


def _session_exists(
    cursor: sqlite3.Cursor,
    session_id: str,
) -> bool:
    cursor.execute(
        "SELECT 1 FROM sessions WHERE session_id = ?",
        (session_id,),
    )
    return cursor.fetchone() is not None


def _resolve_bookmark_target(
    cursor: sqlite3.Cursor,
    session_id: str,
    *,
    message_id: Optional[int],
    panel_id: str,
    answer_group_id: str,
    role: str,
) -> Optional[dict[str, Any]]:
    normalized_role = normalize_bookmark_role(role)
    normalized_panel_id = str(panel_id or "").strip()
    normalized_answer_group_id = str(answer_group_id or "").strip()

    if message_id is not None:
        cursor.execute(
            """
            SELECT
                id,
                type,
                content,
                COALESCE(model_id, ''),
                COALESCE(panel_id, ''),
                COALESCE(answer_group_id, '')
            FROM messages
            WHERE session_id = ? AND id = ?
            LIMIT 1
            """,
            (session_id, int(message_id)),
        )
    else:
        if not normalized_answer_group_id:
            raise ValueError("未提供 message_id 时必须提供 answer_group_id")
        message_type = "human" if normalized_role == "user" else "ai"
        if normalized_role == "assistant" and not normalized_panel_id:
            raise ValueError("助手消息书签必须提供 panel_id")
        cursor.execute(
            """
            SELECT
                id,
                type,
                content,
                COALESCE(model_id, ''),
                COALESCE(panel_id, ''),
                COALESCE(answer_group_id, '')
            FROM messages
            WHERE session_id = ?
              AND type = ?
              AND COALESCE(panel_id, '') = ?
              AND COALESCE(answer_group_id, '') = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                session_id,
                message_type,
                "" if normalized_role == "user" else normalized_panel_id,
                normalized_answer_group_id,
            ),
        )

    row = cursor.fetchone()
    if not row:
        return None

    resolved_role = "user" if str(row[1] or "") == "human" else "assistant"
    return {
        "message_id": int(row[0]),
        "role": resolved_role,
        "content": normalize_content(row[2]),
        "model_id": str(row[3] or ""),
        "panel_id": str(row[4] or ""),
        "answer_group_id": str(row[5] or ""),
    }


def get_bookmark(
    bookmark_id: str, db_path: str | None = None
) -> Optional[dict[str, Any]]:
    normalized_bookmark_id = str(bookmark_id or "").strip()
    if not normalized_bookmark_id:
        return None

    with connect_sqlite(db_path) as conn:
        init_sessions_table(conn)
        init_bookmarks_table(conn)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                b.id,
                b.session_id,
                b.message_id,
                COALESCE(b.panel_id, ''),
                COALESCE(b.answer_group_id, ''),
                COALESCE(b.role, 'assistant'),
                COALESCE(b.content, ''),
                COALESCE(b.model_id, ''),
                COALESCE(NULLIF(s.title, ''), NULLIF(b.session_title, ''), ''),
                b.created_at,
                b.updated_at
            FROM bookmarks b
            LEFT JOIN sessions s ON s.session_id = b.session_id
            WHERE b.id = ?
            LIMIT 1
            """,
            (normalized_bookmark_id,),
        )
        row = cursor.fetchone()
        return row_to_bookmark(row) if row else None


def list_bookmarks(
    *,
    session_id: Optional[str] = None,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    with connect_sqlite(db_path) as conn:
        init_sessions_table(conn)
        init_bookmarks_table(conn)
        cursor = conn.cursor()

        sql = """
            SELECT
                b.id,
                b.session_id,
                b.message_id,
                COALESCE(b.panel_id, ''),
                COALESCE(b.answer_group_id, ''),
                COALESCE(b.role, 'assistant'),
                COALESCE(b.content, ''),
                COALESCE(b.model_id, ''),
                COALESCE(NULLIF(s.title, ''), NULLIF(b.session_title, ''), ''),
                b.created_at,
                b.updated_at
            FROM bookmarks b
            LEFT JOIN sessions s ON s.session_id = b.session_id
        """
        params: list[Any] = []
        normalized_session_id = str(session_id or "").strip()
        if normalized_session_id:
            sql += " WHERE b.session_id = ?"
            params.append(normalized_session_id)

        sql += " ORDER BY b.updated_at DESC, b.created_at DESC, b.id DESC"
        cursor.execute(sql, tuple(params))
        return [row_to_bookmark(row) for row in cursor.fetchall()]


def create_or_update_bookmark(
    session_id: str,
    *,
    role: str,
    message_id: Optional[int] = None,
    panel_id: str = "",
    answer_group_id: str = "",
    content: Any = "",
    model_id: str = "",
    session_title: str = "",
    db_path: str | None = None,
) -> Optional[dict[str, Any]]:
    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        raise ValueError("必须提供 session_id")

    normalized_role = normalize_bookmark_role(role)
    normalized_content = str(content or "").strip()
    normalized_model_id = str(model_id or "").strip()
    normalized_session_title = str(session_title or "").strip()
    now = time.time()

    with connect_sqlite(db_path) as conn:
        init_sessions_table(conn)
        init_messages_table(conn)
        init_bookmarks_table(conn)
        cursor = conn.cursor()

        if not _session_exists(cursor, normalized_session_id):
            return None

        target = _resolve_bookmark_target(
            cursor,
            normalized_session_id,
            message_id=message_id,
            panel_id=panel_id,
            answer_group_id=answer_group_id,
            role=normalized_role,
        )
        if not target:
            return None

        cursor.execute(
            "SELECT COALESCE(title, '') FROM sessions WHERE session_id = ?",
            (normalized_session_id,),
        )
        session_row = cursor.fetchone()
        resolved_session_title = (
            normalized_session_title
            or str(session_row[0] or "").strip()
            or "未命名对话"
        )
        resolved_content = normalized_content or target["content"]
        resolved_model_id = normalized_model_id or target["model_id"]

        cursor.execute(
            """
            SELECT id, created_at
            FROM bookmarks
            WHERE session_id = ? AND message_id = ?
            LIMIT 1
            """,
            (normalized_session_id, target["message_id"]),
        )
        existing_row = cursor.fetchone()

        if existing_row:
            bookmark_id = str(existing_row[0] or "")
            created_at = float(existing_row[1] or now)
            cursor.execute(
                """
                UPDATE bookmarks
                SET panel_id = ?,
                    answer_group_id = ?,
                    role = ?,
                    content = ?,
                    model_id = ?,
                    session_title = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    target["panel_id"],
                    target["answer_group_id"],
                    target["role"],
                    resolved_content,
                    resolved_model_id,
                    resolved_session_title,
                    now,
                    bookmark_id,
                ),
            )
        else:
            bookmark_id = str(uuid.uuid4())
            created_at = now
            cursor.execute(
                """
                INSERT INTO bookmarks (
                    id,
                    session_id,
                    message_id,
                    panel_id,
                    answer_group_id,
                    role,
                    content,
                    model_id,
                    session_title,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bookmark_id,
                    normalized_session_id,
                    target["message_id"],
                    target["panel_id"],
                    target["answer_group_id"],
                    target["role"],
                    resolved_content,
                    resolved_model_id,
                    resolved_session_title,
                    created_at,
                    now,
                ),
            )

        conn.commit()

    return {
        "id": bookmark_id,
        "session_id": normalized_session_id,
        "message_id": int(target["message_id"]),
        "panel_id": str(target["panel_id"] or ""),
        "answer_group_id": str(target["answer_group_id"] or ""),
        "role": str(target["role"] or normalized_role),
        "content": resolved_content,
        "model_id": resolved_model_id,
        "session_title": resolved_session_title,
        "created_at": created_at,
        "updated_at": now,
    }


def delete_bookmark(bookmark_id: str, db_path: str | None = None) -> bool:
    normalized_bookmark_id = str(bookmark_id or "").strip()
    if not normalized_bookmark_id:
        return False

    with connect_sqlite(db_path) as conn:
        init_bookmarks_table(conn)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bookmarks WHERE id = ?", (normalized_bookmark_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted


def delete_bookmarks_for_session(
    session_id: str,
    db_path: str | None = None,
) -> int:
    """Delete legacy SQLite bookmarks owned by a session."""

    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        return 0

    with connect_sqlite(db_path) as conn:
        init_bookmarks_table(conn)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM bookmarks WHERE session_id = ?",
            (normalized_session_id,),
        )
        deleted_count = max(0, int(cursor.rowcount or 0))
        conn.commit()
        return deleted_count


__all__ = [
    "create_or_update_bookmark",
    "delete_bookmark",
    "delete_bookmarks_for_session",
    "get_bookmark",
    "list_bookmarks",
]
