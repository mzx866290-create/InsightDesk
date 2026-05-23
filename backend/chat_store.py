"""
SQLite-based persistent chat message history
Implements LangChain's BaseChatMessageHistory interface
"""

import json
import sqlite3
import time
import logging
from typing import List, Dict, Any, Optional, cast
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from backend.core.storage_runtime import (
    DATABASE_PROVIDER_POSTGRES,
    app_database_path,
    database_provider,
)
from backend.stores.sqlite_runtime import connect_sqlite
from backend.stores.chat_serialization import (
    normalize_content as _normalize_content,
    normalize_files as _normalize_files,
    normalize_images as _normalize_images,
    normalize_metadata_list as _normalize_metadata_list,
    normalize_token_usage as _normalize_token_usage,
    parse_json_list as _parse_json_list,
)
from backend.stores.chat_schema import (
    init_bookmarks_table as _init_bookmarks_table,
    init_sessions_table as _init_sessions_table,
    init_messages_table as _init_messages_table,
    init_retrieval_feedback_table as _init_retrieval_feedback_table,
    init_session_memory_table as _init_session_memory_table,
    init_session_panels_table as _init_session_panels_table,
    init_workspaces_table as _init_workspaces_table,
    message_search_table_exists as _message_search_table_exists,
)
from backend.stores.chat_rows import (
    row_to_session as _row_to_session,
)
from backend.stores.chat_messages import (
    build_human_message_content_for_model as _build_human_message_content_for_model,
    build_message_search_match_query as _build_message_search_match_query,
    build_search_preview as _build_search_preview,
    derive_session_title as _derive_session_title,
    env_int as _env_int,
    group_message_ids_for_history_pruning as _group_message_ids_for_history_pruning,
)
from backend.stores.chat_normalization import (
    DEFAULT_WORKSPACE_ID,
    DEFAULT_WORKSPACE_NAME as DEFAULT_WORKSPACE_NAME,
    normalize_message_feedback_value as _normalize_message_feedback_value,
    normalize_tags as _normalize_tags,
)
from backend.stores.bookmark_store import (
    create_or_update_bookmark as create_or_update_bookmark,
    delete_bookmark as delete_bookmark,
    get_bookmark as get_bookmark,
    list_bookmarks as list_bookmarks,
)
from backend.stores.prompt_store import (
    DEFAULT_SYSTEM_PROMPT as DEFAULT_SYSTEM_PROMPT,
    activate_assistant_preset as activate_assistant_preset,
    activate_system_prompt as activate_system_prompt,
    create_assistant_preset as create_assistant_preset,
    create_system_prompt as create_system_prompt,
    delete_assistant_preset as delete_assistant_preset,
    delete_system_prompt as delete_system_prompt,
    get_active_assistant_preset as get_active_assistant_preset,
    get_active_system_prompt as get_active_system_prompt,
    get_all_assistant_presets as get_all_assistant_presets,
    get_all_system_prompts as get_all_system_prompts,
    init_assistant_presets_table as _init_assistant_presets_table,
    init_system_prompts_table as _init_system_prompts_table,
    update_assistant_preset as update_assistant_preset,
    update_system_prompt as update_system_prompt,
)
from backend.stores.retrieval_feedback_store import (
    aggregate_retrieval_feedback_by_source as aggregate_retrieval_feedback_by_source,
    list_retrieval_feedback as list_retrieval_feedback,
    set_retrieval_feedback as set_retrieval_feedback,
)
from backend.stores.session_memory_store import (
    clear_session_memory as clear_session_memory,
    create_session_memory as create_session_memory,
    delete_session_memory as delete_session_memory,
    list_session_memory as list_session_memory,
    pin_session_memory as pin_session_memory,
    update_session_memory as update_session_memory,
)
from backend.stores.session_panel_store import (
    get_session_panels as _get_session_panels,
    replace_session_panels as _replace_session_panels,
    upsert_session_panel as _upsert_session_panel,
)
from backend.stores.workspace_store import (
    activate_workspace as activate_workspace,
    create_workspace as create_workspace,
    delete_workspace as delete_workspace,
    get_active_workspace_id as _get_active_workspace_id,
    get_workspace as get_workspace,
    list_workspaces as list_workspaces,
    update_workspace as update_workspace,
    workspace_exists as _workspace_exists,
)

logger = logging.getLogger(__name__)

DB_PATH = app_database_path()


def _should_use_postgres_store(db_path: str | None = None) -> bool:
    """Route default runtime calls to PostgreSQL while preserving explicit SQLite paths."""

    normalized_db_path = str(db_path or "").strip()
    return database_provider() == DATABASE_PROVIDER_POSTGRES and normalized_db_path in {
        "",
        DB_PATH,
    }


# Exported constant so api_server can return it to the frontend
CONTEXT_HISTORY_MESSAGES: int = _env_int("CONTEXT_HISTORY_MESSAGES", 16)

class SQLiteChatMessageHistory(BaseChatMessageHistory):
    """
    SQLite-based chat message history that persists across service restarts.

    Implements LangChain's BaseChatMessageHistory interface.
    """

    def __init__(self, session_id: str, db_path: str | None = None):
        """
        Initialize SQLite chat history for a specific session.

        Args:
            session_id: Unique session identifier
            db_path: Path to SQLite database file
        """
        self.session_id = session_id
        self.db_path = str(db_path or app_database_path()).strip()
        self._init_db()
        self._ensure_session_exists()

    def _init_db(self) -> None:
        """Initialize database schema if not exists."""
        with connect_sqlite(self.db_path) as conn:
            _init_messages_table(conn)
            _init_workspaces_table(conn)
            _init_sessions_table(conn)
            _init_session_memory_table(conn)
            _init_session_panels_table(conn)
            _init_retrieval_feedback_table(conn)
            _init_bookmarks_table(conn)
            _init_system_prompts_table(conn)
            _init_assistant_presets_table(conn)

    def _ensure_session_exists(self) -> None:
        """Ensure session record exists in sessions table."""
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT session_id FROM sessions WHERE session_id = ?",
                (self.session_id,),
            )

            if not cursor.fetchone():
                now = time.time()
                workspace_id = _get_active_workspace_id(cursor)
                cursor.execute(
                    """
                    INSERT INTO sessions (session_id, created_at, updated_at, title, workspace_id)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (self.session_id, now, now, "", workspace_id),
                )
                conn.commit()
                logger.info("Created new session: %s", self.session_id)

    def _resolve_default_panel_id(self, conn: sqlite3.Connection) -> str:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT panel_id
                FROM session_panels
                WHERE session_id = ?
                ORDER BY is_primary DESC, display_order ASC, updated_at ASC
                LIMIT 1
                """,
                (self.session_id,),
            )
        except sqlite3.OperationalError:
            return ""
        row = cursor.fetchone()
        return str(row[0]).strip() if row and row[0] else ""

    def _load_message_rows(
        self,
        apply_context_limit: bool = True,
        panel_id: Optional[str] = None,
        exclude_ai_answer_group_id: Optional[str] = None,
    ) -> List[tuple]:
        """Load raw message rows with optional context-window truncation."""
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.cursor()
            effective_panel_id = (
                panel_id or ""
            ).strip() or self._resolve_default_panel_id(conn)
            excluded_group_id = (exclude_ai_answer_group_id or "").strip()

            if effective_panel_id:
                query = """
                    SELECT
                        id,
                        type,
                        content,
                        model_id,
                        panel_id,
                        answer_group_id,
                        images_json,
                        files_json,
                        sources_json,
                        workflow_json,
                        token_usage_json,
                        task_id,
                        task_type,
                        COALESCE(feedback_value, 0),
                        timestamp
                    FROM messages
                    WHERE session_id = ?
                      AND (COALESCE(panel_id, '') = '' OR COALESCE(panel_id, '') = ?)
                """
                params: list[Any] = [self.session_id, effective_panel_id]
                if excluded_group_id:
                    query += """
                      AND NOT (
                          type = 'ai'
                          AND COALESCE(panel_id, '') = ?
                          AND COALESCE(answer_group_id, '') = ?
                      )
                    """
                    params.extend([effective_panel_id, excluded_group_id])
                query += " ORDER BY id ASC"
                cursor.execute(query, tuple(params))
            else:
                cursor.execute(
                    """
                    SELECT
                        id,
                        type,
                        content,
                        model_id,
                        panel_id,
                        answer_group_id,
                        images_json,
                        files_json,
                        sources_json,
                        workflow_json,
                        token_usage_json,
                        task_id,
                        task_type,
                        COALESCE(feedback_value, 0),
                        timestamp
                    FROM messages
                    WHERE session_id = ?
                    ORDER BY id ASC
                    """,
                    (self.session_id,),
                )

            rows = cursor.fetchall()

            if apply_context_limit:
                # Context window governance: only expose latest N messages to the model
                context_limit = _env_int("CONTEXT_HISTORY_MESSAGES", 16)
                if context_limit > 0 and len(rows) > context_limit:
                    rows = rows[-context_limit:]
            return rows

    def _load_messages(
        self,
        apply_context_limit: bool = True,
        panel_id: Optional[str] = None,
        exclude_ai_answer_group_id: Optional[str] = None,
    ) -> List[BaseMessage]:
        """Load session messages with optional context-window truncation."""
        rows = self._load_message_rows(
            apply_context_limit=apply_context_limit,
            panel_id=panel_id,
            exclude_ai_answer_group_id=exclude_ai_answer_group_id,
        )

        messages: List[BaseMessage] = []
        for (
            _,
            msg_type,
            content,
            _,
            _,
            _,
            images_json,
            files_json,
            _,
            _,
            _,
            _,
            _,
            _,
            _,
        ) in rows:
            images = _parse_json_list(images_json)
            files = _parse_json_list(files_json)
            if msg_type == "human":
                messages.append(
                    HumanMessage(
                        content=_build_human_message_content_for_model(
                            content,
                            images=images,
                            files=files,
                        )
                    )
                )
            elif msg_type == "ai":
                messages.append(AIMessage(content=content))
            elif msg_type == "system":
                messages.append(SystemMessage(content=content))

        return messages

    @property
    def messages(self) -> List[BaseMessage]:  # type: ignore[override]
        """
        Retrieve model-facing messages for this session.

        Returns:
            List of BaseMessage objects ordered by timestamp
        """
        return self._load_messages(apply_context_limit=True)

    def get_panel_messages(self, panel_id: str) -> List[BaseMessage]:
        """Retrieve model-facing messages for a specific panel."""
        return self._load_messages(apply_context_limit=True, panel_id=panel_id)

    def get_panel_messages_for_rerun(
        self,
        panel_id: str,
        answer_group_id: str,
    ) -> List[BaseMessage]:
        """Retrieve panel history excluding the current answer group's AI response."""
        return self._load_messages(
            apply_context_limit=True,
            panel_id=panel_id,
            exclude_ai_answer_group_id=answer_group_id,
        )

    def get_all_messages(self, panel_id: Optional[str] = None) -> List[BaseMessage]:
        """
        Retrieve the full session history without context-window truncation.

        Returns:
            List of BaseMessage objects ordered by timestamp
        """
        return self._load_messages(apply_context_limit=False, panel_id=panel_id)

    def get_all_message_records(
        self,
        panel_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        rows = self._load_message_rows(apply_context_limit=False, panel_id=panel_id)
        return [
            {
                "id": row[0],
                "type": row[1],
                "content": row[2],
                "model_id": row[3] or "",
                "panel_id": row[4] or "",
                "answer_group_id": row[5] or "",
                "images": _normalize_images(_parse_json_list(row[6])),
                "files": _normalize_files(_parse_json_list(row[7])),
                "sources": _parse_json_list(row[8]),
                "workflow_nodes": _parse_json_list(row[9]),
                "token_usage": _normalize_token_usage(row[10]),
                "task_id": row[11] or "",
                "task_type": row[12] or "",
                "feedback_value": _normalize_message_feedback_value(row[13]),
                "timestamp": float(row[14] or 0),
            }
            for row in rows
        ]

    def add_message(
        self,
        message: BaseMessage,
        model_id: str = "",
        panel_id: str = "",
        answer_group_id: str = "",
        images: Optional[List[Dict[str, Any]]] = None,
        files: Optional[List[Dict[str, Any]]] = None,
        sources: Optional[List[Dict[str, Any]]] = None,
        workflow_nodes: Optional[List[Dict[str, Any]]] = None,
        task_id: str = "",
        task_type: str = "",
        token_usage: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a message to the session history.

        Args:
            message: Message to add (HumanMessage, AIMessage, or SystemMessage)
            model_id: Optional model identifier (for multi-model sessions)
            panel_id: Panel identifier for panel-specific assistant history
            answer_group_id: Logical group id for one user turn and its panel answers
        """
        if isinstance(message, HumanMessage):
            msg_type = "human"
        elif isinstance(message, AIMessage):
            msg_type = "ai"
        elif isinstance(message, SystemMessage):
            msg_type = "system"
        else:
            msg_type = "unknown"

        with connect_sqlite(self.db_path) as conn:
            cursor = conn.cursor()
            content_text = _normalize_content(message.content)
            normalized_images = _normalize_images(images)
            normalized_files = _normalize_files(files)
            normalized_sources = _normalize_metadata_list(sources)
            normalized_workflow = _normalize_metadata_list(workflow_nodes)
            normalized_token_usage = _normalize_token_usage(token_usage)
            normalized_task_id = str(task_id or "")
            normalized_task_type = str(task_type or "")

            # Insert message
            cursor.execute(
                """
                INSERT INTO messages (
                    session_id, type, content, timestamp, model_id, panel_id, answer_group_id,
                    images_json, files_json, sources_json, workflow_json, token_usage_json,
                    task_id, task_type
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.session_id,
                    msg_type,
                    content_text,
                    time.time(),
                    model_id,
                    panel_id,
                    answer_group_id,
                    json.dumps(normalized_images, ensure_ascii=False),
                    json.dumps(normalized_files, ensure_ascii=False),
                    json.dumps(normalized_sources, ensure_ascii=False),
                    json.dumps(normalized_workflow, ensure_ascii=False),
                    json.dumps(normalized_token_usage, ensure_ascii=False),
                    normalized_task_id,
                    normalized_task_type,
                ),
            )

            # Update session timestamp and auto-generate title from first user message
            cursor.execute(
                "SELECT title FROM sessions WHERE session_id = ?", (self.session_id,)
            )
            row = cursor.fetchone()
            current_title = row[0] if row else ""

            # Auto-generate title from first human message if empty
            if not current_title and msg_type == "human":
                title = _derive_session_title(
                    content_text,
                    images=normalized_images,
                    files=normalized_files,
                )

                if title:
                    cursor.execute(
                        "UPDATE sessions SET updated_at = ?, title = ? WHERE session_id = ?",
                        (time.time(), title, self.session_id),
                    )
                else:
                    cursor.execute(
                        "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                        (time.time(), self.session_id),
                    )
            else:
                cursor.execute(
                    "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                    (time.time(), self.session_id),
                )

            # Storage governance: cap total persisted messages per session
            max_messages = _env_int("MAX_HISTORY_MESSAGES", 200)
            if max_messages > 0:
                _prune_session_messages(cursor, self.session_id, max_messages)

            conn.commit()

    def add_user_message(
        self,
        message: HumanMessage | str,
        model_id: str = "",
        panel_id: str = "",
        answer_group_id: str = "",
        images: Optional[List[Dict[str, Any]]] = None,
        files: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        stored_message = (
            message if isinstance(message, HumanMessage) else HumanMessage(content=message)
        )
        self.add_message(
            stored_message,
            model_id=model_id,
            panel_id=panel_id,
            answer_group_id=answer_group_id,
            images=images,
            files=files,
        )

    def add_ai_message(
        self,
        message: AIMessage | str,
        model_id: str = "",
        panel_id: str = "",
        answer_group_id: str = "",
        images: Optional[List[Dict[str, Any]]] = None,
        files: Optional[List[Dict[str, Any]]] = None,
        sources: Optional[List[Dict[str, Any]]] = None,
        workflow_nodes: Optional[List[Dict[str, Any]]] = None,
        task_id: str = "",
        task_type: str = "",
        token_usage: Optional[Dict[str, Any]] = None,
    ) -> None:
        stored_message = message if isinstance(message, AIMessage) else AIMessage(content=message)
        self.add_message(
            stored_message,
            model_id=model_id,
            panel_id=panel_id,
            answer_group_id=answer_group_id,
            images=images,
            files=files,
            sources=sources,
            workflow_nodes=workflow_nodes,
            task_id=task_id,
            task_type=task_type,
            token_usage=token_usage,
        )

    def add_user_message_once(
        self,
        message: str,
        answer_group_id: str,
        images: Optional[List[Dict[str, Any]]] = None,
        files: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        if not answer_group_id:
            self.add_user_message(message, images=images, files=files)
            return

        content_text = _normalize_content(message)
        normalized_images = _normalize_images(images)
        normalized_files = _normalize_files(files)
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO messages (
                    session_id, type, content, timestamp, model_id, panel_id, answer_group_id,
                    images_json, files_json
                )
                VALUES (?, 'human', ?, ?, '', '', ?, ?, ?)
                """,
                (
                    self.session_id,
                    content_text,
                    time.time(),
                    answer_group_id,
                    json.dumps(normalized_images, ensure_ascii=False),
                    json.dumps(normalized_files, ensure_ascii=False),
                ),
            )
            cursor.execute(
                """
                UPDATE messages
                SET content = ?, images_json = ?, files_json = ?
                WHERE session_id = ?
                  AND type = 'human'
                  AND COALESCE(panel_id, '') = ''
                  AND COALESCE(answer_group_id, '') = ?
                """,
                (
                    content_text,
                    json.dumps(normalized_images, ensure_ascii=False),
                    json.dumps(normalized_files, ensure_ascii=False),
                    self.session_id,
                    answer_group_id,
                ),
            )
            cursor.execute(
                "SELECT title FROM sessions WHERE session_id = ?", (self.session_id,)
            )
            row = cursor.fetchone()
            current_title = row[0] if row else ""
            if not current_title:
                title = _derive_session_title(
                    content_text,
                    images=normalized_images,
                    files=normalized_files,
                )
                if title:
                    cursor.execute(
                        "UPDATE sessions SET updated_at = ?, title = ? WHERE session_id = ?",
                        (time.time(), title, self.session_id),
                    )
                else:
                    cursor.execute(
                        "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                        (time.time(), self.session_id),
                    )
            else:
                cursor.execute(
                    "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                    (time.time(), self.session_id),
                )
            conn.commit()

    def delete_ai_messages_for_answer_group(
        self,
        panel_id: str,
        answer_group_id: str,
    ) -> None:
        if not panel_id or not answer_group_id:
            return
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM messages
                WHERE session_id = ?
                  AND type = 'ai'
                  AND COALESCE(panel_id, '') = ?
                  AND COALESCE(answer_group_id, '') = ?
                """,
                (self.session_id, panel_id, answer_group_id),
            )
            conn.commit()

    def clear(self) -> None:
        """Clear all messages for this session."""
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM messages WHERE session_id = ?", (self.session_id,)
            )

            # Update session timestamp
            cursor.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (time.time(), self.session_id),
            )

            conn.commit()
            logger.info("Cleared messages for session: %s", self.session_id)


def _prune_session_messages(
    cursor: sqlite3.Cursor,
    session_id: str,
    max_messages: int,
) -> int:
    if max_messages <= 0:
        return 0

    cursor.execute(
        """
        SELECT id, type, COALESCE(answer_group_id, '')
        FROM messages
        WHERE session_id = ?
        ORDER BY id ASC
        """,
        (session_id,),
    )
    rows = cursor.fetchall()
    total_messages = len(rows)
    if total_messages <= max_messages:
        return 0

    prune_groups = _group_message_ids_for_history_pruning(rows)
    if not prune_groups:
        return 0

    remaining_messages = total_messages
    ids_to_delete: List[int] = []

    # Preserve the newest group intact even if one oversized turn exceeds the cap.
    for prune_group in prune_groups[:-1]:
        if remaining_messages <= max_messages:
            break
        ids_to_delete.extend(prune_group)
        remaining_messages -= len(prune_group)

    if not ids_to_delete:
        return 0

    placeholders = ", ".join("?" for _ in ids_to_delete)
    cursor.execute(
        f"""
        DELETE FROM messages
        WHERE session_id = ?
          AND id IN ({placeholders})
        """,
        (session_id, *ids_to_delete),
    )
    logger.info(
        "Pruned session history session_id=%s removed=%d kept=%d max=%d",
        session_id,
        len(ids_to_delete),
        remaining_messages,
        max_messages,
    )
    return len(ids_to_delete)


def _session_exists(
    cursor: sqlite3.Cursor,
    session_id: str,
) -> bool:
    cursor.execute(
        "SELECT 1 FROM sessions WHERE session_id = ?",
        (session_id,),
    )
    return cursor.fetchone() is not None


def _collect_message_search_hits(
    cursor: sqlite3.Cursor,
    normalized_query: str,
    session_ids: set[str],
) -> Dict[str, str]:
    if not normalized_query or not session_ids:
        return {}

    match_query = _build_message_search_match_query(normalized_query)
    sorted_session_ids = sorted(session_ids)

    if match_query and _message_search_table_exists(cursor):
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

    hits: Dict[str, str] = {}
    for row in cursor.fetchall():
        session_id = str(row[0] or "")
        if session_id not in session_ids or session_id in hits:
            continue
        preview = _build_search_preview(row[1], normalized_query)
        if preview:
            hits[session_id] = preview
    return hits


def _fetch_session_row(
    cursor: sqlite3.Cursor,
    session_id: str,
) -> Optional[tuple]:
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
) -> List[Dict]:
    """
    Get all sessions sorted by most recently updated.

    Args:
        db_path: Path to SQLite database file

    Returns:
        List of session dicts with keys: session_id, title, created_at, updated_at, message_count
    """
    with connect_sqlite(db_path) as conn:
        cursor = conn.cursor()
        _init_messages_table(conn)
        _init_workspaces_table(conn)
        _init_sessions_table(conn)
        _init_session_panels_table(conn)

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
        where_clauses: List[str] = []
        params: List[Any] = [DEFAULT_WORKSPACE_ID]

        normalized_query = query.strip().lower()
        match_query = _build_message_search_match_query(normalized_query)
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
                        if match_query and _message_search_table_exists(cursor)
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
                    if match_query and _message_search_table_exists(cursor)
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

        sessions = [_row_to_session(row) for row in cursor.fetchall()]

        normalized_tag = tag.strip().lower()
        if normalized_tag:
            sessions = [
                session
                for session in sessions
                if any(item.lower() == normalized_tag for item in session["tags"])
            ]

        if normalized_query and sessions:
            search_hits = _collect_message_search_hits(
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
    session_id: str, db_path: str | None = None
) -> Optional[Dict[str, Any]]:
    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        return None

    with connect_sqlite(db_path) as conn:
        cursor = conn.cursor()
        _init_messages_table(conn)
        _init_workspaces_table(conn)
        _init_sessions_table(conn)
        _init_session_panels_table(conn)
        row = _fetch_session_row(cursor, normalized_session_id)
        return _row_to_session(row) if row else None


def set_message_feedback(
    session_id: str,
    *,
    feedback_value: int,
    message_id: Optional[int] = None,
    panel_id: str = "",
    answer_group_id: str = "",
    db_path: str | None = None,
) -> Optional[Dict[str, Any]]:
    normalized_feedback_value = _normalize_message_feedback_value(feedback_value)
    normalized_panel_id = str(panel_id or "").strip()
    normalized_answer_group_id = str(answer_group_id or "").strip()

    if _should_use_postgres_store(db_path):
        from backend.stores.factory import create_chat_message_history

        history = create_chat_message_history(session_id)
        return cast(
            Optional[Dict[str, Any]],
            history.set_message_feedback(
                feedback_value=normalized_feedback_value,
                message_id=message_id,
                panel_id=normalized_panel_id,
                answer_group_id=normalized_answer_group_id,
            ),
        )

    with connect_sqlite(db_path) as conn:
        _init_messages_table(conn)
        _init_sessions_table(conn)
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
                raise ValueError("未提供 message_id 时必须提供 answer_group_id")
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


def truncate_session_from_answer_group(
    session_id: str,
    *,
    answer_group_id: str,
    content: str,
    images: Optional[List[Dict[str, Any]]] = None,
    files: Optional[List[Dict[str, Any]]] = None,
    db_path: str | None = None,
) -> Optional[Dict[str, Any]]:
    normalized_answer_group_id = str(answer_group_id or "").strip()
    if not normalized_answer_group_id:
        raise ValueError("必须提供 answer_group_id")

    normalized_content = _normalize_content(content)
    normalized_images = _normalize_images(images)
    normalized_files = _normalize_files(files)
    now = time.time()

    with connect_sqlite(db_path) as conn:
        _init_messages_table(conn)
        _init_sessions_table(conn)
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
    tags: Optional[List[str]] = None,
    workspace_id: Optional[str] = None,
    db_path: str | None = None,
) -> Optional[Dict[str, Any]]:
    with connect_sqlite(db_path) as conn:
        _init_workspaces_table(conn)
        _init_sessions_table(conn)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM sessions WHERE session_id = ?",
            (session_id,),
        )
        if not cursor.fetchone():
            return None

        updates: List[str] = []
        params: List[Any] = []

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
            normalized_tags = _normalize_tags(tags)
            updates.append("tags_json = ?")
            params.append(json.dumps(normalized_tags, ensure_ascii=False))

        if workspace_id is not None:
            normalized_workspace_id = str(workspace_id or "").strip()
            if not normalized_workspace_id:
                raise ValueError("workspace_id 不能为空")
            if not _workspace_exists(cursor, normalized_workspace_id):
                raise ValueError("工作区不存在")
            updates.append("workspace_id = ?")
            params.append(normalized_workspace_id)

        if not updates:
            return get_session(session_id, db_path=db_path)

        updates.append("updated_at = ?")
        params.append(time.time())
        params.append(session_id)

        cursor.execute(
            f"UPDATE sessions SET {', '.join(updates)} WHERE session_id = ?",
            tuple(params),
        )
        conn.commit()

    return get_session(session_id, db_path=db_path)


def reorder_sessions(
    session_ids: List[str],
    *,
    workspace_id: Optional[str] = None,
    db_path: str | None = None,
) -> Dict[str, Any]:
    normalized_ids: List[str] = []
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

    with connect_sqlite(db_path) as conn:
        _init_workspaces_table(conn)
        _init_sessions_table(conn)
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
            session_id
            for session_id in normalized_ids
            if session_id not in existing_ids
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
        ordered_items: List[Dict[str, Any]] = []
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


def delete_session(session_id: str, db_path: str | None = None) -> None:
    """
    Delete a session and all its messages.

    Args:
        session_id: Session ID to delete
        db_path: Path to SQLite database file
    """
    with connect_sqlite(db_path) as conn:
        _init_messages_table(conn)
        _init_workspaces_table(conn)
        _init_sessions_table(conn)
        _init_session_panels_table(conn)
        _init_session_memory_table(conn)
        _init_retrieval_feedback_table(conn)
        _init_bookmarks_table(conn)
        cursor = conn.cursor()

        # Delete messages
        cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM session_panels WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM session_memory WHERE session_id = ?", (session_id,))
        cursor.execute(
            "DELETE FROM retrieval_feedback WHERE session_id = ?", (session_id,)
        )
        cursor.execute("DELETE FROM bookmarks WHERE session_id = ?", (session_id,))

        # Delete session
        cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

        conn.commit()
        logger.info("Deleted session: %s", session_id)


def replace_session_panels(
    session_id: str,
    panel_configs: List[Dict[str, Any]],
    db_path: str = DB_PATH,
) -> None:
    _replace_session_panels(
        session_id,
        panel_configs,
        db_path=db_path,
        connect_sqlite_fn=connect_sqlite,
    )


def upsert_session_panel(
    session_id: str,
    panel_config: Dict[str, Any],
    db_path: str = DB_PATH,
) -> None:
    _upsert_session_panel(
        session_id,
        panel_config,
        db_path=db_path,
        connect_sqlite_fn=connect_sqlite,
    )


def get_session_panels(session_id: str, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    return _get_session_panels(
        session_id,
        db_path=db_path,
        connect_sqlite_fn=connect_sqlite,
    )


def promote_panel_answer(
    session_id: str,
    answer_group_id: str,
    source_panel_id: str,
    db_path: str = DB_PATH,
) -> Optional[Dict[str, Any]]:
    with connect_sqlite(db_path) as conn:
        _init_messages_table(conn)
        _init_session_panels_table(conn)
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
            "sources": _parse_json_list(source_sources_json),
            "workflow_nodes": _parse_json_list(source_workflow_json),
            "token_usage": _normalize_token_usage(source_token_usage_json),
            "task_id": source_task_id,
            "task_type": source_task_type,
        }
