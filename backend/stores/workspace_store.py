"""Workspace persistence helpers for the SQLite chat runtime."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from typing import Any, Optional, cast

from backend.stores.chat_normalization import (
    DEFAULT_WORKSPACE_ID,
    DEFAULT_WORKSPACE_NAME,
    normalize_workspace_color,
    normalize_workspace_description,
    normalize_workspace_name,
    normalize_workspace_output_preset,
    normalize_workspace_panel_configs,
    normalize_workspace_tool_config,
)
from backend.stores.chat_rows import row_to_workspace
from backend.stores.chat_schema import init_sessions_table, init_workspaces_table
from backend.stores.sqlite_runtime import connect_sqlite


def workspace_exists(
    cursor: sqlite3.Cursor,
    workspace_id: str,
) -> bool:
    cursor.execute(
        "SELECT 1 FROM workspaces WHERE workspace_id = ?",
        (workspace_id,),
    )
    return cursor.fetchone() is not None


def get_active_workspace_id(cursor: sqlite3.Cursor) -> str:
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


def _fetch_workspace_row(
    cursor: sqlite3.Cursor,
    workspace_id: str,
) -> Optional[tuple[Any, ...]]:
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


def list_workspaces(
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    with connect_sqlite(db_path) as conn:
        init_workspaces_table(conn)
        init_sessions_table(conn)
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
        return [row_to_workspace(row) for row in cursor.fetchall()]


def get_workspace(
    workspace_id: str,
    db_path: str | None = None,
) -> Optional[dict[str, Any]]:
    normalized_workspace_id = str(workspace_id or "").strip()
    if not normalized_workspace_id:
        return None

    with connect_sqlite(db_path) as conn:
        init_workspaces_table(conn)
        init_sessions_table(conn)
        cursor = conn.cursor()
        row = _fetch_workspace_row(cursor, normalized_workspace_id)
        return row_to_workspace(row) if row else None


def create_workspace(
    name: str,
    *,
    description: str = "",
    color: str = "blue",
    default_panels: Optional[list[dict[str, Any]]] = None,
    tool_config: Optional[dict[str, Any]] = None,
    output_preset: Optional[dict[str, Any]] = None,
    activate: bool = True,
    db_path: str | None = None,
) -> dict[str, Any]:
    normalized_name = normalize_workspace_name(name)
    normalized_description = normalize_workspace_description(description)
    normalized_color = normalize_workspace_color(color)
    normalized_default_panels = normalize_workspace_panel_configs(default_panels)
    normalized_tool_config = normalize_workspace_tool_config(tool_config)
    normalized_output_preset = normalize_workspace_output_preset(output_preset)
    workspace_id = str(uuid.uuid4())
    now = time.time()

    with connect_sqlite(db_path) as conn:
        init_workspaces_table(conn)
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
    default_panels: Optional[list[dict[str, Any]]] = None,
    tool_config: Optional[dict[str, Any]] = None,
    output_preset: Optional[dict[str, Any]] = None,
    db_path: str | None = None,
) -> Optional[dict[str, Any]]:
    with connect_sqlite(db_path) as conn:
        init_workspaces_table(conn)
        cursor = conn.cursor()
        if not workspace_exists(cursor, workspace_id):
            return None

        updates: list[str] = []
        params: list[Any] = []

        if name is not None:
            updates.append("name = ?")
            params.append(normalize_workspace_name(name))
        if description is not None:
            updates.append("description = ?")
            params.append(normalize_workspace_description(description))
        if color is not None:
            updates.append("color = ?")
            params.append(normalize_workspace_color(color))
        if default_panels is not None:
            updates.append("default_panels_json = ?")
            params.append(
                json.dumps(
                    normalize_workspace_panel_configs(default_panels),
                    ensure_ascii=False,
                )
            )
        if tool_config is not None:
            updates.append("tool_config_json = ?")
            params.append(
                json.dumps(
                    normalize_workspace_tool_config(tool_config),
                    ensure_ascii=False,
                )
            )
        if output_preset is not None:
            updates.append("output_preset_json = ?")
            params.append(
                json.dumps(
                    normalize_workspace_output_preset(output_preset),
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
) -> Optional[dict[str, Any]]:
    with connect_sqlite(db_path) as conn:
        init_workspaces_table(conn)
        cursor = conn.cursor()
        if not workspace_exists(cursor, workspace_id):
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
) -> Optional[dict[str, Any]]:
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
        init_workspaces_table(conn)
        init_sessions_table(conn)
        cursor = conn.cursor()
        if not workspace_exists(cursor, normalized_workspace_id):
            return None
        if not workspace_exists(cursor, normalized_target_workspace_id):
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


__all__ = [
    "DEFAULT_WORKSPACE_ID",
    "DEFAULT_WORKSPACE_NAME",
    "activate_workspace",
    "create_workspace",
    "delete_workspace",
    "get_active_workspace_id",
    "get_workspace",
    "list_workspaces",
    "update_workspace",
    "workspace_exists",
]
