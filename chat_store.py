"""
SQLite-based persistent chat message history
Implements LangChain's BaseChatMessageHistory interface
"""

import sqlite3
import time
import logging
import os
import uuid
from typing import List, Dict, Any, Optional
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

logger = logging.getLogger(__name__)

DB_PATH = "./chat_history.db"


def _env_int(name: str, default: int) -> int:
    """Read integer value from env with fallback."""
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


# Exported constant so api_server can return it to the frontend
CONTEXT_HISTORY_MESSAGES: int = _env_int("CONTEXT_HISTORY_MESSAGES", 16)

DEFAULT_SYSTEM_PROMPT = (
    "你是一个企业知识库助手，可以查询内部文档和联网搜索。"
    "请根据用户问题选择合适的工具来回答，回答时请引用信息来源。"
)


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
            updated_at REAL NOT NULL
        )
    """)
    conn.commit()
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


def _normalize_content(content: Any) -> str:
    """Convert LangChain message content to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
            else:
                parts.append(str(item))
        return "\n".join(p for p in parts if p).strip()
    return str(content)


class SQLiteChatMessageHistory(BaseChatMessageHistory):
    """
    SQLite-based chat message history that persists across service restarts.

    Implements LangChain's BaseChatMessageHistory interface.
    """

    def __init__(self, session_id: str, db_path: str = "./chat_history.db"):
        """
        Initialize SQLite chat history for a specific session.

        Args:
            session_id: Unique session identifier
            db_path: Path to SQLite database file
        """
        self.session_id = session_id
        self.db_path = db_path
        self._init_db()
        self._ensure_session_exists()

    def _init_db(self) -> None:
        """Initialize database schema if not exists."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    model_id TEXT DEFAULT ''
                )
            """)

            # 兼容旧版：自动添加 model_id 列
            existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(messages)")}
            if "model_id" not in existing_cols:
                cursor.execute("ALTER TABLE messages ADD COLUMN model_id TEXT DEFAULT ''")
                logger.info("Migrated messages table: added 'model_id' column")

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session 
                ON messages(session_id)
            """)

            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    title TEXT DEFAULT ''
                )
            """)

            # 兼容旧版数据库：如果 title 列不存在则自动添加
            existing_columns = {row[1] for row in cursor.execute("PRAGMA table_info(sessions)")}
            if "title" not in existing_columns:
                cursor.execute("ALTER TABLE sessions ADD COLUMN title TEXT DEFAULT ''")
                logger.info("Migrated sessions table: added 'title' column")

            conn.commit()

            # System prompts table
            _init_system_prompts_table(conn)

    def _ensure_session_exists(self) -> None:
        """Ensure session record exists in sessions table."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT session_id FROM sessions WHERE session_id = ?",
                (self.session_id,),
            )

            if not cursor.fetchone():
                now = time.time()
                cursor.execute(
                    """
                    INSERT INTO sessions (session_id, created_at, updated_at, title)
                    VALUES (?, ?, ?, ?)
                    """,
                    (self.session_id, now, now, ""),
                )
                conn.commit()
                logger.info("Created new session: %s", self.session_id)

    @property
    def messages(self) -> List[BaseMessage]:  # type: ignore[override]
        """
        Retrieve all messages for this session.

        Returns:
            List of BaseMessage objects ordered by timestamp
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT type, content FROM messages 
                WHERE session_id = ? 
                ORDER BY id ASC
                """,
                (self.session_id,),
            )

            messages = []
            rows = cursor.fetchall()

            # Context window governance: only expose latest N messages to the model
            context_limit = _env_int("CONTEXT_HISTORY_MESSAGES", 16)
            if context_limit > 0 and len(rows) > context_limit:
                rows = rows[-context_limit:]

            for msg_type, content in rows:
                if msg_type == "human":
                    messages.append(HumanMessage(content=content))
                elif msg_type == "ai":
                    messages.append(AIMessage(content=content))
                elif msg_type == "system":
                    messages.append(SystemMessage(content=content))

            return messages

    def add_message(self, message: BaseMessage, model_id: str = "") -> None:
        """
        Add a message to the session history.

        Args:
            message: Message to add (HumanMessage, AIMessage, or SystemMessage)
            model_id: Optional model identifier (for multi-model sessions)
        """
        if isinstance(message, HumanMessage):
            msg_type = "human"
        elif isinstance(message, AIMessage):
            msg_type = "ai"
        elif isinstance(message, SystemMessage):
            msg_type = "system"
        else:
            msg_type = "unknown"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            content_text = _normalize_content(message.content)

            # Insert message
            cursor.execute(
                """
                INSERT INTO messages (session_id, type, content, timestamp, model_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (self.session_id, msg_type, content_text, time.time(), model_id),
            )

            # Update session timestamp and auto-generate title from first user message
            cursor.execute(
                "SELECT title FROM sessions WHERE session_id = ?", (self.session_id,)
            )
            row = cursor.fetchone()
            current_title = row[0] if row else ""

            # Auto-generate title from first human message if empty
            if not current_title and msg_type == "human":
                # Use first 50 chars of first user message as title
                title = content_text[:50].strip()
                if len(content_text) > 50:
                    title += "..."

                cursor.execute(
                    "UPDATE sessions SET updated_at = ?, title = ? WHERE session_id = ?",
                    (time.time(), title, self.session_id),
                )
            else:
                cursor.execute(
                    "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                    (time.time(), self.session_id),
                )

            # Storage governance: cap total persisted messages per session
            max_messages = _env_int("MAX_HISTORY_MESSAGES", 200)
            if max_messages > 0:
                cursor.execute(
                    "SELECT COUNT(1) FROM messages WHERE session_id = ?",
                    (self.session_id,),
                )
                total = int(cursor.fetchone()[0])
                overflow = total - max_messages
                if overflow > 0:
                    cursor.execute(
                        """
                        DELETE FROM messages
                        WHERE id IN (
                            SELECT id FROM messages
                            WHERE session_id = ?
                            ORDER BY id ASC
                            LIMIT ?
                        )
                        """,
                        (self.session_id, overflow),
                    )
                    logger.info(
                        "Pruned session history session_id=%s removed=%d kept=%d",
                        self.session_id,
                        overflow,
                        max_messages,
                    )

            conn.commit()

    def clear(self) -> None:
        """Clear all messages for this session."""
        with sqlite3.connect(self.db_path) as conn:
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


def get_all_sessions(db_path: str = "./chat_history.db") -> List[Dict]:
    """
    Get all sessions sorted by most recently updated.

    Args:
        db_path: Path to SQLite database file

    Returns:
        List of session dicts with keys: session_id, title, created_at, updated_at, message_count
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # 确保表存在（数据库文件为空时自动建表）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp REAL NOT NULL,
                model_id TEXT DEFAULT ''
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_session ON messages(session_id)
        """)
        existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(messages)")}
        if "model_id" not in existing_cols:
            cursor.execute("ALTER TABLE messages ADD COLUMN model_id TEXT DEFAULT ''")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                title TEXT DEFAULT ''
            )
        """)
        existing_columns = {row[1] for row in cursor.execute("PRAGMA table_info(sessions)")}
        if "title" not in existing_columns:
            cursor.execute("ALTER TABLE sessions ADD COLUMN title TEXT DEFAULT ''")
        conn.commit()

        cursor.execute("""
            SELECT 
                s.session_id,
                s.title,
                s.created_at,
                s.updated_at,
                COUNT(m.id) as message_count
            FROM sessions s
            LEFT JOIN messages m ON s.session_id = m.session_id
            GROUP BY s.session_id
            ORDER BY s.updated_at DESC
        """)

        sessions = []
        for row in cursor.fetchall():
            sessions.append(
                {
                    "session_id": row[0],
                    "title": row[1] or "新对话",
                    "created_at": row[2],
                    "updated_at": row[3],
                    "message_count": row[4],
                }
            )

        return sessions


def delete_session(session_id: str, db_path: str = "./chat_history.db") -> None:
    """
    Delete a session and all its messages.

    Args:
        session_id: Session ID to delete
        db_path: Path to SQLite database file
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Delete messages
        cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))

        # Delete session
        cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

        conn.commit()
        logger.info("Deleted session: %s", session_id)


# ── System Prompt CRUD ────────────────────────────────────────────────────────


def _row_to_prompt(row: tuple) -> Dict:
    return {
        "id": row[0],
        "name": row[1],
        "content": row[2],
        "is_default": bool(row[3]),
        "is_active": bool(row[4]),
        "created_at": row[5],
        "updated_at": row[6],
    }


def _ensure_prompts_init(db_path: str = DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        _init_system_prompts_table(conn)


def get_all_system_prompts(db_path: str = DB_PATH) -> List[Dict]:
    _ensure_prompts_init(db_path)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, content, is_default, is_active, created_at, updated_at "
            "FROM system_prompts ORDER BY created_at ASC"
        )
        return [_row_to_prompt(r) for r in cursor.fetchall()]


def get_active_system_prompt(db_path: str = DB_PATH) -> Optional[Dict]:
    _ensure_prompts_init(db_path)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, content, is_default, is_active, created_at, updated_at "
            "FROM system_prompts WHERE is_active = 1 LIMIT 1"
        )
        row = cursor.fetchone()
        return _row_to_prompt(row) if row else None


def create_system_prompt(name: str, content: str, db_path: str = DB_PATH) -> Dict:
    _ensure_prompts_init(db_path)
    now = time.time()
    prompt_id = str(uuid.uuid4())
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO system_prompts (id, name, content, is_default, is_active, created_at, updated_at) "
            "VALUES (?, ?, ?, 0, 0, ?, ?)",
            (prompt_id, name, content, now, now),
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
    }


def update_system_prompt(prompt_id: str, name: str, content: str, db_path: str = DB_PATH) -> Optional[Dict]:
    _ensure_prompts_init(db_path)
    now = time.time()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE system_prompts SET name = ?, content = ?, updated_at = ? WHERE id = ?",
            (name, content, now, prompt_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None
        cursor.execute(
            "SELECT id, name, content, is_default, is_active, created_at, updated_at "
            "FROM system_prompts WHERE id = ?",
            (prompt_id,),
        )
        row = cursor.fetchone()
        return _row_to_prompt(row) if row else None


def delete_system_prompt(prompt_id: str, db_path: str = DB_PATH) -> bool:
    _ensure_prompts_init(db_path)
    with sqlite3.connect(db_path) as conn:
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
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        # Check exists
        cursor.execute("SELECT id FROM system_prompts WHERE id = ?", (prompt_id,))
        if not cursor.fetchone():
            return False
        # Deactivate all, then activate target
        cursor.execute("UPDATE system_prompts SET is_active = 0")
        cursor.execute("UPDATE system_prompts SET is_active = 1 WHERE id = ?", (prompt_id,))
        conn.commit()
        return True
