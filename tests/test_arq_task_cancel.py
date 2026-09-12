from __future__ import annotations

import asyncio
import sys
import types
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.helpers.task_route_helpers import cancel_task_route_payload
from backend.stores.task_store import TaskRecord, TaskStatus
from backend.tasks import enqueue as task_enqueue


class _AsyncLock:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _TaskStore:
    def __init__(self, record: TaskRecord):
        self.record = record

    def get(self, task_id: str):
        return self.record if task_id == self.record.task_id else None


def _record(*, status: TaskStatus = TaskStatus.RUNNING) -> TaskRecord:
    return TaskRecord(
        task_id="task-cancel",
        task_type="web_research",
        status=status,
        params={},
        session_id="session-1",
        created_at=1.0,
        updated_at=1.0,
        progress=25,
    )


def _cancel_route(record: TaskRecord, **overrides):
    task_state = {record.task_id: record}
    store = _TaskStore(record)
    suppressed: set[str] = set()
    persisted: list[TaskRecord] = []
    audits: list[tuple[tuple, dict]] = []
    kwargs = {
        "task_id": record.task_id,
        "request": SimpleNamespace(),
        "resolve_tasks": lambda: task_state,
        "tasks_lock": _AsyncLock(),
        "suppressed_task_ids": suppressed,
        "prune_task_records_locked": lambda updated_at=None: None,
        "prune_persisted_tasks": lambda: None,
        "get_task_store": lambda: store,
        "persist_task_record": lambda current: persisted.append(current),
        "require_session_access": lambda request, session_id, role: {"role": role},
        "require_remote_admin": lambda request: {"role": "admin"},
        "audit_security_event": lambda *args, **kwargs: audits.append((args, kwargs)),
        "task_record_payload": lambda current: {
            "task_id": current.task_id,
            "status": current.status.value,
            "params": dict(current.params),
            "error": current.error,
        },
        "task_backend": "memory",
        "cancel_external_task": None,
        "now": lambda: 10.0,
    }
    kwargs.update(overrides)
    payload = asyncio.run(cancel_task_route_payload(**kwargs))
    return payload, suppressed, persisted, audits


def test_memory_task_cancel_is_terminal_and_idempotent():
    record = _record()

    payload, suppressed, persisted, audits = _cancel_route(record)

    assert payload["cancelled"] is True
    assert payload["task"]["status"] == "failed"
    assert payload["task"]["params"]["task_failure_kind"] == "cancelled"
    assert record.error == "Task was cancelled by user."
    assert suppressed == {record.task_id}
    assert persisted == [record]
    assert audits[0][0][0] == "task_cancel"

    repeated, *_ = _cancel_route(record)
    assert repeated["cancelled"] is True


def test_arq_task_cancel_aborts_job_before_marking_terminal():
    record = _record()

    async def cancel_external(task_id: str):
        assert task_id == record.task_id
        return {
            "job_status": "in_progress",
            "requested": True,
            "aborted": True,
            "timed_out": False,
        }

    payload, suppressed, persisted, _ = _cancel_route(
        record,
        task_backend="arq",
        cancel_external_task=cancel_external,
    )

    assert payload["cancelled"] is True
    assert payload["external"]["aborted"] is True
    assert record.status is TaskStatus.FAILED
    assert record.params["task_failure_kind"] == "cancelled"
    assert suppressed == {record.task_id}
    assert persisted == [record]


def test_arq_cancel_timeout_persists_request_without_claiming_completion():
    record = _record()

    async def cancel_external(_task_id: str):
        return {
            "job_status": "in_progress",
            "requested": True,
            "aborted": False,
            "timed_out": True,
        }

    payload, suppressed, persisted, _ = _cancel_route(
        record,
        task_backend="arq",
        cancel_external_task=cancel_external,
    )

    assert payload["cancel_requested"] is True
    assert payload["cancelled"] is False
    assert record.status is TaskStatus.RUNNING
    assert record.params["task_cancel_requested"] is True
    assert "task_failure_kind" not in record.params
    assert suppressed == set()
    assert persisted == [record]


def test_terminal_task_cancel_returns_conflict():
    record = _record(status=TaskStatus.COMPLETED)

    with pytest.raises(HTTPException) as exc_info:
        _cancel_route(record)

    assert exc_info.value.status_code == 409


def test_cancel_arq_task_aborts_running_job_and_closes_pool(monkeypatch):
    events: list[object] = []

    class FakeRedis:
        async def close(self):
            events.append("closed")

    redis = FakeRedis()
    fake_arq = types.ModuleType("arq")
    fake_jobs = types.ModuleType("arq.jobs")

    async def create_pool(settings, *, default_queue_name):
        events.append(("pool", settings, default_queue_name))
        return redis

    class FakeJob:
        def __init__(self, job_id, redis_arg, _queue_name):
            assert redis_arg is redis
            events.append(("job", job_id, _queue_name))

        async def status(self):
            return SimpleNamespace(value="in_progress")

        async def abort(self, *, timeout):
            events.append(("abort", timeout))
            return True

    fake_arq.create_pool = create_pool
    fake_jobs.Job = FakeJob
    monkeypatch.setitem(sys.modules, "arq", fake_arq)
    monkeypatch.setitem(sys.modules, "arq.jobs", fake_jobs)
    monkeypatch.setattr(task_enqueue, "_redis_settings_from_env", lambda: "settings")

    payload = asyncio.run(
        task_enqueue.cancel_arq_task(
            "task-1",
            queue_name="ops:tasks",
            timeout_seconds=2,
        )
    )

    assert payload == {
        "task_id": "task-1",
        "job_id": "task:task-1",
        "job_status": "in_progress",
        "requested": True,
        "aborted": True,
        "timed_out": False,
    }
    assert events == [
        ("pool", "settings", "ops:tasks"),
        ("job", "task:task-1", "ops:tasks"),
        ("abort", 2.0),
        "closed",
    ]
