import asyncio
import logging

from backend.api_task_runtime_helpers import (
    attach_current_kb_status,
    enqueue_task,
    list_tasks_payload,
    task_record_payload,
)
from backend.api_task_store import TaskRecord, TaskStatus


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
