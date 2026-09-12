"""allowlist helpers for MCP connector management."""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Iterable
from typing import Any

logger = logging.getLogger(__name__)



DEFAULT_MCP_SERVER_NAMES: list[str] = []
_runtime_mcp_approval_lock = threading.RLock()
_runtime_mcp_approved_connectors: list[str] = []
def parse_name_list(raw_value: Any) -> list[str]:
    if isinstance(raw_value, str):
        candidates: Iterable[Any] = raw_value.split(",")
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
