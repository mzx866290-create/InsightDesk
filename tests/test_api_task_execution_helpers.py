import asyncio
from pathlib import Path

from api_task_execution_helpers import (
    run_analyze_knowledge_base_task,
    run_generate_report_task,
    run_placeholder_task,
)
from api_task_store import TaskRecord, TaskStatus


def test_run_analyze_knowledge_base_task_updates_progress_and_result(monkeypatch):
    import doc_pipeline

    events: list[tuple[str, object]] = []

    class FakePipeline:
        def __init__(self, vector_store_path=None):
            self.vector_store_path = vector_store_path

        def load_store(self):
            events.append(("load_store", self.vector_store_path))
            return True

        def get_stats(self):
            events.append(("get_stats", self.vector_store_path))
            return {"total_docs": 7, "store_path": self.vector_store_path}

    monkeypatch.setattr(doc_pipeline, "DocPipeline", FakePipeline)

    record = TaskRecord(
        task_id="task-analyze",
        task_type="analyze_knowledge_base",
        status=TaskStatus.RUNNING,
        params={"vector_store_path": "vector_store"},
        session_id=None,
        created_at=1.0,
        updated_at=1.0,
    )
    progress: list[int] = []

    async def run():
        await run_analyze_knowledge_base_task(
            record,
            set_progress=lambda value: _append_progress(progress, value),
            effective_vector_store_path=lambda value=None: value or "vector_store",
        )

    asyncio.run(run())

    assert progress == [30, 80]
    assert events == [("load_store", "vector_store"), ("get_stats", "vector_store")]
    assert "7" in (record.result or "")


def test_run_generate_report_task_counts_session_messages(monkeypatch, tmp_path):
    import chat_store

    db_path = tmp_path / "chat_history.db"

    class TestSQLiteChatMessageHistory(chat_store.SQLiteChatMessageHistory):
        def __init__(self, session_id: str, db_path_arg: str = "./chat_history.db"):
            super().__init__(session_id=session_id, db_path=str(db_path))

    monkeypatch.setattr(chat_store, "SQLiteChatMessageHistory", TestSQLiteChatMessageHistory)

    history = TestSQLiteChatMessageHistory("report-session")
    history.add_user_message("u1")
    history.add_ai_message("a1")
    history.add_user_message("u2")

    record = TaskRecord(
        task_id="task-report",
        task_type="generate_report",
        status=TaskStatus.RUNNING,
        params={},
        session_id="report-session",
        created_at=1.0,
        updated_at=1.0,
    )
    progress: list[int] = []

    async def run():
        await run_generate_report_task(
            record,
            set_progress=lambda value: _append_progress(progress, value),
        )

    asyncio.run(run())

    assert progress == [40, 90]
    assert "3" in (record.result or "")


def test_run_placeholder_task_sets_progress_and_result():
    record = TaskRecord(
        task_id="task-generic",
        task_type="custom_demo",
        status=TaskStatus.RUNNING,
        params={},
        session_id=None,
        created_at=1.0,
        updated_at=1.0,
    )
    progress: list[int] = []

    async def run():
        await run_placeholder_task(
            record,
            set_progress=lambda value: _append_progress(progress, value),
        )

    asyncio.run(run())

    assert progress == [20, 50, 80]
    assert "custom_demo" in (record.result or "")


async def _append_progress(progress: list[int], value: int) -> None:
    progress.append(value)
