"""
SQLite-based persistent chat message history
Implements LangChain's BaseChatMessageHistory interface
"""

import json
import sqlite3
import time
import logging
import uuid
from typing import TYPE_CHECKING, List, Dict, Any, Optional, cast
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from backend.core.storage_runtime import (
    DATABASE_PROVIDER_POSTGRES,
    app_database_path,
    database_provider,
    ensure_sqlite_parent,
)
from backend.stores.chat_serialization import (
    normalize_content as _normalize_content,
    normalize_files as _normalize_files,
    normalize_images as _normalize_images,
    normalize_metadata_list as _normalize_metadata_list,
    normalize_token_usage as _normalize_token_usage,
    parse_json_list as _parse_json_list,
    parse_json_object as _parse_json_object,
)
from backend.stores.chat_schema import (
    init_bookmarks_table as _init_bookmarks_table,
    init_messages_table as _init_messages_table,
    init_retrieval_feedback_table as _init_retrieval_feedback_table,
    init_session_memory_table as _init_session_memory_table,
    init_session_panels_table as _init_session_panels_table,
    message_search_table_exists as _message_search_table_exists,
)
from backend.stores.chat_rows import (
    row_to_assistant_preset as _row_to_assistant_preset,
    row_to_bookmark as _row_to_bookmark,
    row_to_prompt as _row_to_prompt,
    row_to_session as _row_to_session,
    row_to_session_memory as _row_to_session_memory,
    row_to_workspace as _row_to_workspace,
)
from backend.stores.chat_messages import (
    build_human_message_content_for_model as _build_human_message_content_for_model,
    build_message_search_match_query as _build_message_search_match_query,
    build_retrieval_source_key as _build_retrieval_source_key,
    build_search_preview as _build_search_preview,
    derive_session_title as _derive_session_title,
    env_int as _env_int,
    group_message_ids_for_history_pruning as _group_message_ids_for_history_pruning,
)
from backend.stores.chat_normalization import (
    DEFAULT_ASSISTANT_PRESET_ID,
    DEFAULT_WORKSPACE_ID,
    DEFAULT_WORKSPACE_NAME,
    default_assistant_model_config as _default_assistant_model_config,
    normalize_assistant_model_config as _normalize_assistant_model_config,
    normalize_assistant_starters as _normalize_assistant_starters,
    normalize_assistant_tool_config as _normalize_assistant_tool_config,
    normalize_bookmark_role as _normalize_bookmark_role,
    normalize_message_feedback_value as _normalize_message_feedback_value,
    normalize_session_memory_content as _normalize_session_memory_content,
    normalize_session_memory_kind as _normalize_session_memory_kind,
    normalize_session_memory_meta as _normalize_session_memory_meta,
    normalize_tags as _normalize_tags,
    normalize_workspace_color as _normalize_workspace_color,
    normalize_workspace_description as _normalize_workspace_description,
    normalize_workspace_name as _normalize_workspace_name,
    normalize_workspace_output_preset as _normalize_workspace_output_preset,
    normalize_workspace_panel_configs as _normalize_workspace_panel_configs,
    normalize_workspace_tool_config as _normalize_workspace_tool_config,
)

if TYPE_CHECKING:
    from backend.stores.protocols import RetrievalFeedbackStore, SessionMemoryStore

logger = logging.getLogger(__name__)

DB_PATH = app_database_path()
SQLITE_TIMEOUT_SECONDS = 5
SQLITE_BUSY_TIMEOUT_MS = 5000
_UNSET = object()


def _should_use_postgres_store(db_path: str | None = None) -> bool:
    """Route default runtime calls to PostgreSQL while preserving explicit SQLite paths."""

    normalized_db_path = str(db_path or "").strip()
    return database_provider() == DATABASE_PROVIDER_POSTGRES and normalized_db_path in {
        "",
        DB_PATH,
    }


def _session_memory_store() -> "SessionMemoryStore":
    from backend.stores.factory import create_session_memory_store

    return create_session_memory_store()


def _retrieval_feedback_store() -> "RetrievalFeedbackStore":
    from backend.stores.factory import create_retrieval_feedback_store

    return create_retrieval_feedback_store()


def connect_sqlite(db_path: str | None = None) -> sqlite3.Connection:
    """Create a SQLite connection with the project's default safety settings."""
    resolved_db_path = str(db_path or app_database_path()).strip()
    ensure_sqlite_parent(resolved_db_path)
    conn = sqlite3.connect(resolved_db_path, timeout=SQLITE_TIMEOUT_SECONDS)
    conn.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


# Exported constant so api_server can return it to the frontend
CONTEXT_HISTORY_MESSAGES: int = _env_int("CONTEXT_HISTORY_MESSAGES", 16)

DEFAULT_SYSTEM_PROMPT = (
    "你是一个企业知识库助手，可以查询内部文档和联网搜索。"
    "请根据用户问题选择合适的工具来回答，回答时请引用信息来源。"
)

def _init_sessions_table(conn: sqlite3.Connection) -> None:
    _init_workspaces_table(conn)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            title TEXT DEFAULT '',
            is_archived INTEGER DEFAULT 0,
            is_favorite INTEGER DEFAULT 0,
            is_pinned INTEGER DEFAULT 0,
            session_order REAL DEFAULT 0,
            tags_json TEXT DEFAULT '[]',
            workspace_id TEXT DEFAULT 'workspace-default'
        )
    """)
    existing_columns = {row[1] for row in cursor.execute("PRAGMA table_info(sessions)")}
    if "title" not in existing_columns:
        cursor.execute("ALTER TABLE sessions ADD COLUMN title TEXT DEFAULT ''")
        logger.info("Migrated sessions table: added 'title' column")
    if "is_archived" not in existing_columns:
        cursor.execute("ALTER TABLE sessions ADD COLUMN is_archived INTEGER DEFAULT 0")
        logger.info("Migrated sessions table: added 'is_archived' column")
    if "is_favorite" not in existing_columns:
        cursor.execute("ALTER TABLE sessions ADD COLUMN is_favorite INTEGER DEFAULT 0")
        logger.info("Migrated sessions table: added 'is_favorite' column")
    if "is_pinned" not in existing_columns:
        cursor.execute("ALTER TABLE sessions ADD COLUMN is_pinned INTEGER DEFAULT 0")
        logger.info("Migrated sessions table: added 'is_pinned' column")
    if "session_order" not in existing_columns:
        cursor.execute("ALTER TABLE sessions ADD COLUMN session_order REAL DEFAULT 0")
        logger.info("Migrated sessions table: added 'session_order' column")
    if "tags_json" not in existing_columns:
        cursor.execute("ALTER TABLE sessions ADD COLUMN tags_json TEXT DEFAULT '[]'")
        logger.info("Migrated sessions table: added 'tags_json' column")
    if "workspace_id" not in existing_columns:
        cursor.execute(
            f"ALTER TABLE sessions ADD COLUMN workspace_id TEXT DEFAULT '{DEFAULT_WORKSPACE_ID}'"
        )
        logger.info("Migrated sessions table: added 'workspace_id' column")
    cursor.execute(
        "UPDATE sessions SET workspace_id = ? WHERE COALESCE(workspace_id, '') = ''",
        (DEFAULT_WORKSPACE_ID,),
    )
    conn.commit()


def _init_workspaces_table(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS workspaces (
            workspace_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            color TEXT DEFAULT 'blue',
            default_panels_json TEXT DEFAULT '[]',
            tool_config_json TEXT DEFAULT '{}',
            output_preset_json TEXT DEFAULT '{}',
            is_active INTEGER DEFAULT 0,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    existing_columns = {
        row[1] for row in cursor.execute("PRAGMA table_info(workspaces)")
    }
    if "description" not in existing_columns:
        cursor.execute("ALTER TABLE workspaces ADD COLUMN description TEXT DEFAULT ''")
        logger.info("Migrated workspaces table: added 'description' column")
    if "color" not in existing_columns:
        cursor.execute("ALTER TABLE workspaces ADD COLUMN color TEXT DEFAULT 'blue'")
        logger.info("Migrated workspaces table: added 'color' column")
    if "default_panels_json" not in existing_columns:
        cursor.execute(
            "ALTER TABLE workspaces ADD COLUMN default_panels_json TEXT DEFAULT '[]'"
        )
        logger.info("Migrated workspaces table: added 'default_panels_json' column")
    if "tool_config_json" not in existing_columns:
        cursor.execute(
            "ALTER TABLE workspaces ADD COLUMN tool_config_json TEXT DEFAULT '{}'"
        )
        logger.info("Migrated workspaces table: added 'tool_config_json' column")
    if "output_preset_json" not in existing_columns:
        cursor.execute(
            "ALTER TABLE workspaces ADD COLUMN output_preset_json TEXT DEFAULT '{}'"
        )
        logger.info("Migrated workspaces table: added 'output_preset_json' column")
    if "is_active" not in existing_columns:
        cursor.execute("ALTER TABLE workspaces ADD COLUMN is_active INTEGER DEFAULT 0")
        logger.info("Migrated workspaces table: added 'is_active' column")
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_workspaces_active_updated
        ON workspaces(is_active DESC, updated_at DESC)
        """
    )
    now = time.time()
    cursor.execute(
        """
        INSERT OR IGNORE INTO workspaces (
            workspace_id, name, description, color, default_panels_json, tool_config_json,
            output_preset_json, is_active, created_at, updated_at
        )
        VALUES (?, ?, '', 'blue', '[]', '{}', '{}', 1, ?, ?)
        """,
        (
            DEFAULT_WORKSPACE_ID,
            DEFAULT_WORKSPACE_NAME,
            now,
            now,
        ),
    )
    cursor.execute(
        "UPDATE workspaces SET default_panels_json = '[]' WHERE COALESCE(default_panels_json, '') = ''"
    )
    cursor.execute(
        "UPDATE workspaces SET tool_config_json = '{}' WHERE COALESCE(tool_config_json, '') = ''"
    )
    cursor.execute(
        "UPDATE workspaces SET output_preset_json = '{}' WHERE COALESCE(output_preset_json, '') = ''"
    )
    cursor.execute(
        "SELECT workspace_id FROM workspaces WHERE COALESCE(is_active, 0) = 1 LIMIT 1"
    )
    if not cursor.fetchone():
        cursor.execute(
            "UPDATE workspaces SET is_active = 1, updated_at = ? WHERE workspace_id = ?",
            (now, DEFAULT_WORKSPACE_ID),
        )
    conn.commit()


def _init_system_prompts_table(conn: sqlite3.Connection) -> None:
    """Ensure system_prompts table exists and has at least the built-in default."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_prompts (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            content TEXT NOT NULL,
            is_default INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 0,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            vector_store_id TEXT DEFAULT '',
            dashboard_template TEXT DEFAULT ''
        )
    """)
    conn.commit()
    # Migration: add vector_store_id if missing
    existing_cols = {
        row[1] for row in cursor.execute("PRAGMA table_info(system_prompts)")
    }
    if "vector_store_id" not in existing_cols:
        cursor.execute(
            "ALTER TABLE system_prompts ADD COLUMN vector_store_id TEXT DEFAULT ''"
        )
        conn.commit()
        logger.info("Migrated system_prompts table: added 'vector_store_id' column")
    if "dashboard_template" not in existing_cols:
        cursor.execute(
            "ALTER TABLE system_prompts ADD COLUMN dashboard_template TEXT DEFAULT ''"
        )
        conn.commit()
        logger.info("Migrated system_prompts table: added 'dashboard_template' column")
    # Seed a built-in default if the table is empty
    cursor.execute("SELECT COUNT(1) FROM system_prompts")
    if cursor.fetchone()[0] == 0:
        now = time.time()
        builtin_id = "builtin-default"
        cursor.execute(
            """
            INSERT INTO system_prompts (id, name, content, is_default, is_active, created_at, updated_at)
            VALUES (?, ?, ?, 1, 1, ?, ?)
            """,
            (builtin_id, "企业知识库助手", DEFAULT_SYSTEM_PROMPT, now, now),
        )
        conn.commit()
        logger.info("Seeded built-in default system prompt")


def _init_assistant_presets_table(conn: sqlite3.Connection) -> None:
    """Ensure assistant preset storage exists and includes one safe default."""
    _init_system_prompts_table(conn)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS assistant_presets (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            avatar TEXT DEFAULT '',
            system_prompt_id TEXT DEFAULT '',
            default_model_config_json TEXT DEFAULT '{}',
            tool_config_json TEXT DEFAULT '{}',
            starters_json TEXT DEFAULT '[]',
            is_default INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 0,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_assistant_presets_active_updated
        ON assistant_presets(is_active DESC, updated_at DESC)
        """
    )
    cursor.execute("SELECT COUNT(1) FROM assistant_presets")
    if cursor.fetchone()[0] == 0:
        now = time.time()
        cursor.execute(
            """
            INSERT INTO assistant_presets (
                id, name, avatar, system_prompt_id, default_model_config_json,
                tool_config_json, starters_json, is_default, is_active, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?)
            """,
            (
                DEFAULT_ASSISTANT_PRESET_ID,
                "企业知识库助手",
                "🤖",
                "builtin-default",
                json.dumps(_default_assistant_model_config(), ensure_ascii=False),
                json.dumps(_normalize_assistant_tool_config(), ensure_ascii=False),
                json.dumps(["总结这份材料", "检索知识库并给出出处"], ensure_ascii=False),
                now,
                now,
            ),
        )
    conn.commit()


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


def _workspace_exists(
    cursor: sqlite3.Cursor,
    workspace_id: str,
) -> bool:
    cursor.execute(
        "SELECT 1 FROM workspaces WHERE workspace_id = ?",
        (workspace_id,),
    )
    return cursor.fetchone() is not None


def _get_active_workspace_id(cursor: sqlite3.Cursor) -> str:
    cursor.execute(
        """
        SELECT workspace_id
        FROM workspaces
        ORDER BY COALESCE(is_active, 0) DESC, updated_at DESC, created_at ASC
        LIMIT 1
        """
    )
    row = cursor.fetchone()
    return str(row[0] or DEFAULT_WORKSPACE_ID) if row else DEFAULT_WORKSPACE_ID


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


def _fetch_workspace_row(
    cursor: sqlite3.Cursor,
    workspace_id: str,
) -> Optional[tuple]:
    cursor.execute(
        """
        SELECT
            w.workspace_id,
            w.name,
            COALESCE(w.description, ''),
            COALESCE(w.color, 'blue'),
            COALESCE(w.default_panels_json, '[]'),
            COALESCE(w.tool_config_json, '{}'),
            COALESCE(w.output_preset_json, '{}'),
            COALESCE(w.is_active, 0),
            w.created_at,
            w.updated_at,
            COUNT(s.session_id) as session_count
        FROM workspaces w
        LEFT JOIN sessions s
          ON COALESCE(s.workspace_id, ?) = w.workspace_id
        WHERE w.workspace_id = ?
        GROUP BY
            w.workspace_id,
            w.name,
            w.description,
            w.color,
            w.default_panels_json,
            w.tool_config_json,
            w.output_preset_json,
            w.is_active,
            w.created_at,
            w.updated_at
        LIMIT 1
        """,
        (DEFAULT_WORKSPACE_ID, workspace_id),
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


def list_workspaces(
    db_path: str | None = None,
) -> List[Dict[str, Any]]:
    with connect_sqlite(db_path) as conn:
        _init_workspaces_table(conn)
        _init_sessions_table(conn)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                w.workspace_id,
                w.name,
                COALESCE(w.description, ''),
                COALESCE(w.color, 'blue'),
                COALESCE(w.default_panels_json, '[]'),
                COALESCE(w.tool_config_json, '{}'),
                COALESCE(w.output_preset_json, '{}'),
                COALESCE(w.is_active, 0),
                w.created_at,
                w.updated_at,
                COUNT(s.session_id) as session_count
            FROM workspaces w
            LEFT JOIN sessions s
              ON COALESCE(s.workspace_id, ?) = w.workspace_id
            GROUP BY
                w.workspace_id,
                w.name,
                w.description,
                w.color,
                w.default_panels_json,
                w.tool_config_json,
                w.output_preset_json,
                w.is_active,
                w.created_at,
                w.updated_at
            ORDER BY COALESCE(w.is_active, 0) DESC, w.updated_at DESC, w.created_at ASC
            """,
            (DEFAULT_WORKSPACE_ID,),
        )
        return [_row_to_workspace(row) for row in cursor.fetchall()]


def get_workspace(
    workspace_id: str,
    db_path: str | None = None,
) -> Optional[Dict[str, Any]]:
    normalized_workspace_id = str(workspace_id or "").strip()
    if not normalized_workspace_id:
        return None

    with connect_sqlite(db_path) as conn:
        _init_workspaces_table(conn)
        _init_sessions_table(conn)
        cursor = conn.cursor()
        row = _fetch_workspace_row(cursor, normalized_workspace_id)
        return _row_to_workspace(row) if row else None


def create_workspace(
    name: str,
    *,
    description: str = "",
    color: str = "blue",
    default_panels: Optional[List[Dict[str, Any]]] = None,
    tool_config: Optional[Dict[str, Any]] = None,
    output_preset: Optional[Dict[str, Any]] = None,
    activate: bool = True,
    db_path: str | None = None,
) -> Dict[str, Any]:
    normalized_name = _normalize_workspace_name(name)
    normalized_description = _normalize_workspace_description(description)
    normalized_color = _normalize_workspace_color(color)
    normalized_default_panels = _normalize_workspace_panel_configs(default_panels)
    normalized_tool_config = _normalize_workspace_tool_config(tool_config)
    normalized_output_preset = _normalize_workspace_output_preset(output_preset)
    workspace_id = str(uuid.uuid4())
    now = time.time()

    with connect_sqlite(db_path) as conn:
        _init_workspaces_table(conn)
        cursor = conn.cursor()
        if activate:
            cursor.execute("UPDATE workspaces SET is_active = 0")
        cursor.execute(
            """
            INSERT INTO workspaces (
                workspace_id, name, description, color, default_panels_json, tool_config_json,
                output_preset_json, is_active, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workspace_id,
                normalized_name,
                normalized_description,
                normalized_color,
                json.dumps(normalized_default_panels, ensure_ascii=False),
                json.dumps(normalized_tool_config, ensure_ascii=False),
                json.dumps(normalized_output_preset, ensure_ascii=False),
                1 if activate else 0,
                now,
                now,
            ),
        )
        conn.commit()
    workspace = get_workspace(workspace_id, db_path=db_path)
    if workspace is None:
        raise RuntimeError("Failed to create workspace")
    return workspace


def update_workspace(
    workspace_id: str,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    color: Optional[str] = None,
    default_panels: Optional[List[Dict[str, Any]]] = None,
    tool_config: Optional[Dict[str, Any]] = None,
    output_preset: Optional[Dict[str, Any]] = None,
    db_path: str | None = None,
) -> Optional[Dict[str, Any]]:
    with connect_sqlite(db_path) as conn:
        _init_workspaces_table(conn)
        cursor = conn.cursor()
        if not _workspace_exists(cursor, workspace_id):
            return None

        updates: List[str] = []
        params: List[Any] = []

        if name is not None:
            updates.append("name = ?")
            params.append(_normalize_workspace_name(name))
        if description is not None:
            updates.append("description = ?")
            params.append(_normalize_workspace_description(description))
        if color is not None:
            updates.append("color = ?")
            params.append(_normalize_workspace_color(color))
        if default_panels is not None:
            updates.append("default_panels_json = ?")
            params.append(
                json.dumps(
                    _normalize_workspace_panel_configs(default_panels),
                    ensure_ascii=False,
                )
            )
        if tool_config is not None:
            updates.append("tool_config_json = ?")
            params.append(
                json.dumps(
                    _normalize_workspace_tool_config(tool_config),
                    ensure_ascii=False,
                )
            )
        if output_preset is not None:
            updates.append("output_preset_json = ?")
            params.append(
                json.dumps(
                    _normalize_workspace_output_preset(output_preset),
                    ensure_ascii=False,
                )
            )

        if not updates:
            return get_workspace(workspace_id, db_path=db_path)

        updates.append("updated_at = ?")
        params.append(time.time())
        params.append(workspace_id)
        cursor.execute(
            f"UPDATE workspaces SET {', '.join(updates)} WHERE workspace_id = ?",
            tuple(params),
        )
        conn.commit()
    return get_workspace(workspace_id, db_path=db_path)


def activate_workspace(
    workspace_id: str,
    *,
    db_path: str | None = None,
) -> Optional[Dict[str, Any]]:
    with connect_sqlite(db_path) as conn:
        _init_workspaces_table(conn)
        cursor = conn.cursor()
        if not _workspace_exists(cursor, workspace_id):
            return None
        now = time.time()
        cursor.execute("UPDATE workspaces SET is_active = 0")
        cursor.execute(
            "UPDATE workspaces SET is_active = 1, updated_at = ? WHERE workspace_id = ?",
            (now, workspace_id),
        )
        conn.commit()
    return get_workspace(workspace_id, db_path=db_path)


def delete_workspace(
    workspace_id: str,
    *,
    target_workspace_id: Optional[str] = None,
    db_path: str | None = None,
) -> Optional[Dict[str, Any]]:
    normalized_workspace_id = str(workspace_id or "").strip()
    if not normalized_workspace_id:
        return None
    if normalized_workspace_id == DEFAULT_WORKSPACE_ID:
        raise ValueError("默认工作区不能删除")

    normalized_target_workspace_id = (
        str(target_workspace_id or "").strip() or DEFAULT_WORKSPACE_ID
    )
    if normalized_target_workspace_id == normalized_workspace_id:
        raise ValueError("迁移目标工作区不能与被删除的工作区相同")

    with connect_sqlite(db_path) as conn:
        _init_workspaces_table(conn)
        _init_sessions_table(conn)
        cursor = conn.cursor()
        if not _workspace_exists(cursor, normalized_workspace_id):
            return None
        if not _workspace_exists(cursor, normalized_target_workspace_id):
            raise ValueError("目标工作区不存在")

        cursor.execute(
            "SELECT COALESCE(is_active, 0) FROM workspaces WHERE workspace_id = ?",
            (normalized_workspace_id,),
        )
        row = cursor.fetchone()
        was_active = bool(row[0]) if row else False
        now = time.time()

        cursor.execute(
            """
            UPDATE sessions
            SET workspace_id = ?, updated_at = ?
            WHERE COALESCE(workspace_id, ?) = ?
            """,
            (
                normalized_target_workspace_id,
                now,
                DEFAULT_WORKSPACE_ID,
                normalized_workspace_id,
            ),
        )
        cursor.execute(
            "UPDATE workspaces SET updated_at = ? WHERE workspace_id = ?",
            (now, normalized_target_workspace_id),
        )
        cursor.execute(
            "DELETE FROM workspaces WHERE workspace_id = ?",
            (normalized_workspace_id,),
        )
        if was_active:
            cursor.execute("UPDATE workspaces SET is_active = 0")
            cursor.execute(
                "UPDATE workspaces SET is_active = 1, updated_at = ? WHERE workspace_id = ?",
                (now, normalized_target_workspace_id),
            )
        conn.commit()

    target_workspace = get_workspace(normalized_target_workspace_id, db_path=db_path)
    return {
        "deleted_workspace_id": normalized_workspace_id,
        "target_workspace_id": normalized_target_workspace_id,
        "target_workspace": target_workspace,
    }


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


def set_retrieval_feedback(
    session_id: str,
    *,
    panel_id: str,
    answer_group_id: str,
    source: Dict[str, Any],
    feedback_value: int,
    db_path: str | None = None,
) -> Dict[str, Any]:
    if _should_use_postgres_store(db_path):
        return _retrieval_feedback_store().set_retrieval_feedback(
            session_id,
            panel_id=panel_id,
            answer_group_id=answer_group_id,
            source=source,
            feedback_value=feedback_value,
        )

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

    with connect_sqlite(db_path) as conn:
        _init_sessions_table(conn)
        _init_retrieval_feedback_table(conn)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM sessions WHERE session_id = ? LIMIT 1",
            (session_id,),
        )
        if not cursor.fetchone():
            raise ValueError("未找到会话")

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
) -> List[Dict[str, Any]]:
    if _should_use_postgres_store(db_path):
        return _retrieval_feedback_store().list_retrieval_feedback(
            session_id,
            panel_id=panel_id,
            answer_group_id=answer_group_id,
        )

    normalized_panel_id = str(panel_id or "").strip()
    normalized_answer_group_id = str(answer_group_id or "").strip()
    if not normalized_panel_id:
        raise ValueError("必须提供 panel_id")
    if not normalized_answer_group_id:
        raise ValueError("必须提供 answer_group_id")

    with connect_sqlite(db_path) as conn:
        _init_retrieval_feedback_table(conn)
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
            "feedback_value": _normalize_message_feedback_value(row[1]),
            "updated_at": float(row[2] or 0),
        }
        for row in rows
    ]


def aggregate_retrieval_feedback_by_source(
    *,
    source_type: Optional[str] = None,
    db_path: str | None = None,
) -> List[Dict[str, Any]]:
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
        _init_retrieval_feedback_table(conn)
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


def _resolve_bookmark_target(
    cursor: sqlite3.Cursor,
    session_id: str,
    *,
    message_id: Optional[int],
    panel_id: str,
    answer_group_id: str,
    role: str,
) -> Optional[Dict[str, Any]]:
    normalized_role = _normalize_bookmark_role(role)
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
        "content": _normalize_content(row[2]),
        "model_id": str(row[3] or ""),
        "panel_id": str(row[4] or ""),
        "answer_group_id": str(row[5] or ""),
    }


def get_bookmark(
    bookmark_id: str, db_path: str | None = None
) -> Optional[Dict[str, Any]]:
    normalized_bookmark_id = str(bookmark_id or "").strip()
    if not normalized_bookmark_id:
        return None

    with connect_sqlite(db_path) as conn:
        _init_sessions_table(conn)
        _init_bookmarks_table(conn)
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
        return _row_to_bookmark(row) if row else None


def list_bookmarks(
    *,
    session_id: Optional[str] = None,
    db_path: str | None = None,
) -> List[Dict[str, Any]]:
    with connect_sqlite(db_path) as conn:
        _init_sessions_table(conn)
        _init_bookmarks_table(conn)
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
        params: List[Any] = []
        normalized_session_id = str(session_id or "").strip()
        if normalized_session_id:
            sql += " WHERE b.session_id = ?"
            params.append(normalized_session_id)

        sql += " ORDER BY b.updated_at DESC, b.created_at DESC, b.id DESC"
        cursor.execute(sql, tuple(params))
        return [_row_to_bookmark(row) for row in cursor.fetchall()]


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
) -> Optional[Dict[str, Any]]:
    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        raise ValueError("必须提供 session_id")

    normalized_role = _normalize_bookmark_role(role)
    normalized_content = str(content or "").strip()
    normalized_model_id = str(model_id or "").strip()
    normalized_session_title = str(session_title or "").strip()
    now = time.time()

    with connect_sqlite(db_path) as conn:
        _init_sessions_table(conn)
        _init_messages_table(conn)
        _init_bookmarks_table(conn)
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
        _init_bookmarks_table(conn)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bookmarks WHERE id = ?", (normalized_bookmark_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted


def list_session_memory(
    session_id: str,
    *,
    kind: Optional[str] = None,
    limit: Optional[int] = None,
    newest_first: bool = False,
    db_path: str | None = None,
) -> List[Dict[str, Any]]:
    if _should_use_postgres_store(db_path):
        return _session_memory_store().list_session_memory(
            session_id,
            kind=kind,
            limit=limit,
            newest_first=newest_first,
        )

    with connect_sqlite(db_path) as conn:
        _init_sessions_table(conn)
        _init_session_memory_table(conn)
        cursor = conn.cursor()

        sql = """
            SELECT id, session_id, kind, content, COALESCE(meta_json, '{}'), created_at, updated_at
            FROM session_memory
            WHERE session_id = ?
        """
        params: List[Any] = [session_id]

        if kind is not None:
            sql += " AND kind = ?"
            params.append(_normalize_session_memory_kind(kind))

        if limit is not None and limit > 0:
            sql += "\nORDER BY updated_at DESC, created_at DESC, id DESC\nLIMIT ?"
            params.append(limit)
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            if not newest_first:
                rows.reverse()
        else:
            direction = "DESC" if newest_first else "ASC"
            sql += f"\nORDER BY updated_at {direction}, created_at {direction}, id {direction}"
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()

        return [_row_to_session_memory(row) for row in rows]


def create_session_memory(
    session_id: str,
    *,
    kind: str,
    content: Any,
    meta: Optional[Dict[str, Any]] = None,
    db_path: str | None = None,
) -> Optional[Dict[str, Any]]:
    if _should_use_postgres_store(db_path):
        return _session_memory_store().create_session_memory(
            session_id,
            kind=kind,
            content=content,
            meta=meta,
        )

    normalized_kind = _normalize_session_memory_kind(kind)
    normalized_content = _normalize_session_memory_content(content)
    normalized_meta = _normalize_session_memory_meta(meta)
    now = time.time()
    memory_id = str(uuid.uuid4())

    with connect_sqlite(db_path) as conn:
        _init_sessions_table(conn)
        _init_session_memory_table(conn)
        cursor = conn.cursor()

        if not _session_exists(cursor, session_id):
            return None

        cursor.execute(
            """
            INSERT INTO session_memory (
                id, session_id, kind, content, meta_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                memory_id,
                session_id,
                normalized_kind,
                normalized_content,
                json.dumps(normalized_meta, ensure_ascii=False),
                now,
                now,
            ),
        )
        cursor.execute(
            "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
            (now, session_id),
        )
        conn.commit()

    return {
        "id": memory_id,
        "session_id": session_id,
        "kind": normalized_kind,
        "content": normalized_content,
        "meta": normalized_meta,
        "created_at": now,
        "updated_at": now,
    }


def pin_session_memory(
    session_id: str,
    *,
    content: Any,
    kind: str = "fact",
    meta: Optional[Dict[str, Any]] = None,
    db_path: str | None = None,
) -> Optional[Dict[str, Any]]:
    if _should_use_postgres_store(db_path):
        return _session_memory_store().pin_session_memory(
            session_id,
            content=content,
            kind=kind,
            meta=meta,
        )

    normalized_kind = _normalize_session_memory_kind(kind)
    normalized_content = _normalize_session_memory_content(content)
    normalized_meta = _normalize_session_memory_meta(meta)
    now = time.time()

    with connect_sqlite(db_path) as conn:
        _init_sessions_table(conn)
        _init_session_memory_table(conn)
        cursor = conn.cursor()

        if not _session_exists(cursor, session_id):
            return None

        cursor.execute(
            """
            SELECT id, session_id, kind, content, COALESCE(meta_json, '{}'), created_at, updated_at
            FROM session_memory
            WHERE session_id = ?
              AND kind = ?
              AND content = ?
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 1
            """,
            (session_id, normalized_kind, normalized_content),
        )
        existing_row = cursor.fetchone()

        if existing_row:
            existing_meta = _normalize_session_memory_meta(
                _parse_json_object(existing_row[4])
            )
            merged_meta = (
                {**existing_meta, **normalized_meta}
                if normalized_meta
                else existing_meta
            )
            cursor.execute(
                "UPDATE session_memory SET meta_json = ?, updated_at = ? WHERE id = ?",
                (
                    json.dumps(merged_meta, ensure_ascii=False),
                    now,
                    existing_row[0],
                ),
            )
            cursor.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )
            conn.commit()
            return {
                "created": False,
                "memory": {
                    **_row_to_session_memory(existing_row),
                    "meta": merged_meta,
                    "updated_at": now,
                },
            }

    created_memory = create_session_memory(
        session_id,
        kind=normalized_kind,
        content=normalized_content,
        meta=normalized_meta,
        db_path=db_path,
    )
    if not created_memory:
        return None

    return {
        "created": True,
        "memory": created_memory,
    }


def update_session_memory(
    session_id: str,
    memory_id: str,
    *,
    content: Any = _UNSET,
    kind: Any = _UNSET,
    meta: Any = _UNSET,
    db_path: str | None = None,
) -> Optional[Dict[str, Any]]:
    if _should_use_postgres_store(db_path):
        return _session_memory_store().update_session_memory(
            session_id,
            memory_id,
            content=None if content is _UNSET else content,
            kind=None if kind is _UNSET else kind,
            meta=None if meta is _UNSET else meta,
            update_content=content is not _UNSET,
            update_kind=kind is not _UNSET,
            update_meta=meta is not _UNSET,
        )

    with connect_sqlite(db_path) as conn:
        _init_sessions_table(conn)
        _init_session_memory_table(conn)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, session_id, kind, content, COALESCE(meta_json, '{}'), created_at, updated_at
            FROM session_memory
            WHERE session_id = ? AND id = ?
            """,
            (session_id, memory_id),
        )
        existing_row = cursor.fetchone()
        if not existing_row:
            return None

        updates: List[str] = []
        params: List[Any] = []

        if content is not _UNSET:
            updates.append("content = ?")
            params.append(_normalize_session_memory_content(content))

        if kind is not _UNSET:
            updates.append("kind = ?")
            params.append(_normalize_session_memory_kind(kind))

        if meta is not _UNSET:
            updates.append("meta_json = ?")
            params.append(
                json.dumps(_normalize_session_memory_meta(meta), ensure_ascii=False)
            )

        if not updates:
            return _row_to_session_memory(existing_row)

        now = time.time()
        updates.append("updated_at = ?")
        params.append(now)
        params.append(session_id)
        params.append(memory_id)

        cursor.execute(
            f"UPDATE session_memory SET {', '.join(updates)} WHERE session_id = ? AND id = ?",
            tuple(params),
        )
        cursor.execute(
            "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
            (now, session_id),
        )
        conn.commit()

        cursor.execute(
            """
            SELECT id, session_id, kind, content, COALESCE(meta_json, '{}'), created_at, updated_at
            FROM session_memory
            WHERE session_id = ? AND id = ?
            """,
            (session_id, memory_id),
        )
        updated_row = cursor.fetchone()
        return _row_to_session_memory(updated_row) if updated_row else None


def delete_session_memory(
    session_id: str,
    memory_id: str,
    *,
    db_path: str | None = None,
) -> bool:
    if _should_use_postgres_store(db_path):
        return _session_memory_store().delete_session_memory(session_id, memory_id)

    with connect_sqlite(db_path) as conn:
        _init_session_memory_table(conn)
        cursor = conn.cursor()
        cursor.execute(
            """
            DELETE FROM session_memory
            WHERE session_id = ? AND id = ?
            """,
            (session_id, memory_id),
        )
        deleted = cursor.rowcount > 0
        if deleted:
            cursor.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (time.time(), session_id),
            )
        conn.commit()
        return deleted


def clear_session_memory(
    session_id: str,
    *,
    db_path: str | None = None,
) -> None:
    if _should_use_postgres_store(db_path):
        _session_memory_store().clear_session_memory(session_id)
        return

    with connect_sqlite(db_path) as conn:
        _init_session_memory_table(conn)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM session_memory WHERE session_id = ?",
            (session_id,),
        )
        cursor.execute(
            "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
            (time.time(), session_id),
        )
        conn.commit()


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


# ── System Prompt CRUD ────────────────────────────────────────────────────────


def _ensure_prompts_init(db_path: str = DB_PATH) -> None:
    with connect_sqlite(db_path) as conn:
        _init_system_prompts_table(conn)


def replace_session_panels(
    session_id: str,
    panel_configs: List[Dict[str, Any]],
    db_path: str = DB_PATH,
) -> None:
    if _should_use_postgres_store(db_path):
        _session_memory_store().replace_session_panels(session_id, panel_configs)
        return

    with connect_sqlite(db_path) as conn:
        _init_session_panels_table(conn)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM session_panels WHERE session_id = ?", (session_id,))

        now = time.time()
        for index, panel in enumerate(panel_configs):
            panel_id = str(panel.get("panel_id") or "").strip()
            if not panel_id:
                continue
            cursor.execute(
                """
                INSERT INTO session_panels (
                    session_id, panel_id, provider, connection_type, model, base_url, api_key_ref,
                    temperature, agent_mode, display_order, is_primary, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    panel_id,
                    str(panel.get("provider") or "ollama"),
                    str(panel.get("connection_type") or panel.get("provider") or ""),
                    str(panel.get("model") or ""),
                    str(panel.get("base_url") or ""),
                    str(panel.get("api_key_ref") or ""),
                    float(panel.get("temperature") or 0.3),
                    str(panel.get("agent_mode") or "auto"),
                    index,
                    1 if index == 0 else 0,
                    now,
                    now,
                ),
            )

        conn.commit()


def upsert_session_panel(
    session_id: str,
    panel_config: Dict[str, Any],
    db_path: str = DB_PATH,
) -> None:
    if _should_use_postgres_store(db_path):
        _session_memory_store().upsert_session_panel(session_id, panel_config)
        return

    with connect_sqlite(db_path) as conn:
        _init_session_panels_table(conn)
        cursor = conn.cursor()

        panel_id = str(panel_config.get("panel_id") or "").strip()
        if not panel_id:
            return

        now = time.time()
        cursor.execute(
            """
            SELECT COALESCE(MAX(display_order), -1)
            FROM session_panels
            WHERE session_id = ?
            """,
            (session_id,),
        )
        max_display_order = int(cursor.fetchone()[0] or -1)

        cursor.execute(
            """
            SELECT display_order
            FROM session_panels
            WHERE session_id = ? AND panel_id = ?
            """,
            (session_id, panel_id),
        )
        existing_row = cursor.fetchone()
        display_order = int(existing_row[0]) if existing_row else max_display_order + 1

        cursor.execute(
            """
            INSERT INTO session_panels (
                session_id, panel_id, provider, connection_type, model, base_url, api_key_ref,
                temperature, agent_mode, display_order, is_primary, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id, panel_id) DO UPDATE SET
                provider = excluded.provider,
                connection_type = excluded.connection_type,
                model = excluded.model,
                base_url = excluded.base_url,
                api_key_ref = excluded.api_key_ref,
                temperature = excluded.temperature,
                agent_mode = excluded.agent_mode,
                updated_at = excluded.updated_at
            """,
            (
                session_id,
                panel_id,
                str(panel_config.get("provider") or "ollama"),
                str(
                    panel_config.get("connection_type")
                    or panel_config.get("provider")
                    or ""
                ),
                str(panel_config.get("model") or ""),
                str(panel_config.get("base_url") or ""),
                str(panel_config.get("api_key_ref") or ""),
                float(panel_config.get("temperature") or 0.3),
                str(panel_config.get("agent_mode") or "auto"),
                display_order,
                1 if display_order == 0 else 0,
                now,
                now,
            ),
        )
        conn.commit()


def get_session_panels(session_id: str, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    if _should_use_postgres_store(db_path):
        return _session_memory_store().get_session_panels(session_id)

    with connect_sqlite(db_path) as conn:
        _init_session_panels_table(conn)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                panel_id,
                provider,
                connection_type,
                model,
                base_url,
                api_key_ref,
                temperature,
                agent_mode,
                is_primary,
                display_order
            FROM session_panels
            WHERE session_id = ?
            ORDER BY display_order ASC, updated_at ASC
            """,
            (session_id,),
        )

        panels: List[Dict[str, Any]] = []
        for row in cursor.fetchall():
            panels.append(
                {
                    "panel_id": row[0],
                    "is_primary": bool(row[8]),
                    "display_order": int(row[9] or 0),
                    "model_config": {
                        "panel_id": row[0],
                        "provider": row[1] or row[2] or "ollama",
                        "connection_type": row[2] or row[1] or "ollama",
                        "model": row[3] or "",
                        "base_url": row[4] or "",
                        "api_key": "",
                        "api_key_ref": row[5] or "",
                        "temperature": float(row[6] or 0.3),
                        "agent_mode": row[7] or "auto",
                    },
                }
            )
        return panels


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


def get_all_system_prompts(db_path: str = DB_PATH) -> List[Dict]:
    _ensure_prompts_init(db_path)
    with connect_sqlite(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, content, is_default, is_active, created_at, updated_at, vector_store_id, dashboard_template "
            "FROM system_prompts ORDER BY created_at ASC"
        )
        return [_row_to_prompt(r) for r in cursor.fetchall()]


def get_active_system_prompt(db_path: str = DB_PATH) -> Optional[Dict]:
    _ensure_prompts_init(db_path)
    with connect_sqlite(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, content, is_default, is_active, created_at, updated_at, vector_store_id, dashboard_template "
            "FROM system_prompts WHERE is_active = 1 LIMIT 1"
        )
        row = cursor.fetchone()
        return _row_to_prompt(row) if row else None


def create_system_prompt(
    name: str,
    content: str,
    db_path: str = DB_PATH,
    vector_store_id: str = "",
    dashboard_template: Optional[Dict[str, Any]] = None,
) -> Dict:
    _ensure_prompts_init(db_path)
    now = time.time()
    prompt_id = str(uuid.uuid4())
    dashboard_template_json = json.dumps(dashboard_template or {}, ensure_ascii=False)
    with connect_sqlite(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO system_prompts (id, name, content, is_default, is_active, created_at, updated_at, vector_store_id, dashboard_template) "
            "VALUES (?, ?, ?, 0, 0, ?, ?, ?, ?)",
            (
                prompt_id,
                name,
                content,
                now,
                now,
                vector_store_id,
                dashboard_template_json,
            ),
        )
        conn.commit()
    return {
        "id": prompt_id,
        "name": name,
        "content": content,
        "is_default": False,
        "is_active": False,
        "created_at": now,
        "updated_at": now,
        "vector_store_id": vector_store_id,
        "dashboard_template": dashboard_template or {},
    }


def update_system_prompt(
    prompt_id: str,
    name: str,
    content: str,
    db_path: str = DB_PATH,
    vector_store_id: str = "",
    dashboard_template: Optional[Dict[str, Any]] = None,
) -> Optional[Dict]:
    _ensure_prompts_init(db_path)
    now = time.time()
    dashboard_template_json = json.dumps(dashboard_template or {}, ensure_ascii=False)
    with connect_sqlite(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE system_prompts SET name = ?, content = ?, updated_at = ?, vector_store_id = ?, dashboard_template = ? WHERE id = ?",
            (name, content, now, vector_store_id, dashboard_template_json, prompt_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None
        cursor.execute(
            "SELECT id, name, content, is_default, is_active, created_at, updated_at, vector_store_id, dashboard_template "
            "FROM system_prompts WHERE id = ?",
            (prompt_id,),
        )
        row = cursor.fetchone()
        return _row_to_prompt(row) if row else None


def delete_system_prompt(prompt_id: str, db_path: str = DB_PATH) -> bool:
    _ensure_prompts_init(db_path)
    with connect_sqlite(db_path) as conn:
        cursor = conn.cursor()
        # Prevent deleting the only remaining prompt
        cursor.execute("SELECT COUNT(1) FROM system_prompts")
        if cursor.fetchone()[0] <= 1:
            return False
        cursor.execute("DELETE FROM system_prompts WHERE id = ?", (prompt_id,))
        conn.commit()
        if cursor.rowcount == 0:
            return False
        # If we deleted the active one, activate the first remaining
        cursor.execute("SELECT COUNT(1) FROM system_prompts WHERE is_active = 1")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "UPDATE system_prompts SET is_active = 1 WHERE id = (SELECT id FROM system_prompts LIMIT 1)"
            )
            conn.commit()
        return True


def activate_system_prompt(prompt_id: str, db_path: str = DB_PATH) -> bool:
    _ensure_prompts_init(db_path)
    with connect_sqlite(db_path) as conn:
        cursor = conn.cursor()
        # Check exists
        cursor.execute("SELECT id FROM system_prompts WHERE id = ?", (prompt_id,))
        if not cursor.fetchone():
            return False
        # Deactivate all, then activate target
        cursor.execute("UPDATE system_prompts SET is_active = 0")
        cursor.execute(
            "UPDATE system_prompts SET is_active = 1 WHERE id = ?", (prompt_id,)
        )
        conn.commit()
        return True


# ── Assistant Preset CRUD ───────────────────────────────────────────────────


def _ensure_assistant_presets_init(db_path: str = DB_PATH) -> None:
    with connect_sqlite(db_path) as conn:
        _init_assistant_presets_table(conn)


def get_all_assistant_presets(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    _ensure_assistant_presets_init(db_path)
    with connect_sqlite(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, name, avatar, system_prompt_id, default_model_config_json,
                   tool_config_json, starters_json, is_default, is_active, created_at, updated_at
            FROM assistant_presets
            ORDER BY is_default DESC, created_at ASC
            """
        )
        return [_row_to_assistant_preset(row) for row in cursor.fetchall()]


def get_active_assistant_preset(db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    _ensure_assistant_presets_init(db_path)
    with connect_sqlite(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, name, avatar, system_prompt_id, default_model_config_json,
                   tool_config_json, starters_json, is_default, is_active, created_at, updated_at
            FROM assistant_presets
            WHERE is_active = 1
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        return _row_to_assistant_preset(row) if row else None


def create_assistant_preset(
    name: str,
    db_path: str = DB_PATH,
    *,
    avatar: str = "",
    system_prompt_id: str = "",
    default_model_config: Optional[Dict[str, Any]] = None,
    tool_config: Optional[Dict[str, Any]] = None,
    starters: Optional[List[str]] = None,
) -> Dict[str, Any]:
    _ensure_assistant_presets_init(db_path)
    normalized_name = str(name or "").strip()
    if not normalized_name:
        raise ValueError("助手预设名称不能为空")
    now = time.time()
    preset_id = str(uuid.uuid4())
    normalized_model_config = _normalize_assistant_model_config(default_model_config)
    normalized_tool_config = _normalize_assistant_tool_config(tool_config)
    normalized_starters = _normalize_assistant_starters(starters)
    with connect_sqlite(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO assistant_presets (
                id, name, avatar, system_prompt_id, default_model_config_json,
                tool_config_json, starters_json, is_default, is_active, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?)
            """,
            (
                preset_id,
                normalized_name[:80],
                str(avatar or "").strip()[:16],
                str(system_prompt_id or "").strip(),
                json.dumps(normalized_model_config, ensure_ascii=False),
                json.dumps(normalized_tool_config, ensure_ascii=False),
                json.dumps(normalized_starters, ensure_ascii=False),
                now,
                now,
            ),
        )
        conn.commit()
    return {
        "id": preset_id,
        "name": normalized_name[:80],
        "avatar": str(avatar or "").strip()[:16],
        "system_prompt_id": str(system_prompt_id or "").strip(),
        "default_model_config": normalized_model_config,
        "tool_config": normalized_tool_config,
        "starters": normalized_starters,
        "is_default": False,
        "is_active": False,
        "created_at": now,
        "updated_at": now,
    }


def update_assistant_preset(
    preset_id: str,
    name: str,
    db_path: str = DB_PATH,
    *,
    avatar: str = "",
    system_prompt_id: str = "",
    default_model_config: Optional[Dict[str, Any]] = None,
    tool_config: Optional[Dict[str, Any]] = None,
    starters: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    _ensure_assistant_presets_init(db_path)
    normalized_name = str(name or "").strip()
    if not normalized_name:
        raise ValueError("助手预设名称不能为空")
    now = time.time()
    normalized_model_config = _normalize_assistant_model_config(default_model_config)
    normalized_tool_config = _normalize_assistant_tool_config(tool_config)
    normalized_starters = _normalize_assistant_starters(starters)
    with connect_sqlite(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE assistant_presets
            SET name = ?, avatar = ?, system_prompt_id = ?,
                default_model_config_json = ?, tool_config_json = ?,
                starters_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                normalized_name[:80],
                str(avatar or "").strip()[:16],
                str(system_prompt_id or "").strip(),
                json.dumps(normalized_model_config, ensure_ascii=False),
                json.dumps(normalized_tool_config, ensure_ascii=False),
                json.dumps(normalized_starters, ensure_ascii=False),
                now,
                preset_id,
            ),
        )
        if cursor.rowcount == 0:
            return None
        conn.commit()
    return next(
        (preset for preset in get_all_assistant_presets(db_path) if preset["id"] == preset_id),
        None,
    )


def delete_assistant_preset(preset_id: str, db_path: str = DB_PATH) -> bool:
    _ensure_assistant_presets_init(db_path)
    with connect_sqlite(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(1) FROM assistant_presets")
        if cursor.fetchone()[0] <= 1:
            return False
        cursor.execute("DELETE FROM assistant_presets WHERE id = ?", (preset_id,))
        if cursor.rowcount == 0:
            return False
        cursor.execute("SELECT COUNT(1) FROM assistant_presets WHERE is_active = 1")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                """
                UPDATE assistant_presets
                SET is_active = 1
                WHERE id = (
                    SELECT id FROM assistant_presets ORDER BY is_default DESC, created_at ASC LIMIT 1
                )
                """
            )
        conn.commit()
        return True


def activate_assistant_preset(preset_id: str, db_path: str = DB_PATH) -> bool:
    _ensure_assistant_presets_init(db_path)
    with connect_sqlite(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM assistant_presets WHERE id = ?", (preset_id,))
        if not cursor.fetchone():
            return False
        cursor.execute("UPDATE assistant_presets SET is_active = 0")
        cursor.execute(
            "UPDATE assistant_presets SET is_active = 1, updated_at = ? WHERE id = ?",
            (time.time(), preset_id),
        )
        conn.commit()
        return True
