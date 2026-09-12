"""config_store helpers for MCP connector management."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


from backend.mcp_helpers.common import (  # noqa: F401
    PROJECT_ROOT,
    _active_mcp_server_config_path,
)
from backend.mcp_helpers.allowlist import (  # noqa: F401
    default_mcp_server_names,
)
from backend.mcp_helpers.policy import (  # noqa: F401
    default_mcp_connections,
    list_mcp_connector_template_catalog,
)
from backend.mcp_helpers.manifest import (  # noqa: F401
    load_mcp_connection_config,
)
from backend.mcp_helpers.catalog import (  # noqa: F401
    build_mcp_connector_marketplace,
    list_mcp_server_catalog,
)
from backend.mcp_config_redaction import (  # noqa: F401
    _merge_redacted_mcp_config_value,
    redact_mcp_server_config,
)

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
