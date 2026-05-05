"""Compatibility helpers for runtime app config storage."""

from __future__ import annotations

import json
import time
from typing import Any

from backend.stores.config_store import SQLiteAppConfigStore, StoredConfigValue

MCP_RUNTIME_HEALTH_HISTORY_CONFIG_KEY = "mcp_runtime_health_history"


def mcp_runtime_health_history_limit(raw_limit: Any = None) -> int:
    try:
        limit = int(raw_limit or 20)
    except (TypeError, ValueError):
        limit = 20
    return min(200, max(1, limit))


def sanitize_mcp_runtime_health_history_item(item: Any) -> dict[str, Any] | None:
    """Keep runtime health history compact and secret-free."""

    if not isinstance(item, dict):
        return None

    summary = item.get("summary") if isinstance(item.get("summary"), dict) else {}
    servers = item.get("servers") if isinstance(item.get("servers"), list) else []
    try:
        timestamp = float(item.get("timestamp") or 0.0)
    except (TypeError, ValueError):
        timestamp = time.time()

    return {
        "timestamp": timestamp,
        "status": str(item.get("status") or "unknown"),
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


def read_mcp_runtime_health_history(
    store: SQLiteAppConfigStore,
    *,
    limit: Any = None,
    config_key: str = MCP_RUNTIME_HEALTH_HISTORY_CONFIG_KEY,
) -> list[dict[str, Any]]:
    safe_limit = mcp_runtime_health_history_limit(limit)
    raw_value = store.get_value(config_key, "[]")
    try:
        decoded = json.loads(raw_value or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        decoded = []
    if not isinstance(decoded, list):
        decoded = []

    history: list[dict[str, Any]] = []
    for item in decoded:
        sanitized = sanitize_mcp_runtime_health_history_item(item)
        if sanitized is not None:
            history.append(sanitized)
        if len(history) >= safe_limit:
            break
    return history


def append_mcp_runtime_health_history(
    store: SQLiteAppConfigStore,
    snapshot: dict[str, Any],
    *,
    limit: Any = None,
    config_key: str = MCP_RUNTIME_HEALTH_HISTORY_CONFIG_KEY,
) -> list[dict[str, Any]]:
    safe_limit = mcp_runtime_health_history_limit(limit)
    sanitized = sanitize_mcp_runtime_health_history_item(snapshot)
    if sanitized is None:
        return read_mcp_runtime_health_history(
            store,
            limit=safe_limit,
            config_key=config_key,
        )

    history = [
        sanitized,
        *read_mcp_runtime_health_history(
            store,
            limit=safe_limit,
            config_key=config_key,
        ),
    ][:safe_limit]
    store.set(
        config_key,
        json.dumps(history, ensure_ascii=False, separators=(",", ":")),
    )
    return history


__all__ = [
    "MCP_RUNTIME_HEALTH_HISTORY_CONFIG_KEY",
    "SQLiteAppConfigStore",
    "StoredConfigValue",
    "append_mcp_runtime_health_history",
    "mcp_runtime_health_history_limit",
    "read_mcp_runtime_health_history",
    "sanitize_mcp_runtime_health_history_item",
]
