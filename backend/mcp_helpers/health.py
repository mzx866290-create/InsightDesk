"""health helpers for MCP connector management."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, cast

logger = logging.getLogger(__name__)


from backend.mcp_helpers.common import (  # noqa: F401
    PROJECT_ROOT,
    _env_flag,
    _env_name_list,
    _env_positive_float,
)
from backend.mcp_helpers.tools import (  # noqa: F401
    _wrap_mcp_tool,
)
from backend.mcp_helpers.allowlist import (  # noqa: F401
    current_mcp_approved_connector_names,
)
from backend.mcp_helpers.policy import (  # noqa: F401
    _runtime_mcp_connection,
    describe_mcp_server,
    evaluate_mcp_connector_policy,
    mcp_server_health_payload,
    normalize_mcp_server_names,
)
from backend.mcp_helpers.catalog import (  # noqa: F401
    _resolve_mcp_connections,
)

_runtime_mcp_health_history_lock = threading.RLock()
_runtime_mcp_health_history: list[dict[str, Any]] = []
def build_mcp_runtime_monitor_payload(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Normalize runtime-health payloads into a compact monitor contract."""

    raw_summary = payload.get("summary")
    summary: dict[str, Any] = dict(raw_summary) if isinstance(raw_summary, dict) else {}
    raw_alerts = summary.get("alerts")
    alerts = raw_alerts if isinstance(raw_alerts, list) else []
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

    raw_summary = payload.get("summary")
    summary: dict[str, Any] = dict(raw_summary) if isinstance(raw_summary, dict) else {}
    raw_servers = payload.get("servers")
    servers = raw_servers if isinstance(raw_servers, list) else []
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
        disabled_payload: dict[str, Any] = {
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
        disabled_payload["monitor"] = build_mcp_runtime_monitor_payload(disabled_payload)
        return attach_mcp_runtime_health_history(
            disabled_payload,
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
            unavailable_servers = [
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
            unavailable_payload: dict[str, Any] = {
                "status": "unavailable",
                "servers": unavailable_servers,
                "summary": {
                    "total": len(unavailable_servers),
                    "healthy": 0,
                    "unhealthy": len(unavailable_servers),
                    "tool_count": 0,
                    **summarize_mcp_runtime_health(unavailable_servers),
                },
            }
            unavailable_payload["monitor"] = build_mcp_runtime_monitor_payload(unavailable_payload)
            return attach_mcp_runtime_health_history(
                unavailable_payload,
                history_limit=history_limit,
                history_recorder=history_recorder,
                history_reader=history_reader,
            )
        client_factory = MultiServerMCPClient

    servers: list[dict[str, Any]] = []
    for name, connection in sorted(active_connections.items()):
        started_at = time.perf_counter()
        try:
            client = client_factory(cast(Any, {name: connection}), tool_name_prefix=False)
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
    tool_count = sum(int(str(item["tool_count"])) for item in servers)
    health_payload: dict[str, Any] = {
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
    health_payload["monitor"] = build_mcp_runtime_monitor_payload(health_payload)
    return attach_mcp_runtime_health_history(
        health_payload,
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
        client = client_factory(cast(Any, active_connections), tool_name_prefix=False)
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
