"""System prompt and assistant preset persistence for the SQLite runtime."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from typing import Any, Optional

from backend.core.storage_runtime import app_database_path
from backend.stores.chat_normalization import (
    DEFAULT_ASSISTANT_PRESET_ID,
    default_assistant_model_config,
    normalize_assistant_model_config,
    normalize_assistant_starters,
    normalize_assistant_tool_config,
)
from backend.stores.chat_rows import row_to_assistant_preset, row_to_prompt
from backend.stores.sqlite_runtime import connect_sqlite

logger = logging.getLogger(__name__)

DB_PATH = app_database_path()
DEFAULT_SYSTEM_PROMPT = (
    "你是一个企业知识库助手，可以查询内部文档和联网搜索。"
    "请根据用户问题选择合适的工具来回答，回答时请引用信息来源。"
)


def init_system_prompts_table(conn: sqlite3.Connection) -> None:
    """Ensure system_prompts table exists and has at least the built-in default."""

    cursor = conn.cursor()
    cursor.execute(
        """
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
        """
    )
    conn.commit()

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

    cursor.execute("SELECT COUNT(1) FROM system_prompts")
    if cursor.fetchone()[0] == 0:
        now = time.time()
        cursor.execute(
            """
            INSERT INTO system_prompts (id, name, content, is_default, is_active, created_at, updated_at)
            VALUES (?, ?, ?, 1, 1, ?, ?)
            """,
            ("builtin-default", "企业知识库助手", DEFAULT_SYSTEM_PROMPT, now, now),
        )
        conn.commit()
        logger.info("Seeded built-in default system prompt")


def init_assistant_presets_table(conn: sqlite3.Connection) -> None:
    """Ensure assistant preset storage exists and includes one safe default."""

    init_system_prompts_table(conn)
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
                json.dumps(default_assistant_model_config(), ensure_ascii=False),
                json.dumps(normalize_assistant_tool_config(), ensure_ascii=False),
                json.dumps(
                    ["总结这份材料", "检索知识库并给出出处"],
                    ensure_ascii=False,
                ),
                now,
                now,
            ),
        )
    conn.commit()


def _ensure_prompts_init(db_path: str = DB_PATH) -> None:
    with connect_sqlite(db_path) as conn:
        init_system_prompts_table(conn)


def _ensure_assistant_presets_init(db_path: str = DB_PATH) -> None:
    with connect_sqlite(db_path) as conn:
        init_assistant_presets_table(conn)


def get_all_system_prompts(db_path: str = DB_PATH) -> list[dict[str, Any]]:
    _ensure_prompts_init(db_path)
    with connect_sqlite(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, content, is_default, is_active, created_at, updated_at, vector_store_id, dashboard_template "
            "FROM system_prompts ORDER BY created_at ASC"
        )
        return [row_to_prompt(row) for row in cursor.fetchall()]


def get_active_system_prompt(db_path: str = DB_PATH) -> Optional[dict[str, Any]]:
    _ensure_prompts_init(db_path)
    with connect_sqlite(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, content, is_default, is_active, created_at, updated_at, vector_store_id, dashboard_template "
            "FROM system_prompts WHERE is_active = 1 LIMIT 1"
        )
        row = cursor.fetchone()
        return row_to_prompt(row) if row else None


def create_system_prompt(
    name: str,
    content: str,
    db_path: str = DB_PATH,
    vector_store_id: str = "",
    dashboard_template: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
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
    dashboard_template: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
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
        return row_to_prompt(row) if row else None


def delete_system_prompt(prompt_id: str, db_path: str = DB_PATH) -> bool:
    _ensure_prompts_init(db_path)
    with connect_sqlite(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(1) FROM system_prompts")
        if cursor.fetchone()[0] <= 1:
            return False
        cursor.execute("DELETE FROM system_prompts WHERE id = ?", (prompt_id,))
        conn.commit()
        if cursor.rowcount == 0:
            return False
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
        cursor.execute("SELECT id FROM system_prompts WHERE id = ?", (prompt_id,))
        if not cursor.fetchone():
            return False
        cursor.execute("UPDATE system_prompts SET is_active = 0")
        cursor.execute(
            "UPDATE system_prompts SET is_active = 1 WHERE id = ?", (prompt_id,)
        )
        conn.commit()
        return True


def get_all_assistant_presets(db_path: str = DB_PATH) -> list[dict[str, Any]]:
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
        return [row_to_assistant_preset(row) for row in cursor.fetchall()]


def get_active_assistant_preset(db_path: str = DB_PATH) -> Optional[dict[str, Any]]:
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
        return row_to_assistant_preset(row) if row else None


def create_assistant_preset(
    name: str,
    db_path: str = DB_PATH,
    *,
    avatar: str = "",
    system_prompt_id: str = "",
    default_model_config: Optional[dict[str, Any]] = None,
    tool_config: Optional[dict[str, Any]] = None,
    starters: Optional[list[str]] = None,
) -> dict[str, Any]:
    _ensure_assistant_presets_init(db_path)
    normalized_name = str(name or "").strip()
    if not normalized_name:
        raise ValueError("助手预设名称不能为空")
    now = time.time()
    preset_id = str(uuid.uuid4())
    normalized_model_config = normalize_assistant_model_config(default_model_config)
    normalized_tool_config = normalize_assistant_tool_config(tool_config)
    normalized_starters = normalize_assistant_starters(starters)
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
    default_model_config: Optional[dict[str, Any]] = None,
    tool_config: Optional[dict[str, Any]] = None,
    starters: Optional[list[str]] = None,
) -> Optional[dict[str, Any]]:
    _ensure_assistant_presets_init(db_path)
    normalized_name = str(name or "").strip()
    if not normalized_name:
        raise ValueError("助手预设名称不能为空")
    now = time.time()
    normalized_model_config = normalize_assistant_model_config(default_model_config)
    normalized_tool_config = normalize_assistant_tool_config(tool_config)
    normalized_starters = normalize_assistant_starters(starters)
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
        (
            preset
            for preset in get_all_assistant_presets(db_path)
            if preset["id"] == preset_id
        ),
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


__all__ = [
    "DEFAULT_SYSTEM_PROMPT",
    "activate_assistant_preset",
    "activate_system_prompt",
    "create_assistant_preset",
    "create_system_prompt",
    "delete_assistant_preset",
    "delete_system_prompt",
    "get_active_assistant_preset",
    "get_active_system_prompt",
    "get_all_assistant_presets",
    "get_all_system_prompts",
    "init_assistant_presets_table",
    "init_system_prompts_table",
    "update_assistant_preset",
    "update_system_prompt",
]
