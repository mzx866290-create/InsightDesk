"""Session panel persistence helpers for SQLite and PostgreSQL runtimes."""

from __future__ import annotations

import time
import sqlite3
from typing import TYPE_CHECKING, Any, Callable

from backend.core.storage_runtime import (
    DATABASE_PROVIDER_POSTGRES,
    app_database_path,
    database_provider,
)
from backend.stores.chat_schema import init_session_panels_table
from backend.stores.sqlite_runtime import connect_sqlite

if TYPE_CHECKING:
    from backend.stores.protocols import SessionMemoryStore

DB_PATH = app_database_path()


def _should_use_postgres_store(db_path: str | None = None) -> bool:
    normalized_db_path = str(db_path or "").strip()
    return database_provider() == DATABASE_PROVIDER_POSTGRES and normalized_db_path in {
        "",
        DB_PATH,
    }


def _session_memory_store() -> "SessionMemoryStore":
    from backend.stores.factory import create_session_memory_store

    return create_session_memory_store()


def replace_session_panels(
    session_id: str,
    panel_configs: list[dict[str, Any]],
    db_path: str = DB_PATH,
    *,
    connect_sqlite_fn: Callable[[str | None], sqlite3.Connection] = connect_sqlite,
) -> None:
    if _should_use_postgres_store(db_path):
        _session_memory_store().replace_session_panels(session_id, panel_configs)
        return

    with connect_sqlite_fn(db_path) as conn:
        init_session_panels_table(conn)
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
    panel_config: dict[str, Any],
    db_path: str = DB_PATH,
    *,
    connect_sqlite_fn: Callable[[str | None], sqlite3.Connection] = connect_sqlite,
) -> None:
    if _should_use_postgres_store(db_path):
        _session_memory_store().upsert_session_panel(session_id, panel_config)
        return

    with connect_sqlite_fn(db_path) as conn:
        init_session_panels_table(conn)
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


def get_session_panels(
    session_id: str,
    db_path: str = DB_PATH,
    *,
    connect_sqlite_fn: Callable[[str | None], sqlite3.Connection] = connect_sqlite,
) -> list[dict[str, Any]]:
    if _should_use_postgres_store(db_path):
        return _session_memory_store().get_session_panels(session_id)

    with connect_sqlite_fn(db_path) as conn:
        init_session_panels_table(conn)
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

        panels: list[dict[str, Any]] = []
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


__all__ = [
    "get_session_panels",
    "replace_session_panels",
    "upsert_session_panel",
]
