"""Task queue and stale task health payload helpers."""

from __future__ import annotations

import time
from typing import Any, Iterable, Mapping

from backend.stores.task_store import TaskRecord
from backend.tasks.enqueue import (
    _close_redis_pool,
    _redis_int_call,
    _redis_settings_from_env,
)
from backend.tasks.settings import (
    arq_queue_name_from_env,
    arq_queue_warning_length_from_env,
    arq_task_stale_thresholds_from_env,
    arq_worker_heartbeat_enabled,
    arq_worker_heartbeat_key_from_env,
    arq_worker_heartbeat_seconds_from_env,
    arq_worker_heartbeat_ttl_seconds,
)


def _normalize_task_stale_thresholds(
    thresholds: Mapping[str, Any] | None = None,
) -> dict[str, int]:
    if thresholds is None:
        return arq_task_stale_thresholds_from_env()

    normalized: dict[str, int] = {}
    for key in ("pending_stale_seconds", "running_stale_seconds"):
        raw = thresholds.get(key, 0)
        try:
            value = int(raw or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be a non-negative integer") from exc
        if value < 0:
            raise ValueError(f"{key} must be a non-negative integer")
        normalized[key] = value
    return normalized


def _task_status_value(record: TaskRecord) -> str:
    status = getattr(record, "status", "")
    return str(getattr(status, "value", status)).strip().lower()


def _positive_timestamp(value: Any) -> float | None:
    try:
        timestamp = float(value or 0)
    except (TypeError, ValueError):
        return None
    if timestamp <= 0:
        return None
    return timestamp


def task_stale_warning_payloads(
    records: Iterable[TaskRecord],
    *,
    now: float | None = None,
    thresholds: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build lightweight stale task warning payloads without touching Redis."""
    current_time = time.time() if now is None else float(now)
    resolved_thresholds = _normalize_task_stale_thresholds(thresholds)
    records_by_id: dict[str, TaskRecord] = {}
    for record in records:
        task_id = str(getattr(record, "task_id", "") or "").strip()
        if task_id:
            records_by_id[task_id] = record

    warnings: list[dict[str, Any]] = []
    for record in records_by_id.values():
        status = _task_status_value(record)
        if status == "pending":
            threshold_seconds = resolved_thresholds["pending_stale_seconds"]
            reference_at = _positive_timestamp(getattr(record, "created_at", None))
            code = "task_pending_stale"
        elif status == "running":
            threshold_seconds = resolved_thresholds["running_stale_seconds"]
            reference_at = _positive_timestamp(getattr(record, "updated_at", None))
            code = "task_running_stale"
        else:
            continue

        if threshold_seconds <= 0 or reference_at is None:
            continue

        stale_seconds = max(0.0, current_time - reference_at)
        if stale_seconds <= threshold_seconds:
            continue

        warnings.append(
            {
                "code": code,
                "severity": "warning",
                "task_id": str(record.task_id),
                "task_type": str(getattr(record, "task_type", "") or ""),
                "status": status,
                "threshold_seconds": threshold_seconds,
                "stale_seconds": round(stale_seconds, 3),
                "reference_at": reference_at,
                "created_at": getattr(record, "created_at", None),
                "updated_at": getattr(record, "updated_at", None),
            }
        )

    warnings.sort(key=lambda item: (-float(item["stale_seconds"]), str(item["task_id"])))
    return warnings


def task_stale_health_payload(
    records: Iterable[TaskRecord],
    *,
    now: float | None = None,
    thresholds: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Summarize stale pending/running task warnings for task runtime payloads."""
    resolved_thresholds = _normalize_task_stale_thresholds(thresholds)
    warnings = task_stale_warning_payloads(
        records,
        now=now,
        thresholds=resolved_thresholds,
    )
    pending_warning_count = sum(1 for item in warnings if item["status"] == "pending")
    running_warning_count = sum(1 for item in warnings if item["status"] == "running")
    return {
        "enabled": any(value > 0 for value in resolved_thresholds.values()),
        "warning_count": len(warnings),
        "pending_warning_count": pending_warning_count,
        "running_warning_count": running_warning_count,
        "warnings": warnings,
        "thresholds": resolved_thresholds,
    }


async def arq_queue_health_payload(
    *,
    redis: Any | None = None,
    queue_name: str | None = None,
    warning_length: int | None = None,
    heartbeat_key: str | None = None,
    heartbeat_seconds: int | None = None,
    close_redis: bool = True,
) -> dict[str, Any]:
    """Read Redis-backed ARQ queue length and worker heartbeat state."""
    resolved_queue_name = str(queue_name or arq_queue_name_from_env()).strip()
    resolved_warning_length = (
        arq_queue_warning_length_from_env()
        if warning_length is None
        else int(warning_length)
    )
    if resolved_warning_length < 0:
        raise ValueError("warning_length must be a non-negative integer")

    resolved_heartbeat_seconds = (
        arq_worker_heartbeat_seconds_from_env()
        if heartbeat_seconds is None
        else int(heartbeat_seconds)
    )
    resolved_heartbeat_key = (
        arq_worker_heartbeat_key_from_env(queue_name=resolved_queue_name)
        if heartbeat_key is None
        else str(heartbeat_key or "").strip()
    )
    heartbeat_enabled = arq_worker_heartbeat_enabled(
        key=resolved_heartbeat_key,
        heartbeat_seconds=resolved_heartbeat_seconds,
    )

    owns_redis = redis is None
    if redis is None:
        try:
            from arq import create_pool
        except ModuleNotFoundError as exc:
            return _unavailable_queue_health_payload(
                resolved_queue_name,
                resolved_warning_length,
                heartbeat_enabled=heartbeat_enabled,
                heartbeat_key=resolved_heartbeat_key,
                heartbeat_seconds=resolved_heartbeat_seconds,
                error=str(exc),
            )
        try:
            redis = await create_pool(
                _redis_settings_from_env(),
                default_queue_name=resolved_queue_name,
            )
        except Exception as exc:
            return _unavailable_queue_health_payload(
                resolved_queue_name,
                resolved_warning_length,
                heartbeat_enabled=heartbeat_enabled,
                heartbeat_key=resolved_heartbeat_key,
                heartbeat_seconds=resolved_heartbeat_seconds,
                error=str(exc),
            )

    try:
        queue_length = await _redis_int_call(redis, "zcard", resolved_queue_name)
        heartbeat_exists = None
        heartbeat_ttl = None
        if heartbeat_enabled:
            heartbeat_exists_value = await _redis_int_call(redis, "exists", resolved_heartbeat_key)
            heartbeat_exists = bool(heartbeat_exists_value)
            heartbeat_ttl = await _redis_int_call(redis, "ttl", resolved_heartbeat_key)

        warning_codes: list[str] = []
        if queue_length is not None and resolved_warning_length > 0:
            if queue_length > resolved_warning_length:
                warning_codes.append("arq_queue_backlog")
        if heartbeat_enabled and heartbeat_exists is False:
            warning_codes.append("arq_worker_heartbeat_missing")

        return {
            "enabled": True,
            "status": "warning" if warning_codes else "ok",
            "queue_name": resolved_queue_name,
            "length": queue_length,
            "warning_length": resolved_warning_length,
            "warning_count": len(warning_codes),
            "warnings": warning_codes,
            "heartbeat": {
                "enabled": heartbeat_enabled,
                "key": resolved_heartbeat_key,
                "ttl_seconds": heartbeat_ttl,
                "present": heartbeat_exists,
                "expected_ttl_seconds": arq_worker_heartbeat_ttl_seconds(
                    resolved_heartbeat_seconds
                ),
            },
        }
    except Exception as exc:
        return _unavailable_queue_health_payload(
            resolved_queue_name,
            resolved_warning_length,
            heartbeat_enabled=heartbeat_enabled,
            heartbeat_key=resolved_heartbeat_key,
            heartbeat_seconds=resolved_heartbeat_seconds,
            error=str(exc),
        )
    finally:
        if owns_redis and close_redis:
            await _close_redis_pool(redis)


def _unavailable_queue_health_payload(
    queue_name: str,
    warning_length: int,
    *,
    heartbeat_enabled: bool,
    heartbeat_key: str,
    heartbeat_seconds: int,
    error: str,
) -> dict[str, Any]:
    return {
        "enabled": True,
        "status": "unavailable",
        "queue_name": queue_name,
        "length": None,
        "warning_length": warning_length,
        "warning_count": 1,
        "warnings": ["arq_queue_health_unavailable"],
        "heartbeat": {
            "enabled": heartbeat_enabled,
            "key": heartbeat_key,
            "ttl_seconds": None,
            "present": None,
            "expected_ttl_seconds": arq_worker_heartbeat_ttl_seconds(
                heartbeat_seconds
            ),
        },
        "error": error,
    }


__all__ = [
    "arq_queue_health_payload",
    "task_stale_health_payload",
    "task_stale_warning_payloads",
]
