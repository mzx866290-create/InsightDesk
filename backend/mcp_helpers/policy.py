"""policy helpers for MCP connector management."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


from backend.mcp_helpers.common import (  # noqa: F401
    MCP_APPROVAL_RISK_LEVELS,
    MCP_CONNECTOR_METADATA_KEYS,
    MCP_RISK_LEVELS,
    PROJECT_ROOT,
    _env_flag,
)
from backend.mcp_helpers.allowlist import (  # noqa: F401
    parse_name_list,
)

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
