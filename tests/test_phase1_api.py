import asyncio
import json
import sys
import types
from pathlib import Path

from fastapi.testclient import TestClient
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage

import agent_core
import api_server
import chat_store


def _history_cls_for_db(db_path: Path):
    class TestSQLiteChatMessageHistory(chat_store.SQLiteChatMessageHistory):
        def __init__(self, session_id: str, db_path_arg: str = "./chat_history.db"):
            super().__init__(session_id=session_id, db_path=str(db_path))

    return TestSQLiteChatMessageHistory


def test_session_messages_returns_full_history(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    test_history_cls = _history_cls_for_db(db_path)

    monkeypatch.setattr(chat_store, "SQLiteChatMessageHistory", test_history_cls)
    monkeypatch.setattr(chat_store, "CONTEXT_HISTORY_MESSAGES", 2)
    monkeypatch.setenv("CONTEXT_HISTORY_MESSAGES", "2")

    history = test_history_cls("session-full-history")
    history.add_message(HumanMessage(content="u1"))
    history.add_message(AIMessage(content="a1"))
    history.add_message(HumanMessage(content="u2"))
    history.add_message(AIMessage(content="a2"))
    history.add_message(HumanMessage(content="u3"))

    client = TestClient(api_server.app)
    response = client.get("/api/sessions/session-full-history/messages")

    assert response.status_code == 200
    payload = response.json()
    assert payload["context_limit"] == 2
    assert payload["total_messages"] == 5
    assert [item["content"] for item in payload["messages"]] == ["u1", "a1", "u2", "a2", "u3"]


def test_knowledge_base_delete_enforces_project_boundaries(monkeypatch, tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    valid_kb = project_root / "kb_valid"
    valid_kb.mkdir()
    (valid_kb / "index.faiss").write_text("ok", encoding="utf-8")

    missing_index = project_root / "kb_missing_index"
    missing_index.mkdir()

    outside_dir = tmp_path / "outside_kb"
    outside_dir.mkdir()
    (outside_dir / "index.faiss").write_text("ok", encoding="utf-8")

    monkeypatch.setattr(api_server, "PROJECT_ROOT", project_root.resolve())
    monkeypatch.setenv("VECTOR_STORE_PATH", "kb_valid")

    client = TestClient(api_server.app)

    outside_response = client.delete(
        "/api/knowledge-base/by-path",
        params={"path": str(outside_dir.resolve())},
    )
    assert outside_response.status_code == 403

    missing_index_response = client.delete(
        "/api/knowledge-base/by-path",
        params={"path": str(missing_index.resolve())},
    )
    assert missing_index_response.status_code == 400

    default_delete_response = client.delete("/api/knowledge-base")
    assert default_delete_response.status_code == 200
    assert not valid_kb.exists()


def test_agent_cache_key_uses_full_prompt_and_template_hash(monkeypatch):
    calls: list[dict] = []

    async def fake_build_agent(**kwargs):
        calls.append(kwargs)
        return {"build_index": len(calls)}

    api_server._agent_cache.clear()
    monkeypatch.setattr(agent_core, "build_agent", fake_build_agent)

    model_config = api_server.ModelConfig(
        panel_id="panel-1",
        provider="local",
        model="qwen2.5:7b",
        base_url="http://localhost:11434",
        api_key="",
        temperature=0.3,
        agent_mode="auto",
    )

    prompt_prefix = "p" * 64
    template_prefix = "t" * 128

    first = asyncio.run(
        api_server._get_or_build_agent(
            model_config,
            system_prompt=prompt_prefix + "-one",
            dashboard_template={"title_hint": template_prefix + "-one"},
        )
    )
    second = asyncio.run(
        api_server._get_or_build_agent(
            model_config,
            system_prompt=prompt_prefix + "-two",
            dashboard_template={"title_hint": template_prefix + "-two"},
        )
    )
    third = asyncio.run(
        api_server._get_or_build_agent(
            model_config,
            system_prompt=prompt_prefix + "-one",
            dashboard_template={"title_hint": template_prefix + "-one"},
        )
    )

    assert len(calls) == 2
    assert first != second
    assert first == third


def test_local_ollama_temperature_uses_requested_value(monkeypatch):
    dummy_module = types.SimpleNamespace(
        ChatOllama=lambda **kwargs: kwargs,
    )
    monkeypatch.setitem(sys.modules, "langchain_ollama", dummy_module)

    llm = agent_core.get_llm(
        provider="local",
        model_name="qwen2.5:7b",
        base_url="http://localhost:11434",
        api_key="",
        temperature=0.77,
    )

    assert llm["temperature"] == 0.77


def test_build_agent_auto_routes_cloud_to_function_calling(monkeypatch):
    langgraph_calls: list[dict] = []
    tool_calls: list[dict] = []

    monkeypatch.setattr(agent_core, "get_llm", lambda *args, **kwargs: object())

    async def fake_build_langgraph_agent(*args, **kwargs):
        langgraph_calls.append(kwargs)
        return object()

    def fake_create_tools(*args, **kwargs):
        tool_calls.append(kwargs)
        return []

    monkeypatch.setattr(agent_core, "build_langgraph_agent", fake_build_langgraph_agent)
    monkeypatch.setattr(agent_core, "create_tools", fake_create_tools)

    agent = asyncio.run(
        agent_core.build_agent(
            provider="cloud",
            agent_mode="auto",
            knowledge_base_enabled=False,
            web_search_enabled=False,
        )
    )

    assert agent.__class__.__name__ == "PlainChatWrapper"
    assert not langgraph_calls
    assert len(tool_calls) == 1


def test_query_knowledge_uses_top3_and_fetch_k_10_by_default():
    class FakePipeline:
        def __init__(self):
            self.vectorstore = object()
            self.vector_store_path = "./vector_store"
            self.calls: list[tuple[str, int, int]] = []

        def search_with_rerank(self, question: str, k: int, fetch_k: int):
            self.calls.append((question, k, fetch_k))
            return [
                Document(
                    page_content="第一段内容",
                    metadata={"source": "doc-a.md"},
                )
            ]

    pipeline = FakePipeline()
    query_tool = next(
        tool for tool in agent_core.create_tools(pipeline) if tool.name == "query_knowledge"
    )

    result = asyncio.run(query_tool.ainvoke({"question": "测试问题"}))

    assert pipeline.calls == [("测试问题", 3, 10)]
    assert "【文档 1: doc-a.md】" in result
    assert "__SOURCES__:" in result


def test_chat_parallel_waits_for_all_producers(monkeypatch):
    async def fake_invoke_agent_stream(
        panel_id,
        mc,
        user_input,
        session_id,
        web_search_enabled,
        knowledge_base_enabled,
        **kwargs,
    ):
        yield f"data: {json.dumps({'panel_id': panel_id, 'type': 'token', 'content': panel_id})}\n\n"
        if panel_id == "panel-1":
            await asyncio.sleep(0.02)
        else:
            await asyncio.sleep(0.01)
        yield f"data: {json.dumps({'panel_id': panel_id, 'type': 'done'})}\n\n"

    monkeypatch.setattr(api_server, "_invoke_agent_stream", fake_invoke_agent_stream)

    client = TestClient(api_server.app)
    response = client.post(
        "/api/chat/parallel",
        json={
            "session_id": "parallel-test",
            "message": "hello",
            "images": [],
            "files": [],
            "web_search_enabled": False,
            "knowledge_base_enabled": False,
            "models": [
                {
                    "panel_id": "panel-1",
                    "provider": "local",
                    "model": "qwen2.5:7b",
                    "base_url": "http://localhost:11434",
                    "api_key": "",
                    "temperature": 0.3,
                    "agent_mode": "auto",
                },
                {
                    "panel_id": "panel-2",
                    "provider": "cloud",
                    "model": "gpt-4o-mini",
                    "base_url": "https://example.invalid/v1",
                    "api_key": "test-key",
                    "temperature": 0.3,
                    "agent_mode": "auto",
                },
            ],
        },
    )

    assert response.status_code == 200
    assert '"panel_id": "panel-1"' in response.text
    assert '"panel_id": "panel-2"' in response.text
    assert '"type": "all_done"' in response.text
