import asyncio
import json
import logging
import os
import re
import shlex
import threading
import time
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MCP_SERVER_NAMES: list[str] = []
MCP_SERVER_CONFIG_FILENAME = "mcp_server_config.json"
MCP_CONFIG_REDACTED_VALUE = "***redacted***"
MCP_CONNECTOR_METADATA_KEYS = {
    "label",
    "description",
    "category",
    "builtin",
    "capability_scopes",
    "risk_level",
    "requires_approval",
    "config_schema",
}
MCP_RISK_LEVELS = {"low", "medium", "high", "critical"}
MCP_APPROVAL_RISK_LEVELS = {"high", "critical"}
MCP_CONNECTOR_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
MCP_MARKET_CATEGORY_LABELS = {
    "data": "Data",
    "development": "Development",
    "documents": "Documents",
    "files": "Files",
    "platform": "Platform",
    "productivity": "Productivity",
    "communication": "Communication",
    "custom": "Custom",
}


class McpConnectorManifestError(ValueError):
    """Validation error with stable fields for marketplace manifest UX."""

    def __init__(self, code: str, message: str, *, field: str = "manifest"):
        super().__init__(message)
        self.code = code
        self.field = field
        self.message = message

    def to_api_detail(self) -> dict[str, str]:
        return {
            "code": self.code,
            "field": self.field,
            "message": self.message,
        }
_runtime_mcp_approval_lock = threading.RLock()
_runtime_mcp_approved_connectors: list[str] = []
_runtime_mcp_health_history_lock = threading.RLock()
_runtime_mcp_health_history: list[dict[str, Any]] = []
MCP_SERVER_METADATA: dict[str, dict[str, Any]] = {
    "filesystem": {
        "label": "Filesystem",
        "description": "Connect to a user-approved local filesystem MCP server.",
        "category": "files",
        "builtin": False,
        "capability_scopes": ["filesystem:read", "filesystem:write"],
        "risk_level": "high",
        "requires_approval": True,
        "config_schema": {
            "transport": "stdio",
            "required": ["command", "args"],
            "optional": ["transport", "cwd", "encoding", "env"],
            "sensitive": ["env"],
        },
    },
    "fetch": {
        "label": "Fetch",
        "description": "Connect to an external fetch/web retrieval MCP server.",
        "category": "data",
        "builtin": False,
        "capability_scopes": ["web:fetch"],
        "risk_level": "medium",
        "requires_approval": False,
        "config_schema": {
            "transport": "stdio",
            "required": ["command"],
            "optional": ["transport", "args", "cwd", "encoding", "env"],
            "sensitive": ["env"],
        },
    },
    "github": {
        "label": "GitHub",
        "description": "Connect to GitHub repositories, issues, pull requests, and project metadata.",
        "category": "development",
        "builtin": False,
        "capability_scopes": ["github:read", "github:write"],
        "risk_level": "high",
        "requires_approval": True,
        "config_schema": {
            "transport": "stdio",
            "required": ["command"],
            "optional": ["transport", "args", "cwd", "encoding", "env"],
            "sensitive": ["env"],
        },
    },
    "notion": {
        "label": "Notion",
        "description": "Connect to Notion workspaces and pages through a configured MCP server.",
        "category": "documents",
        "builtin": False,
        "capability_scopes": ["notion:read", "notion:write"],
        "risk_level": "high",
        "requires_approval": True,
        "config_schema": {
            "transport": "stdio",
            "required": ["command"],
            "optional": ["transport", "args", "cwd", "encoding", "env"],
            "sensitive": ["env"],
        },
    },
    "jira": {
        "label": "Jira",
        "description": "Connect to Jira issues, projects, and workflow metadata.",
        "category": "productivity",
        "builtin": False,
        "capability_scopes": ["jira:read", "jira:write"],
        "risk_level": "high",
        "requires_approval": True,
        "config_schema": {
            "transport": "stdio",
            "required": ["command"],
            "optional": ["transport", "args", "cwd", "encoding", "env"],
            "sensitive": ["env"],
        },
    },
    "slack": {
        "label": "Slack",
        "description": "Connect to Slack channels, messages, and workspace context.",
        "category": "communication",
        "builtin": False,
        "capability_scopes": ["slack:read", "slack:write"],
        "risk_level": "high",
        "requires_approval": True,
        "config_schema": {
            "transport": "stdio",
            "required": ["command"],
            "optional": ["transport", "args", "cwd", "encoding", "env"],
            "sensitive": ["env"],
        },
    },
    "sqlite-readonly": {
        "label": "SQLite Readonly",
        "description": "Connect to a read-only SQLite MCP server for local data inspection.",
        "category": "data",
        "builtin": False,
        "capability_scopes": ["sqlite:read"],
        "risk_level": "medium",
        "requires_approval": False,
        "config_schema": {
            "transport": "stdio",
            "required": ["command", "args"],
            "optional": ["transport", "cwd", "encoding", "env"],
            "sensitive": ["env"],
        },
    },
}


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


def _env_name_list(name: str) -> list[str] | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    return parse_name_list(raw)


def _env_positive_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def parse_name_list(raw_value: Any) -> list[str]:
    if isinstance(raw_value, str):
        candidates = raw_value.split(",")
    elif isinstance(raw_value, (list, tuple, set, frozenset)):
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


def normalize_mcp_connector_name(raw_value: Any) -> str:
    """Normalize a connector id without changing its configured casing."""

    return str(raw_value or "").strip()


def normalize_mcp_approved_connectors(raw_value: Any) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for item in parse_name_list(raw_value):
        name = normalize_mcp_connector_name(item)
        if not name or name in seen:
            continue
        names.append(name)
        seen.add(name)
    return names


def add_mcp_approved_connector(
    approved_connector_names: Any,
    connector_name: Any,
) -> list[str]:
    names = normalize_mcp_approved_connectors(approved_connector_names)
    name = normalize_mcp_connector_name(connector_name)
    if name and name not in names:
        names.append(name)
    return names


def remove_mcp_approved_connector(
    approved_connector_names: Any,
    connector_name: Any,
) -> list[str]:
    names = normalize_mcp_approved_connectors(approved_connector_names)
    name = normalize_mcp_connector_name(connector_name)
    if not name:
        return names
    return [item for item in names if item != name]


def list_mcp_approved_connectors(
    env_connector_names: Any = None,
    runtime_connector_names: Any = None,
) -> dict[str, Any]:
    env_names = normalize_mcp_approved_connectors(env_connector_names)
    runtime_names = normalize_mcp_approved_connectors(runtime_connector_names)
    approved_names = normalize_mcp_approved_connectors([*env_names, *runtime_names])
    sources: dict[str, list[str]] = {}
    for name in approved_names:
        source_names: list[str] = []
        if name in env_names:
            source_names.append("env")
        if name in runtime_names:
            source_names.append("runtime")
        sources[name] = source_names
    return {
        "approved_connectors": approved_names,
        "env_connectors": env_names,
        "runtime_connectors": runtime_names,
        "sources": sources,
        "total": len(approved_names),
    }


def get_runtime_mcp_approved_connectors() -> list[str]:
    with _runtime_mcp_approval_lock:
        return list(_runtime_mcp_approved_connectors)


def set_runtime_mcp_approved_connectors(raw_value: Any) -> list[str]:
    names = normalize_mcp_approved_connectors(raw_value)
    with _runtime_mcp_approval_lock:
        _runtime_mcp_approved_connectors[:] = names
        return list(_runtime_mcp_approved_connectors)


def clear_runtime_mcp_approved_connectors() -> list[str]:
    return set_runtime_mcp_approved_connectors([])


def _connector_name_in_approval_list(connector_name: str, names: list[str]) -> bool:
    return "*" in names or connector_name in names


def current_mcp_approved_connectors_payload() -> dict[str, Any]:
    return list_mcp_approved_connectors(
        os.getenv("MCP_APPROVED_CONNECTORS"),
        get_runtime_mcp_approved_connectors(),
    )


def current_mcp_approved_connector_names() -> list[str]:
    return list(current_mcp_approved_connectors_payload()["approved_connectors"])


def approve_runtime_mcp_connector(connector_name: Any) -> dict[str, Any]:
    name = normalize_mcp_connector_name(connector_name)
    if not name:
        raise ValueError("connector name is required")

    with _runtime_mcp_approval_lock:
        before = list(_runtime_mcp_approved_connectors)
        updated = add_mcp_approved_connector(before, name)
        _runtime_mcp_approved_connectors[:] = updated

    payload = current_mcp_approved_connectors_payload()
    payload["connector"] = {
        "name": name,
        "changed": updated != before,
        "runtime_approved": _connector_name_in_approval_list(
            name, payload["runtime_connectors"]
        ),
        "effective_approved": _connector_name_in_approval_list(
            name, payload["approved_connectors"]
        ),
    }
    return payload


def revoke_runtime_mcp_connector(connector_name: Any) -> dict[str, Any]:
    name = normalize_mcp_connector_name(connector_name)
    if not name:
        raise ValueError("connector name is required")

    with _runtime_mcp_approval_lock:
        before = list(_runtime_mcp_approved_connectors)
        updated = remove_mcp_approved_connector(before, name)
        _runtime_mcp_approved_connectors[:] = updated

    payload = current_mcp_approved_connectors_payload()
    payload["connector"] = {
        "name": name,
        "removed": updated != before,
        "runtime_approved": _connector_name_in_approval_list(
            name, payload["runtime_connectors"]
        ),
        "effective_approved": _connector_name_in_approval_list(
            name, payload["approved_connectors"]
        ),
    }
    return payload


def default_mcp_server_names() -> list[str]:
    return list(DEFAULT_MCP_SERVER_NAMES)


def _connection_mcp_metadata(connection: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(connection, dict):
        return {}

    metadata: dict[str, Any] = {}
    raw_metadata = connection.get("metadata")
    if isinstance(raw_metadata, dict):
        metadata.update(raw_metadata)

    for key in MCP_CONNECTOR_METADATA_KEYS:
        if key in connection:
            metadata[key] = connection[key]

    return metadata


def _runtime_mcp_connection(connection: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in connection.items()
        if key not in MCP_CONNECTOR_METADATA_KEYS and key != "metadata"
    }


def _normalize_bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default

    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _normalize_risk_level(value: Any, *, default: str = "medium") -> str:
    normalized = str(value or default).strip().lower()
    if normalized in MCP_RISK_LEVELS:
        return normalized
    return default


def _infer_mcp_config_schema(connection: dict[str, Any] | None) -> dict[str, Any]:
    transport = str((connection or {}).get("transport") or "stdio").strip() or "stdio"
    if transport == "stdio":
        return {
            "transport": transport,
            "required": ["command"],
            "optional": ["transport", "args", "cwd", "encoding", "env"],
            "sensitive": ["env"],
        }
    if transport in {"sse", "streamable_http", "http"}:
        return {
            "transport": transport,
            "required": ["url"],
            "optional": ["transport", "headers", "timeout", "sse_read_timeout"],
            "sensitive": ["headers"],
        }
    return {
        "transport": transport,
        "required": ["transport"],
        "optional": [],
        "sensitive": [],
    }


def _normalize_schema_list(value: Any, fallback: list[str]) -> list[str]:
    if value is None:
        return list(fallback)
    return parse_name_list(value)


def _normalize_mcp_config_schema(
    value: Any,
    *,
    connection: dict[str, Any] | None,
) -> dict[str, Any]:
    inferred = _infer_mcp_config_schema(connection)
    if not isinstance(value, dict):
        return inferred

    transport = (
        str(value.get("transport") or inferred["transport"]).strip()
        or inferred["transport"]
    )
    return {
        "transport": transport,
        "required": _normalize_schema_list(
            value.get("required", value.get("required_fields")),
            inferred["required"],
        ),
        "optional": _normalize_schema_list(
            value.get("optional", value.get("optional_fields")),
            inferred["optional"],
        ),
        "sensitive": _normalize_schema_list(
            value.get("sensitive", value.get("sensitive_fields")),
            inferred["sensitive"],
        ),
    }


def normalize_mcp_server_names(
    raw_value: Any,
    *,
    available_names: set[str] | None = None,
) -> list[str]:
    names = parse_name_list(raw_value)
    if available_names is None:
        return names
    return [name for name in names if name in available_names]


def describe_mcp_server(
    server_name: str,
    connection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_name = str(server_name or "").strip()
    metadata = dict(MCP_SERVER_METADATA.get(normalized_name, {}))
    metadata.update(_connection_mcp_metadata(connection))
    builtin = bool(metadata.get("builtin", False))
    risk_level = _normalize_risk_level(metadata.get("risk_level"), default="medium")
    capability_scopes = parse_name_list(
        metadata.get("capability_scopes", ["custom:tools"])
    ) or ["custom:tools"]
    return {
        "name": normalized_name,
        "label": str(metadata.get("label") or normalized_name or "MCP Server"),
        "description": str(metadata.get("description") or "").strip(),
        "category": str(metadata.get("category") or "custom").strip() or "custom",
        "builtin": builtin,
        "transport": str((connection or {}).get("transport") or "stdio"),
        "capability_scopes": capability_scopes,
        "risk_level": risk_level,
        "requires_approval": _normalize_bool(
            metadata.get("requires_approval"),
            default=(not builtin or risk_level in {"high", "critical"}),
        ),
        "config_schema": _normalize_mcp_config_schema(
            metadata.get("config_schema"),
            connection=connection,
        ),
    }


def list_mcp_connector_template_catalog(
    *,
    configured_names: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Return installable connector templates without creating runtime connections."""

    configured = configured_names or set()
    templates: list[dict[str, Any]] = []
    for server_name in sorted(MCP_SERVER_METADATA):
        if server_name in configured:
            continue
        templates.append(
            {
                **describe_mcp_server(server_name, None),
                **mcp_server_health_payload(
                    server_name,
                    None,
                    source="template",
                    available_names=set(),
                ),
                "template": True,
            }
        )
    return templates


def _normalize_policy_set(raw_value: Any) -> set[str]:
    return set(parse_name_list(raw_value))


def _scope_allowed(scope: str, allowed_scopes: set[str]) -> bool:
    if "*" in allowed_scopes or scope in allowed_scopes:
        return True
    namespace, separator, _ = scope.partition(":")
    return bool(separator and f"{namespace}:*" in allowed_scopes)


def _describe_mcp_connector_payload(
    connector: dict[str, Any] | str,
    connection: dict[str, Any] | None,
) -> dict[str, Any]:
    if isinstance(connector, str):
        return describe_mcp_server(connector, connection)

    payload = connector if isinstance(connector, dict) else {}
    combined_connection: dict[str, Any] = dict(connection or {})
    combined_connection.update(payload)
    connector_name = str(
        payload.get("name") or payload.get("server_name") or payload.get("id") or ""
    ).strip()
    return describe_mcp_server(connector_name, combined_connection)


def evaluate_mcp_connector_policy(
    connector: dict[str, Any] | str,
    connection: dict[str, Any] | None = None,
    *,
    allowed_scopes: Any = None,
    approved_connector_names: Any = None,
    allow_high_risk: bool = False,
) -> dict[str, Any]:
    """Evaluate whether an MCP connector may be enabled or used.

    The helper is intentionally static: it only inspects connector metadata and
    caller-provided policy inputs, and never starts or contacts an MCP server.
    """

    description = _describe_mcp_connector_payload(connector, connection)
    connector_name = str(description["name"])
    capability_scopes = list(description["capability_scopes"])
    risk_level = str(description["risk_level"])
    configured_requires_approval = bool(description["requires_approval"])

    allowed_scope_set = _normalize_policy_set(allowed_scopes)
    missing_scopes = (
        [
            scope
            for scope in capability_scopes
            if not _scope_allowed(scope, allowed_scope_set)
        ]
        if allowed_scopes is not None
        else []
    )

    approved_names = _normalize_policy_set(approved_connector_names)
    connector_approved = bool(
        approved_connector_names is not None
        and ("*" in approved_names or connector_name in approved_names)
    )
    risk_requires_approval = (
        risk_level in MCP_APPROVAL_RISK_LEVELS and not allow_high_risk
    )
    approval_required = configured_requires_approval or risk_requires_approval
    requires_approval = bool(approval_required and not connector_approved)

    reasons: list[str] = []
    if missing_scopes:
        reasons.append("scope_missing")
    if configured_requires_approval and not connector_approved:
        reasons.append("connector_requires_approval")
    if risk_requires_approval and not connector_approved:
        reasons.append("high_risk_requires_approval")
    if requires_approval:
        reasons.append("connector_not_approved")
    if connector_approved and approval_required:
        reasons.append("connector_approved")
    if risk_level in MCP_APPROVAL_RISK_LEVELS and allow_high_risk:
        reasons.append("high_risk_allowed")

    return {
        "allowed": bool(not missing_scopes and not requires_approval),
        "requires_approval": requires_approval,
        "reasons": reasons,
        "name": connector_name,
        "capability_scopes": capability_scopes,
        "missing_scopes": missing_scopes,
        "risk_level": risk_level,
        "approved": connector_approved,
    }


def _configured_mcp_connection_issues(connection: dict[str, Any] | None) -> list[str]:
    if not isinstance(connection, dict) or not connection:
        return ["connection_missing"]

    transport = str(connection.get("transport") or "stdio").strip()
    if not transport:
        return ["transport_missing"]

    issues: list[str] = []
    if transport == "stdio":
        command = str(connection.get("command") or "").strip()
        if not command:
            issues.append("command_missing")

        args = connection.get("args")
        if args is not None and not isinstance(args, list):
            issues.append("args_invalid")
        elif isinstance(args, list) and args:
            # Static health only: verify local Python entrypoints and cwd, never spawn servers.
            first_arg = Path(str(args[0]))
            if first_arg.suffix == ".py" and not first_arg.is_file():
                issues.append("entrypoint_missing")

        cwd = connection.get("cwd")
        if cwd is not None and not Path(str(cwd)).is_dir():
            issues.append("cwd_missing")
    elif transport in {"sse", "streamable_http", "http"}:
        url = str(connection.get("url") or "").strip()
        if not url:
            issues.append("url_missing")
    else:
        issues.append("transport_unsupported")

    return issues


def _mcp_server_is_requested(
    server_name: str,
    *,
    available_names: set[str],
    enabled_server_names: list[str] | None = None,
) -> bool:
    if enabled_server_names is not None:
        return server_name in normalize_mcp_server_names(
            enabled_server_names,
            available_names=available_names,
        )

    raw_env_names = os.getenv("ENABLED_MCP_SERVERS")
    env_server_names = normalize_mcp_server_names(
        raw_env_names,
        available_names=available_names,
    )
    if raw_env_names is not None:
        return server_name in env_server_names
    return True


def mcp_server_health_payload(
    server_name: str,
    connection: dict[str, Any] | None,
    *,
    source: str,
    available_names: set[str],
    knowledge_base_enabled: bool = True,
    web_search_enabled: bool = True,
    enabled_server_names: list[str] | None = None,
    enable_mcp_tools: bool | None = None,
) -> dict[str, Any]:
    configured_issues = _configured_mcp_connection_issues(connection)
    configured = not configured_issues
    mcp_enabled = (
        enable_mcp_tools
        if enable_mcp_tools is not None
        else _env_flag("ENABLE_MCP_TOOLS", default=enabled_server_names is not None)
    )
    requested = _mcp_server_is_requested(
        server_name,
        available_names=available_names,
        enabled_server_names=enabled_server_names,
    )
    feature_enabled = True
    enabled = bool(mcp_enabled and requested and feature_enabled)
    healthy = bool(enabled and configured)

    status_reasons: list[str] = []
    if not mcp_enabled:
        status_reasons.append("mcp_tools_disabled")
    if not requested:
        status_reasons.append("server_not_selected")
    if not feature_enabled:
        status_reasons.append("feature_disabled")
    status_reasons.extend(configured_issues)

    if not configured:
        status = "unconfigured"
    elif not enabled:
        status = "disabled"
    else:
        status = "healthy"

    return {
        "enabled": enabled,
        "configured": configured,
        "healthy": healthy,
        "status": status,
        "status_reasons": status_reasons,
        "source": source,
    }


def default_mcp_connections(
    *,
    project_root: Path = PROJECT_ROOT,
    python_command: str | None = None,
) -> dict[str, dict[str, Any]]:
    return {}


def default_mcp_server_config_path(*, project_root: Path = PROJECT_ROOT) -> Path:
    return project_root / "runtime" / MCP_SERVER_CONFIG_FILENAME


def _active_mcp_server_config_path(
    *,
    project_root: Path = PROJECT_ROOT,
    config_path: str | None = None,
    for_write: bool = False,
) -> Path | None:
    raw_path = str(config_path or os.getenv("MCP_SERVER_CONFIG_PATH") or "").strip()
    if raw_path:
        path = Path(raw_path)
        if not path.is_absolute():
            path = (project_root / path).resolve()
        return path

    default_path = default_mcp_server_config_path(project_root=project_root)
    if for_write or default_path.is_file():
        return default_path
    return None


def _mcp_config_contains_secret_key(key: Any) -> bool:
    normalized = str(key or "").strip().lower().replace("-", "_")
    if normalized in {"env", "headers", "authorization", "proxy_authorization"}:
        return True
    return any(
        marker in normalized
        for marker in (
            "api_key",
            "apikey",
            "auth",
            "credential",
            "password",
            "private_key",
            "secret",
            "token",
        )
    )


def _redact_mcp_config_value(value: Any, *, force: bool = False) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _redact_mcp_config_value(
                item,
                force=force or _mcp_config_contains_secret_key(key),
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_mcp_config_value(item, force=force) for item in value]
    if force and value not in (None, ""):
        return MCP_CONFIG_REDACTED_VALUE
    return value


def redact_mcp_server_config(config: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(server_name): _redact_mcp_config_value(dict(connection))
        for server_name, connection in config.items()
        if isinstance(connection, dict)
    }


def _merge_redacted_mcp_config_value(new_value: Any, previous_value: Any) -> Any:
    if new_value == MCP_CONFIG_REDACTED_VALUE:
        return previous_value
    if isinstance(new_value, dict):
        previous_mapping = previous_value if isinstance(previous_value, dict) else {}
        return {
            str(key): _merge_redacted_mcp_config_value(
                item,
                previous_mapping.get(key),
            )
            for key, item in new_value.items()
        }
    if isinstance(new_value, list):
        previous_items = previous_value if isinstance(previous_value, list) else []
        return [
            _merge_redacted_mcp_config_value(
                item,
                previous_items[index] if index < len(previous_items) else None,
            )
            for index, item in enumerate(new_value)
        ]
    return new_value


def normalize_mcp_server_config_payload(
    raw_config: Any,
    *,
    previous_config: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    if isinstance(raw_config, dict) and isinstance(raw_config.get("servers"), dict):
        raw_servers = raw_config["servers"]
    else:
        raw_servers = raw_config
    if not isinstance(raw_servers, dict):
        raise ValueError("MCP server config must be a JSON object")

    previous = previous_config or {}
    normalized: dict[str, dict[str, Any]] = {}
    for raw_name, raw_connection in raw_servers.items():
        server_name = str(raw_name or "").strip()
        if not server_name:
            raise ValueError("MCP server name is required")
        if not isinstance(raw_connection, dict):
            raise ValueError(f"MCP server config entry must be an object: {server_name}")
        merged = _merge_redacted_mcp_config_value(
            dict(raw_connection),
            previous.get(server_name, {}),
        )
        normalized[server_name] = dict(merged)
    return normalized


def current_mcp_server_config_payload(
    *,
    project_root: Path = PROJECT_ROOT,
    config_path: str | None = None,
    python_command: str | None = None,
) -> dict[str, Any]:
    path = _active_mcp_server_config_path(
        project_root=project_root,
        config_path=config_path,
    )
    if path is not None and path.is_file():
        servers = load_mcp_connection_config(str(path), project_root=project_root)
        source = "config"
        active_path = str(path)
    else:
        servers = default_mcp_connections(
            project_root=project_root,
            python_command=python_command,
        )
        source = "default"
        active_path = str(
            _active_mcp_server_config_path(
                project_root=project_root,
                config_path=config_path,
                for_write=True,
            )
            or ""
        )

    catalog_config_path = str(path) if source == "config" and path is not None else None
    catalog = list_mcp_server_catalog(
        project_root=project_root,
        python_command=python_command,
        config_path=catalog_config_path,
    )
    configured_names = {str(item.get("name") or "") for item in catalog}
    catalog = [
        *catalog,
        *list_mcp_connector_template_catalog(configured_names=configured_names),
    ]
    return {
        "connectors": catalog,
        "marketplace": build_mcp_connector_marketplace(catalog),
        "default_enabled": default_mcp_server_names(),
        "servers": redact_mcp_server_config(servers),
        "total": len(servers),
        "source": source,
        "path": active_path,
        "hot_update": {
            "enabled": True,
            "applied": False,
            "requires_agent_cache_clear": False,
            "restart_required": False,
        },
        "sensitive_fields_redacted": True,
        "persistence": {
            "enabled": True,
            "sensitive_fields_redacted": True,
        },
    }


def save_mcp_server_config_payload(
    raw_config: Any,
    *,
    project_root: Path = PROJECT_ROOT,
    config_path: str | None = None,
) -> dict[str, Any]:
    path = _active_mcp_server_config_path(
        project_root=project_root,
        config_path=config_path,
        for_write=True,
    )
    if path is None:
        raise ValueError("MCP server config path is required")

    previous = (
        load_mcp_connection_config(str(path), project_root=project_root)
        if path.is_file()
        else {}
    )
    servers = normalize_mcp_server_config_payload(
        raw_config,
        previous_config=previous,
    )
    changed = servers != previous
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(servers, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    payload = current_mcp_server_config_payload(
        project_root=project_root,
        config_path=str(path),
    )
    payload["hot_update"] = {
        "enabled": True,
        "applied": True,
        "changed": changed,
        "requires_agent_cache_clear": changed,
        "restart_required": False,
    }
    return payload


def _manifest_install_command_parts(raw_value: Any) -> list[str]:
    if isinstance(raw_value, str):
        return shlex.split(raw_value, posix=os.name != "nt")
    if isinstance(raw_value, (list, tuple)):
        return [str(item) for item in raw_value if str(item or "").strip()]
    return []


def _require_mcp_manifest_mapping(
    manifest: dict[str, Any],
    field: str,
) -> dict[str, Any] | None:
    value = manifest.get(field)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise McpConnectorManifestError(
            "invalid_manifest_field",
            f"MCP connector manifest field '{field}' must be a JSON object",
            field=field,
        )
    return value


def _normalize_mcp_manifest_risk_level(
    manifest: dict[str, Any],
    metadata: dict[str, Any],
) -> str:
    value = manifest.get("risk_level") or metadata.get("risk_level")
    if value is None or str(value).strip() == "":
        return "medium"

    risk_level = str(value).strip().lower()
    if risk_level not in MCP_RISK_LEVELS:
        raise McpConnectorManifestError(
            "invalid_risk_level",
            "MCP connector manifest risk_level must be one of: "
            + ", ".join(sorted(MCP_RISK_LEVELS)),
            field="risk_level",
        )
    return risk_level


def _connection_from_mcp_manifest(manifest: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    name = normalize_mcp_connector_name(
        manifest.get("name") or manifest.get("id") or manifest.get("server_name")
    )
    if not name:
        raise McpConnectorManifestError(
            "missing_name",
            "MCP connector manifest requires a name",
            field="name",
        )
    if not MCP_CONNECTOR_NAME_PATTERN.match(name):
        raise McpConnectorManifestError(
            "invalid_name",
            "MCP connector manifest name must be 1-64 characters and use only letters, numbers, dots, underscores, or hyphens",
            field="name",
        )

    transport = str(manifest.get("transport") or "stdio").strip() or "stdio"
    if transport not in {"stdio", "sse", "streamable_http", "http"}:
        raise McpConnectorManifestError(
            "unsupported_transport",
            f"Unsupported MCP connector transport: {transport}",
            field="transport",
        )

    for mapping_field in ("env", "headers", "metadata", "config_schema"):
        _require_mcp_manifest_mapping(manifest, mapping_field)

    connection: dict[str, Any] = {"transport": transport}
    if transport == "stdio":
        command = str(manifest.get("command") or "").strip()
        args = manifest.get("args")
        if not command:
            install_parts = _manifest_install_command_parts(
                manifest.get("install_command")
            )
            if install_parts:
                command = install_parts[0]
                args = install_parts[1:]
        if not command:
            raise McpConnectorManifestError(
                "missing_stdio_command",
                "MCP stdio connector manifest requires command or install_command",
                field="command",
            )
        connection["command"] = command
        if isinstance(args, list):
            connection["args"] = [str(item) for item in args]
        elif args:
            connection["args"] = [str(args)]
        else:
            connection["args"] = []
    elif transport in {"sse", "streamable_http", "http"}:
        url = str(manifest.get("url") or "").strip()
        if not url:
            raise McpConnectorManifestError(
                "missing_url",
                "MCP HTTP/SSE connector manifest requires url",
                field="url",
            )
        connection["url"] = url
        headers = manifest.get("headers")
        if isinstance(headers, dict):
            connection["headers"] = {str(key): str(value) for key, value in headers.items()}

    if str(manifest.get("cwd") or "").strip():
        connection["cwd"] = str(manifest.get("cwd")).strip()
    if str(manifest.get("encoding") or "").strip():
        connection["encoding"] = str(manifest.get("encoding")).strip()
    env = manifest.get("env")
    if isinstance(env, dict):
        connection["env"] = {str(key): str(value) for key, value in env.items()}

    metadata = manifest.get("metadata") if isinstance(manifest.get("metadata"), dict) else {}
    connection["metadata"] = {
        "label": str(manifest.get("label") or metadata.get("label") or name),
        "description": str(
            manifest.get("description") or metadata.get("description") or ""
        ).strip(),
        "category": str(
            manifest.get("category") or metadata.get("category") or "custom"
        ).strip() or "custom",
        "capability_scopes": parse_name_list(
            manifest.get("scopes")
            or manifest.get("capability_scopes")
            or metadata.get("capability_scopes")
            or ["custom:tools"]
        ),
        "risk_level": _normalize_mcp_manifest_risk_level(manifest, metadata),
        "requires_approval": _normalize_bool(
            manifest.get("requires_approval", metadata.get("requires_approval")),
            default=True,
        ),
        "version": str(manifest.get("version") or metadata.get("version") or "").strip(),
    }
    if isinstance(manifest.get("config_schema"), dict):
        connection["metadata"]["config_schema"] = manifest["config_schema"]
    return name, connection


def install_mcp_connector_manifest_payload(
    manifest: dict[str, Any],
    *,
    project_root: Path = PROJECT_ROOT,
    config_path: str | None = None,
) -> dict[str, Any]:
    """Persist an MCP connector manifest without executing install commands."""

    if not isinstance(manifest, dict):
        raise ValueError("MCP connector manifest must be a JSON object")

    connector_name, connection = _connection_from_mcp_manifest(manifest)
    path = _active_mcp_server_config_path(
        project_root=project_root,
        config_path=config_path,
        for_write=True,
    )
    if path is None:
        raise ValueError("MCP server config path is required")

    previous = (
        load_mcp_connection_config(str(path), project_root=project_root)
        if path.is_file()
        else {}
    )
    raw_config = {"servers": {**previous, connector_name: connection}}
    payload = save_mcp_server_config_payload(
        raw_config,
        project_root=project_root,
        config_path=str(path),
    )
    installed = next(
        (
            item
            for item in payload.get("connectors", [])
            if item.get("name") == connector_name
        ),
        describe_mcp_server(connector_name, connection),
    )
    payload["installed"] = {
        "name": connector_name,
        "connector": installed,
        "executed_install_command": False,
    }
    return payload


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


def _resolve_mcp_connections(
    *,
    project_root: Path = PROJECT_ROOT,
    python_command: str | None = None,
    config_path: str | None = None,
) -> tuple[dict[str, dict[str, Any]], str]:
    resolved_config_path = _active_mcp_server_config_path(
        project_root=project_root,
        config_path=config_path,
    )
    if resolved_config_path is not None:
        return (
            load_mcp_connection_config(
                str(resolved_config_path),
                project_root=project_root,
            ),
            "config",
        )
    return (
        default_mcp_connections(
            project_root=project_root,
            python_command=python_command,
        ),
        "default",
    )


def list_mcp_server_catalog(
    *,
    project_root: Path = PROJECT_ROOT,
    python_command: str | None = None,
    config_path: str | None = None,
    knowledge_base_enabled: bool = True,
    web_search_enabled: bool = True,
    enabled_server_names: list[str] | None = None,
    enable_mcp_tools: bool | None = None,
    allowed_scopes: Any = None,
    approved_connector_names: Any = None,
    allow_high_risk: bool | None = None,
) -> list[dict[str, Any]]:
    connections, source = _resolve_mcp_connections(
        project_root=project_root,
        python_command=python_command,
        config_path=config_path,
    )
    available_names = set(connections)
    policy_allowed_scopes = (
        allowed_scopes if allowed_scopes is not None else _env_name_list("MCP_ALLOWED_SCOPES")
    )
    policy_approved_names = (
        approved_connector_names
        if approved_connector_names is not None
        else current_mcp_approved_connector_names()
    )
    policy_allow_high_risk = (
        allow_high_risk
        if allow_high_risk is not None
        else _env_flag("MCP_ALLOW_HIGH_RISK", default=False)
    )
    catalog: list[dict[str, Any]] = []
    for server_name in sorted(connections):
        connection = connections[server_name]
        policy = evaluate_mcp_connector_policy(
            server_name,
            connection,
            allowed_scopes=policy_allowed_scopes,
            approved_connector_names=policy_approved_names,
            allow_high_risk=policy_allow_high_risk,
        )
        catalog.append(
            {
                **describe_mcp_server(server_name, connection),
                **mcp_server_health_payload(
                    server_name,
                    connection,
                    source=source,
                    available_names=available_names,
                    knowledge_base_enabled=knowledge_base_enabled,
                    web_search_enabled=web_search_enabled,
                    enabled_server_names=enabled_server_names,
                    enable_mcp_tools=enable_mcp_tools,
                ),
                "policy": policy,
            }
        )
    return catalog


def build_mcp_connector_marketplace(
    catalog: list[dict[str, Any]],
) -> dict[str, Any]:
    """Group catalog entries into a UI-ready, secret-free marketplace payload."""

    categories: dict[str, dict[str, Any]] = {}
    for connector in catalog:
        category = str(connector.get("category") or "custom").strip() or "custom"
        bucket = categories.setdefault(
            category,
            {
                "id": category,
                "label": MCP_MARKET_CATEGORY_LABELS.get(
                    category,
                    category.replace("_", " ").replace("-", " ").title(),
                ),
                "total": 0,
                "enabled": 0,
                "healthy": 0,
                "requires_approval": 0,
                "connectors": [],
            },
        )
        bucket["total"] += 1
        if bool(connector.get("enabled")):
            bucket["enabled"] += 1
        if bool(connector.get("healthy")):
            bucket["healthy"] += 1
        if bool(connector.get("requires_approval")):
            bucket["requires_approval"] += 1
        bucket["connectors"].append(str(connector.get("name") or ""))

    ordered_categories = sorted(
        categories.values(),
        key=lambda item: (str(item["label"]).lower(), str(item["id"])),
    )
    return {
        "categories": ordered_categories,
        "summary": {
            "total": len(catalog),
            "builtin": sum(1 for item in catalog if bool(item.get("builtin"))),
            "custom": sum(1 for item in catalog if not bool(item.get("builtin"))),
            "enabled": sum(1 for item in catalog if bool(item.get("enabled"))),
            "healthy": sum(1 for item in catalog if bool(item.get("healthy"))),
            "requires_approval": sum(
                1 for item in catalog if bool(item.get("requires_approval"))
            ),
            "categories": len(ordered_categories),
        },
    }


def build_mcp_runtime_monitor_payload(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Normalize runtime-health payloads into a compact monitor contract."""

    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    alerts = summary.get("alerts") if isinstance(summary.get("alerts"), list) else []
    status = str(payload.get("status") or "unknown")
    if status == "ok" and int(summary.get("alert_count", 0) or 0) > 0:
        status = "attention"
    return {
        "status": status,
        "checked_at": time.time(),
        "alert_count": int(summary.get("alert_count", 0) or 0),
        "unhealthy_connectors": list(summary.get("unhealthy_connectors") or []),
        "slow_connectors": list(summary.get("slow_connectors") or []),
        "alerts": alerts[:10],
    }


def list_mcp_server_health(
    *,
    project_root: Path = PROJECT_ROOT,
    python_command: str | None = None,
    config_path: str | None = None,
    knowledge_base_enabled: bool = True,
    web_search_enabled: bool = True,
    enabled_server_names: list[str] | None = None,
    enable_mcp_tools: bool | None = None,
) -> dict[str, Any]:
    connections, source = _resolve_mcp_connections(
        project_root=project_root,
        python_command=python_command,
        config_path=config_path,
    )
    available_names = set(connections)
    servers = [
        {
            **describe_mcp_server(server_name, connection),
            **mcp_server_health_payload(
                server_name,
                connection,
                source=source,
                available_names=available_names,
                knowledge_base_enabled=knowledge_base_enabled,
                web_search_enabled=web_search_enabled,
                enabled_server_names=enabled_server_names,
                enable_mcp_tools=enable_mcp_tools,
            ),
        }
        for server_name, connection in sorted(connections.items())
    ]
    return {
        "servers": servers,
        "summary": {
            "total": len(servers),
            "enabled": sum(1 for item in servers if item["enabled"]),
            "configured": sum(1 for item in servers if item["configured"]),
            "healthy": sum(1 for item in servers if item["healthy"]),
        },
    }


def summarize_mcp_runtime_health(
    servers: list[dict[str, Any]],
    *,
    slow_duration_ms: float = 1000.0,
) -> dict[str, Any]:
    """Build a deterministic runtime-health alert summary for API payloads."""

    status_counts: dict[str, int] = {}
    unhealthy_names: list[str] = []
    slow_names: list[str] = []
    alerts: list[dict[str, Any]] = []

    for server in servers:
        name = str(server.get("name") or "").strip()
        status = str(server.get("status") or "unknown").strip() or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1

        if not bool(server.get("healthy")):
            if name:
                unhealthy_names.append(name)
            alerts.append(
                {
                    "severity": "critical" if status == "timeout" else "warning",
                    "code": f"mcp_runtime_{status}",
                    "connector": name,
                    "message": (
                        f"{name or 'MCP connector'} runtime health is {status}"
                    ),
                    "error": str(server.get("error") or "").strip() or None,
                }
            )

        try:
            duration_ms = float(server.get("duration_ms") or 0.0)
        except (TypeError, ValueError):
            duration_ms = 0.0

        if duration_ms >= slow_duration_ms:
            if name:
                slow_names.append(name)
            alerts.append(
                {
                    "severity": "info",
                    "code": "mcp_runtime_slow",
                    "connector": name,
                    "message": (
                        f"{name or 'MCP connector'} runtime ping took "
                        f"{round(duration_ms, 3):g}ms"
                    ),
                    "duration_ms": round(duration_ms, 3),
                }
            )

    return {
        "status_counts": status_counts,
        "unhealthy_connectors": unhealthy_names,
        "slow_connectors": slow_names,
        "alert_count": len(alerts),
        "alerts": alerts,
    }


def _runtime_health_history_limit(raw_limit: Any = None) -> int:
    raw_value = (
        raw_limit
        if raw_limit is not None
        else os.getenv("MCP_RUNTIME_HEALTH_HISTORY_LIMIT")
    )
    try:
        limit = int(raw_value or 20)
    except (TypeError, ValueError):
        limit = 20
    return min(200, max(1, limit))


def clear_mcp_runtime_health_history() -> None:
    """Clear in-process MCP runtime-health history, mainly for tests."""

    with _runtime_mcp_health_history_lock:
        _runtime_mcp_health_history.clear()


def get_mcp_runtime_health_history(limit: Any = None) -> list[dict[str, Any]]:
    """Return recent runtime-health snapshots newest first."""

    safe_limit = _runtime_health_history_limit(limit)
    with _runtime_mcp_health_history_lock:
        recent = list(_runtime_mcp_health_history[-safe_limit:])
    return [dict(item) for item in reversed(recent)]


def _record_mcp_runtime_health_snapshot_in_memory(
    snapshot: dict[str, Any],
    *,
    history_limit: Any = None,
) -> None:
    safe_limit = _runtime_health_history_limit(history_limit)
    with _runtime_mcp_health_history_lock:
        _runtime_mcp_health_history.append(snapshot)
        if len(_runtime_mcp_health_history) > safe_limit:
            del _runtime_mcp_health_history[:-safe_limit]


def record_mcp_runtime_health_snapshot(
    payload: dict[str, Any],
    *,
    recorded_at: float | None = None,
    history_limit: Any = None,
    history_recorder: Callable[[dict[str, Any], int], Any] | None = None,
) -> dict[str, Any]:
    """Persist a compact, secret-free runtime-health snapshot.

    A caller may inject a durable recorder; the in-process list is still always
    updated so runtime health remains available if persistence is unavailable.
    """

    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    servers = payload.get("servers") if isinstance(payload.get("servers"), list) else []
    snapshot = {
        "timestamp": time.time() if recorded_at is None else float(recorded_at),
        "status": str(payload.get("status") or "unknown"),
        "summary": {
            "total": int(summary.get("total", 0) or 0),
            "healthy": int(summary.get("healthy", 0) or 0),
            "unhealthy": int(summary.get("unhealthy", 0) or 0),
            "tool_count": int(summary.get("tool_count", 0) or 0),
            "status_counts": dict(summary.get("status_counts") or {}),
            "alert_count": int(summary.get("alert_count", 0) or 0),
            "unhealthy_connectors": list(summary.get("unhealthy_connectors") or []),
            "slow_connectors": list(summary.get("slow_connectors") or []),
        },
        "servers": [
            {
                "name": str(server.get("name") or ""),
                "status": str(server.get("status") or "unknown"),
                "healthy": bool(server.get("healthy")),
                "tool_count": int(server.get("tool_count", 0) or 0),
                "duration_ms": float(server.get("duration_ms", 0.0) or 0.0),
                "error": str(server.get("error") or "").strip() or None,
            }
            for server in servers
            if isinstance(server, dict)
        ],
    }
    _record_mcp_runtime_health_snapshot_in_memory(snapshot, history_limit=history_limit)
    if history_recorder is not None:
        try:
            history_recorder(dict(snapshot), _runtime_health_history_limit(history_limit))
        except Exception:
            logger.exception("Failed to persist MCP runtime-health history snapshot")
    return dict(snapshot)


def attach_mcp_runtime_health_history(
    payload: dict[str, Any],
    *,
    record_history: bool = True,
    history_limit: Any = None,
    history_recorder: Callable[[dict[str, Any], int], Any] | None = None,
    history_reader: Callable[[int], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    safe_limit = _runtime_health_history_limit(history_limit)
    if record_history:
        record_mcp_runtime_health_snapshot(
            payload,
            history_limit=safe_limit,
            history_recorder=history_recorder,
        )
    if history_reader is not None:
        try:
            payload["history"] = history_reader(safe_limit)
        except Exception:
            logger.exception("Failed to read persisted MCP runtime-health history")
            payload["history"] = get_mcp_runtime_health_history(safe_limit)
    else:
        payload["history"] = get_mcp_runtime_health_history(safe_limit)
    payload["history_limit"] = safe_limit
    return payload


def select_mcp_connections(
    *,
    knowledge_base_enabled: bool = True,
    web_search_enabled: bool = True,
    project_root: Path = PROJECT_ROOT,
    python_command: str | None = None,
    enabled_server_names: list[str] | None = None,
    config_path: str | None = None,
    enable_mcp_tools: bool | None = None,
    allowed_scopes: Any = None,
    approved_connector_names: Any = None,
    allow_high_risk: bool | None = None,
) -> dict[str, dict[str, Any]]:
    mcp_enabled = (
        enable_mcp_tools
        if enable_mcp_tools is not None
        else _env_flag("ENABLE_MCP_TOOLS", default=enabled_server_names is not None)
    )
    if not mcp_enabled:
        return {}

    connections, _ = _resolve_mcp_connections(
        project_root=project_root,
        python_command=python_command,
        config_path=config_path,
    )

    if not connections:
        return {}

    requested_server_names = (
        normalize_mcp_server_names(
            enabled_server_names,
            available_names=set(connections),
        )
        if enabled_server_names is not None
        else normalize_mcp_server_names(
            os.getenv("ENABLED_MCP_SERVERS"),
            available_names=set(connections),
        )
    )
    if requested_server_names:
        connections = {
            name: connections[name]
            for name in requested_server_names
            if name in connections
        }
    elif enabled_server_names is not None:
        return {}

    policy_allowed_scopes = (
        allowed_scopes if allowed_scopes is not None else _env_name_list("MCP_ALLOWED_SCOPES")
    )
    policy_approved_names = (
        approved_connector_names
        if approved_connector_names is not None
        else current_mcp_approved_connector_names()
    )
    policy_allow_high_risk = (
        allow_high_risk
        if allow_high_risk is not None
        else _env_flag("MCP_ALLOW_HIGH_RISK", default=False)
    )

    allowed_connections: dict[str, dict[str, Any]] = {}
    for name, connection in connections.items():
        policy = evaluate_mcp_connector_policy(
            name,
            connection,
            allowed_scopes=policy_allowed_scopes,
            approved_connector_names=policy_approved_names,
            allow_high_risk=policy_allow_high_risk,
        )
        if not policy["allowed"]:
            logger.warning(
                "Skipping MCP connector %s due to policy: %s",
                name,
                ",".join(policy["reasons"]),
            )
            continue
        allowed_connections[name] = connection

    return {
        name: _runtime_mcp_connection(connection)
        for name, connection in allowed_connections.items()
    }


async def list_mcp_server_runtime_health(
    *,
    knowledge_base_enabled: bool = True,
    web_search_enabled: bool = True,
    project_root: Path = PROJECT_ROOT,
    python_command: str | None = None,
    enabled_server_names: list[str] | None = None,
    config_path: str | None = None,
    enable_mcp_tools: bool | None = None,
    allowed_scopes: Any = None,
    approved_connector_names: Any = None,
    allow_high_risk: bool | None = None,
    connections: dict[str, dict[str, Any]] | None = None,
    client_factory: Callable[..., Any] | None = None,
    timeout_seconds: float | None = None,
    history_limit: Any = None,
    history_recorder: Callable[[dict[str, Any], int], Any] | None = None,
    history_reader: Callable[[int], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Ping selected MCP servers by loading their tool manifest.

    Unlike static catalog health, this may start or contact MCP servers, so it
    is intentionally opt-in and protected by a short timeout.
    """

    active_connections = connections
    if active_connections is None:
        active_connections = select_mcp_connections(
            knowledge_base_enabled=knowledge_base_enabled,
            web_search_enabled=web_search_enabled,
            project_root=project_root,
            python_command=python_command,
            enabled_server_names=enabled_server_names,
            config_path=config_path,
            enable_mcp_tools=enable_mcp_tools,
            allowed_scopes=allowed_scopes,
            approved_connector_names=approved_connector_names,
            allow_high_risk=allow_high_risk,
        )

    active_connections = {
        name: _runtime_mcp_connection(connection)
        for name, connection in (active_connections or {}).items()
    }
    if not active_connections:
        payload = {
            "status": "disabled",
            "servers": [],
            "summary": {
                "total": 0,
                "healthy": 0,
                "unhealthy": 0,
                "tool_count": 0,
                **summarize_mcp_runtime_health([]),
            },
        }
        payload["monitor"] = build_mcp_runtime_monitor_payload(payload)
        return attach_mcp_runtime_health_history(
            payload,
            history_limit=history_limit,
            history_recorder=history_recorder,
            history_reader=history_reader,
        )

    resolved_timeout = timeout_seconds or _env_positive_float(
        "MCP_RUNTIME_PING_TIMEOUT_SECONDS",
        5.0,
    )
    if client_factory is None:
        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
        except ImportError:
            servers = [
                {
                    "name": name,
                    "status": "unavailable",
                    "healthy": False,
                    "tool_count": 0,
                    "tools": [],
                    "duration_ms": 0.0,
                    "error": "mcp_adapters_unavailable",
                }
                for name in sorted(active_connections)
            ]
            payload = {
                "status": "unavailable",
                "servers": servers,
                "summary": {
                    "total": len(servers),
                    "healthy": 0,
                    "unhealthy": len(servers),
                    "tool_count": 0,
                    **summarize_mcp_runtime_health(servers),
                },
            }
            payload["monitor"] = build_mcp_runtime_monitor_payload(payload)
            return attach_mcp_runtime_health_history(
                payload,
                history_limit=history_limit,
                history_recorder=history_recorder,
                history_reader=history_reader,
            )
        client_factory = MultiServerMCPClient

    servers: list[dict[str, Any]] = []
    for name, connection in sorted(active_connections.items()):
        started_at = time.perf_counter()
        try:
            client = client_factory({name: connection}, tool_name_prefix=False)
            tools = await asyncio.wait_for(client.get_tools(), timeout=resolved_timeout)
            tool_names = sorted(
                {
                    str(getattr(tool, "name", "") or "").strip()
                    for tool in tools
                    if str(getattr(tool, "name", "") or "").strip()
                }
            )
            servers.append(
                {
                    "name": name,
                    "status": "healthy",
                    "healthy": True,
                    "tool_count": len(tool_names),
                    "tools": tool_names,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
                    "error": None,
                }
            )
        except asyncio.TimeoutError:
            servers.append(
                {
                    "name": name,
                    "status": "timeout",
                    "healthy": False,
                    "tool_count": 0,
                    "tools": [],
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
                    "error": f"runtime_ping_timeout_after_{resolved_timeout:g}s",
                }
            )
        except Exception as exc:
            servers.append(
                {
                    "name": name,
                    "status": "unhealthy",
                    "healthy": False,
                    "tool_count": 0,
                    "tools": [],
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
                    "error": str(exc)[:240],
                }
            )

    healthy_count = sum(1 for item in servers if item["healthy"])
    tool_count = sum(int(item["tool_count"]) for item in servers)
    payload = {
        "status": "ok" if healthy_count == len(servers) else "degraded",
        "servers": servers,
        "summary": {
            "total": len(servers),
            "healthy": healthy_count,
            "unhealthy": len(servers) - healthy_count,
            "tool_count": tool_count,
            **summarize_mcp_runtime_health(servers),
        },
    }
    payload["monitor"] = build_mcp_runtime_monitor_payload(payload)
    return attach_mcp_runtime_health_history(
        payload,
        history_limit=history_limit,
        history_recorder=history_recorder,
        history_reader=history_reader,
    )


async def load_mcp_tool_overrides(
    *,
    knowledge_base_enabled: bool = True,
    web_search_enabled: bool = True,
    expected_tool_names: set[str] | None = None,
    connections: dict[str, dict[str, Any]] | None = None,
    client_factory: Callable[..., Any] | None = None,
    enabled_server_names: list[str] | None = None,
) -> dict[str, Any]:
    active_connections = connections
    if active_connections is None:
        active_connections = select_mcp_connections(
            knowledge_base_enabled=knowledge_base_enabled,
            web_search_enabled=web_search_enabled,
            enabled_server_names=enabled_server_names,
        )

    if not active_connections:
        return {}
    active_connections = {
        name: _runtime_mcp_connection(connection)
        for name, connection in active_connections.items()
    }

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
