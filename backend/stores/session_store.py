"""Session persistence helpers for the SQLite chat runtime."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from typing import Any, Callable, Optional, cast

from backend.stores.chat_messages import (
    build_message_search_match_query,
    build_search_preview,
)
from backend.stores.chat_normalization import DEFAULT_WORKSPACE_ID, normalize_tags
from backend.stores.chat_rows import row_to_session
from backend.stores.chat_schema import (
    init_bookmarks_table,
    init_messages_table,
    init_retrieval_feedback_table,
    init_session_memory_table,
    init_session_panels_table,
    init_sessions_table,
    init_workspaces_table,
    message_search_table_exists,
)
from backend.stores.chat_serialization import (
    normalize_content,
    normalize_files,
    normalize_images,
)
from backend.stores.sqlite_runtime import connect_sqlite
from backend.stores.workspace_store import workspace_exists

logger = logging.getLogger(__name__)


def session_exists(
    cursor: sqlite3.Cursor,
    session_id: str,
) -> bool:
    cursor.execute(
        "SELECT 1 FROM sessions WHERE session_id = ?",
        (session_id,),
    )
    return cursor.fetchone() is not None


def collect_message_search_hits(
    cursor: sqlite3.Cursor,
    normalized_query: str,
    session_ids: set[str],
) -> dict[str, str]:
    if not normalized_query or not session_ids:
        return {}

    match_query = build_message_search_match_query(normalized_query)
    sorted_session_ids = sorted(session_ids)

    if match_query and message_search_table_exists(cursor):
        placeholders = ", ".join("?" for _ in sorted_session_ids)
        try:
            cursor.execute(
                f"""
                SELECT m.session_id, m.content
                FROM message_search
                JOIN messages AS m ON m.id = message_search.rowid
                WHERE message_search MATCH ?
                  AND m.session_id IN ({placeholders})
                ORDER BY m.id DESC
                """,
                (match_query, *sorted_session_ids),
            )
        except sqlite3.OperationalError:
            logger.exception(
                "FTS5 message preview lookup failed, falling back to LIKE queries"
            )
            cursor.execute(
                """
                SELECT session_id, content
                FROM messages
                WHERE LOWER(COALESCE(content, '')) LIKE ?
                ORDER BY id DESC
                """,
                (f"%{normalized_query}%",),
            )
    else:
        cursor.execute(
            """
            SELECT session_id, content
            FROM messages
            WHERE LOWER(COALESCE(content, '')) LIKE ?
            ORDER BY id DESC
            """,
            (f"%{normalized_query}%",),
        )

    hits: dict[str, str] = {}
    for row in cursor.fetchall():
        session_id = str(row[0] or "")
        if session_id not in session_ids or session_id in hits:
            continue
        preview = build_search_preview(row[1], normalized_query)
        if preview:
            hits[session_id] = preview
    return hits


def fetch_session_row(
    cursor: sqlite3.Cursor,
    session_id: str,
) -> Optional[tuple[Any, ...]]:
    cursor.execute(
        """
        SELECT
            s.session_id,
            s.title,
            s.created_at,
            s.updated_at,
            COALESCE(
                SUM(
                    CASE
                        WHEN m.id IS NULL THEN 0
                        WHEN m.type = 'human' THEN 1
                        WHEN m.type = 'ai'
                             AND (
                                 COALESCE(m.panel_id, '') = ''
                                 OR COALESCE(primary_panel.panel_id, '') = COALESCE(m.panel_id, '')
                             ) THEN 1
                        ELSE 0
                    END
                ),
                0
            ) as message_count,
            COALESCE(s.is_archived, 0) as is_archived,
            COALESCE(s.is_favorite, 0) as is_favorite,
            COALESCE(s.is_pinned, 0) as is_pinned,
            COALESCE(s.session_order, 0) as session_order,
            COALESCE(s.tags_json, '[]') as tags_json,
            COALESCE(s.workspace_id, ?) as workspace_id
        FROM sessions s
        LEFT JOIN messages m ON s.session_id = m.session_id
        LEFT JOIN (
            SELECT session_id, panel_id
            FROM session_panels
            WHERE is_primary = 1
        ) AS primary_panel
          ON primary_panel.session_id = s.session_id
        WHERE s.session_id = ?
        GROUP BY s.session_id, s.workspace_id
        LIMIT 1
        """,
        (DEFAULT_WORKSPACE_ID, session_id),
    )
    return cast(tuple[Any, ...] | None, cursor.fetchone())


def get_all_sessions(
    db_path: str | None = None,
    query: str = "",
    archived: Optional[bool] = None,
    favorite: Optional[bool] = None,
    tag: str = "",
    workspace_id: Optional[str] = None,
    *,
    connect_sqlite_fn: Callable[[str | None], sqlite3.Connection] = connect_sqlite,
) -> list[dict[str, Any]]:
    """Return session summaries sorted by pinned/manual/recent order."""

    with connect_sqlite_fn(db_path) as conn:
        cursor = conn.cursor()
        init_messages_table(conn)
        init_workspaces_table(conn)
        init_sessions_table(conn)
        init_session_panels_table(conn)

        sql = """
            SELECT
                s.session_id,
                s.title,
                s.created_at,
                s.updated_at,
                COALESCE(
                    SUM(
                        CASE
                            WHEN m.id IS NULL THEN 0
                            WHEN m.type = 'human' THEN 1
                            WHEN m.type = 'ai'
                                 AND (
                                     COALESCE(m.panel_id, '') = ''
                                     OR COALESCE(primary_panel.panel_id, '') = COALESCE(m.panel_id, '')
                                 ) THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) as message_count,
                COALESCE(s.is_archived, 0) as is_archived,
                COALESCE(s.is_favorite, 0) as is_favorite,
                COALESCE(s.is_pinned, 0) as is_pinned,
                COALESCE(s.session_order, 0) as session_order,
                COALESCE(s.tags_json, '[]') as tags_json,
                COALESCE(s.workspace_id, ?) as workspace_id
            FROM sessions s
            LEFT JOIN messages m ON s.session_id = m.session_id
            LEFT JOIN (
                SELECT session_id, panel_id
                FROM session_panels
                WHERE is_primary = 1
            ) AS primary_panel
              ON primary_panel.session_id = s.session_id
        """
        where_clauses: list[str] = []
        params: list[Any] = [DEFAULT_WORKSPACE_ID]

        normalized_query = query.strip().lower()
        match_query = build_message_search_match_query(normalized_query)
        search_table_exists = message_search_table_exists(cursor)
        if normalized_query:
            where_clauses.append(
                """
                (
                    LOWER(COALESCE(s.title, '')) LIKE ?
                    OR LOWER(COALESCE(s.tags_json, '[]')) LIKE ?
                    OR {message_search_clause}
                )
                """.format(
                    message_search_clause=(
                        "s.session_id IN ("
                        "SELECT session_id FROM message_search WHERE message_search MATCH ?"
                        ")"
                        if match_query and search_table_exists
                        else "EXISTS ("
                        "SELECT 1 FROM messages search_m "
                        "WHERE search_m.session_id = s.session_id "
                        "AND LOWER(COALESCE(search_m.content, '')) LIKE ?"
                        ")"
                    )
                )
            )
            params.extend(
                [
                    f"%{normalized_query}%",
                    f"%{normalized_query}%",
                    match_query
                    if match_query and search_table_exists
                    else f"%{normalized_query}%",
                ]
            )

        if archived is not None:
            where_clauses.append("COALESCE(s.is_archived, 0) = ?")
            params.append(1 if archived else 0)

        if favorite is not None:
            where_clauses.append("COALESCE(s.is_favorite, 0) = ?")
            params.append(1 if favorite else 0)

        if workspace_id is not None:
            where_clauses.append("COALESCE(s.workspace_id, ?) = ?")
            params.extend([DEFAULT_WORKSPACE_ID, workspace_id])

        if where_clauses:
            sql += "\nWHERE " + " AND ".join(where_clauses)

        sql += """
\nGROUP BY s.session_id, s.workspace_id
ORDER BY
    COALESCE(s.is_pinned, 0) DESC,
    CASE WHEN COALESCE(s.session_order, 0) > 0 THEN 0 ELSE 1 END ASC,
    COALESCE(s.session_order, 0) DESC,
    s.updated_at DESC
"""
        cursor.execute(sql, tuple(params))

        sessions = [row_to_session(row) for row in cursor.fetchall()]

        normalized_tag = tag.strip().lower()
        if normalized_tag:
            sessions = [
                session
                for session in sessions
                if any(item.lower() == normalized_tag for item in session["tags"])
            ]

        if normalized_query and sessions:
            search_hits = collect_message_search_hits(
                cursor,
                normalized_query,
                {str(session["session_id"]) for session in sessions},
            )
            for session in sessions:
                search_preview = search_hits.get(str(session["session_id"]))
                if search_preview:
                    session["search_preview"] = search_preview
                    session["search_source"] = "message"
                elif normalized_query in str(session.get("title") or "").lower():
                    session["search_preview"] = str(session.get("title") or "")
                    session["search_source"] = "title"

        return sessions


def get_session(
    session_id: str,
    db_path: str | None = None,
    *,
    connect_sqlite_fn: Callable[[str | None], sqlite3.Connection] = connect_sqlite,
) -> Optional[dict[str, Any]]:
    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        return None

    with connect_sqlite_fn(db_path) as conn:
        cursor = conn.cursor()
        init_messages_table(conn)
        init_workspaces_table(conn)
        init_sessions_table(conn)
        init_session_panels_table(conn)
        row = fetch_session_row(cursor, normalized_session_id)
        return row_to_session(row) if row else None


def truncate_session_from_answer_group(
    session_id: str,
    *,
    answer_group_id: str,
    content: str,
    images: Optional[list[dict[str, Any]]] = None,
    files: Optional[list[dict[str, Any]]] = None,
    db_path: str | None = None,
    connect_sqlite_fn: Callable[[str | None], sqlite3.Connection] = connect_sqlite,
) -> Optional[dict[str, Any]]:
    normalized_answer_group_id = str(answer_group_id or "").strip()
    if not normalized_answer_group_id:
        raise ValueError("必须提供 answer_group_id")

    normalized_content = normalize_content(content)
    normalized_images = normalize_images(images)
    normalized_files = normalize_files(files)
    now = time.time()

    with connect_sqlite_fn(db_path) as conn:
        init_messages_table(conn)
        init_sessions_table(conn)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id
            FROM messages
            WHERE session_id = ?
              AND type = 'human'
              AND COALESCE(panel_id, '') = ''
              AND COALESCE(answer_group_id, '') = ?
            ORDER BY id ASC
            LIMIT 1
            """,
            (session_id, normalized_answer_group_id),
        )
        row = cursor.fetchone()
        if not row:
            return None

        anchor_message_id = int(row[0])

        cursor.execute(
            """
            UPDATE messages
            SET content = ?, images_json = ?, files_json = ?, timestamp = ?
            WHERE id = ?
            """,
            (
                normalized_content,
                json.dumps(normalized_images, ensure_ascii=False),
                json.dumps(normalized_files, ensure_ascii=False),
                now,
                anchor_message_id,
            ),
        )

        cursor.execute(
            """
            DELETE FROM messages
            WHERE session_id = ?
              AND id > ?
            """,
            (session_id, anchor_message_id),
        )
        deleted_count = int(cursor.rowcount or 0)

        cursor.execute(
            "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
            (now, session_id),
        )
        conn.commit()

    return {
        "session_id": session_id,
        "answer_group_id": normalized_answer_group_id,
        "anchor_message_id": anchor_message_id,
        "deleted_count": deleted_count,
    }


def update_session_meta(
    session_id: str,
    *,
    title: Optional[str] = None,
    is_archived: Optional[bool] = None,
    is_favorite: Optional[bool] = None,
    is_pinned: Optional[bool] = None,
    tags: Optional[list[str]] = None,
    workspace_id: Optional[str] = None,
    db_path: str | None = None,
    connect_sqlite_fn: Callable[[str | None], sqlite3.Connection] = connect_sqlite,
) -> Optional[dict[str, Any]]:
    with connect_sqlite_fn(db_path) as conn:
        init_workspaces_table(conn)
        init_sessions_table(conn)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM sessions WHERE session_id = ?",
            (session_id,),
        )
        if not cursor.fetchone():
            return None

        updates: list[str] = []
        params: list[Any] = []

        if title is not None:
            normalized_title = title.strip()
            if not normalized_title:
                raise ValueError("会话标题不能为空")
            updates.append("title = ?")
            params.append(normalized_title)

        if is_archived is not None:
            updates.append("is_archived = ?")
            params.append(1 if is_archived else 0)

        if is_favorite is not None:
            updates.append("is_favorite = ?")
            params.append(1 if is_favorite else 0)

        if is_pinned is not None:
            updates.append("is_pinned = ?")
            params.append(1 if is_pinned else 0)

        if tags is not None:
            normalized_tags = normalize_tags(tags)
            updates.append("tags_json = ?")
            params.append(json.dumps(normalized_tags, ensure_ascii=False))

        if workspace_id is not None:
            normalized_workspace_id = str(workspace_id or "").strip()
            if not normalized_workspace_id:
                raise ValueError("workspace_id 不能为空")
            if not workspace_exists(cursor, normalized_workspace_id):
                raise ValueError("工作区不存在")
            updates.append("workspace_id = ?")
            params.append(normalized_workspace_id)

        if not updates:
            return get_session(
                session_id,
                db_path=db_path,
                connect_sqlite_fn=connect_sqlite_fn,
            )

        updates.append("updated_at = ?")
        params.append(time.time())
        params.append(session_id)

        cursor.execute(
            f"UPDATE sessions SET {', '.join(updates)} WHERE session_id = ?",
            tuple(params),
        )
        conn.commit()

    return get_session(
        session_id,
        db_path=db_path,
        connect_sqlite_fn=connect_sqlite_fn,
    )


def reorder_sessions(
    session_ids: list[str],
    *,
    workspace_id: Optional[str] = None,
    db_path: str | None = None,
    connect_sqlite_fn: Callable[[str | None], sqlite3.Connection] = connect_sqlite,
) -> dict[str, Any]:
    normalized_ids: list[str] = []
    seen: set[str] = set()
    for raw_id in session_ids:
        session_id = str(raw_id or "").strip()
        if not session_id or session_id in seen:
            continue
        seen.add(session_id)
        normalized_ids.append(session_id)

    if len(normalized_ids) < 2:
        raise ValueError("至少需要两个会话 ID 才能排序")

    normalized_workspace_id: Optional[str] = None
    if workspace_id is not None:
        normalized_workspace_id = str(workspace_id or "").strip()
        if not normalized_workspace_id:
            raise ValueError("workspace_id 不能为空")

    with connect_sqlite_fn(db_path) as conn:
        init_workspaces_table(conn)
        init_sessions_table(conn)
        cursor = conn.cursor()

        placeholders = ",".join("?" for _ in normalized_ids)
        cursor.execute(
            f"""
            SELECT session_id, COALESCE(workspace_id, ?)
            FROM sessions
            WHERE session_id IN ({placeholders})
            """,
            tuple([DEFAULT_WORKSPACE_ID, *normalized_ids]),
        )
        rows = cursor.fetchall()
        existing_ids = {str(row[0] or "") for row in rows}
        missing_ids = [
            session_id for session_id in normalized_ids if session_id not in existing_ids
        ]
        if missing_ids:
            raise ValueError(f"未找到会话：{missing_ids[0]}")

        if normalized_workspace_id is not None:
            out_of_scope = [
                str(row[0] or "")
                for row in rows
                if str(row[1] or DEFAULT_WORKSPACE_ID) != normalized_workspace_id
            ]
            if out_of_scope:
                raise ValueError("所有会话都必须属于目标工作区")

        total = len(normalized_ids)
        ordered_items: list[dict[str, Any]] = []
        for index, session_id in enumerate(normalized_ids):
            order_value = float(total - index)
            cursor.execute(
                "UPDATE sessions SET session_order = ? WHERE session_id = ?",
                (order_value, session_id),
            )
            ordered_items.append(
                {
                    "session_id": session_id,
                    "session_order": order_value,
                }
            )

        conn.commit()

    return {
        "count": len(ordered_items),
        "orders": ordered_items,
    }


def delete_session(
    session_id: str,
    db_path: str | None = None,
    *,
    connect_sqlite_fn: Callable[[str | None], sqlite3.Connection] = connect_sqlite,
) -> None:
    """Delete a session and all session-scoped chat metadata."""

    with connect_sqlite_fn(db_path) as conn:
        init_messages_table(conn)
        init_workspaces_table(conn)
        init_sessions_table(conn)
        init_session_panels_table(conn)
        init_session_memory_table(conn)
        init_retrieval_feedback_table(conn)
        init_bookmarks_table(conn)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM session_panels WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM session_memory WHERE session_id = ?", (session_id,))
        cursor.execute(
            "DELETE FROM retrieval_feedback WHERE session_id = ?", (session_id,)
        )
        cursor.execute("DELETE FROM bookmarks WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

        conn.commit()
        logger.info("Deleted session: %s", session_id)


__all__ = [
    "collect_message_search_hits",
    "delete_session",
    "fetch_session_row",
    "get_all_sessions",
    "get_session",
    "reorder_sessions",
    "session_exists",
    "truncate_session_from_answer_group",
    "update_session_meta",
]
