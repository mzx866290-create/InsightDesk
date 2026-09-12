"""catalog helpers for MCP connector management."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


from backend.mcp_helpers.common import (  # noqa: F401
    MCP_MARKET_CATEGORY_LABELS,
    PROJECT_ROOT,
    _active_mcp_server_config_path,
    _env_flag,
    _env_name_list,
)
from backend.mcp_helpers.allowlist import (  # noqa: F401
    current_mcp_approved_connector_names,
)
from backend.mcp_helpers.policy import (  # noqa: F401
    default_mcp_connections,
    describe_mcp_server,
    evaluate_mcp_connector_policy,
    mcp_server_health_payload,
)
from backend.mcp_helpers.manifest import (  # noqa: F401
    load_mcp_connection_config,
)

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
