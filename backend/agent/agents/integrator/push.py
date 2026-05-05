"""Dry-run push artifact builder for external integrations."""

from __future__ import annotations

from typing import Any


def build_push_dry_run_artifact(
    *,
    task_id: str,
    connector: dict[str, Any],
    payload: Any,
    request: str,
) -> dict[str, Any]:
    content = {
        "operation_id": f"{task_id or 'integration'}:push",
        "action": "push",
        "dry_run": True,
        "would_send": True,
        "connector": connector,
        "request": request,
        "payload": payload,
        "payload_summary": summarize_payload(payload),
    }
    return {
        "type": "integration_dry_run",
        "title": "Integration push dry-run",
        "content": content,
    }


def summarize_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return {
            "kind": "object",
            "keys": sorted(str(key) for key in payload.keys()),
            "item_count": len(payload),
        }
    if isinstance(payload, list):
        return {"kind": "array", "item_count": len(payload)}
    text = str(payload or "").strip()
    return {
        "kind": "text",
        "char_count": len(text),
        "preview": text[:200],
    }


__all__ = ["build_push_dry_run_artifact", "summarize_payload"]
