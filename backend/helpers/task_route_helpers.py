"""Route-level helpers for task endpoints."""

import asyncio
import time
from typing import Any, Awaitable, Callable, Coroutine, Optional, cast

from fastapi import HTTPException, Request

from backend.helpers.task_approval_route_helpers import (
    TASK_NOT_FOUND_DETAIL,
    apply_approval_decision_to_record,
    approval_decision_value,
    ensure_task_accepts_approval_decision,
)
from backend.tasks.backends import dispatch_task_record


def filter_visible_task_records(
    records: list[Any],
    request: Request,
    *,
    require_session_access: Callable[[Request, str, str], dict[str, Any]],
    require_remote_viewer: Callable[[Request], dict[str, Any]],
) -> list[Any]:
    visible_records: list[Any] = []
    for record in records:
        session_id = str(getattr(record, "session_id", "") or "").strip()
        if session_id:
            try:
                require_session_access(request, session_id, "viewer")
            except HTTPException as exc:
                if exc.status_code == 403:
                    continue
                raise
        else:
            require_remote_viewer(request)
        visible_records.append(record)
    return visible_records


def spawn_background_task(coro: Awaitable[None]) -> Any:
    return asyncio.create_task(cast(Coroutine[Any, Any, None], coro))


def resolve_task_backend_value(task_backend: str | Callable[[], str]) -> str:
    value = task_backend() if callable(task_backend) else task_backend
    return str(value or "memory").strip().lower() or "memory"


async def create_background_task_result(
    *,
    http_request: Request,
    task_type: str,
    params: dict[str, Any],
    session_id: Optional[str] = None,
    on_record_created: Callable[..., None] | None = None,
    resolve_tasks: Callable[[], dict[str, Any]],
    tasks_lock: Any,
    enqueue_task: Callable[..., Awaitable[dict[str, Any]]],
    prune_task_records_locked: Callable[..., None],
    persist_task_record: Callable[..., None],
    prune_persisted_tasks: Callable[[], None],
    run_task: Callable[..., Awaitable[None]],
    logger: Any,
    task_backend: str,
    enqueue_external_task: Callable[[Any], Awaitable[Any]] | None,
    require_session_access: Callable[[Request, str, str], dict[str, Any]],
    require_remote_editor: Callable[[Request], dict[str, Any]],
    grant_derived_resource_access: Callable[..., Any],
    access_store: Any,
    audit_security_event: Callable[..., Any],
) -> dict[str, Any]:
    if session_id:
        require_session_access(http_request, session_id, "editor")
    else:
        require_remote_editor(http_request)

    payload = await enqueue_task(
        resolve_tasks(),
        tasks_lock,
        task_type=task_type,
        params=params,
        session_id=session_id,
        prune_in_memory=prune_task_records_locked,
        persist_record=persist_task_record,
        prune_persisted=prune_persisted_tasks,
        run_task=run_task,
        spawn_background_task=spawn_background_task,
        logger=logger,
        task_backend=task_backend,
        enqueue_external_task=enqueue_external_task,
        on_record_created=on_record_created,
    )
    if session_id and payload.get("task_id"):
        grant_derived_resource_access(
            http_request,
            source_resource_type="session",
            source_resource_id=session_id,
            target_resource_type="task",
            target_resource_id=str(payload.get("task_id") or ""),
            access_store=access_store,
            require_remote_role=require_remote_editor,
            now=time.time,
            audit_security_event=audit_security_event,
        )
    return payload


async def dispatch_existing_task_record_result(
    record: Any,
    *,
    task_backend: str,
    run_task: Callable[..., Awaitable[None]],
    enqueue_external_task: Callable[[Any], Awaitable[Any]] | None,
    logger: Any,
) -> str:
    backend = await dispatch_task_record(
        record,
        task_backend=task_backend,
        run_task=run_task,
        spawn_background_task=spawn_background_task,
        enqueue_external_task=enqueue_external_task,
    )
    logger.info(
        "task_id=%s task_type=%s dispatched backend=%s",
        getattr(record, "task_id", ""),
        getattr(record, "task_type", ""),
        backend,
    )
    return backend


async def list_tasks_route_payload(
    *,
    request: Request,
    limit: int,
    status: str,
    resolve_tasks: Callable[[], dict[str, Any]],
    tasks_lock: Any,
    prune_task_records_locked: Callable[..., None],
    prune_persisted_tasks: Callable[[], None],
    get_task_store: Callable[[], Any],
    task_history_limit: int,
    require_session_access: Callable[[Request, str, str], dict[str, Any]],
    require_remote_viewer: Callable[[Request], dict[str, Any]],
    task_backend: str,
    arq_queue_health_payload: Callable[[], Awaitable[dict[str, Any]]] | None,
    list_tasks_payload: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    task_state = resolve_tasks()
    async with tasks_lock:
        prune_task_records_locked()
        in_memory_tasks = list(task_state.values())
    prune_persisted_tasks()
    persisted_tasks = get_task_store().list_recent(limit=max(limit, task_history_limit))
    filtered_in_memory_tasks = filter_visible_task_records(
        in_memory_tasks,
        request,
        require_session_access=require_session_access,
        require_remote_viewer=require_remote_viewer,
    )
    filtered_persisted_tasks = filter_visible_task_records(
        persisted_tasks,
        request,
        require_session_access=require_session_access,
        require_remote_viewer=require_remote_viewer,
    )
    queue_health = None
    if task_backend in {"arq", "redis"} and arq_queue_health_payload is not None:
        queue_health = await arq_queue_health_payload()
    return list_tasks_payload(
        in_memory_tasks=filtered_in_memory_tasks,
        persisted_tasks=filtered_persisted_tasks,
        limit=limit,
        status_filter=status,
        queue_health=queue_health,
    )


async def get_task_route_payload(
    *,
    task_id: str,
    request: Request,
    resolve_tasks: Callable[[], dict[str, Any]],
    tasks_lock: Any,
    prune_task_records_locked: Callable[..., None],
    prune_persisted_tasks: Callable[[], None],
    get_task_store: Callable[[], Any],
    require_session_access: Callable[[Request, str, str], dict[str, Any]],
    require_remote_viewer: Callable[[Request], dict[str, Any]],
    task_record_payload: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    record = await _find_task_record(
        task_id=task_id,
        resolve_tasks=resolve_tasks,
        tasks_lock=tasks_lock,
        prune_task_records_locked=prune_task_records_locked,
        prune_persisted_tasks=prune_persisted_tasks,
        get_task_store=get_task_store,
    )
    if record is None:
        raise HTTPException(status_code=404, detail=TASK_NOT_FOUND_DETAIL)
    if getattr(record, "session_id", None):
        require_session_access(request, str(record.session_id), "viewer")
    else:
        require_remote_viewer(request)
    return task_record_payload(record)


async def apply_task_approval_decision_result(
    *,
    task_id: str,
    http_request: Request,
    approval_request: Any,
    resolve_tasks: Callable[[], dict[str, Any]],
    tasks_lock: Any,
    prune_task_records_locked: Callable[..., None],
    prune_persisted_tasks: Callable[[], None],
    get_task_store: Callable[[], Any],
    persist_task_record: Callable[..., None],
    dispatch_existing_task_record: Callable[[Any], Awaitable[str]],
    require_session_access: Callable[[Request, str, str], dict[str, Any]],
    require_remote_admin: Callable[[Request], dict[str, Any]],
    audit_security_event: Callable[..., Any],
    task_record_payload: Callable[[Any], dict[str, Any]],
    now: Callable[[], float],
) -> dict[str, Any]:
    task_state = resolve_tasks()
    record = await _find_task_record(
        task_id=task_id,
        resolve_tasks=lambda: task_state,
        tasks_lock=tasks_lock,
        prune_task_records_locked=prune_task_records_locked,
        prune_persisted_tasks=prune_persisted_tasks,
        get_task_store=get_task_store,
    )
    if record is None:
        raise HTTPException(status_code=404, detail=TASK_NOT_FOUND_DETAIL)

    ensure_task_accepts_approval_decision(record)
    if getattr(record, "session_id", None):
        require_session_access(http_request, str(record.session_id), "editor")
    else:
        require_remote_admin(http_request)

    apply_approval_decision_to_record(record, approval_request, updated_at=now())

    async with tasks_lock:
        task_state[task_id] = record
        prune_task_records_locked(record.updated_at)
    persist_task_record(record)
    prune_persisted_tasks()
    await dispatch_existing_task_record(record)
    audit_security_event(
        "task_approval_decision",
        http_request,
        details=(
            f"task_id={task_id} decision={approval_decision_value(approval_request)} "
            f"session_id={getattr(record, 'session_id', '') or '<none>'}"
        ),
    )
    return task_record_payload(record)


async def _find_task_record(
    *,
    task_id: str,
    resolve_tasks: Callable[[], dict[str, Any]],
    tasks_lock: Any,
    prune_task_records_locked: Callable[..., None],
    prune_persisted_tasks: Callable[[], None],
    get_task_store: Callable[[], Any],
) -> Any | None:
    task_state = resolve_tasks()
    async with tasks_lock:
        prune_task_records_locked()
        record = task_state.get(task_id)
    if record is None:
        prune_persisted_tasks()
        record = get_task_store().get(task_id)
    return record


__all__ = [
    "apply_task_approval_decision_result",
    "create_background_task_result",
    "dispatch_existing_task_record_result",
    "filter_visible_task_records",
    "get_task_route_payload",
    "list_tasks_route_payload",
    "resolve_task_backend_value",
    "spawn_background_task",
]
