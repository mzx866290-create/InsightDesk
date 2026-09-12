"""tools helpers for MCP connector management."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)



def _normalize_mcp_tool_result(result: Any) -> str:
    if isinstance(result, str):
        return result

    if isinstance(result, dict):
        text = result.get("text")
        if text is not None:
            return str(text)
        content = result.get("content")
        if content is not None:
            return str(content)

    if isinstance(result, list):
        parts: list[str] = []
        for item in result:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text")
                if text is not None:
                    parts.append(str(text))
                    continue
                content = item.get("content")
                if content is not None:
                    parts.append(str(content))
                    continue
            text = getattr(item, "text", None)
            if text is not None:
                parts.append(str(text))
                continue
            parts.append(str(item))
        return "\n".join(part for part in parts if part).strip()

    return str(result)
def _wrap_mcp_tool(tool: Any) -> Any:
    from langchain_core.tools import StructuredTool

    args_schema = getattr(tool, "args_schema", None)
    description = str(getattr(tool, "description", "") or getattr(tool, "name", "MCP tool"))

    async def _normalized_coroutine(**kwargs):
        result = await tool.ainvoke(kwargs)
        return _normalize_mcp_tool_result(result)

    if args_schema is None:
        return tool

    return StructuredTool.from_function(
        coroutine=_normalized_coroutine,
        name=str(getattr(tool, "name", "") or "mcp_tool"),
        description=description,
        args_schema=args_schema,
        infer_schema=False,
    )
