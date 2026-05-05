"""Container-side ARQ E2E smoke probe.

The default ``run`` mode creates a persisted placeholder task, enqueues it
through ARQ, and waits for the worker to mark it completed in the shared task
store. ``enqueue`` and ``wait`` modes are split out so deployment drills can
exercise graceful worker shutdown without duplicating task creation code.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import time
import uuid

from backend.core.storage_runtime import app_database_path
from backend.stores.task_store import SQLiteTaskStore, TaskRecord, TaskStatus
from backend.tasks.enqueue import enqueue_arq_task
from backend.tasks.settings import arq_queue_name_from_env


DEFAULT_PROBE_STEP_SECONDS = 0.5


def _probe_step_seconds(value: float | None) -> float:
    if value is None:
        return DEFAULT_PROBE_STEP_SECONDS
    return min(30.0, max(0.1, float(value)))


def _build_probe_task(*, probe_step_seconds: float) -> TaskRecord:
    now = time.time()
    return TaskRecord(
        task_id=f"arq-e2e-{uuid.uuid4().hex}",
        task_type="arq_e2e_probe",
        status=TaskStatus.PENDING,
        params={
            "source": "deploy/arq_e2e_probe.py",
            "probe_step_seconds": _probe_step_seconds(probe_step_seconds),
        },
        session_id=None,
        created_at=now,
        updated_at=now,
        progress=0,
    )


def _create_probe_task_store():
    os.environ.setdefault("TASK_STORE_FAIL_INCOMPLETE_ON_START", "false")
    db_path = (
        os.getenv("APP_DB_PATH")
        or os.getenv("CHAT_HISTORY_DB_PATH")
        or app_database_path()
    )
    return SQLiteTaskStore(
        db_path=db_path,
        history_limit=50,
        ttl_seconds=3600,
        fail_incomplete_on_start=False,
    )


async def enqueue_probe(*, probe_step_seconds: float) -> tuple[str, str | None]:
    task_store = _create_probe_task_store()
    record = _build_probe_task(probe_step_seconds=probe_step_seconds)
    task_store.save(record)
    job_id = await enqueue_arq_task(record, queue_name=arq_queue_name_from_env())
    print(f"TASK_ID={record.task_id}")
    print(f"JOB_ID={job_id}")
    return record.task_id, job_id


async def wait_for_probe(
    *,
    task_id: str,
    timeout_seconds: float,
    poll_seconds: float,
) -> int:
    task_store = _create_probe_task_store()
    deadline = time.monotonic() + max(1.0, float(timeout_seconds))

    while time.monotonic() < deadline:
        latest = task_store.get(task_id)
        if latest is None:
            print(f"ERROR: task disappeared task_id={task_id}")
            return 1
        if latest.status == TaskStatus.COMPLETED:
            print(
                "OK: task completed "
                f"task_id={task_id} progress={latest.progress}"
            )
            return 0
        if latest.status == TaskStatus.FAILED:
            print(
                "ERROR: task failed "
                f"task_id={task_id} error={latest.error}"
            )
            return 1
        await asyncio.sleep(max(0.1, float(poll_seconds)))

    latest = task_store.get(task_id)
    status = getattr(latest.status, "value", latest.status) if latest else "missing"
    print(
        "ERROR: timed out waiting for task completion "
        f"task_id={task_id} status={status}"
    )
    return 1


async def run_probe(
    *,
    timeout_seconds: float,
    poll_seconds: float,
    probe_step_seconds: float,
) -> int:
    task_id, _job_id = await enqueue_probe(probe_step_seconds=probe_step_seconds)
    return await wait_for_probe(
        task_id=task_id,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an ARQ worker E2E smoke probe.")
    parser.add_argument("--mode", choices=("run", "enqueue", "wait"), default="run")
    parser.add_argument("--task-id", default="")
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument(
        "--probe-step-seconds",
        type=float,
        default=DEFAULT_PROBE_STEP_SECONDS,
        help="Seconds to sleep between placeholder progress updates.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.mode == "enqueue":
        asyncio.run(enqueue_probe(probe_step_seconds=args.probe_step_seconds))
        return 0
    if args.mode == "wait":
        task_id = str(args.task_id or "").strip()
        if not task_id:
            print("ERROR: --task-id is required when --mode wait")
            return 2
        return asyncio.run(
            wait_for_probe(
                task_id=task_id,
                timeout_seconds=args.timeout_seconds,
                poll_seconds=args.poll_seconds,
            )
        )
    return asyncio.run(
        run_probe(
            timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds,
            probe_step_seconds=args.probe_step_seconds,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
