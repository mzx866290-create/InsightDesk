"""MCP runtime persistence helpers.

Keep app-config persistence and in-memory approval synchronization outside the
API server entrypoint so router wiring does not depend on private wrappers.
"""

from __future__ import annotations

import os
from typing import Any, Callable

from backend.agent_mcp_helpers import (
    add_mcp_approved_connector,
    normalize_mcp_approved_connectors,
    remove_mcp_approved_connector,
)
from backend.stores.config_store import (
    MCP_RUNTIME_HEALTH_HISTORY_CONFIG_KEY,
    SQLiteAppConfigStore,
    append_mcp_runtime_health_history,
    mcp_runtime_health_history_limit,
    read_mcp_runtime_health_history,
)

MCP_APPROVED_CONNECTORS_CONFIG_KEY = "mcp_approved_connectors"


def runtime_health_history_limit(raw_limit: Any = None) -> int:
    raw_value = (
        raw_limit
        if raw_limit is not None
        else os.getenv("MCP_RUNTIME_HEALTH_HISTORY_LIMIT")
    )
    return mcp_runtime_health_history_limit(raw_value)


def stored_runtime_health_history(
    store: SQLiteAppConfigStore,
    limit: Any = None,
    *,
    config_key: str = MCP_RUNTIME_HEALTH_HISTORY_CONFIG_KEY,
) -> list[dict[str, Any]]:
    return read_mcp_runtime_health_history(
        store,
        limit=runtime_health_history_limit(limit),
        config_key=config_key,
    )


def persist_runtime_health_history_item(
    store: SQLiteAppConfigStore,
    snapshot: dict[str, Any],
    history_limit: Any,
    *,
    config_key: str = MCP_RUNTIME_HEALTH_HISTORY_CONFIG_KEY,
) -> None:
    append_mcp_runtime_health_history(
        store,
        snapshot,
        limit=runtime_health_history_limit(history_limit),
        config_key=config_key,
    )


def runtime_health_history_payload(
    store: SQLiteAppConfigStore,
    *,
    limit: Any = 10,
    fallback_reader: Callable[[Any], dict[str, Any]],
    logger: Any,
    config_key: str = MCP_RUNTIME_HEALTH_HISTORY_CONFIG_KEY,
) -> dict[str, Any]:
    safe_limit = runtime_health_history_limit(limit)
    try:
        history = stored_runtime_health_history(
            store,
            safe_limit,
            config_key=config_key,
        )
        persistence_enabled = True
    except Exception:
        logger.exception("Failed to read persisted MCP runtime-health history")
        fallback_payload = fallback_reader(safe_limit)
        history = (
            list(fallback_payload.get("history", []))
            if isinstance(fallback_payload, dict)
            else list(fallback_payload or [])
        )
        persistence_enabled = False
    return {
        "history": history,
        "history_limit": safe_limit,
        "persistence": {
            "enabled": persistence_enabled,
            "config_key": config_key,
        },
    }


def stored_mcp_approved_connectors(
    store: SQLiteAppConfigStore,
    *,
    config_key: str = MCP_APPROVED_CONNECTORS_CONFIG_KEY,
) -> list[str]:
    raw_value = store.get_value(config_key, "")
    return normalize_mcp_approved_connectors(raw_value)


def persist_mcp_approved_connectors(
    store: SQLiteAppConfigStore,
    connector_names: Any,
    *,
    set_runtime_connectors: Callable[[Any], list[str]],
    config_key: str = MCP_APPROVED_CONNECTORS_CONFIG_KEY,
) -> list[str]:
    names = normalize_mcp_approved_connectors(connector_names)
    if names:
        store.set(config_key, ",".join(names))
    else:
        store.delete(config_key)
    set_runtime_connectors(names)
    return names


def hydrate_runtime_mcp_approved_connectors(
    store: SQLiteAppConfigStore,
    *,
    set_runtime_connectors: Callable[[Any], list[str]],
    config_key: str = MCP_APPROVED_CONNECTORS_CONFIG_KEY,
) -> list[str]:
    names = stored_mcp_approved_connectors(store, config_key=config_key)
    set_runtime_connectors(names)
    return names


def approvals_payload_with_persistence(
    store: SQLiteAppConfigStore,
    *,
    runtime_payload: Callable[[], dict[str, Any]],
    set_runtime_connectors: Callable[[Any], list[str]],
    config_key: str = MCP_APPROVED_CONNECTORS_CONFIG_KEY,
) -> dict[str, Any]:
    persisted = hydrate_runtime_mcp_approved_connectors(
        store,
        set_runtime_connectors=set_runtime_connectors,
        config_key=config_key,
    )
    payload = runtime_payload()
    payload["persisted_connectors"] = persisted
    payload["persistence"] = {
        "enabled": True,
        "config_key": config_key,
    }
    return payload


def approve_persisted_runtime_mcp_connector(
    store: SQLiteAppConfigStore,
    connector_name: Any,
    *,
    runtime_payload: Callable[[], dict[str, Any]],
    set_runtime_connectors: Callable[[Any], list[str]],
    config_key: str = MCP_APPROVED_CONNECTORS_CONFIG_KEY,
) -> dict[str, Any]:
    name = str(connector_name or "").strip()
    if not name:
        raise ValueError("connector name is required")
    before = stored_mcp_approved_connectors(store, config_key=config_key)
    updated = persist_mcp_approved_connectors(
        store,
        add_mcp_approved_connector(before, name),
        set_runtime_connectors=set_runtime_connectors,
        config_key=config_key,
    )
    payload = approvals_payload_with_persistence(
        store,
        runtime_payload=runtime_payload,
        set_runtime_connectors=set_runtime_connectors,
        config_key=config_key,
    )
    payload["connector"] = {
        "name": name,
        "changed": updated != before,
        "runtime_approved": name in payload["runtime_connectors"]
        or "*" in payload["runtime_connectors"],
        "effective_approved": name in payload["approved_connectors"]
        or "*" in payload["approved_connectors"],
    }
    return payload


def revoke_persisted_runtime_mcp_connector(
    store: SQLiteAppConfigStore,
    connector_name: Any,
    *,
    runtime_payload: Callable[[], dict[str, Any]],
    set_runtime_connectors: Callable[[Any], list[str]],
    config_key: str = MCP_APPROVED_CONNECTORS_CONFIG_KEY,
) -> dict[str, Any]:
    name = str(connector_name or "").strip()
    if not name:
        raise ValueError("connector name is required")
    before = stored_mcp_approved_connectors(store, config_key=config_key)
    updated = persist_mcp_approved_connectors(
        store,
        remove_mcp_approved_connector(before, name),
        set_runtime_connectors=set_runtime_connectors,
        config_key=config_key,
    )
    payload = approvals_payload_with_persistence(
        store,
        runtime_payload=runtime_payload,
        set_runtime_connectors=set_runtime_connectors,
        config_key=config_key,
    )
    payload["connector"] = {
        "name": name,
        "removed": updated != before,
        "runtime_approved": name in payload["runtime_connectors"]
        or "*" in payload["runtime_connectors"],
        "effective_approved": name in payload["approved_connectors"]
        or "*" in payload["approved_connectors"],
    }
    return payload
