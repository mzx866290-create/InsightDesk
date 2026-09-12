"""manifest helpers for MCP connector management."""

from __future__ import annotations

import json
import logging
import os
import shlex
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


from backend.mcp_helpers.common import (  # noqa: F401
    MCP_CONNECTOR_NAME_PATTERN,
    MCP_RISK_LEVELS,
    McpConnectorManifestError,
    PROJECT_ROOT,
    _active_mcp_server_config_path,
)
from backend.mcp_helpers.allowlist import (  # noqa: F401
    normalize_mcp_connector_name,
    parse_name_list,
)
from backend.mcp_helpers.policy import (  # noqa: F401
    _normalize_bool,
    describe_mcp_server,
)

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

    raw_metadata = manifest.get("metadata")
    metadata: dict[str, Any] = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
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
    # deferred: config_store payloads call back into this module
    from backend.mcp_helpers.config_store import save_mcp_server_config_payload


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
