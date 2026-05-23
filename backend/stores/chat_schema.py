"""SQLite schema helpers for chat persistence."""

from __future__ import annotations

import logging
import sqlite3
import time

from backend.stores.chat_normalization import (
    DEFAULT_WORKSPACE_ID,
    DEFAULT_WORKSPACE_NAME,
)

logger = logging.getLogger(__name__)


def init_workspaces_table(conn: sqlite3.Connection) -> None:
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


def init_sessions_table(conn: sqlite3.Connection) -> None:
    init_workspaces_table(conn)
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


def init_messages_table(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp REAL NOT NULL,
            model_id TEXT DEFAULT '',
            panel_id TEXT DEFAULT '',
            answer_group_id TEXT DEFAULT '',
            images_json TEXT DEFAULT '',
            files_json TEXT DEFAULT '',
            sources_json TEXT DEFAULT '',
            workflow_json TEXT DEFAULT '',
            token_usage_json TEXT DEFAULT '',
            task_id TEXT DEFAULT '',
            task_type TEXT DEFAULT '',
            feedback_value INTEGER DEFAULT 0
        )
    """)
    existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(messages)")}
    if "model_id" not in existing_cols:
        cursor.execute("ALTER TABLE messages ADD COLUMN model_id TEXT DEFAULT ''")
        logger.info("Migrated messages table: added 'model_id' column")
    if "panel_id" not in existing_cols:
        cursor.execute("ALTER TABLE messages ADD COLUMN panel_id TEXT DEFAULT ''")
        logger.info("Migrated messages table: added 'panel_id' column")
    if "answer_group_id" not in existing_cols:
        cursor.execute(
            "ALTER TABLE messages ADD COLUMN answer_group_id TEXT DEFAULT ''"
        )
        logger.info("Migrated messages table: added 'answer_group_id' column")
    if "images_json" not in existing_cols:
        cursor.execute("ALTER TABLE messages ADD COLUMN images_json TEXT DEFAULT ''")
        logger.info("Migrated messages table: added 'images_json' column")
    if "files_json" not in existing_cols:
        cursor.execute("ALTER TABLE messages ADD COLUMN files_json TEXT DEFAULT ''")
        logger.info("Migrated messages table: added 'files_json' column")
    if "sources_json" not in existing_cols:
        cursor.execute("ALTER TABLE messages ADD COLUMN sources_json TEXT DEFAULT ''")
        logger.info("Migrated messages table: added 'sources_json' column")
    if "workflow_json" not in existing_cols:
        cursor.execute("ALTER TABLE messages ADD COLUMN workflow_json TEXT DEFAULT ''")
        logger.info("Migrated messages table: added 'workflow_json' column")
    if "token_usage_json" not in existing_cols:
        cursor.execute("ALTER TABLE messages ADD COLUMN token_usage_json TEXT DEFAULT ''")
        logger.info("Migrated messages table: added 'token_usage_json' column")
    if "task_id" not in existing_cols:
        cursor.execute("ALTER TABLE messages ADD COLUMN task_id TEXT DEFAULT ''")
        logger.info("Migrated messages table: added 'task_id' column")
    if "task_type" not in existing_cols:
        cursor.execute("ALTER TABLE messages ADD COLUMN task_type TEXT DEFAULT ''")
        logger.info("Migrated messages table: added 'task_type' column")
    if "feedback_value" not in existing_cols:
        cursor.execute(
            "ALTER TABLE messages ADD COLUMN feedback_value INTEGER DEFAULT 0"
        )
        logger.info("Migrated messages table: added 'feedback_value' column")
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_session
        ON messages(session_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_session_panel
        ON messages(session_id, panel_id)
    """)
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_human_group
        ON messages(session_id, type, panel_id, answer_group_id)
        WHERE type = 'human' AND panel_id = '' AND answer_group_id <> ''
    """)
    init_message_search_table(conn)
    conn.commit()


def message_search_table_exists(cursor: sqlite3.Cursor) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = 'message_search'
        LIMIT 1
        """
    )
    return cursor.fetchone() is not None


def init_message_search_table(conn: sqlite3.Connection) -> bool:
    cursor = conn.cursor()
    table_existed = message_search_table_exists(cursor)
    try:
        cursor.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS message_search
            USING fts5(session_id UNINDEXED, content, tokenize = 'unicode61')
            """
        )
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS messages_ai_message_search
            AFTER INSERT ON messages
            BEGIN
                INSERT INTO message_search(rowid, session_id, content)
                VALUES (new.id, new.session_id, COALESCE(new.content, ''));
            END
            """
        )
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS messages_ad_message_search
            AFTER DELETE ON messages
            BEGIN
                DELETE FROM message_search WHERE rowid = old.id;
            END
            """
        )
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS messages_au_message_search
            AFTER UPDATE ON messages
            BEGIN
                DELETE FROM message_search WHERE rowid = old.id;
                INSERT INTO message_search(rowid, session_id, content)
                VALUES (new.id, new.session_id, COALESCE(new.content, ''));
            END
            """
        )
    except sqlite3.OperationalError as exc:
        logger.warning(
            "FTS5 message search unavailable, falling back to LIKE queries: %s", exc
        )
        return False

    if not table_existed:
        cursor.execute(
            """
            INSERT INTO message_search(rowid, session_id, content)
            SELECT id, session_id, COALESCE(content, '')
            FROM messages
            """
        )
    else:
        cursor.execute("SELECT COUNT(1) FROM message_search")
        indexed_count = int(cursor.fetchone()[0] or 0)
        cursor.execute("SELECT COUNT(1) FROM messages")
        message_count = int(cursor.fetchone()[0] or 0)
        if indexed_count == 0 and message_count > 0:
            cursor.execute(
                """
                INSERT INTO message_search(rowid, session_id, content)
                SELECT id, session_id, COALESCE(content, '')
                FROM messages
                """
            )
    return True


def init_session_memory_table(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS session_memory (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            content TEXT NOT NULL,
            meta_json TEXT DEFAULT '{}',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    existing_columns = {
        row[1] for row in cursor.execute("PRAGMA table_info(session_memory)")
    }
    if "meta_json" not in existing_columns:
        cursor.execute(
            "ALTER TABLE session_memory ADD COLUMN meta_json TEXT DEFAULT '{}'"
        )
        logger.info("Migrated session_memory table: added 'meta_json' column")
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_session_memory_session
        ON session_memory(session_id)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_session_memory_session_updated
        ON session_memory(session_id, updated_at DESC)
        """
    )
    conn.commit()


def init_session_panels_table(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS session_panels (
            session_id TEXT NOT NULL,
            panel_id TEXT NOT NULL,
            provider TEXT DEFAULT 'ollama',
            connection_type TEXT DEFAULT '',
            model TEXT DEFAULT '',
            base_url TEXT DEFAULT '',
            api_key_ref TEXT DEFAULT '',
            temperature REAL DEFAULT 0.3,
            agent_mode TEXT DEFAULT 'auto',
            display_order INTEGER DEFAULT 0,
            is_primary INTEGER DEFAULT 0,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (session_id, panel_id)
        )
    """)
    existing_columns = {
        row[1] for row in cursor.execute("PRAGMA table_info(session_panels)")
    }
    if "api_key_ref" not in existing_columns:
        cursor.execute(
            "ALTER TABLE session_panels ADD COLUMN api_key_ref TEXT DEFAULT ''"
        )
        logger.info("Migrated session_panels table: added 'api_key_ref' column")
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_session_panels_session
        ON session_panels(session_id, display_order)
    """)
    conn.commit()


def init_retrieval_feedback_table(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS retrieval_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            panel_id TEXT NOT NULL,
            answer_group_id TEXT NOT NULL,
            source_key TEXT NOT NULL,
            source_type TEXT DEFAULT '',
            source_title TEXT DEFAULT '',
            source_url TEXT DEFAULT '',
            feedback_value INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
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


def init_bookmarks_table(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS bookmarks (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            message_id INTEGER,
            panel_id TEXT DEFAULT '',
            answer_group_id TEXT DEFAULT '',
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            model_id TEXT DEFAULT '',
            session_title TEXT DEFAULT '',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_bookmarks_message
        ON bookmarks(session_id, message_id)
        WHERE message_id IS NOT NULL
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_bookmarks_updated
        ON bookmarks(updated_at DESC, created_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_bookmarks_session
        ON bookmarks(session_id, updated_at DESC)
        """
    )
    conn.commit()


__all__ = [
    "init_bookmarks_table",
    "init_message_search_table",
    "init_messages_table",
    "init_retrieval_feedback_table",
    "init_sessions_table",
    "init_session_memory_table",
    "init_session_panels_table",
    "init_workspaces_table",
    "message_search_table_exists",
]
