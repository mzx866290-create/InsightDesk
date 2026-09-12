"""ARQ enqueue and Redis connection helpers."""

from __future__ import annotations

import inspect
import os
from typing import Any

from backend.stores.task_store import TaskRecord
from backend.tasks.settings import (
    arq_cancel_timeout_from_env,
    arq_queue_name_from_env,
)


def _redis_settings_from_env():
    try:
        from arq.connections import RedisSettings
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "TASK_BACKEND=arq requires the optional 'arq' package. "
            "Install project requirements before enabling the ARQ backend."
        ) from exc

    dsn = str(
        os.getenv("ARQ_REDIS_DSN")
        or os.getenv("REDIS_URL")
        or os.getenv("ARQ_REDIS_URL")
        or ""
    ).strip()
    if dsn:
        return RedisSettings.from_dsn(dsn)

    return RedisSettings(
        host=os.getenv("ARQ_REDIS_HOST", "localhost"),
        port=int(os.getenv("ARQ_REDIS_PORT", "6379")),
        database=int(os.getenv("ARQ_REDIS_DATABASE", "0")),
        password=os.getenv("ARQ_REDIS_PASSWORD") or None,
    )


async def _close_redis_pool(redis) -> None:
    close = getattr(redis, "close", None) or getattr(redis, "aclose", None)
    if close is None:
        return
    result = close()
    if inspect.isawaitable(result):
        await result


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _redis_int_call(redis: Any, method_name: str, *args: Any) -> int | None:
    method = getattr(redis, method_name, None)
    if method is None:
        return None
    value = await _maybe_await(method(*args))
    if value is None:
        return None
    return int(value)


async def enqueue_arq_task(
    record: TaskRecord,
    *,
    queue_name: str | None = None,
) -> str:
    """Enqueue an existing persisted task record into ARQ."""
    try:
        from arq import create_pool
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "TASK_BACKEND=arq requires the optional 'arq' package. "
            "Install project requirements before enabling the ARQ backend."
        ) from exc

    redis = await create_pool(
        _redis_settings_from_env(),
        default_queue_name=str(queue_name or arq_queue_name_from_env()),
    )
    try:
        job = await redis.enqueue_job(
            "run_task_by_id",
            record.task_id,
            _job_id=f"task:{record.task_id}",
        )
        if job is None:
            return record.task_id
        return str(getattr(job, "job_id", "") or record.task_id)
    finally:
        await _close_redis_pool(redis)


async def cancel_arq_task(
    task_id: str,
    *,
    queue_name: str | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """Request cancellation of a queued or running ARQ task."""

    normalized_task_id = str(task_id or "").strip()
    if not normalized_task_id:
        raise ValueError("task_id is required")

    try:
        from arq import create_pool
        from arq.jobs import Job
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "TASK_BACKEND=arq requires the optional 'arq' package. "
            "Install project requirements before enabling the ARQ backend."
        ) from exc

    resolved_queue_name = str(queue_name or arq_queue_name_from_env()).strip()
    job_id = f"task:{normalized_task_id}"
    redis = await create_pool(
        _redis_settings_from_env(),
        default_queue_name=resolved_queue_name,
    )
    try:
        job = Job(job_id, redis, _queue_name=resolved_queue_name)
        raw_status = await job.status()
        job_status = str(getattr(raw_status, "value", raw_status) or "").strip().lower()
        if job_status in {"complete", "not_found"}:
            return {
                "task_id": normalized_task_id,
                "job_id": job_id,
                "job_status": job_status,
                "requested": False,
                "aborted": False,
                "timed_out": False,
            }

        timeout = float(
            arq_cancel_timeout_from_env()
            if timeout_seconds is None
            else timeout_seconds
        )
        if timeout <= 0:
            raise ValueError("timeout_seconds must be positive")
        try:
            aborted = bool(await job.abort(timeout=timeout))
        except TimeoutError:
            return {
                "task_id": normalized_task_id,
                "job_id": job_id,
                "job_status": job_status,
                "requested": True,
                "aborted": False,
                "timed_out": True,
            }
        return {
            "task_id": normalized_task_id,
            "job_id": job_id,
            "job_status": job_status,
            "requested": True,
            "aborted": aborted,
            "timed_out": False,
        }
    finally:
        await _close_redis_pool(redis)


__all__ = [
    "_close_redis_pool",
    "_maybe_await",
    "_redis_int_call",
    "_redis_settings_from_env",
    "cancel_arq_task",
    "enqueue_arq_task",
]
