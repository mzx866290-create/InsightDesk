"""Row-to-payload mappers for chat persistence."""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.stores.chat_normalization import (
    DEFAULT_WORKSPACE_ID,
    normalize_assistant_model_config,
    normalize_assistant_starters,
    normalize_assistant_tool_config,
    normalize_bookmark_role,
    normalize_session_memory_meta,
    normalize_tags,
    normalize_workspace_color,
    normalize_workspace_display_name,
    normalize_workspace_output_preset,
    normalize_workspace_panel_configs,
    normalize_workspace_tool_config,
)
from backend.stores.chat_serialization import (
    parse_json_list,
    parse_json_object,
    parse_string_list,
)

logger = logging.getLogger(__name__)


def row_to_session(row: tuple[Any, ...]) -> dict[str, Any]:
    session = {
        "session_id": row[0],
        "title": row[1] or "新对话",
        "created_at": row[2],
        "updated_at": row[3],
        "message_count": row[4],
        "is_archived": bool(row[5]),
        "is_favorite": bool(row[6]),
        "is_pinned": bool(row[7]),
        "session_order": float(row[8] or 0),
        "tags": normalize_tags(parse_string_list(row[9])),
        "workspace_id": str(row[10] or DEFAULT_WORKSPACE_ID),
    }
    if len(row) > 11 and row[11]:
        session["search_preview"] = str(row[11])
    if len(row) > 12 and row[12]:
        session["search_source"] = str(row[12])
    return session


def row_to_workspace(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "workspace_id": str(row[0] or ""),
        "name": normalize_workspace_display_name(row[0], row[1]),
        "description": str(row[2] or ""),
        "color": normalize_workspace_color(row[3]),
        "preset": {
            "default_panels": normalize_workspace_panel_configs(
                parse_json_list(row[4])
            ),
            "tool_config": normalize_workspace_tool_config(parse_json_object(row[5])),
            "output_preset": normalize_workspace_output_preset(
                parse_json_object(row[6])
            ),
        },
        "is_active": bool(row[7]),
        "created_at": float(row[8] or 0),
        "updated_at": float(row[9] or 0),
        "session_count": int(row[10] or 0) if len(row) > 10 else 0,
    }


def row_to_session_memory(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "id": row[0],
        "session_id": row[1],
        "kind": row[2],
        "content": row[3],
        "meta": normalize_session_memory_meta(parse_json_object(row[4])),
        "created_at": float(row[5] or 0),
        "updated_at": float(row[6] or 0),
    }


def row_to_bookmark(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "id": str(row[0] or ""),
        "session_id": str(row[1] or ""),
        "message_id": int(row[2]) if row[2] is not None else None,
        "panel_id": str(row[3] or ""),
        "answer_group_id": str(row[4] or ""),
        "role": normalize_bookmark_role(row[5]),
        "content": str(row[6] or ""),
        "model_id": str(row[7] or ""),
        "session_title": str(row[8] or ""),
        "created_at": float(row[9] or 0),
        "updated_at": float(row[10] or 0),
    }


def row_to_prompt(row: tuple[Any, ...]) -> dict[str, Any]:
    raw_dashboard_template = row[8] if len(row) > 8 else ""
    dashboard_template: dict[str, Any] = {}
    if raw_dashboard_template:
        try:
            parsed = json.loads(raw_dashboard_template)
            if isinstance(parsed, dict):
                dashboard_template = parsed
        except json.JSONDecodeError:
            logger.warning(
                "Invalid dashboard_template JSON found in system_prompts row id=%s",
                row[0],
            )
    return {
        "id": row[0],
        "name": row[1],
        "content": row[2],
        "is_default": bool(row[3]),
        "is_active": bool(row[4]),
        "created_at": row[5],
        "updated_at": row[6],
        "vector_store_id": row[7] if len(row) > 7 else "",
        "dashboard_template": dashboard_template,
    }


def row_to_assistant_preset(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "id": row[0],
        "name": row[1],
        "avatar": row[2] or "",
        "system_prompt_id": row[3] or "",
        "default_model_config": normalize_assistant_model_config(
            parse_json_object(row[4])
        ),
        "tool_config": normalize_assistant_tool_config(parse_json_object(row[5])),
        "starters": normalize_assistant_starters(parse_string_list(row[6])),
        "is_default": bool(row[7]),
        "is_active": bool(row[8]),
        "created_at": row[9],
        "updated_at": row[10],
    }


__all__ = [
    "row_to_assistant_preset",
    "row_to_bookmark",
    "row_to_prompt",
    "row_to_session",
    "row_to_session_memory",
    "row_to_workspace",
]
