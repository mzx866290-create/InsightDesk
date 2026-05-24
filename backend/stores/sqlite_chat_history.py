"""SQLite-backed LangChain chat message history."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from typing import Any, Callable, Dict, List, Optional

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from backend.core.storage_runtime import app_database_path
from backend.stores.chat_messages import (
    build_human_message_content_for_model as _build_human_message_content_for_model,
    derive_session_title as _derive_session_title,
    env_int as _env_int,
    group_message_ids_for_history_pruning as _group_message_ids_for_history_pruning,
)
from backend.stores.chat_normalization import (
    normalize_message_feedback_value as _normalize_message_feedback_value,
)
from backend.stores.chat_schema import (
    init_bookmarks_table as _init_bookmarks_table,
    init_messages_table as _init_messages_table,
    init_retrieval_feedback_table as _init_retrieval_feedback_table,
    init_session_memory_table as _init_session_memory_table,
    init_session_panels_table as _init_session_panels_table,
    init_sessions_table as _init_sessions_table,
    init_workspaces_table as _init_workspaces_table,
)
from backend.stores.chat_serialization import (
    normalize_content as _normalize_content,
    normalize_files as _normalize_files,
    normalize_images as _normalize_images,
    normalize_metadata_list as _normalize_metadata_list,
    normalize_token_usage as _normalize_token_usage,
    parse_json_list as _parse_json_list,
)
from backend.stores.prompt_store import (
    init_assistant_presets_table as _init_assistant_presets_table,
    init_system_prompts_table as _init_system_prompts_table,
)
from backend.stores.sqlite_runtime import connect_sqlite
from backend.stores.workspace_store import get_active_workspace_id as _get_active_workspace_id

logger = logging.getLogger(__name__)


class SQLiteChatMessageHistory(BaseChatMessageHistory):
    """
    SQLite-based chat message history that persists across service restarts.

    Implements LangChain's BaseChatMessageHistory interface.
    """

    def __init__(
        self,
        session_id: str,
        db_path: str | None = None,
        *,
        connect_sqlite_fn: Callable[[str | None], sqlite3.Connection] = connect_sqlite,
    ):
        """
        Initialize SQLite chat history for a specific session.

        Args:
            session_id: Unique session identifier
            db_path: Path to SQLite database file
        """
        self.session_id = session_id
        self.db_path = str(db_path or app_database_path()).strip()
        self._connect_sqlite = connect_sqlite_fn
        self._init_db()
        self._ensure_session_exists()

    def _init_db(self) -> None:
        """Initialize database schema if not exists."""
        with self._connect_sqlite(self.db_path) as conn:
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
        with self._connect_sqlite(self.db_path) as conn:
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
        with self._connect_sqlite(self.db_path) as conn:
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

        with self._connect_sqlite(self.db_path) as conn:
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
                prune_session_messages(cursor, self.session_id, max_messages)

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
        with self._connect_sqlite(self.db_path) as conn:
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
        with self._connect_sqlite(self.db_path) as conn:
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
        with self._connect_sqlite(self.db_path) as conn:
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


def prune_session_messages(
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


__all__ = ["SQLiteChatMessageHistory", "prune_session_messages"]
