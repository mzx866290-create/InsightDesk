import asyncio
import logging

from backend.api_task_runtime_helpers import task_stale_health_payload
from backend.helpers.task_runtime_helpers import (
    attach_current_kb_status,
    arq_keep_result_from_env,
    arq_queue_name_from_env,
    arq_should_start_task_record,
    arq_worker_max_jobs_from_env,
    enqueue_task,
    list_tasks_payload,
    normalize_task_backend,
    task_record_payload,
    task_runtime_health_summary,
)
from backend.api_task_store import TaskRecord, TaskStatus
from backend.tasks.backends import build_task_queue_backend, dispatch_task_record


def test_task_record_payload_and_list_tasks_payload_merge_in_memory_first():
    persisted = [
        TaskRecord(
            task_id="task-1",
            task_type="persisted",
            status=TaskStatus.COMPLETED,
            params={"a": 1},
            session_id="session-1",
            created_at=1.0,
            updated_at=1.0,
            result="done",
            progress=100,
        )
    ]
    in_memory = [
        TaskRecord(
            task_id="task-1",
            task_type="in-memory",
            status=TaskStatus.RUNNING,
            params={"a": 2},
            session_id="session-1",
            created_at=2.0,
            updated_at=2.0,
            progress=50,
        ),
        TaskRecord(
            task_id="task-2",
            task_type="second",
            status=TaskStatus.PENDING,
            params={},
            session_id=None,
            created_at=3.0,
            updated_at=3.0,
        ),
    ]

    payload = list_tasks_payload(
        in_memory_tasks=in_memory,
        persisted_tasks=persisted,
        limit=5,
    )

    assert [item["task_id"] for item in payload["tasks"]] == ["task-2", "task-1"]
    assert payload["tasks"][1]["task_type"] == "in-memory"
    assert task_record_payload(in_memory[0], params_override={"x": 1})["params"] == {"x": 1}


def test_list_tasks_payload_orders_by_updated_at_not_created_at():
    payload = list_tasks_payload(
        in_memory_tasks=[
            TaskRecord(
                task_id="long-running",
                task_type="report",
                status=TaskStatus.RUNNING,
                params={},
                session_id="session-1",
                created_at=1.0,
                updated_at=30.0,
                progress=70,
            )
        ],
        persisted_tasks=[
            TaskRecord(
                task_id="fresh-but-idle",
                task_type="report",
                status=TaskStatus.PENDING,
                params={},
                session_id="session-2",
                created_at=20.0,
                updated_at=20.0,
                progress=0,
            )
        ],
        limit=5,
    )

    assert [item["task_id"] for item in payload["tasks"]] == [
        "long-running",
        "fresh-but-idle",
    ]
    assert payload["health"]["enabled"] is True


def test_list_tasks_payload_includes_stale_and_queue_health():
    payload = list_tasks_payload(
        in_memory_tasks=[
            TaskRecord(
                task_id="pending-old",
                task_type="generate_report",
                status=TaskStatus.PENDING,
                params={},
                session_id="session-1",
                created_at=100.0,
                updated_at=100.0,
            )
        ],
        persisted_tasks=[],
        limit=5,
        now=1000.0,
        stale_thresholds={"pending_stale_seconds": 600, "running_stale_seconds": 0},
        queue_health={
            "enabled": True,
            "status": "ok",
            "queue_name": "ops:tasks",
            "length": 3,
            "warning_count": 0,
            "warnings": [],
        },
        runtime_config={
            "backend": "arq",
            "queue_name": "ops:tasks",
            "retry": {
                "enabled": True,
                "attempts": 3,
                "max_retries": 2,
                "backoff_seconds": 15,
                "strategy": "fixed",
            },
            "worker": {
                "drain": {
                    "enabled": True,
                    "graceful_shutdown": True,
                    "drain_seconds": 30,
                    "job_completion_wait_seconds": 30,
                },
                "heartbeat": {
                    "enabled": True,
                    "key": "ops:tasks:worker:heartbeat",
                    "interval_seconds": 30,
                    "expected_ttl_seconds": 31,
                },
            },
        },
    )

    assert payload["health"]["warning_count"] == 1
    assert payload["health"]["pending_warning_count"] == 1
    assert payload["health"]["queue"]["length"] == 3
    assert payload["health"]["runtime"]["retry"]["attempts"] == 3
    assert payload["health"]["summary"] == {
        "status": "warning",
        "warning_count": 1,
        "stale_warning_count": 1,
        "queue_warning_count": 0,
        "warning_codes": ["task_pending_stale"],
        "retry_enabled": True,
        "worker_drain_enabled": True,
        "worker_heartbeat_enabled": True,
    }


def test_task_runtime_health_summary_merges_queue_and_worker_signals():
    summary = task_runtime_health_summary(
        {
            "warning_count": 1,
            "warnings": [{"code": "task_running_stale"}],
            "queue": {
                "status": "warning",
                "warning_count": 2,
                "warnings": [
                    "arq_queue_backlog",
                    "arq_worker_heartbeat_missing",
                ],
            },
            "runtime": {
                "retry": {"enabled": False},
                "worker": {
                    "drain": {"enabled": False},
                    "heartbeat": {"enabled": True},
                },
            },
        }
    )

    assert summary == {
        "status": "warning",
        "warning_count": 3,
        "stale_warning_count": 1,
        "queue_warning_count": 2,
        "warning_codes": [
            "task_running_stale",
            "arq_queue_backlog",
            "arq_worker_heartbeat_missing",
        ],
        "retry_enabled": False,
        "worker_drain_enabled": False,
        "worker_heartbeat_enabled": True,
    }


def test_task_stale_health_payload_warns_pending_tasks_over_threshold():
    payload = task_stale_health_payload(
        [
            TaskRecord(
                task_id="pending-old",
                task_type="generate_report",
                status=TaskStatus.PENDING,
                params={},
                session_id="session-1",
                created_at=100.0,
                updated_at=500.0,
            )
        ],
        now=1000.0,
        thresholds={"pending_stale_seconds": 600, "running_stale_seconds": 0},
    )

    assert payload["warning_count"] == 1
    assert payload["pending_warning_count"] == 1
    assert payload["running_warning_count"] == 0
    assert payload["warnings"][0]["code"] == "task_pending_stale"
    assert payload["warnings"][0]["task_id"] == "pending-old"
    assert payload["warnings"][0]["stale_seconds"] == 900.0


def test_task_stale_health_payload_warns_running_tasks_over_threshold():
    payload = task_stale_health_payload(
        [
            TaskRecord(
                task_id="running-old",
                task_type="web_research",
                status=TaskStatus.RUNNING,
                params={},
                session_id="session-1",
                created_at=50.0,
                updated_at=100.0,
                progress=40,
            )
        ],
        now=1000.0,
        thresholds={"pending_stale_seconds": 0, "running_stale_seconds": 600},
    )

    assert payload["warning_count"] == 1
    assert payload["pending_warning_count"] == 0
    assert payload["running_warning_count"] == 1
    assert payload["warnings"][0]["code"] == "task_running_stale"
    assert payload["warnings"][0]["task_id"] == "running-old"
    assert payload["warnings"][0]["stale_seconds"] == 900.0


def test_task_stale_health_payload_skips_tasks_under_threshold():
    payload = task_stale_health_payload(
        [
            TaskRecord(
                task_id="pending-fresh",
                task_type="generate_report",
                status=TaskStatus.PENDING,
                params={},
                session_id="session-1",
                created_at=850.0,
                updated_at=850.0,
            ),
            TaskRecord(
                task_id="running-fresh",
                task_type="web_research",
                status=TaskStatus.RUNNING,
                params={},
                session_id="session-1",
                created_at=100.0,
                updated_at=900.0,
                progress=60,
            ),
        ],
        now=1000.0,
        thresholds={"pending_stale_seconds": 300, "running_stale_seconds": 120},
    )

    assert payload["enabled"] is True
    assert payload["warning_count"] == 0
    assert payload["warnings"] == []


def test_task_stale_health_payload_respects_disabled_thresholds():
    payload = task_stale_health_payload(
        [
            TaskRecord(
                task_id="pending-disabled",
                task_type="generate_report",
                status=TaskStatus.PENDING,
                params={},
                session_id="session-1",
                created_at=1.0,
                updated_at=1.0,
            ),
            TaskRecord(
                task_id="running-disabled",
                task_type="web_research",
                status=TaskStatus.RUNNING,
                params={},
                session_id="session-1",
                created_at=1.0,
                updated_at=1.0,
            ),
        ],
        now=1000.0,
        thresholds={"pending_stale_seconds": 0, "running_stale_seconds": 0},
    )

    assert payload["enabled"] is False
    assert payload["warning_count"] == 0
    assert payload["warnings"] == []


def test_list_tasks_payload_can_filter_waiting_approval_status():
    payload = list_tasks_payload(
        in_memory_tasks=[
            TaskRecord(
                task_id="task-waiting",
                task_type="multi_agent_workflow",
                status=TaskStatus.WAITING_APPROVAL,
                params={},
                session_id="session-1",
                created_at=3.0,
                updated_at=5.0,
                progress=80,
            )
        ],
        persisted_tasks=[
            TaskRecord(
                task_id="task-done",
                task_type="generate_report",
                status=TaskStatus.COMPLETED,
                params={},
                session_id="session-1",
                created_at=1.0,
                updated_at=2.0,
                progress=100,
            )
        ],
        limit=5,
        status_filter="waiting_approval",
    )

    assert [item["task_id"] for item in payload["tasks"]] == ["task-waiting"]


def test_attach_current_kb_status_marks_completed_and_running_tasks():
    lookup = {
        ("att-a", "kb-main"): TaskRecord(
            task_id="task-a",
            task_type="promote_attachment_to_kb",
            status=TaskStatus.COMPLETED,
            params={},
            session_id="session-1",
            created_at=1.0,
            updated_at=2.0,
            progress=100,
        ),
        ("att-b", "kb-main"): TaskRecord(
            task_id="task-b",
            task_type="promote_attachment_to_kb",
            status=TaskStatus.RUNNING,
            params={},
            session_id="session-1",
            created_at=3.0,
            updated_at=4.0,
            progress=40,
        ),
    }

    payload = attach_current_kb_status(
        {
            "attachments": [
                {"attachment_id": "att-a", "kind": "file", "name": "a.txt"},
                {"attachment_id": "att-b", "kind": "file", "name": "b.txt"},
                {"attachment_id": "att-c", "kind": "image", "name": "c.png"},
            ],
            "summary": {"total_attachments": 3},
        },
        vector_store_path="kb-main",
        lookup_task=lambda attachment_id, vector_store_path: lookup.get(
            (attachment_id, vector_store_path)
        ),
    )

    assert payload["summary"]["indexed_in_current_kb_count"] == 1
    assert payload["summary"]["indexing_in_current_kb_count"] == 1
    assert payload["attachments"][0]["promotion_status"] == "completed"
    assert payload["attachments"][1]["promotion_status"] == "running"
    assert payload["attachments"][2]["promotion_status"] == "idle"


def test_enqueue_task_adds_record_and_schedules_background_work():
    async def run():
        tasks: dict[str, TaskRecord] = {}
        lock = asyncio.Lock()
        persisted: list[str] = []
        pruned: list[str] = []
        scheduled: list[object] = []

        async def fake_run_task(record: TaskRecord):
            record.progress = 100

        def spawn_background_task(coro):
            scheduled.append(coro)
            return object()

        payload = await enqueue_task(
            tasks,
            lock,
            task_type="generate_report",
            params={"mode": "demo"},
            session_id="session-1",
            prune_in_memory=lambda now=None: pruned.append("memory"),
            persist_record=lambda record: persisted.append(record.task_id),
            prune_persisted=lambda: pruned.append("persisted"),
            run_task=fake_run_task,
            spawn_background_task=spawn_background_task,
            logger=logging.getLogger("test-task-runtime"),
        )

        assert payload["task_type"] == "generate_report"
        assert payload["session_id"] == "session-1"
        assert payload["task_id"] in tasks
        assert persisted == [payload["task_id"]]
        assert pruned == ["memory", "persisted"]
        assert len(scheduled) == 1
        for coro in scheduled:
            coro.close()

    asyncio.run(run())


def test_enqueue_task_arq_backend_persists_and_queues_without_local_spawn():
    async def run():
        tasks: dict[str, TaskRecord] = {}
        lock = asyncio.Lock()
        persisted: list[str] = []
        scheduled: list[object] = []
        queued: list[str] = []

        async def fake_run_task(record: TaskRecord):
            record.progress = 100

        async def fake_enqueue_external_task(record: TaskRecord):
            queued.append(record.task_id)
            return "queued"

        def spawn_background_task(coro):
            scheduled.append(coro)
            return object()

        payload = await enqueue_task(
            tasks,
            lock,
            task_type="web_research",
            params={"query": "AI agents"},
            session_id="session-1",
            prune_in_memory=lambda now=None: None,
            persist_record=lambda record: persisted.append(record.task_id),
            prune_persisted=lambda: None,
            run_task=fake_run_task,
            spawn_background_task=spawn_background_task,
            logger=logging.getLogger("test-task-runtime"),
            task_backend="arq",
            enqueue_external_task=fake_enqueue_external_task,
        )

        assert payload["task_id"] in tasks
        assert persisted == [payload["task_id"]]
        assert queued == [payload["task_id"]]
        assert scheduled == []

    asyncio.run(run())


def test_task_queue_backend_dispatches_memory_and_arq_records():
    async def run():
        record = TaskRecord(
            task_id="task-1",
            task_type="generate_report",
            status=TaskStatus.PENDING,
            params={},
            session_id="session-1",
            created_at=1.0,
            updated_at=1.0,
        )
        scheduled: list[str] = []
        queued: list[str] = []

        async def fake_run_task(task_record: TaskRecord):
            scheduled.append(task_record.task_id)

        def spawn_background_task(coro):
            coro.close()
            scheduled.append("spawned")
            return object()

        async def fake_enqueue_external_task(task_record: TaskRecord):
            queued.append(task_record.task_id)
            return "job-1"

        memory_backend = await dispatch_task_record(
            record,
            task_backend="memory",
            run_task=fake_run_task,
            spawn_background_task=spawn_background_task,
        )
        arq_backend = await dispatch_task_record(
            record,
            task_backend="arq",
            run_task=fake_run_task,
            spawn_background_task=spawn_background_task,
            enqueue_external_task=fake_enqueue_external_task,
        )

        assert memory_backend == "memory"
        assert arq_backend == "arq"
        assert scheduled == ["spawned"]
        assert queued == ["task-1"]
        assert build_task_queue_backend("redis", enqueue_external_task=fake_enqueue_external_task).name == "arq"

    asyncio.run(run())


def test_normalize_task_backend_accepts_memory_and_arq_aliases():
    assert normalize_task_backend("memory") == "memory"
    assert normalize_task_backend("local") == "memory"
    assert normalize_task_backend("arq") == "arq"
    assert normalize_task_backend("redis") == "arq"


def test_arq_queue_name_from_env_uses_default_and_override(monkeypatch):
    monkeypatch.delenv("ARQ_QUEUE_NAME", raising=False)
    assert arq_queue_name_from_env() == "insightdesk:tasks"

    monkeypatch.setenv("ARQ_QUEUE_NAME", "custom:tasks")
    assert arq_queue_name_from_env() == "custom:tasks"


def test_arq_worker_settings_from_env_use_defaults_and_overrides(monkeypatch):
    monkeypatch.delenv("ARQ_WORKER_MAX_JOBS", raising=False)
    monkeypatch.delenv("ARQ_KEEP_RESULT_SECONDS", raising=False)
    assert arq_worker_max_jobs_from_env() == 4
    assert arq_keep_result_from_env() == 3600

    monkeypatch.setenv("ARQ_WORKER_MAX_JOBS", "8")
    monkeypatch.setenv("ARQ_KEEP_RESULT_SECONDS", "900")
    assert arq_worker_max_jobs_from_env() == 8
    assert arq_keep_result_from_env() == 900


def test_task_runtime_helpers_reexport_arq_worker_start_policy(monkeypatch):
    monkeypatch.setenv("ARQ_RETRY_ATTEMPTS", "2")

    assert arq_should_start_task_record(status=TaskStatus.PENDING, job_try=1) is True
    assert arq_should_start_task_record(status=TaskStatus.COMPLETED, job_try=1) is False
    assert arq_should_start_task_record(status=TaskStatus.FAILED, job_try=2) is True
