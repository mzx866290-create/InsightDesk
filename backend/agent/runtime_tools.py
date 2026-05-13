"""Runtime tool assembly, including MCP overrides."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Callable

from backend.agent_mcp_helpers import load_mcp_tool_overrides
from backend.agent.tool_registry import list_enabled_builtin_tool_specs
from backend.agent.tools import create_tools
from backend.core.tracing import trace_span

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.doc_pipeline import DocPipeline


def _tool_result_size(result: Any) -> int:
    if result is None:
        return 0
    if isinstance(result, (bytes, bytearray)):
        return len(result)
    return len(str(result))


def _wrap_tool_with_trace(tool: Any) -> Any:
    """Wrap runtime tool execution without recording full inputs or outputs."""
    from langchain_core.tools import StructuredTool

    args_schema = getattr(tool, "args_schema", None)
    if args_schema is None:
        return tool

    tool_name = str(getattr(tool, "name", "") or "unknown_tool")
    description = str(getattr(tool, "description", "") or tool_name)

    async def _traced_coroutine(**kwargs: Any) -> Any:
        started_at = time.monotonic()
        param_keys = sorted(str(key) for key in kwargs.keys())
        async with trace_span(
            "tool.execute",
            {
                "component": "agent.tool",
                "tool.name": tool_name,
                "tool.param_keys": param_keys,
            },
        ) as span:
            try:
                result = await tool.ainvoke(kwargs)
            except Exception:
                span.set_attributes(
                    {
                        "tool.status": "error",
                        "tool.duration_ms": int((time.monotonic() - started_at) * 1000),
                        "tool.result_size": 0,
                    }
                )
                raise

            span.set_attributes(
                {
                    "tool.status": "success",
                    "tool.duration_ms": int((time.monotonic() - started_at) * 1000),
                    "tool.result_size": _tool_result_size(result),
                }
            )
            return result

    return StructuredTool.from_function(
        coroutine=_traced_coroutine,
        name=tool_name,
        description=description,
        return_direct=bool(getattr(tool, "return_direct", False)),
        args_schema=args_schema,
        infer_schema=False,
        response_format=getattr(tool, "response_format", "content"),
    )


async def build_runtime_tools(
    pipeline: DocPipeline,
    *,
    web_search_enabled: bool = True,
    knowledge_base_enabled: bool = True,
    enabled_mcp_servers: list[str] | None = None,
    mcp_tool_loader: Callable[..., Any] = load_mcp_tool_overrides,
    trace_tool_execution: bool = True,
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
    if trace_tool_execution:
        runtime_tools = [_wrap_tool_with_trace(tool) for tool in runtime_tools]
    return runtime_tools
