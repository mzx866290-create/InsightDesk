import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

import agent_core
import api_server
import chat_store


def _history_cls_for_db(db_path: Path):
    class TestSQLiteChatMessageHistory(chat_store.SQLiteChatMessageHistory):
        def __init__(self, session_id: str, db_path_arg: str = "./chat_history.db"):
            super().__init__(session_id=session_id, db_path=str(db_path))

    return TestSQLiteChatMessageHistory


def test_pin_session_memory_endpoint_dedupes_and_lists(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)

    history = history_cls("session-memory")
    history.add_user_message("请记住我们的汇报默认使用中文")

    client = TestClient(api_server.app)

    first = client.post(
        "/api/sessions/session-memory/memory/pin",
        json={
            "content": "后续所有汇报默认使用中文，面向 CFO。",
            "kind": "decision",
        },
    )
    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["ok"] is True
    assert first_payload["created"] is True
    assert first_payload["memory"]["kind"] == "decision"

    second = client.post(
        "/api/sessions/session-memory/memory/pin",
        json={
            "content": "后续所有汇报默认使用中文，面向 CFO。",
            "kind": "decision",
        },
    )
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["created"] is False
    assert second_payload["memory"]["id"] == first_payload["memory"]["id"]

    listed = client.get("/api/sessions/session-memory/memory")
    assert listed.status_code == 200
    listed_payload = listed.json()
    assert listed_payload["session_id"] == "session-memory"
    assert listed_payload["memories"] == [second_payload["memory"]]

    filtered = client.get(
        "/api/sessions/session-memory/memory",
        params={"kind": "decision"},
    )
    assert filtered.status_code == 200
    assert len(filtered.json()["memories"]) == 1


def test_pin_session_memory_rejects_invalid_requests(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)
    history_cls("session-invalid")

    client = TestClient(api_server.app)

    missing = client.post(
        "/api/sessions/missing-session/memory/pin",
        json={"content": "keep this"},
    )
    assert missing.status_code == 404

    blank = client.post(
        "/api/sessions/session-invalid/memory/pin",
        json={"content": "   "},
    )
    assert blank.status_code == 400

    invalid_kind = client.post(
        "/api/sessions/session-invalid/memory/pin",
        json={"content": "keep this", "kind": "custom"},
    )
    assert invalid_kind.status_code == 400


def test_patch_session_memory_updates_content_and_kind(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)
    history = history_cls("session-memory-update")
    history.add_user_message("start memory editing test")

    created = chat_store.pin_session_memory(
        "session-memory-update",
        content="initial memory",
        kind="fact",
        db_path=str(db_path),
    )
    assert created is not None
    memory_id = created["memory"]["id"]

    client = TestClient(api_server.app)

    updated = client.patch(
        f"/api/sessions/session-memory-update/memory/{memory_id}",
        json={"content": "updated memory", "kind": "decision"},
    )
    assert updated.status_code == 200
    updated_payload = updated.json()
    assert updated_payload["ok"] is True
    assert updated_payload["memory"]["id"] == memory_id
    assert updated_payload["memory"]["content"] == "updated memory"
    assert updated_payload["memory"]["kind"] == "decision"

    listed = client.get("/api/sessions/session-memory-update/memory")
    assert listed.status_code == 200
    assert listed.json()["memories"][0]["content"] == "updated memory"

    empty_payload = client.patch(
        f"/api/sessions/session-memory-update/memory/{memory_id}",
        json={},
    )
    assert empty_payload.status_code == 400

    invalid_kind = client.patch(
        f"/api/sessions/session-memory-update/memory/{memory_id}",
        json={"kind": "invalid"},
    )
    assert invalid_kind.status_code == 400


def test_summarize_session_memory_creates_and_skips_when_up_to_date(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)
    history = history_cls("session-memory-summary")

    for index in range(7):
        history.add_user_message(f"user-{index}")
        history.add_ai_message(f"assistant-{index}")

    client = TestClient(api_server.app)

    first = client.post("/api/sessions/session-memory-summary/memory/summarize")
    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["ok"] is True
    assert first_payload["created"] is True
    assert first_payload["memory"]["kind"] == "summary"
    assert first_payload["memory"]["meta"]["source"] == "auto"
    first_id = first_payload["memory"]["id"]

    second = client.post("/api/sessions/session-memory-summary/memory/summarize")
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["created"] is False
    assert second_payload["reason"] == "up_to_date"
    assert second_payload["memory"]["id"] == first_id

    for index in range(7, 10):
        history.add_user_message(f"user-{index}")
        history.add_ai_message(f"assistant-{index}")

    third = client.post("/api/sessions/session-memory-summary/memory/summarize")
    assert third.status_code == 200
    third_payload = third.json()
    assert third_payload["memory"]["kind"] == "summary"
    assert third_payload["memory"]["meta"]["message_coverage"] >= 20


def test_summarize_session_memory_rejects_short_sessions(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)
    history = history_cls("session-summary-short")
    history.add_user_message("short session")
    history.add_ai_message("too short")

    client = TestClient(api_server.app)
    response = client.post("/api/sessions/session-summary-short/memory/summarize")

    assert response.status_code == 400
    assert "Need at least" in response.json()["detail"]


def test_summarize_session_memory_uses_llm_when_enabled(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)
    history = history_cls("session-summary-llm")

    for index in range(7):
        history.add_user_message(f"user llm {index}")
        history.add_ai_message(f"assistant llm {index}")

    monkeypatch.setenv("SESSION_MEMORY_SUMMARY_USE_LLM", "1")

    def fake_resolve_model(*args, **kwargs):
        return api_server.ModelConfig(
            panel_id="panel-main",
            provider="ollama",
            connection_type="ollama",
            model="qwen3.5-2B:latest",
            base_url="http://localhost:11434",
            api_key="",
            temperature=0.1,
            agent_mode="auto",
        )

    class FakeLLM:
        async def ainvoke(self, payload):
            class Response:
                content = "阶段摘要：当前目标是完成预算复盘；约束是保持中文输出并聚焦 CFO；下一步整理关键风险与行动项。"

            return Response()

    monkeypatch.setattr(api_server, "_resolve_summary_model_config", fake_resolve_model)
    monkeypatch.setattr(agent_core, "get_llm", lambda *args, **kwargs: FakeLLM())

    client = TestClient(api_server.app)
    response = client.post("/api/sessions/session-summary-llm/memory/summarize")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["memory"]["kind"] == "summary"
    assert payload["memory"]["meta"]["generator"] == "llm"
    assert "阶段摘要" in payload["memory"]["content"]


def test_delete_session_memory_endpoint_and_reset_clears_memories(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)

    history = history_cls("session-delete-memory")
    history.add_user_message("Keep this session alive")

    first = chat_store.pin_session_memory(
        "session-delete-memory",
        content="Always respond in Chinese.",
        kind="decision",
        db_path=str(db_path),
    )
    second = chat_store.pin_session_memory(
        "session-delete-memory",
        content="Summarize finance items first.",
        kind="todo",
        db_path=str(db_path),
    )
    assert first is not None
    assert second is not None

    client = TestClient(api_server.app)

    delete_response = client.delete(
        f"/api/sessions/session-delete-memory/memory/{first['memory']['id']}",
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["ok"] is True

    listed_after_delete = chat_store.list_session_memory(
        "session-delete-memory",
        db_path=str(db_path),
    )
    assert [item["id"] for item in listed_after_delete] == [second["memory"]["id"]]

    reset_response = client.post("/api/sessions/session-delete-memory/reset")
    assert reset_response.status_code == 200

    listed_after_reset = chat_store.list_session_memory(
        "session-delete-memory",
        db_path=str(db_path),
    )
    assert listed_after_reset == []


def test_langgraph_wrapper_injects_session_memory(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    test_history_cls = _history_cls_for_db(db_path)

    monkeypatch.setattr(agent_core, "SQLiteChatMessageHistory", test_history_cls)
    monkeypatch.setattr(agent_core, "get_llm", lambda *args, **kwargs: object())
    monkeypatch.setattr(agent_core, "DocPipeline", lambda *args, **kwargs: object())

    history = test_history_cls("memory-injection-session")
    history.add_message(HumanMessage(content="这轮汇报要面向 CFO"))
    history.add_message(AIMessage(content="收到，我会按财务视角组织输出"))
    chat_store.pin_session_memory(
        "memory-injection-session",
        content="后续输出默认使用中文，受众是 CFO。",
        kind="decision",
        db_path=str(db_path),
    )

    captured_chat_history: dict[str, list] = {}

    async def fake_build_langgraph_agent(*args, **kwargs):
        class FakeApp:
            async def ainvoke(self, state):
                captured_chat_history["value"] = state["chat_history"]
                return {"output": "done", "sources": []}

        return FakeApp()

    monkeypatch.setattr(agent_core, "build_langgraph_agent", fake_build_langgraph_agent)

    agent = asyncio.run(
        agent_core.build_agent(
            provider="local",
            agent_mode="langgraph",
            knowledge_base_enabled=False,
            web_search_enabled=False,
        )
    )

    result = asyncio.run(
        agent.ainvoke(
            {"input": "继续整理汇报提纲"},
            config={
                "configurable": {
                    "session_id": "memory-injection-session",
                    "persist_history": False,
                }
            },
        )
    )

    assert result["output"] == "done"
    chat_history = captured_chat_history["value"]
    assert isinstance(chat_history[0], SystemMessage)
    assert "长期记忆" in chat_history[0].content
    assert "CFO" in chat_history[0].content
    assert [type(message).__name__ for message in chat_history[1:]] == [
        "HumanMessage",
        "AIMessage",
    ]


def test_direct_multimodal_answer_preserves_system_memory_when_truncating():
    class FakeLLM:
        def __init__(self):
            self.payload = None

        async def ainvoke(self, payload):
            self.payload = payload

            class Response:
                content = "ok"

            return Response()

    llm = FakeLLM()
    chat_history = [SystemMessage(content="长期记忆：回答时始终用中文")]
    for index in range(12):
        chat_history.append(HumanMessage(content=f"user-{index}"))
        chat_history.append(AIMessage(content=f"assistant-{index}"))

    result = asyncio.run(
        agent_core._direct_multimodal_answer(
            llm,
            "请继续",
            chat_history,
            system_prompt="你是一个测试助手",
        )
    )

    assert result == "ok"
    assert llm.payload is not None
    assert isinstance(llm.payload[0], SystemMessage)
    assert llm.payload[0].content == "你是一个测试助手"
    assert isinstance(llm.payload[1], SystemMessage)
    assert "长期记忆" in llm.payload[1].content
    assert llm.payload[-1].content == "请继续"
    assert len(llm.payload) == 11
