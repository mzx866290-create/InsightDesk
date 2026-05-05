import asyncio
from pathlib import Path

import pytest

import backend.helpers.task_execution_helpers as task_execution_helpers
from backend.helpers.task_execution_helpers import (
    run_analyze_knowledge_base_task,
    run_generate_deck_task,
    run_multi_agent_workflow_task,
    run_promote_attachment_to_kb_task,
    run_generate_report_task,
    run_placeholder_task,
)
from backend.api_task_store import TaskRecord, TaskStatus


def test_run_analyze_knowledge_base_task_updates_progress_and_result(monkeypatch):
    import backend.doc_pipeline as doc_pipeline

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
    import backend.chat_store as chat_store

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
    saved_artifacts: list[dict[str, object]] = []

    async def run():
        await run_generate_report_task(
            record,
            set_progress=lambda value: _append_progress(progress, value),
            resolve_report_messages=lambda history, **kwargs: history.get_all_messages(),
            ensure_deckable_chat=lambda messages: [("u1", "a1")],
            build_chat_report_title=lambda messages: "Weekly Brief",
            build_report_markdown=lambda messages, title: f"# {title}\n\na1",
            build_report_artifact=lambda **kwargs: {
                "artifact_id": "artifact-report-1",
                **kwargs,
            },
            save_artifact=lambda artifact: saved_artifacts.append(artifact),
        )

    asyncio.run(run())

    assert progress == [25, 55, 90]
    assert record.result == "报告《Weekly Brief》已生成，可预览或下载。"
    assert record.params["report_title"] == "Weekly Brief"
    assert record.params["artifact_id"] == "artifact-report-1"
    assert record.params["report_scope"] == "session"
    assert "# Weekly Brief" in str(record.params["report_markdown"])
    assert saved_artifacts == [
        {
            "artifact_id": "artifact-report-1",
            "session_id": "report-session",
            "title": "Weekly Brief",
            "markdown": "# Weekly Brief\n\na1",
            "qa_pairs": [("u1", "a1")],
            "answer_group_id": "",
            "panel_id": "",
        }
    ]


def test_run_generate_report_task_supports_scoped_report(monkeypatch, tmp_path):
    import backend.chat_store as chat_store
    from backend.api_deck_report_helpers import resolve_report_messages
    from langchain_core.messages import AIMessage, HumanMessage

    db_path = tmp_path / "chat_history.db"

    class TestSQLiteChatMessageHistory(chat_store.SQLiteChatMessageHistory):
        def __init__(self, session_id: str, db_path_arg: str = "./chat_history.db"):
            super().__init__(session_id=session_id, db_path=str(db_path))

    monkeypatch.setattr(chat_store, "SQLiteChatMessageHistory", TestSQLiteChatMessageHistory)

    history = TestSQLiteChatMessageHistory("scoped-report-session")
    history.add_user_message("Trend scan", answer_group_id="group-1")
    history.add_ai_message(
        "Panel A answer",
        panel_id="panel-a",
        answer_group_id="group-1",
    )
    history.add_ai_message(
        "Panel B research answer",
        panel_id="panel-b",
        answer_group_id="group-1",
        sources=[{"title": "Live feed", "snippet": "Realtime update"}],
        task_type="web_research",
        model_id="web_research",
    )

    record = TaskRecord(
        task_id="task-report-scoped",
        task_type="generate_report",
        status=TaskStatus.RUNNING,
        params={"answer_group_id": "group-1", "panel_id": "panel-b"},
        session_id="scoped-report-session",
        created_at=1.0,
        updated_at=1.0,
    )
    progress: list[int] = []
    saved_artifacts: list[dict[str, object]] = []

    async def run():
        await run_generate_report_task(
            record,
            set_progress=lambda value: _append_progress(progress, value),
            resolve_report_messages=lambda history, **kwargs: resolve_report_messages(
                history,
                human_message_factory=lambda content: HumanMessage(content=content),
                ai_message_factory=lambda content: AIMessage(content=content),
                **kwargs,
            ),
            ensure_deckable_chat=lambda messages: [("Trend scan", "Panel B research answer")],
            build_chat_report_title=lambda messages: "Trend scan",
            build_report_markdown=lambda messages, title: f"# {title}\n\n{messages[1].content}",
            build_report_artifact=lambda **kwargs: {
                "artifact_id": "artifact-report-scoped",
                **kwargs,
            },
            save_artifact=lambda artifact: saved_artifacts.append(artifact),
        )

    asyncio.run(run())

    assert progress == [25, 55, 90]
    assert record.params["report_scope"] == "answer_group"
    assert record.params["artifact_id"] == "artifact-report-scoped"
    assert record.params["answer_group_id"] == "group-1"
    assert record.params["panel_id"] == "panel-b"
    assert "Panel B research answer" in str(record.params["report_markdown"])
    assert saved_artifacts[0]["answer_group_id"] == "group-1"
    assert saved_artifacts[0]["panel_id"] == "panel-b"
    assert "参考来源" in str(record.params["report_markdown"])


def test_run_generate_deck_task_supports_scoped_deck(monkeypatch, tmp_path):
    import backend.chat_store as chat_store
    from backend.api_deck_report_helpers import resolve_report_messages
    from langchain_core.messages import AIMessage, HumanMessage
    from types import SimpleNamespace

    db_path = tmp_path / "chat_history.db"

    class TestSQLiteChatMessageHistory(chat_store.SQLiteChatMessageHistory):
        def __init__(self, session_id: str, db_path_arg: str = "./chat_history.db"):
            super().__init__(session_id=session_id, db_path=str(db_path))

    monkeypatch.setattr(chat_store, "SQLiteChatMessageHistory", TestSQLiteChatMessageHistory)

    history = TestSQLiteChatMessageHistory("scoped-deck-session")
    history.add_user_message("Trend scan", answer_group_id="group-9")
    history.add_ai_message(
        "Panel A answer",
        panel_id="panel-a",
        answer_group_id="group-9",
    )
    history.add_ai_message(
        "Panel B research answer",
        panel_id="panel-b",
        answer_group_id="group-9",
        sources=[{"title": "Live feed", "snippet": "Realtime update"}],
        task_type="web_research",
        model_id="web_research",
    )

    record = TaskRecord(
        task_id="task-deck-scoped",
        task_type="generate_deck",
        status=TaskStatus.RUNNING,
        params={
            "panel_config": {
                "panel_id": "panel-b",
                "provider": "ollama",
                "connection_type": "ollama",
                "model": "qwen3.5-2B:latest",
                "base_url": "http://localhost:11434",
                "api_key": "",
                "temperature": 0.3,
                "agent_mode": "auto",
            },
            "knowledge_base_enabled": False,
            "target_slide_count": 6,
            "theme": "sunrise",
            "answer_group_id": "group-9",
            "panel_id": "panel-b",
        },
        session_id="scoped-deck-session",
        created_at=1.0,
        updated_at=1.0,
    )
    progress: list[int] = []
    saved: list[object] = []
    saved_artifacts: list[object] = []

    async def fake_build_deck(**kwargs):
        assert kwargs["session_id"] == "scoped-deck-session"
        assert kwargs["knowledge_base_enabled"] is False
        assert kwargs["target_slide_count"] == 6
        assert kwargs["theme"] == "sunrise"
        assert kwargs["source_answer_group_id"] == "group-9"
        assert kwargs["source_panel_id"] == "panel-b"
        assert kwargs["panel_config"].panel_id == "panel-b"
        assert kwargs["system_prompt"] is None
        assert kwargs["vector_store_path"] is None
        assert kwargs["messages"][0].content == "Trend scan"
        assert "Panel B research answer" in kwargs["messages"][1].content
        assert "Panel A answer" not in kwargs["messages"][1].content
        return SimpleNamespace(
            deck_id="deck-task-1",
            meta=SimpleNamespace(title="Trend Scan Deck"),
        )

    async def run():
        await run_generate_deck_task(
            record,
            set_progress=lambda value: _append_progress(progress, value),
            resolve_report_messages=lambda history, **kwargs: resolve_report_messages(
                history,
                human_message_factory=lambda content: HumanMessage(content=content),
                ai_message_factory=lambda content: AIMessage(content=content),
                **kwargs,
            ),
            normalize_model_config=lambda config: SimpleNamespace(**config),
            resolve_active_prompt_runtime=lambda enabled: (None, None, {}),
            build_deck=fake_build_deck,
            save_deck=lambda deck: saved.append(deck),
            build_deck_artifact=lambda deck: {
                "artifact_id": "artifact-deck-1",
                "deck_id": deck.deck_id,
            },
            save_artifact=lambda artifact: saved_artifacts.append(artifact),
        )

    asyncio.run(run())

    assert progress == [20, 45, 85]
    assert len(saved) == 1
    assert saved_artifacts == [{"artifact_id": "artifact-deck-1", "deck_id": "deck-task-1"}]
    assert record.params["artifact_id"] == "artifact-deck-1"
    assert record.params["deck_id"] == "deck-task-1"
    assert record.params["deck_title"] == "Trend Scan Deck"
    assert record.params["deck_scope"] == "answer_group"
    assert record.params["answer_group_id"] == "group-9"
    assert record.params["panel_id"] == "panel-b"
    assert "Trend Scan Deck" in (record.result or "")


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


def test_run_multi_agent_workflow_task_waits_for_approval(monkeypatch):
    record = TaskRecord(
        task_id="task-workflow-waiting",
        task_type="multi_agent_workflow",
        status=TaskStatus.RUNNING,
        params={"user_request": "Publish the report externally"},
        session_id="session-1",
        created_at=1.0,
        updated_at=1.0,
    )
    progress: list[int] = []

    async def fake_run_orchestrator(user_request: str, *, context=None, **kwargs):
        assert user_request == "Publish the report externally"
        assert context == {}
        return {
            "status": "waiting_approval",
            "plan": [
                {
                    "id": "step-1",
                    "agent": "writing",
                    "task_type": "writing",
                    "status": "waiting_approval",
                    "requires_approval": True,
                    "approval_status": "pending",
                }
            ],
            "approval_reason": "Report publication requires review",
            "approval_step_id": "step-1",
            "final_output": "",
        }

    monkeypatch.setattr(task_execution_helpers, "run_orchestrator", fake_run_orchestrator)

    async def run():
        await run_multi_agent_workflow_task(
            record,
            set_progress=lambda value: _append_progress(progress, value),
        )

    asyncio.run(run())

    assert progress == [20, 80]
    assert record.params["workflow_status"] == "waiting_approval"
    assert record.params["approval_reason"] == "Report publication requires review"
    assert record.params["approval_step_id"] == "step-1"
    assert "waiting for human approval" in (record.result or "")


def test_run_multi_agent_workflow_task_resumes_after_approval(monkeypatch):
    record = TaskRecord(
        task_id="task-workflow-approved",
        task_type="multi_agent_workflow",
        status=TaskStatus.RUNNING,
        params={
            "user_request": "Publish the report externally",
            "workflow_state": {"status": "waiting_approval", "plan": []},
            "approval_decision": "approved",
            "approval_reviewer": "owner-1",
            "approval_comment": "Looks good",
        },
        session_id="session-1",
        created_at=1.0,
        updated_at=1.0,
    )
    progress: list[int] = []

    async def fake_resume_orchestrator(state, **kwargs):
        assert state == {"status": "waiting_approval", "plan": []}
        assert kwargs["approval_decision"] == "approved"
        assert kwargs["approval_reviewer"] == "owner-1"
        assert kwargs["approval_comment"] == "Looks good"
        return {
            "status": "completed",
            "plan": [{"id": "step-1", "status": "completed"}],
            "final_output": "Workflow finished successfully.",
            "approval_decision": "approved",
        }

    monkeypatch.setattr(task_execution_helpers, "resume_orchestrator", fake_resume_orchestrator)

    async def run():
        await run_multi_agent_workflow_task(
            record,
            set_progress=lambda value: _append_progress(progress, value),
        )

    asyncio.run(run())

    assert progress == [20, 80]
    assert record.params["workflow_status"] == "completed"
    assert record.params["approval_decision"] == "approved"
    assert record.params["workflow_final_output"] == "Workflow finished successfully."
    assert record.result == "Workflow finished successfully."
    assert "approval_comment" not in record.params


def test_run_multi_agent_workflow_task_uses_seed_plan_and_runtime_research_config(monkeypatch):
    record = TaskRecord(
        task_id="task-workflow-plan",
        task_type="multi_agent_workflow",
        status=TaskStatus.RUNNING,
        params={
            "user_request": "Research the AI slide market",
            "context": {"session_id": "session-1"},
            "plan": [
                {
                    "id": "step-1",
                    "agent": "research",
                    "task_type": "research",
                    "description": "Research the AI slide market",
                    "input": "AI slide market",
                    "metadata": {"research_mode": "deep"},
                }
            ],
            "panel_config": {
                "provider": "ollama",
                "model": "qwen3:latest",
                "base_url": "http://localhost:11434",
                "api_key": "",
                "temperature": 0.2,
            },
            "research_mode": "deep",
            "providers": ["tavily", "exa"],
            "max_rounds": 2,
            "max_results_per_query": 5,
            "max_fetch_pages": 4,
        },
        session_id="session-1",
        created_at=1.0,
        updated_at=1.0,
    )
    progress: list[int] = []

    monkeypatch.setattr(task_execution_helpers, "_model_config_value", lambda cfg, key, default=None: cfg.get(key, default))

    def fake_create_llm(provider, model, base_url, api_key, temperature):
        assert provider == "ollama"
        assert model == "qwen3:latest"
        assert base_url == "http://localhost:11434"
        assert api_key == ""
        assert temperature == 0.2
        return "fake-llm"

    async def fake_run_orchestrator(user_request: str, **kwargs):
        assert user_request == "Research the AI slide market"
        assert kwargs["context"] == {"session_id": "session-1"}
        assert kwargs["plan"][0]["agent"] == "research"
        assert kwargs["llm"] == "fake-llm"
        assert kwargs["research_config"].mode == "deep"
        assert list(kwargs["research_config"].providers or []) == ["tavily", "exa"]
        assert kwargs["research_config"].max_results_per_query == 5
        return {
            "status": "completed",
            "plan": kwargs["plan"],
            "agent_results": {"step-1": {"status": "completed", "agent": "research"}},
            "agent_metrics": {
                "step-1": {
                    "agent": "research",
                    "status": "completed",
                    "total_tokens": 42,
                    "estimated_cost_usd": 0.0042,
                }
            },
            "agent_cost_summary": {
                "step_count": 1,
                "completed_count": 1,
                "failed_count": 0,
                "total_tokens": 42,
                "estimated_cost_usd": 0.0042,
            },
            "final_output": "Workflow finished with seeded plan.",
        }

    monkeypatch.setattr(task_execution_helpers, "run_orchestrator", fake_run_orchestrator)

    async def run():
        await run_multi_agent_workflow_task(
            record,
            set_progress=lambda value: _append_progress(progress, value),
            normalize_model_config=lambda value: value,
            create_llm=fake_create_llm,
        )

    asyncio.run(run())

    assert progress == [20, 80]
    assert record.params["workflow_status"] == "completed"
    assert record.params["workflow_agent_results"]["step-1"]["agent"] == "research"
    assert record.params["workflow_agent_metrics"]["step-1"]["total_tokens"] == 42
    assert record.params["workflow_agent_cost_summary"]["estimated_cost_usd"] == 0.0042
    assert record.result == "Workflow finished with seeded plan."


def test_run_multi_agent_workflow_task_persists_chat_result(monkeypatch):
    record = TaskRecord(
        task_id="task-workflow-chat",
        task_type="multi_agent_workflow",
        status=TaskStatus.RUNNING,
        params={
            "user_request": "Research the AI slide market",
            "panel_id": "panel-main",
            "answer_group_id": "grp-1",
            "workflow_agent_results": {
                "step-1": {
                    "agent": "research",
                    "sources": [{"title": "Market report", "url": "https://example.com/report"}],
                }
            },
        },
        session_id="session-1",
        created_at=1.0,
        updated_at=1.0,
    )
    persisted: list[dict[str, object]] = []

    async def fake_run_orchestrator(user_request: str, **kwargs):
        return {
            "status": "completed",
            "plan": [{"id": "step-1", "agent": "research", "task_type": "research", "status": "completed"}],
            "agent_results": {
                "step-1": {
                    "agent": "research",
                    "status": "completed",
                    "sources": [{"title": "Market report", "url": "https://example.com/report"}],
                }
            },
            "final_output": "Workflow finished with report.",
        }

    monkeypatch.setattr(task_execution_helpers, "run_orchestrator", fake_run_orchestrator)
    monkeypatch.setattr(
        task_execution_helpers,
        "persist_multi_agent_workflow_task_result",
        lambda current, *, content, db_path="./chat_history.db": persisted.append(
            {"task_id": current.task_id, "content": content, "params": dict(current.params or {})}
        ),
    )

    async def run():
        await run_multi_agent_workflow_task(
            record,
            set_progress=lambda value: _append_progress([], value),
        )

    asyncio.run(run())

    assert record.result == "Workflow finished with report."
    assert persisted
    assert persisted[0]["content"] == "Workflow finished with report."
    assert persisted[0]["params"]["workflow_plan"][0]["status"] == "completed"


def test_run_multi_agent_workflow_task_persists_research_archive(monkeypatch):
    record = TaskRecord(
        task_id="task-workflow-research-archive",
        task_type="multi_agent_workflow",
        status=TaskStatus.RUNNING,
        params={"user_request": "Research the AI slide market"},
        session_id="session-archive",
        created_at=1.0,
        updated_at=1.0,
    )
    saved_artifacts: list[dict[str, object]] = []

    research_artifact = {
        "type": "research_report",
        "version": "v2",
        "query": "AI slide market",
        "claim_evidence_chains": [{"claim_id": "claim-001", "status": "partial"}],
        "claim_verification_summary": {"total_claims": 1, "partial_claims": 1},
    }

    async def fake_run_orchestrator(user_request: str, **kwargs):
        return {
            "status": "completed",
            "plan": [{"id": "step-1", "agent": "research", "task_type": "research", "status": "completed"}],
            "agent_results": {
                "step-1": {
                    "agent": "research",
                    "status": "completed",
                    "output": "Research archive markdown.",
                    "artifacts": [research_artifact],
                    "sources": [{"title": "Market report", "url": "https://example.com/report"}],
                    "metadata": {"research_mode": "deep"},
                }
            },
            "final_output": "Workflow finished with research.",
        }

    def fake_build_research_archive_artifact(**kwargs):
        assert kwargs["session_id"] == "session-archive"
        assert kwargs["task_id"] == "task-workflow-research-archive"
        return {
            "artifact_id": "artifact-research-archive",
            "content": {
                "research_report": kwargs["agent_result"]["artifacts"][0],
            },
        }

    monkeypatch.setattr(task_execution_helpers, "run_orchestrator", fake_run_orchestrator)

    async def run():
        await run_multi_agent_workflow_task(
            record,
            set_progress=lambda value: _append_progress([], value),
            build_research_archive_artifact=fake_build_research_archive_artifact,
            save_artifact=lambda artifact: saved_artifacts.append(artifact),
        )

    asyncio.run(run())

    assert record.params["research_archive_artifact_id"] == "artifact-research-archive"
    assert saved_artifacts[0]["content"]["research_report"]["claim_evidence_chains"][0]["claim_id"] == "claim-001"


def test_run_promote_attachment_to_kb_task_rejects_workspace_mismatch(monkeypatch):
    import backend.chat_store as chat_store

    events: list[tuple[str, object]] = []

    monkeypatch.setattr(
        chat_store,
        "get_session",
        lambda session_id, db_path="./chat_history.db": {
            "session_id": session_id,
            "workspace_id": "workspace-other",
        },
    )

    record = TaskRecord(
        task_id="task-promote-workspace-mismatch",
        task_type="promote_attachment_to_kb",
        status=TaskStatus.RUNNING,
        params={
            "attachment_name": "brief.txt",
            "attachment_kind": "file",
            "attachment_data_url": "data:text/plain;base64,QWxwaGE=",
            "vector_store_path": "vector_store_target",
            "workspace_id": "workspace-alpha",
        },
        session_id="session-1",
        created_at=1.0,
        updated_at=1.0,
    )
    progress: list[int] = []

    async def run():
        await run_promote_attachment_to_kb_task(
            record,
            set_progress=lambda value: _append_progress(progress, value),
            update_progress=lambda task, value: events.append(("progress", value)),
            effective_vector_store_path=lambda value=None: value or "vector_store_target",
            chat_file_suffix=lambda filename: ".txt",
            decode_data_url=lambda data_url, filename: b"Alpha",
            clear_agent_cache=lambda: _append_async_event(events, ("clear_cache", None)),
            logger=type("Logger", (), {"warning": lambda *args, **kwargs: None})(),
        )

    with pytest.raises(
        ValueError,
        match="Attachment source session no longer belongs to the requested workspace.",
    ):
        asyncio.run(run())

    assert progress == []
    assert events == []


async def _append_progress(progress: list[int], value: int) -> None:
    progress.append(value)


async def _append_async_event(events: list[tuple[str, object]], event: tuple[str, object]) -> None:
    events.append(event)
