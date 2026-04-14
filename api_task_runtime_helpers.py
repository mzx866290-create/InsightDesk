import asyncio
import logging
import time
import uuid
from typing import Any, Awaitable, Callable, Optional

from api_task_store import TaskRecord, TaskStatus


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

    spawn_background_task(run_task(record))
    logger.info("task_id=%s task_type=%s created", task_id, task_type)

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
) -> dict[str, Any]:
    all_tasks_by_id = {task.task_id: task for task in persisted_tasks}
    for task in in_memory_tasks:
        all_tasks_by_id[task.task_id] = task

    all_tasks = list(all_tasks_by_id.values())
    all_tasks.sort(key=lambda t: (t.updated_at, t.created_at), reverse=True)
    return {"tasks": [task_record_payload(task) for task in all_tasks[:limit]]}
