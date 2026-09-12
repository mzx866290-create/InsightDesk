"""PostgreSQL adapter for core chat-session metadata operations."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable, Optional

from backend.stores.chat_messages import build_search_preview
from backend.stores.chat_normalization import DEFAULT_WORKSPACE_ID, normalize_tags
from backend.stores.chat_rows import row_to_session
from backend.stores.chat_serialization import (
    normalize_content,
    normalize_files,
    normalize_images,
    normalize_token_usage,
    parse_json_list,
)
from backend.stores.bookmark_store import delete_bookmarks_for_session
from backend.stores.pg_base import PostgresStoreMixin
from backend.stores.pg_chat_schema import (
    init_postgres_core_chat_schema,
    init_postgres_retrieval_feedback_schema,
    init_postgres_session_memory_schema,
)

logger = logging.getLogger(__name__)


class PostgresSessionStore(PostgresStoreMixin):
    """Persist session lists, metadata, ordering, truncation, and promotion."""

    _SUMMARY_SELECT = """
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
            ) AS message_count,
            COALESCE(s.is_archived, 0) AS is_archived,
            COALESCE(s.is_favorite, 0) AS is_favorite,
            COALESCE(s.is_pinned, 0) AS is_pinned,
            COALESCE(s.session_order, 0) AS session_order,
            COALESCE(s.tags_json, '[]') AS tags_json,
            COALESCE(s.workspace_id, %s) AS workspace_id
        FROM sessions AS s
        LEFT JOIN messages AS m ON s.session_id = m.session_id
        LEFT JOIN (
            SELECT session_id, panel_id
            FROM session_panels
            WHERE is_primary = 1
        ) AS primary_panel ON primary_panel.session_id = s.session_id
    """
    _SUMMARY_GROUP_BY = """
        GROUP BY
            s.session_id,
            s.title,
            s.created_at,
            s.updated_at,
            s.is_archived,
            s.is_favorite,
            s.is_pinned,
            s.session_order,
            s.tags_json,
            s.workspace_id
    """

    def __init__(
        self,
        dsn: str | None = None,
        *,
        connection_factory: Callable[..., Any] | None = None,
        legacy_bookmark_cleanup: Callable[[str], int] | None = None,
    ) -> None:
        PostgresStoreMixin.__init__(self, dsn, connection_factory=connection_factory)
        self.db_path = self.dsn
        self._legacy_bookmark_cleanup = (
            legacy_bookmark_cleanup or delete_bookmarks_for_session
        )
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                init_postgres_core_chat_schema(cursor)
                init_postgres_session_memory_schema(cursor)
                init_postgres_retrieval_feedback_schema(cursor)
            conn.commit()

    def _session_from_row(self, row: Any) -> dict[str, Any]:
        values = (
            self._row_value(row, 0, "session_id"),
            self._row_value(row, 1, "title"),
            self._row_value(row, 2, "created_at"),
            self._row_value(row, 3, "updated_at"),
            int(self._row_value(row, 4, "message_count") or 0),
            self._row_value(row, 5, "is_archived"),
            self._row_value(row, 6, "is_favorite"),
            self._row_value(row, 7, "is_pinned"),
            self._row_value(row, 8, "session_order"),
            self._row_value(row, 9, "tags_json"),
            self._row_value(row, 10, "workspace_id"),
        )
        return row_to_session(values)

    def get_all_sessions(
        self,
        *,
        query: str = "",
        archived: Optional[bool] = None,
        favorite: Optional[bool] = None,
        tag: str = "",
        workspace_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        normalized_query = str(query or "").strip().lower()
        sql = self._SUMMARY_SELECT
        where_clauses: list[str] = []
        params: list[Any] = [DEFAULT_WORKSPACE_ID]

        if normalized_query:
            search_pattern = f"%{normalized_query}%"
            where_clauses.append(
                """
                (
                    LOWER(COALESCE(s.title, '')) LIKE %s
                    OR LOWER(COALESCE(s.tags_json, '[]')) LIKE %s
                    OR EXISTS (
                        SELECT 1
                        FROM messages AS search_m
                        WHERE search_m.session_id = s.session_id
                          AND LOWER(COALESCE(search_m.content, '')) LIKE %s
                    )
                )
                """
            )
            params.extend([search_pattern, search_pattern, search_pattern])

        if archived is not None:
            where_clauses.append("COALESCE(s.is_archived, 0) = %s")
            params.append(1 if archived else 0)

        if favorite is not None:
            where_clauses.append("COALESCE(s.is_favorite, 0) = %s")
            params.append(1 if favorite else 0)

        if workspace_id is not None:
            where_clauses.append("COALESCE(s.workspace_id, %s) = %s")
            params.extend([DEFAULT_WORKSPACE_ID, workspace_id])

        if where_clauses:
            sql += "\nWHERE " + " AND ".join(where_clauses)

        sql += self._SUMMARY_GROUP_BY
        sql += """
            ORDER BY
                COALESCE(s.is_pinned, 0) DESC,
                CASE WHEN COALESCE(s.session_order, 0) > 0 THEN 0 ELSE 1 END ASC,
                COALESCE(s.session_order, 0) DESC,
                s.updated_at DESC
        """

        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, tuple(params))
                sessions = [
                    self._session_from_row(row) for row in cursor.fetchall()
                ]

                normalized_tag = str(tag or "").strip().lower()
                if normalized_tag:
                    sessions = [
                        session
                        for session in sessions
                        if any(
                            item.lower() == normalized_tag
                            for item in session.get("tags", [])
                        )
                    ]

                if normalized_query and sessions:
                    session_ids = [str(item["session_id"]) for item in sessions]
                    placeholders = ", ".join("%s" for _ in session_ids)
                    cursor.execute(
                        f"""
                        SELECT session_id, content
                        FROM messages
                        WHERE session_id IN ({placeholders})
                          AND LOWER(COALESCE(content, '')) LIKE %s
                        ORDER BY id DESC
                        """,
                        tuple([*session_ids, f"%{normalized_query}%"]),
                    )
                    message_hits: dict[str, str] = {}
                    for row in cursor.fetchall():
                        hit_session_id = str(
                            self._row_value(row, 0, "session_id") or ""
                        )
                        if not hit_session_id or hit_session_id in message_hits:
                            continue
                        preview = build_search_preview(
                            self._row_value(row, 1, "content"),
                            normalized_query,
                        )
                        if preview:
                            message_hits[hit_session_id] = preview

                    for session in sessions:
                        session_id = str(session["session_id"])
                        if session_id in message_hits:
                            session["search_preview"] = message_hits[session_id]
                            session["search_source"] = "message"
                        elif normalized_query in str(session.get("title") or "").lower():
                            session["search_preview"] = str(session.get("title") or "")
                            session["search_source"] = "title"

        return sessions

    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return None

        sql = (
            self._SUMMARY_SELECT
            + "\nWHERE s.session_id = %s\n"
            + self._SUMMARY_GROUP_BY
            + "\nLIMIT 1"
        )
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    sql,
                    (DEFAULT_WORKSPACE_ID, normalized_session_id),
                )
                row = cursor.fetchone()
        return self._session_from_row(row) if row else None

    def truncate_session_from_answer_group(
        self,
        session_id: str,
        *,
        answer_group_id: str,
        content: str,
        images: Optional[list[dict[str, Any]]] = None,
        files: Optional[list[dict[str, Any]]] = None,
    ) -> Optional[dict[str, Any]]:
        normalized_session_id = str(session_id or "").strip()
        normalized_answer_group_id = str(answer_group_id or "").strip()
        if not normalized_answer_group_id:
            raise ValueError("必须提供 answer_group_id")
        if not normalized_session_id:
            return None

        normalized_content = normalize_content(content)
        images_json = json.dumps(normalize_images(images), ensure_ascii=False)
        files_json = json.dumps(normalize_files(files), ensure_ascii=False)
        now = time.time()

        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM messages
                    WHERE session_id = %s
                      AND type = 'human'
                      AND COALESCE(panel_id, '') = ''
                      AND COALESCE(answer_group_id, '') = %s
                    ORDER BY id ASC
                    LIMIT 1
                    """,
                    (normalized_session_id, normalized_answer_group_id),
                )
                anchor_row = cursor.fetchone()
                if not anchor_row:
                    return None

                anchor_message_id = int(
                    self._row_value(anchor_row, 0, "id") or 0
                )
                cursor.execute(
                    """
                    UPDATE messages
                    SET content = %s, images_json = %s, files_json = %s, timestamp = %s
                    WHERE id = %s
                    """,
                    (
                        normalized_content,
                        images_json,
                        files_json,
                        now,
                        anchor_message_id,
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO message_search (rowid, session_id, content)
                    VALUES (%s, %s, %s)
                    ON CONFLICT(rowid) DO UPDATE SET
                        session_id = EXCLUDED.session_id,
                        content = EXCLUDED.content
                    """,
                    (anchor_message_id, normalized_session_id, normalized_content),
                )
                cursor.execute(
                    """
                    DELETE FROM messages
                    WHERE session_id = %s AND id > %s
                    RETURNING id
                    """,
                    (normalized_session_id, anchor_message_id),
                )
                deleted_ids = [
                    int(self._row_value(row, 0, "id") or 0)
                    for row in cursor.fetchall()
                ]
                if deleted_ids:
                    placeholders = ", ".join("%s" for _ in deleted_ids)
                    cursor.execute(
                        f"DELETE FROM message_search WHERE rowid IN ({placeholders})",
                        tuple(deleted_ids),
                    )
                cursor.execute(
                    "UPDATE sessions SET updated_at = %s WHERE session_id = %s",
                    (now, normalized_session_id),
                )
            conn.commit()

        return {
            "session_id": normalized_session_id,
            "answer_group_id": normalized_answer_group_id,
            "anchor_message_id": anchor_message_id,
            "deleted_count": len(deleted_ids),
        }

    def update_session_meta(
        self,
        session_id: str,
        *,
        title: Optional[str] = None,
        is_archived: Optional[bool] = None,
        is_favorite: Optional[bool] = None,
        is_pinned: Optional[bool] = None,
        tags: Optional[list[str]] = None,
        workspace_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return None

        updates: list[str] = []
        params: list[Any] = []
        if title is not None:
            normalized_title = str(title or "").strip()
            if not normalized_title:
                raise ValueError("会话标题不能为空")
            updates.append("title = %s")
            params.append(normalized_title)
        if is_archived is not None:
            updates.append("is_archived = %s")
            params.append(1 if is_archived else 0)
        if is_favorite is not None:
            updates.append("is_favorite = %s")
            params.append(1 if is_favorite else 0)
        if is_pinned is not None:
            updates.append("is_pinned = %s")
            params.append(1 if is_pinned else 0)
        if tags is not None:
            updates.append("tags_json = %s")
            params.append(json.dumps(normalize_tags(tags), ensure_ascii=False))
        if workspace_id is not None:
            normalized_workspace_id = str(workspace_id or "").strip()
            if not normalized_workspace_id:
                raise ValueError("workspace_id 不能为空")
            updates.append("workspace_id = %s")
            params.append(normalized_workspace_id)

        if not updates:
            return self.get_session(normalized_session_id)

        now = time.time()
        updates.append("updated_at = %s")
        params.extend([now, normalized_session_id])
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM sessions WHERE session_id = %s LIMIT 1",
                    (normalized_session_id,),
                )
                if not cursor.fetchone():
                    return None
                cursor.execute(
                    f"UPDATE sessions SET {', '.join(updates)} WHERE session_id = %s",
                    tuple(params),
                )
            conn.commit()
        return self.get_session(normalized_session_id)

    def reorder_sessions(
        self,
        session_ids: list[str],
        *,
        workspace_id: Optional[str] = None,
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

        placeholders = ", ".join("%s" for _ in normalized_ids)
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT session_id, COALESCE(workspace_id, %s)
                    FROM sessions
                    WHERE session_id IN ({placeholders})
                    """,
                    tuple([DEFAULT_WORKSPACE_ID, *normalized_ids]),
                )
                rows = list(cursor.fetchall())
                existing_ids = {
                    str(self._row_value(row, 0, "session_id") or "")
                    for row in rows
                }
                missing_ids = [
                    session_id
                    for session_id in normalized_ids
                    if session_id not in existing_ids
                ]
                if missing_ids:
                    raise ValueError(f"未找到会话：{missing_ids[0]}")

                if normalized_workspace_id is not None:
                    out_of_scope = [
                        str(self._row_value(row, 0, "session_id") or "")
                        for row in rows
                        if str(
                            self._row_value(row, 1, "workspace_id")
                            or DEFAULT_WORKSPACE_ID
                        )
                        != normalized_workspace_id
                    ]
                    if out_of_scope:
                        raise ValueError("所有会话都必须属于目标工作区")

                total = len(normalized_ids)
                ordered_items: list[dict[str, Any]] = []
                for index, session_id in enumerate(normalized_ids):
                    order_value = float(total - index)
                    cursor.execute(
                        "UPDATE sessions SET session_order = %s WHERE session_id = %s",
                        (order_value, session_id),
                    )
                    ordered_items.append(
                        {
                            "session_id": session_id,
                            "session_order": order_value,
                        }
                    )
            conn.commit()

        return {"count": len(ordered_items), "orders": ordered_items}

    def mirror_workspace_snapshot(
        self,
        *,
        workspace_id: str,
        name: str,
        description: str,
        color: str,
        default_panels_json: str,
        tool_config_json: str,
        output_preset_json: str,
        is_active: bool,
        created_at: float,
        updated_at: float,
    ) -> None:
        """Keep the PostgreSQL workspace mirror in sync with the SQLite authority.

        During the staged PostgreSQL migration workspaces are still owned by the
        SQLite runtime database, but implicit session creation reads the active
        workspace from PostgreSQL. A stale mirror silently assigns new sessions
        to the wrong workspace, so every mutation mirrors the snapshot here.
        """
        normalized_id = str(workspace_id or "").strip()
        if not normalized_id:
            raise ValueError("workspace_id is required")
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO workspaces (
                        workspace_id, name, description, color,
                        default_panels_json, tool_config_json, output_preset_json,
                        is_active, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (workspace_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        color = EXCLUDED.color,
                        default_panels_json = EXCLUDED.default_panels_json,
                        tool_config_json = EXCLUDED.tool_config_json,
                        output_preset_json = EXCLUDED.output_preset_json,
                        is_active = EXCLUDED.is_active,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        normalized_id,
                        str(name or ""),
                        str(description or ""),
                        str(color or "blue"),
                        default_panels_json or "[]",
                        tool_config_json or "{}",
                        output_preset_json or "{}",
                        1 if is_active else 0,
                        float(created_at),
                        float(updated_at),
                    ),
                )
            conn.commit()

    def deactivate_all_workspace_mirrors(self) -> None:
        """Clear active flags before promoting a different workspace."""
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE workspaces SET is_active = 0")
            conn.commit()

    def reassign_workspace_sessions(
        self,
        source_workspace_id: str,
        target_workspace_id: str,
    ) -> int:
        """Move sessions away from a deleted SQLite-backed workspace.

        Workspaces remain SQLite-backed during the staged PostgreSQL migration.
        Remove the legacy PostgreSQL workspace mirror in the same transaction so
        future implicit sessions cannot select a workspace that no longer exists.
        """

        normalized_source_id = str(source_workspace_id or "").strip()
        normalized_target_id = str(target_workspace_id or "").strip()
        if not normalized_source_id or not normalized_target_id:
            raise ValueError("source and target workspace IDs are required")
        if normalized_source_id == normalized_target_id:
            raise ValueError("source and target workspaces must be different")

        now = time.time()
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE sessions
                    SET workspace_id = %s, updated_at = %s
                    WHERE COALESCE(workspace_id, %s) = %s
                    RETURNING session_id
                    """,
                    (
                        normalized_target_id,
                        now,
                        DEFAULT_WORKSPACE_ID,
                        normalized_source_id,
                    ),
                )
                moved_session_ids = list(cursor.fetchall())
                cursor.execute(
                    "DELETE FROM workspaces WHERE workspace_id = %s",
                    (normalized_source_id,),
                )
            conn.commit()
        return len(moved_session_ids)

    def delete_session(self, session_id: str) -> None:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return

        with self._connect() as conn:
            with conn.cursor() as cursor:
                # Delete search rows first because PostgreSQL has no SQLite FTS triggers.
                cursor.execute(
                    "DELETE FROM message_search WHERE session_id = %s",
                    (normalized_session_id,),
                )
                for table_name in (
                    "messages",
                    "session_panels",
                    "session_memory",
                    "retrieval_feedback",
                    "sessions",
                ):
                    cursor.execute(
                        f"DELETE FROM {table_name} WHERE session_id = %s",
                        (normalized_session_id,),
                    )
            conn.commit()

        # PostgreSQL owns the session deletion. Legacy SQLite bookmark cleanup is
        # best-effort after that transaction commits: cleanup failure must not
        # misreport or roll back a session deletion that already succeeded.
        deleted_bookmarks: int | None = None
        try:
            deleted_bookmarks = self._legacy_bookmark_cleanup(normalized_session_id)
        except Exception:
            logger.exception(
                "Deleted PostgreSQL session %s but failed to clean legacy bookmarks",
                normalized_session_id,
            )
        logger.info(
            "Deleted PostgreSQL session: %s (legacy_bookmarks=%s)",
            normalized_session_id,
            deleted_bookmarks if deleted_bookmarks is not None else "cleanup_failed",
        )

    def promote_panel_answer(
        self,
        session_id: str,
        answer_group_id: str,
        source_panel_id: str,
    ) -> Optional[dict[str, Any]]:
        normalized_session_id = str(session_id or "").strip()
        normalized_answer_group_id = str(answer_group_id or "").strip()
        normalized_source_panel_id = str(source_panel_id or "").strip()
        if not normalized_session_id:
            return None

        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT panel_id
                    FROM session_panels
                    WHERE session_id = %s
                    ORDER BY is_primary DESC, display_order ASC, updated_at ASC
                    LIMIT 1
                    """,
                    (normalized_session_id,),
                )
                primary_row = cursor.fetchone()
                target_panel_id = str(
                    self._row_value(primary_row, 0, "panel_id") or ""
                ).strip()
                if not target_panel_id:
                    target_panel_id = normalized_source_panel_id

                cursor.execute(
                    """
                    SELECT id, content, model_id, sources_json, workflow_json,
                           token_usage_json, task_id, task_type
                    FROM messages
                    WHERE session_id = %s
                      AND type = 'ai'
                      AND COALESCE(panel_id, '') = %s
                      AND COALESCE(answer_group_id, '') = %s
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (
                        normalized_session_id,
                        normalized_source_panel_id,
                        normalized_answer_group_id,
                    ),
                )
                source_row = cursor.fetchone()
                if not source_row:
                    return None

                source_content = str(self._row_value(source_row, 1, "content") or "")
                source_model_id = str(self._row_value(source_row, 2, "model_id") or "")
                source_sources_json = str(
                    self._row_value(source_row, 3, "sources_json") or ""
                )
                source_workflow_json = str(
                    self._row_value(source_row, 4, "workflow_json") or ""
                )
                source_token_usage_json = str(
                    self._row_value(source_row, 5, "token_usage_json") or ""
                )
                source_task_id = str(self._row_value(source_row, 6, "task_id") or "")
                source_task_type = str(
                    self._row_value(source_row, 7, "task_type") or ""
                )

                cursor.execute(
                    """
                    SELECT id
                    FROM messages
                    WHERE session_id = %s
                      AND type = 'ai'
                      AND COALESCE(panel_id, '') = %s
                      AND COALESCE(answer_group_id, '') = %s
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (
                        normalized_session_id,
                        target_panel_id,
                        normalized_answer_group_id,
                    ),
                )
                target_row = cursor.fetchone()
                if target_row:
                    target_message_id = int(
                        self._row_value(target_row, 0, "id") or 0
                    )
                    cursor.execute(
                        """
                        UPDATE messages
                        SET content = %s,
                            model_id = %s,
                            sources_json = %s,
                            workflow_json = %s,
                            token_usage_json = %s,
                            task_id = %s,
                            task_type = %s
                        WHERE id = %s
                        """,
                        (
                            source_content,
                            source_model_id,
                            source_sources_json,
                            source_workflow_json,
                            source_token_usage_json,
                            source_task_id,
                            source_task_type,
                            target_message_id,
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO messages (
                            session_id, type, content, timestamp, model_id, panel_id,
                            answer_group_id, sources_json, workflow_json,
                            token_usage_json, task_id, task_type
                        )
                        VALUES (%s, 'ai', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            normalized_session_id,
                            source_content,
                            time.time(),
                            source_model_id,
                            target_panel_id,
                            normalized_answer_group_id,
                            source_sources_json,
                            source_workflow_json,
                            source_token_usage_json,
                            source_task_id,
                            source_task_type,
                        ),
                    )
                    inserted_row = cursor.fetchone()
                    target_message_id = int(
                        self._row_value(inserted_row, 0, "id") or 0
                    )

                cursor.execute(
                    """
                    INSERT INTO message_search (rowid, session_id, content)
                    VALUES (%s, %s, %s)
                    ON CONFLICT(rowid) DO UPDATE SET
                        session_id = EXCLUDED.session_id,
                        content = EXCLUDED.content
                    """,
                    (target_message_id, normalized_session_id, source_content),
                )
                cursor.execute(
                    "UPDATE sessions SET updated_at = %s WHERE session_id = %s",
                    (time.time(), normalized_session_id),
                )
            conn.commit()

        return {
            "target_panel_id": target_panel_id,
            "source_panel_id": normalized_source_panel_id,
            "answer_group_id": normalized_answer_group_id,
            "content": source_content,
            "model_id": source_model_id,
            "sources": parse_json_list(source_sources_json),
            "workflow_nodes": parse_json_list(source_workflow_json),
            "token_usage": normalize_token_usage(source_token_usage_json),
            "task_id": source_task_id,
            "task_type": source_task_type,
        }


__all__ = ["PostgresSessionStore"]
