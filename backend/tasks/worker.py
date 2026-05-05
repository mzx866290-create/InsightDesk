"""ARQ worker entrypoint for persisted task records.

Run with:

    arq backend.tasks.worker.WorkerSettings
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import os
import time

from backend.stores.task_store import SQLiteTaskStore, TaskStatus
from backend.tasks.enqueue import _redis_settings_from_env
from backend.tasks.settings import (
    arq_pending_stale_seconds_from_env,
    arq_queue_name_from_env,
    arq_retry_defer_seconds_from_env,
    arq_running_stale_seconds_from_env,
    arq_should_retry_failed_task,
    arq_should_start_task_record,
    arq_worker_runtime_settings_from_env,
)

logger = logging.getLogger(__name__)


def _probe_task_store() -> SQLiteTaskStore:
    db_path = (
        os.getenv("APP_DB_PATH")
        or os.getenv("CHAT_HISTORY_DB_PATH")
        or "./chat_history.db"
    )
    return SQLiteTaskStore(
        db_path=db_path,
        history_limit=50,
        ttl_seconds=3600,
        fail_incomplete_on_start=False,
    )


async def _run_probe_task(record, *, task_store: SQLiteTaskStore) -> None:
    if record.status != TaskStatus.PENDING:
        return
    record.status = TaskStatus.RUNNING
    record.progress = max(10, int(record.progress or 0))
    record.updated_at = time.time()
    task_store.save(record)
    step_seconds = float(record.params.get("probe_step_seconds") or 0.5)
    for progress in (35, 65):
        await asyncio.sleep(max(0.1, step_seconds))
        record.progress = progress
        record.updated_at = time.time()
        task_store.save(record)
    await asyncio.sleep(max(0.1, step_seconds))
    record.status = TaskStatus.COMPLETED
    record.progress = 100
    record.result = "arq_e2e_probe_completed"
    record.updated_at = time.time()
    task_store.save(record)


async def run_task_by_id(ctx, task_id: str) -> None:
    """Load a persisted task and execute it through the existing runtime."""
    job_try = ctx.get("job_try") if isinstance(ctx, dict) else None
    probe_task_store = _probe_task_store()
    probe_record = probe_task_store.get(str(task_id))

    if str(getattr(probe_record, "task_type", "") or "").strip() == "arq_e2e_probe":
        if not arq_should_start_task_record(status=probe_record.status, job_try=job_try):
            logger.info(
                "task_id=%s skipped duplicate arq delivery status=%s job_try=%s",
                task_id,
                getattr(probe_record.status, "value", probe_record.status),
                job_try,
            )
            return
        await _run_probe_task(probe_record, task_store=probe_task_store)
        return

    api_server = importlib.import_module("backend.api_server")
    task_store = api_server._get_task_store()
    record = task_store.get(str(task_id))
    if record is None:
        raise ValueError(f"Task was not found: {task_id}")
    if not arq_should_start_task_record(status=record.status, job_try=job_try):
        logger.info(
            "task_id=%s skipped duplicate arq delivery status=%s job_try=%s",
            task_id,
            getattr(record.status, "value", record.status),
            job_try,
        )
        return

    await api_server._run_task(record)

    latest_record = task_store.get(str(task_id)) or record
    if not arq_should_retry_failed_task(
        status=latest_record.status,
        job_try=job_try,
    ):
        return

    try:
        from arq import Retry
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "TASK_BACKEND=arq requires the optional 'arq' package. "
            "Install project requirements before enabling the ARQ backend."
        ) from exc
    raise Retry(defer=arq_retry_defer_seconds_from_env())


class WorkerSettings:
    functions = [run_task_by_id]
    redis_settings = _redis_settings_from_env()
    queue_name = arq_queue_name_from_env()
    task_pending_stale_seconds = arq_pending_stale_seconds_from_env()
    task_running_stale_seconds = arq_running_stale_seconds_from_env()


for _setting_name, _setting_value in arq_worker_runtime_settings_from_env(
    queue_name=WorkerSettings.queue_name,
).items():
    setattr(WorkerSettings, _setting_name, _setting_value)
