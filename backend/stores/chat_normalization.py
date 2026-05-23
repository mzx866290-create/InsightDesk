"""Shared normalization helpers for chat persistence models."""

from __future__ import annotations

import json
from typing import Any

from backend.stores.chat_serialization import normalize_content

DEFAULT_WORKSPACE_ID = "workspace-default"
DEFAULT_WORKSPACE_NAME = "默认工作区"
DEFAULT_ASSISTANT_PRESET_ID = "assistant-preset-default"
WORKSPACE_COLOR_CHOICES = {"slate", "blue", "green", "amber", "rose"}
WORKSPACE_DECK_THEME_CHOICES = {"default", "midnight", "sunrise"}


def normalize_workspace_display_name(workspace_id: Any, name: Any) -> str:
    normalized_name = str(name or "").strip()
    if workspace_id == DEFAULT_WORKSPACE_ID and (
        not normalized_name or normalized_name == "Default Workspace"
    ):
        return DEFAULT_WORKSPACE_NAME
    return normalized_name or DEFAULT_WORKSPACE_NAME


def normalize_tags(tags: list[str] | None = None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for raw_tag in tags or []:
        if not isinstance(raw_tag, str):
            continue
        tag = raw_tag.strip()
        if not tag:
            continue
        tag = tag[:20]
        tag_key = tag.lower()
        if tag_key in seen:
            continue
        seen.add(tag_key)
        normalized.append(tag)
        if len(normalized) >= 8:
            break

    return normalized


def normalize_workspace_name(name: Any) -> str:
    normalized = str(name or "").strip()
    if not normalized:
        raise ValueError("工作区名称不能为空")
    return normalized[:60]


def normalize_workspace_description(description: Any = None) -> str:
    normalized = str(description or "").strip()
    if len(normalized) <= 280:
        return normalized
    return normalized[:277].rstrip() + "..."


def normalize_workspace_color(color: Any = None) -> str:
    normalized = str(color or "blue").strip().lower() or "blue"
    if normalized not in WORKSPACE_COLOR_CHOICES:
        return "blue"
    return normalized


def normalize_workspace_panel_configs(value: Any = None) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    normalized_configs: list[dict[str, Any]] = []
    seen_panel_ids: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        panel_id = (
            str(item.get("panel_id") or "").strip() or f"panel-preset-{index + 1}"
        )
        if panel_id in seen_panel_ids:
            continue
        seen_panel_ids.add(panel_id)

        provider = str(
            item.get("provider") or item.get("connection_type") or "ollama"
        ).strip()
        connection_type = str(
            item.get("connection_type") or item.get("provider") or provider or "ollama"
        ).strip()
        try:
            temperature = float(item.get("temperature") or 0.3)
        except (TypeError, ValueError):
            temperature = 0.3
        temperature = max(0.0, min(2.0, temperature))
        agent_mode = str(item.get("agent_mode") or "auto").strip().lower() or "auto"
        if agent_mode not in {"auto", "langgraph", "function_calling", "plain_chat"}:
            agent_mode = "auto"

        normalized_configs.append(
            {
                "panel_id": panel_id,
                "provider": provider or "ollama",
                "connection_type": connection_type or "ollama",
                "model": str(item.get("model") or "").strip(),
                "base_url": str(item.get("base_url") or "").strip(),
                "api_key": "",
                "api_key_ref": str(item.get("api_key_ref") or "").strip(),
                "temperature": temperature,
                "agent_mode": agent_mode,
            }
        )

    return normalized_configs[:6]


def normalize_workspace_tool_config(value: Any = None) -> dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    raw_servers = payload.get("mcp_servers_enabled")
    if isinstance(raw_servers, list):
        mcp_servers_enabled = []
        seen_servers: set[str] = set()
        for item in raw_servers:
            server_name = str(item or "").strip()
            if not server_name or server_name in seen_servers:
                continue
            mcp_servers_enabled.append(server_name)
            seen_servers.add(server_name)
    else:
        mcp_servers_enabled = []
    return {
        "web_search_enabled": bool(payload.get("web_search_enabled", False)),
        "knowledge_base_enabled": bool(payload.get("knowledge_base_enabled", True)),
        "mcp_servers_enabled": mcp_servers_enabled,
    }


def normalize_workspace_output_preset(value: Any = None) -> dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    deck_theme = (
        str(payload.get("deck_theme") or "default").strip().lower() or "default"
    )
    if deck_theme not in WORKSPACE_DECK_THEME_CHOICES:
        deck_theme = "default"
    try:
        target_slide_count = int(payload.get("target_slide_count") or 8)
    except (TypeError, ValueError):
        target_slide_count = 8
    target_slide_count = max(4, min(10, target_slide_count))
    return {
        "deck_theme": deck_theme,
        "target_slide_count": target_slide_count,
    }


def default_assistant_model_config() -> dict[str, Any]:
    return {
        "panel_id": "assistant-preset-panel",
        "provider": "ollama",
        "connection_type": "ollama",
        "model": "qwen3.5-2B:latest",
        "base_url": "http://localhost:11434",
        "api_key": "",
        "api_key_ref": "",
        "temperature": 0.3,
        "agent_mode": "auto",
    }


def normalize_assistant_model_config(value: Any = None) -> dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    normalized = normalize_workspace_panel_configs(
        [{**default_assistant_model_config(), **payload}]
    )
    return normalized[0] if normalized else default_assistant_model_config()


def normalize_assistant_tool_config(value: Any = None) -> dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    raw_servers = payload.get("mcp_servers_enabled")
    servers: list[str] = []
    if isinstance(raw_servers, list):
        seen_servers: set[str] = set()
        for item in raw_servers:
            server_name = str(item or "").strip()
            if not server_name or server_name in seen_servers:
                continue
            servers.append(server_name)
            seen_servers.add(server_name)
    return {
        "web_search_enabled": bool(payload.get("web_search_enabled", False)),
        "knowledge_base_enabled": bool(payload.get("knowledge_base_enabled", True)),
        "mcp_servers_enabled": servers,
    }


def normalize_assistant_starters(value: Any = None) -> list[str]:
    raw_items = value if isinstance(value, list) else []
    starters: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        starter = " ".join(str(item or "").strip().split())
        if not starter or starter in seen:
            continue
        starters.append(starter[:160])
        seen.add(starter)
        if len(starters) >= 8:
            break
    return starters


def normalize_message_feedback_value(value: Any = None) -> int:
    try:
        normalized = int(value or 0)
    except (TypeError, ValueError):
        raise ValueError("消息反馈值只能是 -1、0 或 1") from None
    if normalized not in {-1, 0, 1}:
        raise ValueError("消息反馈值只能是 -1、0 或 1")
    return normalized


def normalize_session_memory_kind(kind: str | None = None) -> str:
    normalized = str(kind or "fact").strip().lower() or "fact"
    if normalized not in {"summary", "fact", "decision", "todo"}:
        raise ValueError("不支持的会话记忆类型")
    return normalized


def normalize_session_memory_content(content: Any) -> str:
    normalized = normalize_content(content).strip()
    if not normalized:
        raise ValueError("会话记忆内容不能为空")
    if len(normalized) <= 2000:
        return normalized
    return normalized[:1997].rstrip() + "..."


def normalize_session_memory_meta(meta: Any = None) -> dict[str, Any]:
    if not isinstance(meta, dict):
        return {}
    try:
        normalized = json.loads(json.dumps(meta, ensure_ascii=False))
    except (TypeError, ValueError):
        return {}
    return normalized if isinstance(normalized, dict) else {}


def normalize_bookmark_role(role: Any) -> str:
    normalized = str(role or "").strip().lower()
    if normalized in {"user", "human"}:
        return "user"
    if normalized in {"assistant", "ai"}:
        return "assistant"
    raise ValueError("书签角色必须是 'user' 或 'assistant'")


__all__ = [
    "DEFAULT_ASSISTANT_PRESET_ID",
    "DEFAULT_WORKSPACE_ID",
    "DEFAULT_WORKSPACE_NAME",
    "WORKSPACE_COLOR_CHOICES",
    "WORKSPACE_DECK_THEME_CHOICES",
    "default_assistant_model_config",
    "normalize_assistant_model_config",
    "normalize_assistant_starters",
    "normalize_assistant_tool_config",
    "normalize_bookmark_role",
    "normalize_message_feedback_value",
    "normalize_session_memory_content",
    "normalize_session_memory_kind",
    "normalize_session_memory_meta",
    "normalize_tags",
    "normalize_workspace_color",
    "normalize_workspace_description",
    "normalize_workspace_display_name",
    "normalize_workspace_name",
    "normalize_workspace_output_preset",
    "normalize_workspace_panel_configs",
    "normalize_workspace_tool_config",
]
