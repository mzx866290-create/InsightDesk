import asyncio
import json
import logging
import re
import time
import uuid
from typing import Any, Awaitable, Callable, MutableMapping, Optional

from api_task_store import TaskRecord, TaskStatus


def should_start_dashboard_task(
    user_message: Any,
    *,
    knowledge_base_enabled: bool,
    logger: logging.Logger,
) -> bool:
    if not knowledge_base_enabled:
        return False
    try:
        from agent_core import _should_generate_dashboard
    except Exception:
        logger.exception("Failed to import dashboard detection helper")
        return False
    try:
        return bool(_should_generate_dashboard(user_message))
    except Exception:
        logger.exception("Dashboard detection failed")
        return False


def contains_dashboard_card(content: str) -> bool:
    return ":::dashboard-card" in (content or "")


def summarize_dashboard_task_result(content: str) -> str:
    if not content:
        return "知识看板已生成。"

    match = re.search(r":::dashboard-card\s*\n([\s\S]*?)\n:::", content)
    if match:
        try:
            payload = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            payload = {}
        title = str(payload.get("title") or "").strip() if isinstance(payload, dict) else ""
        if title:
            return f"知识看板已生成：{title}"
    return "知识看板已生成。"


def summarize_dashboard_task_error(content: str) -> str:
    stripped = re.sub(r":::\w[\w-]*\s*\n[\s\S]*?:::", "", content or "").strip()
    if not stripped:
        return "知识看板生成失败。"
    compact = re.sub(r"\s+", " ", stripped)
    return compact[:160]


def is_terminal_task_status(status: TaskStatus) -> bool:
    return status in {TaskStatus.COMPLETED, TaskStatus.FAILED}


def prune_task_records(
    tasks: MutableMapping[str, TaskRecord],
    *,
    history_limit: int,
    ttl_seconds: int,
    now: float | None = None,
    logger: logging.Logger | None = None,
) -> int:
    current_time = time.time() if now is None else now
    removed = 0

    expired_task_ids = [
        task_id
        for task_id, task in tasks.items()
        if is_terminal_task_status(task.status)
        and current_time - task.updated_at > ttl_seconds
    ]
    for task_id in expired_task_ids:
        if tasks.pop(task_id, None) is not None:
            removed += 1

    if len(tasks) > history_limit:
        terminal_task_ids = [
            task_id
            for task_id, _ in sorted(
                (
                    (task_id, task)
                    for task_id, task in tasks.items()
                    if is_terminal_task_status(task.status)
                ),
                key=lambda item: item[1].updated_at,
            )
        ]
        while len(tasks) > history_limit and terminal_task_ids:
            task_id = terminal_task_ids.pop(0)
            if tasks.pop(task_id, None) is not None:
                removed += 1

    if removed and logger is not None:
        logger.info("Pruned %d task records; %d remain in memory", removed, len(tasks))
    return removed


async def create_inline_task_record(
    tasks: MutableMapping[str, TaskRecord],
    tasks_lock: asyncio.Lock,
    *,
    task_type: str,
    params: dict[str, Any],
    prune_in_memory: Callable[[float | None], None],
    persist_record: Callable[[TaskRecord], None],
    prune_persisted: Callable[[], None],
    session_id: Optional[str] = None,
    progress: int = 10,
) -> TaskRecord:
    task_id = str(uuid.uuid4())
    now = time.time()
    record = TaskRecord(
        task_id=task_id,
        task_type=task_type,
        status=TaskStatus.RUNNING,
        params=params,
        session_id=session_id,
        created_at=now,
        updated_at=now,
        progress=max(0, min(100, progress)),
    )
    async with tasks_lock:
        tasks[task_id] = record
        prune_in_memory(now)
    persist_record(record)
    prune_persisted()
    return record


async def set_inline_task_state(
    tasks: MutableMapping[str, TaskRecord],
    tasks_lock: asyncio.Lock,
    *,
    record: TaskRecord,
    status: TaskStatus,
    prune_in_memory: Callable[[float | None], None],
    persist_record: Callable[[TaskRecord], None],
    prune_persisted: Callable[[], None],
    progress: Optional[int] = None,
    result: Optional[str] = None,
    error: Optional[str] = None,
) -> TaskRecord:
    now = time.time()
    async with tasks_lock:
        existing = tasks.get(record.task_id) or record
        existing.status = status
        existing.updated_at = now
        if progress is not None:
            existing.progress = max(0, min(100, progress))
        if result is not None:
            existing.result = result
        if error is not None:
            existing.error = error
        record = existing
        tasks[record.task_id] = record
        prune_in_memory(now)
    persist_record(record)
    prune_persisted()
    return record
