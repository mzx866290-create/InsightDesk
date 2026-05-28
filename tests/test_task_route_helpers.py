import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.helpers import task_route_helpers
from backend.helpers.task_route_helpers import (
    apply_task_approval_decision_result,
    create_background_task_result,
    dispatch_existing_task_record_result,
    filter_visible_task_records,
    get_task_route_payload,
    list_tasks_route_payload,
    resolve_task_backend_value,
)
from backend.helpers.task_runtime_helpers import list_tasks_payload
from backend.stores.task_store import TaskRecord, TaskStatus


class _AsyncLock:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


def test_filter_visible_task_records_skips_forbidden_session_tasks():
    records = [
        SimpleNamespace(task_id="visible", session_id="session-visible"),
        SimpleNamespace(task_id="hidden", session_id="session-hidden"),
        SimpleNamespace(task_id="global", session_id=""),
    ]

    def require_session_access(_request, session_id, role):
        assert role == "viewer"
        if session_id == "session-hidden":
            raise HTTPException(status_code=403, detail="hidden")
        return {"session_id": session_id}

    visible = filter_visible_task_records(
        records,
        SimpleNamespace(),
        require_session_access=require_session_access,
        require_remote_viewer=lambda request: {"role": "viewer"},
    )

    assert [record.task_id for record in visible] == ["visible", "global"]


def test_filter_visible_task_records_reraises_non_forbidden_session_errors():
    with pytest.raises(HTTPException) as exc_info:
        filter_visible_task_records(
            [SimpleNamespace(task_id="missing", session_id="session-missing")],
            SimpleNamespace(),
            require_session_access=lambda *args: (_ for _ in ()).throw(
                HTTPException(status_code=404, detail="missing")
            ),
            require_remote_viewer=lambda request: {"role": "viewer"},
        )

    assert exc_info.value.status_code == 404


def test_resolve_task_backend_value_normalizes_static_and_callable_values():
    assert resolve_task_backend_value(" ARQ ") == "arq"
    assert resolve_task_backend_value(lambda: " Redis ") == "redis"
    assert resolve_task_backend_value("") == "memory"


def test_create_background_task_result_enqueues_and_grants_session_task():
    calls = []
    request = SimpleNamespace(name="request")
    task_state = {"existing": object()}

    async def fake_enqueue_task(tasks, lock, **kwargs):
        calls.append(("enqueue", tasks, lock, kwargs))
        return {"task_id": "task-1", "status": "pending"}

    payload = asyncio.run(
        create_background_task_result(
            http_request=request,
            task_type="web_research",
            params={"topic": "x"},
            session_id="session-1",
            on_record_created=lambda record: None,
            resolve_tasks=lambda: task_state,
            tasks_lock="lock",
            enqueue_task=fake_enqueue_task,
            prune_task_records_locked=lambda created_at=None: None,
            persist_task_record=lambda record: None,
            prune_persisted_tasks=lambda: None,
            run_task=lambda record: None,
            logger=SimpleNamespace(),
            task_backend="memory",
            enqueue_external_task=None,
            require_session_access=lambda req, session_id, role: calls.append(
                ("session-access", req, session_id, role)
            )
            or {"role": role},
            require_remote_editor=lambda req: calls.append(("remote-editor", req)),
            grant_derived_resource_access=lambda *args, **kwargs: calls.append(
                ("grant", args, kwargs)
            ),
            access_store="access-store",
            audit_security_event=lambda *args, **kwargs: None,
        )
    )

    assert payload == {"task_id": "task-1", "status": "pending"}
    assert calls[0] == ("session-access", request, "session-1", "editor")
    assert calls[1][0] == "enqueue"
    assert calls[1][1] is task_state
    assert calls[1][2] == "lock"
    assert calls[1][3]["task_type"] == "web_research"
    assert calls[1][3]["params"] == {"topic": "x"}
    assert calls[1][3]["session_id"] == "session-1"
    assert calls[1][3]["task_backend"] == "memory"
    assert callable(calls[1][3]["spawn_background_task"])
    assert calls[2][0] == "grant"
    assert calls[2][2]["source_resource_type"] == "session"
    assert calls[2][2]["source_resource_id"] == "session-1"
    assert calls[2][2]["target_resource_type"] == "task"
    assert calls[2][2]["target_resource_id"] == "task-1"


def test_create_background_task_result_requires_remote_editor_without_session():
    calls = []

    async def fake_enqueue_task(tasks, lock, **kwargs):
        return {"task_id": "global-task"}

    asyncio.run(
        create_background_task_result(
            http_request="request",
            task_type="upload_documents",
            params={},
            session_id=None,
            resolve_tasks=lambda: {},
            tasks_lock="lock",
            enqueue_task=fake_enqueue_task,
            prune_task_records_locked=lambda created_at=None: None,
            persist_task_record=lambda record: None,
            prune_persisted_tasks=lambda: None,
            run_task=lambda record: None,
            logger=SimpleNamespace(),
            task_backend="memory",
            enqueue_external_task=None,
            require_session_access=lambda req, session_id, role: calls.append(
                ("session-access", session_id)
            ),
            require_remote_editor=lambda req: calls.append(("remote-editor", req))
            or {"role": "editor"},
            grant_derived_resource_access=lambda *args, **kwargs: calls.append(
                ("grant",)
            ),
            access_store="access-store",
            audit_security_event=lambda *args, **kwargs: None,
        )
    )

    assert calls == [("remote-editor", "request")]


def test_dispatch_existing_task_record_result_dispatches_and_logs(monkeypatch):
    calls = []
    record = SimpleNamespace(task_id="task-1", task_type="report")

    async def fake_dispatch_task_record(record_arg, **kwargs):
        calls.append(("dispatch", record_arg, kwargs))
        return "arq"

    monkeypatch.setattr(
        task_route_helpers,
        "dispatch_task_record",
        fake_dispatch_task_record,
    )

    result = asyncio.run(
        dispatch_existing_task_record_result(
            record,
            task_backend="arq",
            run_task=lambda task_record: None,
            enqueue_external_task=None,
            logger=SimpleNamespace(
                info=lambda *args, **kwargs: calls.append(("log-info", args))
            ),
        ),
    )

    assert result == "arq"
    assert calls[0][0] == "dispatch"
    assert calls[0][1] is record
    assert calls[0][2]["task_backend"] == "arq"
    assert callable(calls[0][2]["spawn_background_task"])
    assert calls[1] == (
        "log-info",
        (
            "task_id=%s task_type=%s dispatched backend=%s",
            "task-1",
            "report",
            "arq",
        ),
    )


def test_list_tasks_route_payload_filters_and_includes_queue_health():
    calls = []
    request = SimpleNamespace(name="request")
    memory_task = TaskRecord(
        task_id="memory",
        task_type="report",
        status=TaskStatus.RUNNING,
        params={},
        session_id="session-1",
        created_at=20.0,
        updated_at=30.0,
    )
    persisted_task = TaskRecord(
        task_id="persisted",
        task_type="report",
        status=TaskStatus.PENDING,
        params={},
        session_id=None,
        created_at=10.0,
        updated_at=10.0,
    )

    class TaskStore:
        def list_recent(self, *, limit):
            calls.append(("list-recent", limit))
            return [persisted_task]

    async def queue_health():
        calls.append(("queue-health",))
        return {"enabled": True, "status": "ok", "warnings": []}

    payload = asyncio.run(
        list_tasks_route_payload(
            request=request,
            limit=5,
            status="",
            resolve_tasks=lambda: {"memory": memory_task},
            tasks_lock=_AsyncLock(),
            prune_task_records_locked=lambda created_at=None: calls.append(
                ("prune-memory", created_at)
            ),
            prune_persisted_tasks=lambda: calls.append(("prune-persisted",)),
            get_task_store=lambda: TaskStore(),
            task_history_limit=25,
            require_session_access=lambda req, session_id, role: calls.append(
                ("session-access", req, session_id, role)
            )
            or {"role": role},
            require_remote_viewer=lambda req: calls.append(("remote-viewer", req))
            or {"role": "viewer"},
            task_backend="arq",
            arq_queue_health_payload=queue_health,
            list_tasks_payload=list_tasks_payload,
        )
    )

    assert [item["task_id"] for item in payload["tasks"]] == ["memory", "persisted"]
    assert payload["health"]["queue"] == {
        "enabled": True,
        "status": "ok",
        "warnings": [],
    }
    assert calls == [
        ("prune-memory", None),
        ("prune-persisted",),
        ("list-recent", 25),
        ("session-access", request, "session-1", "viewer"),
        ("remote-viewer", request),
        ("queue-health",),
    ]


def test_get_task_route_payload_reads_memory_task_and_checks_session_access():
    calls = []
    request = SimpleNamespace(name="request")
    record = SimpleNamespace(task_id="task-1", session_id="session-1")

    payload = asyncio.run(
        get_task_route_payload(
            task_id="task-1",
            request=request,
            resolve_tasks=lambda: {"task-1": record},
            tasks_lock=_AsyncLock(),
            prune_task_records_locked=lambda created_at=None: calls.append(
                ("prune-memory", created_at)
            ),
            prune_persisted_tasks=lambda: calls.append(("prune-persisted",)),
            get_task_store=lambda: SimpleNamespace(get=lambda task_id: None),
            require_session_access=lambda req, session_id, role: calls.append(
                ("session-access", req, session_id, role)
            )
            or {"role": role},
            require_remote_viewer=lambda req: calls.append(("remote-viewer", req)),
            task_record_payload=lambda task_record: {"task_id": task_record.task_id},
        )
    )

    assert payload == {"task_id": "task-1"}
    assert calls == [
        ("prune-memory", None),
        ("session-access", request, "session-1", "viewer"),
    ]


def test_get_task_route_payload_falls_back_to_persisted_global_task():
    calls = []
    record = SimpleNamespace(task_id="task-2", session_id="")

    payload = asyncio.run(
        get_task_route_payload(
            task_id="task-2",
            request="request",
            resolve_tasks=lambda: {},
            tasks_lock=_AsyncLock(),
            prune_task_records_locked=lambda created_at=None: calls.append(
                ("prune-memory", created_at)
            ),
            prune_persisted_tasks=lambda: calls.append(("prune-persisted",)),
            get_task_store=lambda: SimpleNamespace(get=lambda task_id: record),
            require_session_access=lambda req, session_id, role: calls.append(
                ("session-access", session_id)
            ),
            require_remote_viewer=lambda req: calls.append(("remote-viewer", req))
            or {"role": "viewer"},
            task_record_payload=lambda task_record: {"task_id": task_record.task_id},
        )
    )

    assert payload == {"task_id": "task-2"}
    assert calls == [
        ("prune-memory", None),
        ("prune-persisted",),
        ("remote-viewer", "request"),
    ]


def test_get_task_route_payload_maps_missing_task_to_404():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            get_task_route_payload(
                task_id="missing",
                request="request",
                resolve_tasks=lambda: {},
                tasks_lock=_AsyncLock(),
                prune_task_records_locked=lambda created_at=None: None,
                prune_persisted_tasks=lambda: None,
                get_task_store=lambda: SimpleNamespace(get=lambda task_id: None),
                require_session_access=lambda req, session_id, role: {},
                require_remote_viewer=lambda req: {},
                task_record_payload=lambda task_record: {},
            )
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Task was not found."


def test_apply_task_approval_decision_result_updates_persists_and_dispatches():
    calls = []
    audits = []
    task_state = {}
    record = SimpleNamespace(
        task_id="task-approval",
        task_type="multi_agent_workflow",
        status=TaskStatus.WAITING_APPROVAL,
        params={},
        session_id="session-1",
        created_at=1.0,
        updated_at=1.0,
        approval={"state": "waiting"},
    )
    approval_request = SimpleNamespace(decision="approved", reason="looks good")

    async def dispatch_existing_task_record(task_record):
        calls.append(("dispatch", task_record.task_id))
        return "memory"

    payload = asyncio.run(
        apply_task_approval_decision_result(
            task_id="task-approval",
            http_request="request",
            approval_request=approval_request,
            resolve_tasks=lambda: task_state,
            tasks_lock=_AsyncLock(),
            prune_task_records_locked=lambda created_at=None: calls.append(
                ("prune-memory", created_at)
            ),
            prune_persisted_tasks=lambda: calls.append(("prune-persisted",)),
            get_task_store=lambda: SimpleNamespace(get=lambda task_id: record),
            persist_task_record=lambda task_record: calls.append(
                ("persist", task_record.task_id)
            ),
            dispatch_existing_task_record=dispatch_existing_task_record,
            require_session_access=lambda req, session_id, role: calls.append(
                ("session-access", req, session_id, role)
            )
            or {"role": role},
            require_remote_admin=lambda req: calls.append(("remote-admin", req)),
            audit_security_event=lambda *args, **kwargs: audits.append((args, kwargs)),
            task_record_payload=lambda task_record: {
                "task_id": task_record.task_id,
                "status": task_record.status,
                "updated_at": task_record.updated_at,
            },
            now=lambda: 100.0,
        )
    )

    assert payload == {
        "task_id": "task-approval",
        "status": TaskStatus.PENDING,
        "updated_at": 100.0,
    }
    assert task_state["task-approval"] is record
    assert calls == [
        ("prune-memory", None),
        ("prune-persisted",),
        ("session-access", "request", "session-1", "editor"),
        ("prune-memory", 100.0),
        ("persist", "task-approval"),
        ("prune-persisted",),
        ("dispatch", "task-approval"),
    ]
    assert audits == [
        (
            ("task_approval_decision", "request"),
            {
                "details": (
                    "task_id=task-approval decision=approved session_id=session-1"
                )
            },
        )
    ]
