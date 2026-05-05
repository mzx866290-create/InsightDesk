"""Task runtime helper utilities."""

import asyncio
import logging
import time
import uuid
from typing import Any, Awaitable, Callable, Optional

from backend.stores.task_store import TaskRecord, TaskStatus
from backend.tasks.backends import dispatch_task_record
from backend.tasks.health import task_stale_health_payload
from backend.tasks.settings import (
    arq_keep_result_from_env,
    arq_queue_name_from_env,
    arq_retry_defer_seconds_from_env,
    arq_retry_runtime_settings_from_env,
    arq_runtime_config_payload,
    arq_should_retry_failed_task,
    arq_should_start_task_record,
    arq_worker_drain_settings_from_env,
    arq_worker_max_jobs_from_env,
    arq_worker_runtime_settings_from_env,
    normalize_task_backend,
)


def task_record_payload(
    record: TaskRecord,
    *,
    params_override: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    return {
        "task_id": record.task_id,
        "status": record.status,
        "task_type": record.task_type,
        "progress": record.progress,
        "result": record.result,
        "error": record.error,
        "params": params_override if params_override is not None else record.params,
        "session_id": record.session_id,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def attach_current_kb_status(
    payload: dict[str, Any],
    *,
    vector_store_path: str,
    lookup_task: Callable[[str, str], TaskRecord | None],
) -> dict[str, Any]:
    attachments = list(payload.get("attachments") or [])
    summary = dict(payload.get("summary") or {})
    indexed_count = 0
    indexing_count = 0

    for attachment in attachments:
        status = "idle"
        task_id = None
        updated_at = None
        in_current_kb = False

        if str(attachment.get("kind") or "").strip() == "file":
            task = lookup_task(
                str(attachment.get("attachment_id") or "").strip(),
                vector_store_path,
            )
            if task is not None:
                status = task.status.value
                task_id = task.task_id
                updated_at = task.updated_at
                in_current_kb = task.status == TaskStatus.COMPLETED
                if in_current_kb:
                    indexed_count += 1
                elif task.status in {TaskStatus.PENDING, TaskStatus.RUNNING}:
                    indexing_count += 1

        attachment["current_vector_store_path"] = vector_store_path
        attachment["promotion_status"] = status
        attachment["promotion_task_id"] = task_id
        attachment["promotion_updated_at"] = updated_at
        attachment["is_in_current_kb"] = in_current_kb

    summary["indexed_in_current_kb_count"] = indexed_count
    summary["indexing_in_current_kb_count"] = indexing_count
    return {
        "attachments": attachments,
        "summary": summary,
        "current_vector_store_path": vector_store_path,
    }


async def enqueue_task(
    tasks: dict[str, TaskRecord],
    tasks_lock: asyncio.Lock,
    *,
    task_type: str,
    params: dict[str, Any],
    session_id: Optional[str],
    prune_in_memory: Callable[[float | None], None],
    persist_record: Callable[[TaskRecord], None],
    prune_persisted: Callable[[], None],
    run_task: Callable[[TaskRecord], Awaitable[None]],
    spawn_background_task: Callable[[Awaitable[None]], Any],
    logger: logging.Logger,
    on_record_created: Optional[Callable[[TaskRecord], None]] = None,
    task_backend: str | None = None,
    enqueue_external_task: Optional[Callable[[TaskRecord], Awaitable[Any]]] = None,
) -> dict[str, Any]:
    task_id = str(uuid.uuid4())
    now = time.time()
    record = TaskRecord(
        task_id=task_id,
        task_type=task_type,
        status=TaskStatus.PENDING,
        params=params,
        session_id=session_id,
        created_at=now,
        updated_at=now,
    )
    async with tasks_lock:
        tasks[task_id] = record
        prune_in_memory(now)
    persist_record(record)
    prune_persisted()
    if on_record_created is not None:
        try:
            on_record_created(record)
        except Exception:
            logger.exception("task_id=%s on_record_created callback failed", task_id)

    backend = await dispatch_task_record(
        record,
        task_backend=task_backend,
        run_task=run_task,
        spawn_background_task=spawn_background_task,
        enqueue_external_task=enqueue_external_task,
    )
    logger.info(
        "task_id=%s task_type=%s dispatched backend=%s",
        task_id,
        task_type,
        backend,
    )

    payload = task_record_payload(record)
    return {
        "task_id": payload["task_id"],
        "status": payload["status"],
        "task_type": payload["task_type"],
        "params": payload["params"],
        "session_id": payload["session_id"],
        "created_at": payload["created_at"],
    }


def list_tasks_payload(
    *,
    in_memory_tasks: list[TaskRecord],
    persisted_tasks: list[TaskRecord],
    limit: int,
    status_filter: str = "",
    queue_health: dict[str, Any] | None = None,
    runtime_config: dict[str, Any] | None = None,
    now: float | None = None,
    stale_thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    all_tasks_by_id = {task.task_id: task for task in persisted_tasks}
    for task in in_memory_tasks:
        all_tasks_by_id[task.task_id] = task

    all_tasks = list(all_tasks_by_id.values())
    normalized_status_filter = str(status_filter or "").strip().lower()
    if normalized_status_filter:
        all_tasks = [
            task
            for task in all_tasks
            if str(getattr(task, "status", "")).strip().lower() == normalized_status_filter
            or str(getattr(getattr(task, "status", None), "value", "")).strip().lower()
            == normalized_status_filter
        ]
    all_tasks.sort(key=lambda t: (t.updated_at, t.created_at), reverse=True)
    health = task_stale_health_payload(
        all_tasks,
        now=now,
        thresholds=stale_thresholds,
    )
    if queue_health is not None:
        health["queue"] = queue_health
    if runtime_config is not None:
        health["runtime"] = runtime_config
    health["summary"] = task_runtime_health_summary(health)
    return {
        "tasks": [task_record_payload(task) for task in all_tasks[:limit]],
        "health": health,
    }


def task_runtime_health_summary(health: dict[str, Any]) -> dict[str, Any]:
    """Build a single warning summary from stale tasks, queue and worker signals."""
    stale_warnings = list(health.get("warnings") or [])
    stale_warning_codes = [
        str(item.get("code") or "").strip()
        for item in stale_warnings
        if isinstance(item, dict) and str(item.get("code") or "").strip()
    ]

    queue = health.get("queue")
    queue_warnings: list[str] = []
    queue_status = None
    if isinstance(queue, dict):
        queue_status = str(queue.get("status") or "").strip() or None
        queue_warnings = [
            str(item).strip()
            for item in (queue.get("warnings") or [])
            if str(item).strip()
        ]

    runtime = health.get("runtime")
    retry_enabled = None
    drain_enabled = None
    heartbeat_enabled = None
    if isinstance(runtime, dict):
        retry = runtime.get("retry")
        worker = runtime.get("worker")
        if isinstance(retry, dict):
            retry_enabled = bool(retry.get("enabled"))
        if isinstance(worker, dict):
            drain = worker.get("drain")
            heartbeat = worker.get("heartbeat")
            if isinstance(drain, dict):
                drain_enabled = bool(drain.get("enabled"))
            if isinstance(heartbeat, dict):
                heartbeat_enabled = bool(heartbeat.get("enabled"))

    warning_codes = [*stale_warning_codes, *queue_warnings]
    queue_warning_count = (
        int(queue.get("warning_count") or len(queue_warnings))
        if isinstance(queue, dict)
        else 0
    )
    total_warning_count = int(health.get("warning_count") or 0)
    total_warning_count += queue_warning_count

    return {
        "status": "warning"
        if warning_codes or queue_status in {"warning", "unavailable"}
        else "ok",
        "warning_count": total_warning_count,
        "stale_warning_count": int(health.get("warning_count") or 0),
        "queue_warning_count": queue_warning_count,
        "warning_codes": warning_codes,
        "retry_enabled": retry_enabled,
        "worker_drain_enabled": drain_enabled,
        "worker_heartbeat_enabled": heartbeat_enabled,
    }


def arq_runtime_config_for_tasks() -> dict[str, Any]:
    """Compatibility wrapper used by task runtime code and focused tests."""
    return arq_runtime_config_payload()
