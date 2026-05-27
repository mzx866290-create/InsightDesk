"""Helpers for task approval policy persistence and normalization."""

import json
import logging
from typing import Any

from fastapi import HTTPException

TASK_APPROVAL_POLICY_CONFIG_KEY = "task_approval_policy"
DEFAULT_TASK_APPROVAL_POLICY: dict[str, Any] = {
    "enabled": False,
    "required_task_types": [],
    "high_risk_requires_approval": True,
    "default_reviewer_role": "admin",
    "updated_at": None,
}


def task_approval_policy_source(raw_policy: Any) -> dict[str, Any]:
    if hasattr(raw_policy, "model_dump"):
        payload = raw_policy.model_dump()
        return dict(payload) if isinstance(payload, dict) else {}
    if hasattr(raw_policy, "dict"):
        payload = raw_policy.dict()
        return dict(payload) if isinstance(payload, dict) else {}
    if isinstance(raw_policy, dict):
        return dict(raw_policy)
    return {}


def normalize_task_approval_policy(raw_policy: Any) -> dict[str, Any]:
    data = task_approval_policy_source(raw_policy)

    task_types: list[str] = []
    seen_task_types: set[str] = set()
    raw_task_types = data.get("required_task_types")
    if isinstance(raw_task_types, list):
        for raw_task_type in raw_task_types:
            task_type = str(raw_task_type or "").strip()
            if not task_type or task_type in seen_task_types:
                continue
            task_types.append(task_type)
            seen_task_types.add(task_type)
    if len(task_types) > 20:
        raise HTTPException(
            status_code=400,
            detail="required_task_types must contain at most 20 items.",
        )

    reviewer_role = str(data.get("default_reviewer_role") or "").strip() or "admin"
    return {
        "enabled": bool(data.get("enabled", False)),
        "required_task_types": task_types,
        "high_risk_requires_approval": bool(
            data.get("high_risk_requires_approval", True)
        ),
        "default_reviewer_role": reviewer_role,
        "updated_at": data.get("updated_at"),
    }


def load_task_approval_policy_payload(
    config_store: Any,
    logger: logging.Logger,
    *,
    config_key: str = TASK_APPROVAL_POLICY_CONFIG_KEY,
) -> dict[str, Any]:
    record = config_store.get(config_key)
    if record is None:
        return dict(DEFAULT_TASK_APPROVAL_POLICY)
    try:
        stored_policy = json.loads(str(getattr(record, "value", "") or "{}"))
    except json.JSONDecodeError:
        logger.warning("Stored task approval policy is not valid JSON")
        return dict(DEFAULT_TASK_APPROVAL_POLICY)
    payload = normalize_task_approval_policy(stored_policy)
    payload["updated_at"] = float(getattr(record, "updated_at", 0.0) or 0.0) or None
    return payload


def save_task_approval_policy_payload(
    config_store: Any,
    raw_policy: Any,
    *,
    config_key: str = TASK_APPROVAL_POLICY_CONFIG_KEY,
) -> dict[str, Any]:
    payload = normalize_task_approval_policy(raw_policy)
    payload.pop("updated_at", None)
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    record = config_store.set(config_key, encoded)
    payload["updated_at"] = float(getattr(record, "updated_at", 0.0) or 0.0) or None
    return payload
