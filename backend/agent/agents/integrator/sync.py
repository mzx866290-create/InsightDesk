"""Dry-run sync artifact builder for external integrations."""

from __future__ import annotations

from typing import Any

from backend.agent.agents.integrator.push import summarize_payload


def build_sync_dry_run_artifact(
    *,
    task_id: str,
    connector: dict[str, Any],
    payload: Any,
    request: str,
    sync_direction: str,
) -> dict[str, Any]:
    content = {
        "operation_id": f"{task_id or 'integration'}:sync",
        "action": "sync",
        "dry_run": True,
        "would_sync": True,
        "direction": sync_direction,
        "connector": connector,
        "request": request,
        "payload": payload,
        "payload_summary": summarize_payload(payload),
    }
    return {
        "type": "integration_dry_run",
        "title": "Integration sync dry-run",
        "content": content,
    }


__all__ = ["build_sync_dry_run_artifact"]
