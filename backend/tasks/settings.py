"""Task backend and ARQ runtime configuration helpers."""

from __future__ import annotations

import os
from typing import Any, Literal, Mapping

TaskBackendName = Literal["memory", "arq"]
DEFAULT_TASK_BACKEND: TaskBackendName = "memory"
TASK_BACKEND_SWITCH_READY_ENV = "TASK_BACKEND_SWITCH_READY"
DEFAULT_ARQ_QUEUE_NAME = "insightdesk:tasks"
DEFAULT_ARQ_WORKER_MAX_JOBS = 4
DEFAULT_ARQ_KEEP_RESULT_SECONDS = 3600
DEFAULT_ARQ_RETRY_ATTEMPTS = 3
DEFAULT_ARQ_RETRY_BACKOFF_SECONDS = 15
DEFAULT_ARQ_WORKER_HEARTBEAT_SECONDS = 30
DEFAULT_ARQ_WORKER_HEARTBEAT_KEY = f"{DEFAULT_ARQ_QUEUE_NAME}:worker:heartbeat"
DEFAULT_ARQ_WORKER_DRAIN_SECONDS = 30
DEFAULT_ARQ_PENDING_STALE_SECONDS = 600
DEFAULT_ARQ_RUNNING_STALE_SECONDS = 1800
DEFAULT_ARQ_QUEUE_WARNING_LENGTH = 100

_DISABLED_CONFIG_VALUES = {"0", "false", "off", "none", "disabled"}


def normalize_task_backend(value: str | None = None) -> TaskBackendName:
    """Normalize task backend config while keeping memory as the safe default."""
    raw = str(value if value is not None else os.getenv("TASK_BACKEND", DEFAULT_TASK_BACKEND)).strip().lower()
    if raw in {"", "memory", "inline", "local"}:
        return "memory"
    if raw in {"arq", "redis"}:
        return "arq"
    raise ValueError(f"Unsupported TASK_BACKEND: {value}")


def task_backend_from_env() -> TaskBackendName:
    return normalize_task_backend(os.getenv("TASK_BACKEND", DEFAULT_TASK_BACKEND))


def task_backend_default_switch_contract_from_env() -> dict[str, Any]:
    """Return the documented contract for switching the production default to ARQ."""
    switch_gate = str(os.getenv(TASK_BACKEND_SWITCH_READY_ENV) or "").strip().lower()
    explicit_backend = str(os.getenv("TASK_BACKEND") or "").strip()
    switch_ready = switch_gate in {"1", "true", "yes", "on"}
    return {
        "current_default": DEFAULT_TASK_BACKEND,
        "target_default": "arq",
        "effective_backend": task_backend_from_env(),
        "explicit_task_backend": explicit_backend or None,
        "switch_gate_env": TASK_BACKEND_SWITCH_READY_ENV,
        "switch_ready": switch_ready,
        "decision": "keep_memory_default" if not switch_ready else "eligible_for_arq_default",
        "required_closure": [
            "arq_long_running_validation",
            "arq_drain_drill_report",
            "ops_readiness_include_real",
        ],
    }


def arq_queue_name_from_env() -> str:
    return str(os.getenv("ARQ_QUEUE_NAME") or DEFAULT_ARQ_QUEUE_NAME).strip() or DEFAULT_ARQ_QUEUE_NAME


def _positive_int_from_env(name: str, default: int) -> int:
    raw = str(os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _non_negative_int_from_env(name: str, default: int) -> int:
    raw = str(os.getenv(name) or "").strip()
    if not raw:
        return default
    if raw.lower() in _DISABLED_CONFIG_VALUES:
        return 0
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a non-negative integer") from exc
    if value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def arq_worker_max_jobs_from_env() -> int:
    return _positive_int_from_env("ARQ_WORKER_MAX_JOBS", DEFAULT_ARQ_WORKER_MAX_JOBS)


def arq_keep_result_from_env() -> int:
    return _positive_int_from_env("ARQ_KEEP_RESULT_SECONDS", DEFAULT_ARQ_KEEP_RESULT_SECONDS)


def arq_retry_attempts_from_env() -> int:
    return _non_negative_int_from_env("ARQ_RETRY_ATTEMPTS", DEFAULT_ARQ_RETRY_ATTEMPTS)


def arq_retry_backoff_seconds_from_env() -> int:
    return _non_negative_int_from_env(
        "ARQ_RETRY_BACKOFF_SECONDS",
        DEFAULT_ARQ_RETRY_BACKOFF_SECONDS,
    )


def arq_retry_config_from_env() -> dict[str, Any]:
    attempts = arq_retry_attempts_from_env()
    backoff_seconds = arq_retry_backoff_seconds_from_env()
    retries = max(0, attempts - 1)
    return {
        "enabled": attempts > 1,
        "attempts": attempts,
        "max_retries": retries,
        "backoff_seconds": backoff_seconds,
        "strategy": "fixed" if retries > 0 and backoff_seconds > 0 else "none",
    }


def arq_retry_runtime_settings_from_env() -> dict[str, Any]:
    """Return ARQ worker retry settings derived from retry policy env vars."""
    attempts = arq_retry_attempts_from_env()
    effective_attempts = max(1, attempts)
    return {
        "max_tries": effective_attempts,
        "retry_jobs": attempts > 1,
    }


def arq_retry_defer_seconds_from_env() -> int:
    """Return the defer delay used when re-queueing a failed persisted task."""
    retry_config = arq_retry_config_from_env()
    if retry_config["strategy"] != "fixed":
        return 0
    return int(retry_config["backoff_seconds"])


def arq_should_retry_failed_task(
    *,
    status: Any,
    job_try: Any,
    retry_config: Mapping[str, Any] | None = None,
) -> bool:
    """Decide whether an ARQ task that persisted as failed should be retried."""
    normalized_status = str(getattr(status, "value", status) or "").strip().lower()
    if normalized_status != "failed":
        return False

    config = dict(retry_config or arq_retry_config_from_env())
    if not bool(config.get("enabled")):
        return False

    try:
        current_try = int(job_try or 1)
        attempts = int(config.get("attempts") or 0)
    except (TypeError, ValueError):
        return False
    return current_try < attempts


def arq_should_start_task_record(
    *,
    status: Any,
    job_try: Any = None,
    retry_config: Mapping[str, Any] | None = None,
) -> bool:
    """Decide whether an ARQ worker delivery should execute a persisted task."""
    normalized_status = str(getattr(status, "value", status) or "").strip().lower()
    if normalized_status == "pending":
        return True
    if normalized_status != "failed":
        return False

    config = dict(retry_config or arq_retry_config_from_env())
    if not bool(config.get("enabled")):
        return False

    try:
        current_try = int(job_try or 1)
        attempts = int(config.get("attempts") or 0)
    except (TypeError, ValueError):
        return False
    return current_try > 1 and current_try <= attempts


def arq_worker_drain_seconds_from_env() -> int:
    return _non_negative_int_from_env(
        "ARQ_WORKER_DRAIN_SECONDS",
        DEFAULT_ARQ_WORKER_DRAIN_SECONDS,
    )


def arq_worker_drain_config_from_env() -> dict[str, Any]:
    drain_seconds = arq_worker_drain_seconds_from_env()
    return {
        "enabled": drain_seconds > 0,
        "graceful_shutdown": drain_seconds > 0,
        "drain_seconds": drain_seconds,
        "job_completion_wait_seconds": drain_seconds,
    }


def arq_worker_drain_settings_from_env() -> dict[str, int]:
    """Return ARQ worker shutdown settings derived from drain policy env vars."""
    return {"job_completion_wait": arq_worker_drain_seconds_from_env()}


def build_arq_worker_heartbeat_key(queue_name: str | None = None) -> str:
    """Build the Redis key used by ARQ's worker health-check sentinel."""
    normalized_queue = str(queue_name or DEFAULT_ARQ_QUEUE_NAME).strip() or DEFAULT_ARQ_QUEUE_NAME
    return f"{normalized_queue}:worker:heartbeat"


def arq_worker_heartbeat_key_from_env(queue_name: str | None = None) -> str:
    raw = os.getenv("ARQ_WORKER_HEARTBEAT_KEY")
    if raw is not None:
        value = str(raw).strip()
        if value.lower() in _DISABLED_CONFIG_VALUES:
            return ""
        if value:
            return value
    return build_arq_worker_heartbeat_key(queue_name)


def arq_worker_heartbeat_seconds_from_env() -> int:
    return _non_negative_int_from_env(
        "ARQ_WORKER_HEARTBEAT_SECONDS",
        DEFAULT_ARQ_WORKER_HEARTBEAT_SECONDS,
    )


def arq_pending_stale_seconds_from_env() -> int:
    return _non_negative_int_from_env(
        "ARQ_PENDING_STALE_SECONDS",
        DEFAULT_ARQ_PENDING_STALE_SECONDS,
    )


def arq_running_stale_seconds_from_env() -> int:
    return _non_negative_int_from_env(
        "ARQ_RUNNING_STALE_SECONDS",
        DEFAULT_ARQ_RUNNING_STALE_SECONDS,
    )


def arq_queue_warning_length_from_env() -> int:
    return _non_negative_int_from_env(
        "ARQ_QUEUE_WARNING_LENGTH",
        DEFAULT_ARQ_QUEUE_WARNING_LENGTH,
    )


def arq_task_stale_thresholds_from_env() -> dict[str, int]:
    """Return pending/running task stale thresholds in seconds."""
    return {
        "pending_stale_seconds": arq_pending_stale_seconds_from_env(),
        "running_stale_seconds": arq_running_stale_seconds_from_env(),
    }


def arq_worker_heartbeat_ttl_seconds(heartbeat_seconds: int) -> int:
    if heartbeat_seconds < 0:
        raise ValueError("heartbeat_seconds must be a non-negative integer")
    if heartbeat_seconds == 0:
        return 0
    # ARQ stores the health-check key with interval + 1s TTL.
    return heartbeat_seconds + 1


def arq_worker_heartbeat_enabled(key: str, heartbeat_seconds: int) -> bool:
    return bool(str(key or "").strip()) and heartbeat_seconds > 0


def arq_worker_heartbeat_settings_from_env(queue_name: str | None = None) -> dict[str, int | str]:
    heartbeat_seconds = arq_worker_heartbeat_seconds_from_env()
    heartbeat_key = arq_worker_heartbeat_key_from_env(queue_name=queue_name)
    if not arq_worker_heartbeat_enabled(
        key=heartbeat_key,
        heartbeat_seconds=heartbeat_seconds,
    ):
        return {}
    return {
        "health_check_interval": heartbeat_seconds,
        "health_check_key": heartbeat_key,
    }


def arq_worker_heartbeat_config_from_env(queue_name: str | None = None) -> dict[str, Any]:
    heartbeat_seconds = arq_worker_heartbeat_seconds_from_env()
    heartbeat_key = arq_worker_heartbeat_key_from_env(queue_name=queue_name)
    enabled = arq_worker_heartbeat_enabled(
        key=heartbeat_key,
        heartbeat_seconds=heartbeat_seconds,
    )
    return {
        "enabled": enabled,
        "key": heartbeat_key,
        "interval_seconds": heartbeat_seconds,
        "expected_ttl_seconds": arq_worker_heartbeat_ttl_seconds(heartbeat_seconds),
    }


def arq_worker_runtime_settings_from_env(queue_name: str | None = None) -> dict[str, Any]:
    """Return ARQ WorkerSettings-compatible runtime settings."""
    return {
        "max_jobs": arq_worker_max_jobs_from_env(),
        "keep_result": arq_keep_result_from_env(),
        **arq_retry_runtime_settings_from_env(),
        **arq_worker_drain_settings_from_env(),
        **arq_worker_heartbeat_settings_from_env(queue_name=queue_name),
    }


def arq_runtime_config_payload(queue_name: str | None = None) -> dict[str, Any]:
    """Return ARQ runtime policy config without touching Redis."""
    resolved_queue_name = str(queue_name or arq_queue_name_from_env()).strip()
    return {
        "backend": "arq",
        "queue_name": resolved_queue_name,
        "retry": arq_retry_config_from_env(),
        "worker": {
            "max_jobs": arq_worker_max_jobs_from_env(),
            "keep_result_seconds": arq_keep_result_from_env(),
            "heartbeat": arq_worker_heartbeat_config_from_env(
                queue_name=resolved_queue_name
            ),
            "drain": arq_worker_drain_config_from_env(),
        },
    }


__all__ = [
    "DEFAULT_ARQ_KEEP_RESULT_SECONDS",
    "DEFAULT_ARQ_PENDING_STALE_SECONDS",
    "DEFAULT_ARQ_QUEUE_NAME",
    "DEFAULT_ARQ_QUEUE_WARNING_LENGTH",
    "DEFAULT_ARQ_RETRY_ATTEMPTS",
    "DEFAULT_ARQ_RETRY_BACKOFF_SECONDS",
    "DEFAULT_ARQ_RUNNING_STALE_SECONDS",
    "DEFAULT_ARQ_WORKER_DRAIN_SECONDS",
    "DEFAULT_ARQ_WORKER_HEARTBEAT_KEY",
    "DEFAULT_ARQ_WORKER_HEARTBEAT_SECONDS",
    "DEFAULT_ARQ_WORKER_MAX_JOBS",
    "DEFAULT_TASK_BACKEND",
    "TASK_BACKEND_SWITCH_READY_ENV",
    "TaskBackendName",
    "arq_keep_result_from_env",
    "arq_pending_stale_seconds_from_env",
    "arq_queue_name_from_env",
    "arq_queue_warning_length_from_env",
    "arq_retry_attempts_from_env",
    "arq_retry_backoff_seconds_from_env",
    "arq_retry_config_from_env",
    "arq_retry_defer_seconds_from_env",
    "arq_retry_runtime_settings_from_env",
    "arq_running_stale_seconds_from_env",
    "arq_runtime_config_payload",
    "arq_should_retry_failed_task",
    "arq_should_start_task_record",
    "arq_task_stale_thresholds_from_env",
    "arq_worker_drain_config_from_env",
    "arq_worker_drain_seconds_from_env",
    "arq_worker_drain_settings_from_env",
    "arq_worker_heartbeat_config_from_env",
    "arq_worker_heartbeat_enabled",
    "arq_worker_heartbeat_key_from_env",
    "arq_worker_heartbeat_seconds_from_env",
    "arq_worker_heartbeat_settings_from_env",
    "arq_worker_heartbeat_ttl_seconds",
    "arq_worker_max_jobs_from_env",
    "arq_worker_runtime_settings_from_env",
    "build_arq_worker_heartbeat_key",
    "normalize_task_backend",
    "task_backend_default_switch_contract_from_env",
    "task_backend_from_env",
]
