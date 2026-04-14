import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent


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


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def parse_name_list(raw_value: Any) -> list[str]:
    if isinstance(raw_value, str):
        candidates = raw_value.split(",")
    elif isinstance(raw_value, (list, tuple)):
        candidates = raw_value
    else:
        return []

    names: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        name = str(item or "").strip()
        if not name or name in seen:
            continue
        names.append(name)
        seen.add(name)
    return names


def default_mcp_connections(
    *,
    project_root: Path = PROJECT_ROOT,
    python_command: str | None = None,
) -> dict[str, dict[str, Any]]:
    command = python_command or sys.executable
    scripts = {
        "knowledge-base": project_root / "mcp_servers" / "knowledge_server.py",
        "web-search": project_root / "mcp_servers" / "search_server.py",
    }

    connections: dict[str, dict[str, Any]] = {}
    for server_name, script_path in scripts.items():
        if not script_path.is_file():
            continue
        connections[server_name] = {
            "transport": "stdio",
            "command": command,
            "args": [str(script_path)],
            "cwd": str(project_root),
            "encoding": "utf-8",
        }
    return connections


def load_mcp_connection_config(
    config_path: str,
    *,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, dict[str, Any]]:
    raw_path = str(config_path or "").strip()
    if not raw_path:
        return {}

    path = Path(raw_path)
    if not path.is_absolute():
        path = (project_root / path).resolve()

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("MCP server config not found: %s", path)
        return {}
    except json.JSONDecodeError:
        logger.warning("MCP server config is not valid JSON: %s", path)
        return {}
    except OSError:
        logger.warning("MCP server config could not be read: %s", path)
        return {}

    if not isinstance(payload, dict):
        logger.warning("MCP server config must be a JSON object: %s", path)
        return {}

    base_dir = path.parent
    resolved: dict[str, dict[str, Any]] = {}
    for server_name, raw_connection in payload.items():
        if not isinstance(raw_connection, dict):
            logger.warning("Ignoring invalid MCP server config entry: %s", server_name)
            continue

        connection = dict(raw_connection)
        if connection.get("transport") == "stdio":
            args = connection.get("args")
            if isinstance(args, list):
                normalized_args = [str(item) for item in args]
                if normalized_args:
                    first_arg = Path(normalized_args[0])
                    if not first_arg.is_absolute() and first_arg.suffix == ".py":
                        normalized_args[0] = str((base_dir / first_arg).resolve())
                connection["args"] = normalized_args

            cwd = connection.get("cwd")
            if cwd is not None:
                cwd_path = Path(str(cwd))
                if not cwd_path.is_absolute():
                    connection["cwd"] = str((base_dir / cwd_path).resolve())

        resolved[str(server_name)] = connection

    return resolved


def select_mcp_connections(
    *,
    knowledge_base_enabled: bool = True,
    web_search_enabled: bool = True,
    project_root: Path = PROJECT_ROOT,
    python_command: str | None = None,
) -> dict[str, dict[str, Any]]:
    if not _env_flag("ENABLE_MCP_TOOLS", False):
        return {}

    config_path = str(os.getenv("MCP_SERVER_CONFIG_PATH") or "").strip()
    if config_path:
        connections = load_mcp_connection_config(
            config_path,
            project_root=project_root,
        )
    else:
        connections = default_mcp_connections(
            project_root=project_root,
            python_command=python_command,
        )

    if not connections:
        return {}

    enabled_server_names = parse_name_list(os.getenv("ENABLED_MCP_SERVERS"))
    if enabled_server_names:
        connections = {
            name: connections[name]
            for name in enabled_server_names
            if name in connections
        }

    if not knowledge_base_enabled:
        connections.pop("knowledge-base", None)
    if not web_search_enabled:
        connections.pop("web-search", None)

    return connections


async def load_mcp_tool_overrides(
    *,
    knowledge_base_enabled: bool = True,
    web_search_enabled: bool = True,
    expected_tool_names: set[str] | None = None,
    connections: dict[str, dict[str, Any]] | None = None,
    client_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    active_connections = connections
    if active_connections is None:
        active_connections = select_mcp_connections(
            knowledge_base_enabled=knowledge_base_enabled,
            web_search_enabled=web_search_enabled,
        )

    if not active_connections:
        return {}

    if client_factory is None:
        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
        except ImportError:
            logger.warning("MCP adapters are not available; falling back to built-in tools")
            return {}
        client_factory = MultiServerMCPClient

    try:
        client = client_factory(active_connections, tool_name_prefix=False)
        tools = await client.get_tools()
    except Exception:
        logger.exception("Failed to load MCP tools; falling back to built-in tools")
        return {}

    tool_overrides: dict[str, Any] = {}
    for tool in tools:
        name = str(getattr(tool, "name", "") or "").strip()
        if not name:
            continue
        if expected_tool_names and name not in expected_tool_names:
            continue
        tool_overrides[name] = _wrap_mcp_tool(tool)

    return tool_overrides
