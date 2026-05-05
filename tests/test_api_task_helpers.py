import asyncio

from backend.helpers.task_helpers import (
    contains_dashboard_card,
    create_inline_task_record,
    prune_task_records,
    set_inline_task_state,
    summarize_dashboard_task_error,
    summarize_dashboard_task_result,
)
from backend.api_task_store import TaskRecord, TaskStatus


def test_dashboard_summary_helpers_extract_title_and_strip_markup():
    content = (
        ':::dashboard-card\n{"title":"营收看板","metrics":[1,2]}\n:::\n'
        "Additional plain text details."
    )

    assert contains_dashboard_card(content) is True
    assert summarize_dashboard_task_result(content) == "知识看板已生成：营收看板"
    assert summarize_dashboard_task_error(content) == "Additional plain text details."


def test_prune_task_records_removes_expired_and_excess_terminal_tasks():
    tasks = {
        "expired": TaskRecord(
            task_id="expired",
            task_type="demo",
            status=TaskStatus.COMPLETED,
            params={},
            session_id=None,
            created_at=1.0,
            updated_at=1.0,
        ),
        "old-terminal": TaskRecord(
            task_id="old-terminal",
            task_type="demo",
            status=TaskStatus.FAILED,
            params={},
            session_id=None,
            created_at=2.0,
            updated_at=9.0,
        ),
        "new-terminal": TaskRecord(
            task_id="new-terminal",
            task_type="demo",
            status=TaskStatus.COMPLETED,
            params={},
            session_id=None,
            created_at=3.0,
            updated_at=10.0,
        ),
        "running": TaskRecord(
            task_id="running",
            task_type="demo",
            status=TaskStatus.RUNNING,
            params={},
            session_id=None,
            created_at=4.0,
            updated_at=4.0,
        ),
    }

    removed = prune_task_records(
        tasks,
        history_limit=2,
        ttl_seconds=5,
        now=12.0,
    )

    assert removed == 2
    assert set(tasks) == {"new-terminal", "running"}


def test_inline_task_helpers_create_and_update_records():
    async def run():
        tasks: dict[str, TaskRecord] = {}
        lock = asyncio.Lock()
        persisted: list[tuple[str, str, int, str | None, str | None]] = []
        pruned: list[str] = []

        def prune_in_memory(now=None):
            pruned.append("memory")

        def persist_record(record: TaskRecord):
            persisted.append(
                (
                    record.task_type,
                    record.status.value,
                    record.progress,
                    record.result,
                    record.error,
                )
            )

        def prune_persisted():
            pruned.append("persisted")

        record = await create_inline_task_record(
            tasks,
            lock,
            task_type="generate_dashboard",
            params={"panel_id": "panel-main"},
            session_id="session-1",
            progress=20,
            prune_in_memory=prune_in_memory,
            persist_record=persist_record,
            prune_persisted=prune_persisted,
        )
        assert record.task_id in tasks
        assert record.status == TaskStatus.RUNNING
        assert record.progress == 20

        updated = await set_inline_task_state(
            tasks,
            lock,
            record=record,
            status=TaskStatus.COMPLETED,
            progress=100,
            result="done",
            prune_in_memory=prune_in_memory,
            persist_record=persist_record,
            prune_persisted=prune_persisted,
        )
        assert updated.status == TaskStatus.COMPLETED
        assert updated.result == "done"
        assert tasks[record.task_id].status == TaskStatus.COMPLETED
        assert persisted[0][1] == "running"
        assert persisted[-1][1] == "completed"
        assert pruned == ["memory", "persisted", "memory", "persisted"]

    asyncio.run(run())
