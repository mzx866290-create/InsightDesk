"""Built-in tool registry and enablement helpers for the agent runtime."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Literal, Optional

logger = logging.getLogger(__name__)

# 联网搜索开关（由上层 API / 前端在每次对话前设置）
_web_search_enabled: bool = True


@dataclass(frozen=True)
class BuiltinToolSpec:
    code: str
    name: str
    description: str
    category: Literal["knowledge_base", "web_search", "always"] = "always"


_BUILTIN_TOOL_REGISTRY: list[BuiltinToolSpec] = []


def register_builtin_tool(spec: BuiltinToolSpec) -> None:
    """Register a built-in tool declaration for routing and enablement."""
    if any(item.code == spec.code for item in _BUILTIN_TOOL_REGISTRY):
        raise ValueError(f"Tool code already registered: {spec.code}")
    if any(item.name == spec.name for item in _BUILTIN_TOOL_REGISTRY):
        raise ValueError(f"Tool name already registered: {spec.name}")
    _BUILTIN_TOOL_REGISTRY.append(spec)


def get_builtin_tool_registry() -> tuple[BuiltinToolSpec, ...]:
    return tuple(_BUILTIN_TOOL_REGISTRY)


def _parse_builtin_tool_name_list(raw_value: Any) -> list[str]:
    if isinstance(raw_value, str):
        candidates = raw_value.split(",")
    elif isinstance(raw_value, (list, tuple)):
        candidates = raw_value
    else:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        name = str(item or "").strip()
        if not name or name in seen:
            continue
        normalized.append(name)
        seen.add(name)
    return normalized


def _load_configured_builtin_tool_names() -> Optional[list[str]]:
    raw_names = os.getenv("ENABLED_BUILTIN_TOOLS")
    if raw_names is not None:
        return _parse_builtin_tool_name_list(raw_names)

    config_path = (os.getenv("BUILTIN_TOOL_CONFIG_PATH") or "").strip()
    if not config_path:
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        logger.warning("Builtin tool config file not found: %s", config_path)
        return None
    except json.JSONDecodeError:
        logger.warning("Builtin tool config file is not valid JSON: %s", config_path)
        return None
    except OSError:
        logger.warning("Builtin tool config file could not be read: %s", config_path)
        return None

    if isinstance(payload, dict):
        configured_names = payload.get("enabled_builtin_tools")
    else:
        configured_names = payload

    parsed_names = _parse_builtin_tool_name_list(configured_names)
    if configured_names is None:
        logger.warning(
            "Builtin tool config missing 'enabled_builtin_tools': %s",
            config_path,
        )
        return None
    return parsed_names


def list_enabled_builtin_tool_specs(
    *,
    knowledge_base_enabled: bool = True,
    web_search_enabled: bool = True,
) -> list[BuiltinToolSpec]:
    specs: list[BuiltinToolSpec] = []
    for spec in _BUILTIN_TOOL_REGISTRY:
        if spec.category == "knowledge_base" and not knowledge_base_enabled:
            continue
        if spec.category == "web_search" and not web_search_enabled:
            continue
        specs.append(spec)

    configured_names = _load_configured_builtin_tool_names()
    if configured_names is None:
        return specs

    specs_by_name = {spec.name: spec for spec in specs}
    configured_specs = [
        specs_by_name[name]
        for name in configured_names
        if name in specs_by_name
    ]
    unknown_names = [name for name in configured_names if name not in specs_by_name]
    if unknown_names:
        logger.warning("Ignoring unknown builtin tool names: %s", ", ".join(unknown_names))
    return configured_specs


def _build_enabled_tool_directory(
    tools_by_name: dict[str, Any],
    *,
    knowledge_base_enabled: bool,
    web_search_enabled: bool,
) -> tuple[dict[str, Any], list[str], str]:
    tools_dict: dict[str, Any] = {}
    tool_options = ["0 - 不需要工具（用于打招呼、闲聊、感谢等）"]

    for spec in list_enabled_builtin_tool_specs(
        knowledge_base_enabled=knowledge_base_enabled,
        web_search_enabled=web_search_enabled,
    ):
        tool_obj = tools_by_name.get(spec.name)
        if tool_obj is None:
            logger.warning("Tool declared but not instantiated: %s", spec.name)
            continue
        tools_dict[spec.code] = tool_obj
        tool_options.append(f"{spec.code} - {spec.description}")

    allowed_choices = "".join(sorted(tools_dict.keys()))
    return tools_dict, tool_options, allowed_choices


for _builtin_tool_spec in (
    BuiltinToolSpec(
        code="1",
        name="query_knowledge",
        description="查询企业知识库（用于查询内部文档、公司资料）",
        category="knowledge_base",
    ),
    BuiltinToolSpec(
        code="4",
        name="get_knowledge_stats",
        description="知识库统计（用于查询知识库状态、文档数量）",
        category="knowledge_base",
    ),
    BuiltinToolSpec(
        code="5",
        name="reload_knowledge_base",
        description="重载知识库（用于刷新知识库）",
        category="knowledge_base",
    ),
    BuiltinToolSpec(
        code="2",
        name="web_search",
        description="联网搜索（用于查询实时信息、新闻、外部知识）",
        category="web_search",
    ),
    BuiltinToolSpec(
        code="3",
        name="quick_answer",
        description="快速问答（用于快速获取网络答案）",
        category="web_search",
    ),
    BuiltinToolSpec(
        code="6",
        name="fetch_webpage",
        description="抓取网页全文（用于读取搜索结果中的具体网页内容）",
        category="web_search",
    ),
):
    register_builtin_tool(_builtin_tool_spec)


def set_web_search_enabled(enabled: bool) -> None:
    """设置联网搜索全局开关。"""
    global _web_search_enabled
    _web_search_enabled = enabled


__all__ = [
    "BuiltinToolSpec",
    "register_builtin_tool",
    "get_builtin_tool_registry",
    "list_enabled_builtin_tool_specs",
    "_build_enabled_tool_directory",
    "set_web_search_enabled",
]
