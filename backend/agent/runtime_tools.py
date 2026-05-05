"""Runtime tool assembly, including MCP overrides."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from backend.agent_mcp_helpers import load_mcp_tool_overrides
from backend.agent.tool_registry import list_enabled_builtin_tool_specs
from backend.agent.tools import create_tools

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.doc_pipeline import DocPipeline


async def build_runtime_tools(
    pipeline: DocPipeline,
    *,
    web_search_enabled: bool = True,
    knowledge_base_enabled: bool = True,
    enabled_mcp_servers: list[str] | None = None,
    mcp_tool_loader: Callable[..., Any] = load_mcp_tool_overrides,
):
    builtin_tools = create_tools(
        pipeline,
        web_search_enabled=web_search_enabled,
        knowledge_base_enabled=knowledge_base_enabled,
    )
    tools_by_name = {tool.name: tool for tool in builtin_tools}

    mcp_tools = await mcp_tool_loader(
        knowledge_base_enabled=knowledge_base_enabled,
        web_search_enabled=web_search_enabled,
        expected_tool_names=None,
        enabled_server_names=enabled_mcp_servers,
    )

    overridden_names: list[str] = []
    extra_mcp_tools: list[Any] = []
    for name, tool in mcp_tools.items():
        if name in tools_by_name:
            tools_by_name[name] = tool
            overridden_names.append(name)
        else:
            extra_mcp_tools.append(tool)

    if overridden_names:
        logger.info(
            "Using MCP-backed tool overrides: %s",
            ", ".join(sorted(overridden_names)),
        )
    if extra_mcp_tools:
        logger.info(
            "Loaded extra MCP tools: %s",
            ", ".join(sorted(str(getattr(tool, "name", "") or "") for tool in extra_mcp_tools)),
        )

    runtime_tools = [
        tools_by_name[spec.name]
        for spec in list_enabled_builtin_tool_specs(
            knowledge_base_enabled=knowledge_base_enabled,
            web_search_enabled=web_search_enabled,
        )
        if spec.name in tools_by_name
    ]
    runtime_tools.extend(
        sorted(
            extra_mcp_tools,
            key=lambda tool: str(getattr(tool, "name", "") or ""),
        )
    )
    return runtime_tools
