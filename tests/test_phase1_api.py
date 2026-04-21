import asyncio
import json
import sys
import types
import time
from pathlib import Path

from fastapi.testclient import TestClient
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage

import backend.agent_core as agent_core
import backend.api_config_store as api_config_store
import backend.api_server as api_server
import backend.chat_store as chat_store
import backend.deck_service as deck_service


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


def test_save_config_persists_valid_tavily_key(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    store = api_config_store.SQLiteAppConfigStore(db_path=str(db_path))
    monkeypatch.setattr(api_server, "_app_config_store", store)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    async def fake_validate(api_key: str) -> None:
        assert api_key == "tvly-valid-key"

    monkeypatch.setattr(api_server, "_validate_tavily_api_key", fake_validate)

    client = TestClient(api_server.app)
    response = client.post("/api/config", json={"tavily_api_key": "tvly-valid-key"})

    assert response.status_code == 200
    assert response.json()["tavily_api_key_set"] is True
    assert store.get_value("tavily_api_key") == "tvly-valid-key"
    assert api_server.os.environ.get("TAVILY_API_KEY") == "tvly-valid-key"


def test_save_config_rejects_invalid_tavily_key(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    store = api_config_store.SQLiteAppConfigStore(db_path=str(db_path))
    monkeypatch.setattr(api_server, "_app_config_store", store)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    async def fake_validate(api_key: str) -> None:
        raise api_server.HTTPException(status_code=400, detail="Tavily API Key 无效，保存失败。")

    monkeypatch.setattr(api_server, "_validate_tavily_api_key", fake_validate)

    client = TestClient(api_server.app)
    response = client.post("/api/config", json={"tavily_api_key": "tvly-invalid-key"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Tavily API Key 无效，保存失败。"
    assert store.get("tavily_api_key") is None
    assert api_server.os.environ.get("TAVILY_API_KEY") in (None, "")


def test_get_config_reads_persisted_tavily_key(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    store = api_config_store.SQLiteAppConfigStore(db_path=str(db_path))
    store.set("tavily_api_key", "tvly-persisted-key")
    monkeypatch.setattr(api_server, "_app_config_store", store)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    client = TestClient(api_server.app)
    response = client.get("/api/config")

    assert response.status_code == 200
    assert response.json()["tavily_api_key_set"] is True
    assert api_server.os.environ.get("TAVILY_API_KEY") == "tvly-persisted-key"


def test_save_config_allows_clearing_persisted_tavily_key(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    store = api_config_store.SQLiteAppConfigStore(db_path=str(db_path))
    store.set("tavily_api_key", "tvly-old-key")
    monkeypatch.setattr(api_server, "_app_config_store", store)
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-old-key")

    client = TestClient(api_server.app)
    response = client.post("/api/config", json={"tavily_api_key": ""})

    assert response.status_code == 200
    assert response.json()["tavily_api_key_set"] is False
    assert store.get("tavily_api_key") is None
    assert api_server.os.environ.get("TAVILY_API_KEY") in (None, "")


def test_save_cloud_model_api_key_persists_encrypted_secret(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    store = api_config_store.SQLiteAppConfigStore(db_path=str(db_path))
    monkeypatch.setattr(api_server, "_app_config_store", store)

    client = TestClient(api_server.app)
    response = client.post(
        "/api/config/cloud-model-api-key",
        json={"api_key": "sk-cloud-secret"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["api_key_set"] is True
    assert payload["api_key_ref"].startswith("cmk-")
    assert (
        store.get_value(f"cloud_model_api_key:{payload['api_key_ref']}")
        == "sk-cloud-secret"
    )


def test_delete_cloud_model_api_key_removes_persisted_secret(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    store = api_config_store.SQLiteAppConfigStore(db_path=str(db_path))
    monkeypatch.setattr(api_server, "_app_config_store", store)
    store.set("cloud_model_api_key:cmk-delete-test", "sk-delete-me")

    client = TestClient(api_server.app)
    response = client.delete("/api/config/cloud-model-api-key/cmk-delete-test")

    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert store.get("cloud_model_api_key:cmk-delete-test") is None


def test_resolve_runtime_model_config_uses_stored_cloud_model_key(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    store = api_config_store.SQLiteAppConfigStore(db_path=str(db_path))
    monkeypatch.setattr(api_server, "_app_config_store", store)
    store.set("cloud_model_api_key:cmk-runtime-test", "sk-runtime-secret")

    resolved = api_server._resolve_runtime_model_config(
        {
            "panel_id": "panel-cloud",
            "provider": "openai_compatible",
            "connection_type": "openai_compatible",
            "model": "gpt-4o-mini",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": "",
            "api_key_ref": "cmk-runtime-test",
            "temperature": 0.3,
            "agent_mode": "auto",
        }
    )

    assert resolved.api_key == "sk-runtime-secret"
    assert resolved.api_key_ref == "cmk-runtime-test"


def test_session_messages_restore_assistant_metadata(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    test_history_cls = _history_cls_for_db(db_path)

    monkeypatch.setattr(chat_store, "SQLiteChatMessageHistory", test_history_cls)

    history = test_history_cls("session-metadata")
    history.add_user_message("Summarize the brief", answer_group_id="grp-meta")
    history.add_ai_message(
        "Summary ready",
        model_id="qwen-main",
        panel_id="panel-main",
        answer_group_id="grp-meta",
        sources=[
            {
                "type": "doc",
                "title": "Sales Brief",
                "snippet": "Revenue grew 18% quarter over quarter.",
            }
        ],
        workflow_nodes=[
            {
                "id": "classify_intent",
                "name": "classify_intent",
                "displayName": "Intent Classification",
                "status": "completed",
                "duration": 12,
            },
            {
                "id": "execute_tool",
                "name": "execute_tool",
                "displayName": "Tool Execution",
                "status": "completed",
                "toolName": "query_knowledge",
                "toolResult": "Found 3 matching knowledge chunks.",
                "duration": 48,
            },
            {
                "id": "generate_answer",
                "name": "generate_answer",
                "displayName": "Answer Generation",
                "status": "completed",
                "duration": 35,
            },
        ],
        task_id="task-meta-1",
        task_type="generate_summary",
    )

    chat_store.replace_session_panels(
        "session-metadata",
        [
            {
                "panel_id": "panel-main",
                "provider": "ollama",
                "connection_type": "ollama",
                "model": "qwen-main",
                "base_url": "http://localhost:11434",
                "temperature": 0.3,
                "agent_mode": "langgraph",
            }
        ],
        db_path=str(db_path),
    )

    client = TestClient(api_server.app)
    response = client.get("/api/sessions/session-metadata/messages")

    assert response.status_code == 200
    payload = response.json()
    assistant_message = payload["messages"][1]

    assert assistant_message["sources"][0]["title"] == "Sales Brief"
    assert assistant_message["workflow_nodes"][1]["toolName"] == "query_knowledge"
    assert assistant_message["workflow_nodes"][2]["status"] == "completed"
    assert assistant_message["task_id"] == "task-meta-1"
    assert assistant_message["task_type"] == "generate_summary"
    assert payload["panel_messages"]["panel-main"][1]["workflow_nodes"][0]["id"] == "classify_intent"


def test_session_messages_returns_panel_specific_histories(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    test_history_cls = _history_cls_for_db(db_path)

    monkeypatch.setattr(chat_store, "SQLiteChatMessageHistory", test_history_cls)

    history = test_history_cls("session-panels")
    history.add_user_message("需求说明", answer_group_id="grp-1")
    history.add_ai_message(
        "主面板回答",
        model_id="qwen-main",
        panel_id="panel-main",
        answer_group_id="grp-1",
    )
    history.add_ai_message(
        "对照面板回答",
        model_id="qwen-compare",
        panel_id="panel-compare",
        answer_group_id="grp-1",
    )

    chat_store.replace_session_panels(
        "session-panels",
        [
            {
                "panel_id": "panel-main",
                "provider": "ollama",
                "connection_type": "ollama",
                "model": "qwen-main",
                "base_url": "http://localhost:11434",
                "temperature": 0.3,
                "agent_mode": "auto",
            },
            {
                "panel_id": "panel-compare",
                "provider": "ollama",
                "connection_type": "ollama",
                "model": "qwen-compare",
                "base_url": "http://localhost:11434",
                "temperature": 0.5,
                "agent_mode": "auto",
            },
        ],
        db_path=str(db_path),
    )

    client = TestClient(api_server.app)
    response = client.get("/api/sessions/session-panels/messages")

    assert response.status_code == 200
    payload = response.json()

    assert [item["content"] for item in payload["messages"]] == ["需求说明", "主面板回答"]
    assert [panel["panel_id"] for panel in payload["panels"]] == ["panel-main", "panel-compare"]
    assert [item["content"] for item in payload["panel_messages"]["panel-main"]] == [
        "需求说明",
        "主面板回答",
    ]
    assert [item["content"] for item in payload["panel_messages"]["panel-compare"]] == [
        "需求说明",
        "对照面板回答",
    ]


def test_import_session_messages_persists_fork_branch(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    test_history_cls = _history_cls_for_db(db_path)

    monkeypatch.setattr(chat_store, "SQLiteChatMessageHistory", test_history_cls)

    test_history_cls("session-import-fork")
    client = TestClient(api_server.app)
    import_response = client.post(
        "/api/sessions/session-import-fork/messages/import",
        json={
            "panels": [
                {
                    "panel_id": "panel-main",
                    "provider": "ollama",
                    "connection_type": "ollama",
                    "model": "qwen-main",
                    "base_url": "http://localhost:11434",
                    "api_key": "",
                    "temperature": 0.3,
                    "agent_mode": "auto",
                },
                {
                    "panel_id": "panel-compare",
                    "provider": "ollama",
                    "connection_type": "ollama",
                    "model": "qwen-compare",
                    "base_url": "http://localhost:11434",
                    "api_key": "",
                    "temperature": 0.5,
                    "agent_mode": "langgraph",
                },
            ],
            "messages": [
                {
                    "role": "user",
                    "content": "请给出调研结论",
                    "answer_group_id": "grp-import-1",
                },
                {
                    "role": "assistant",
                    "content": "主面板结论",
                    "panel_id": "panel-main",
                    "model_id": "qwen-main",
                    "answer_group_id": "grp-import-1",
                    "sources": [
                        {
                            "type": "doc",
                            "title": "结论简报",
                            "snippet": "主面板命中的证据",
                        }
                    ],
                    "workflow_nodes": [
                        {
                            "id": "retrieve",
                            "status": "completed",
                            "toolName": "query_knowledge",
                        }
                    ],
                    "task_id": "task-import-fork",
                    "task_type": "analysis",
                },
                {
                    "role": "user",
                    "content": "再补充风险项",
                    "answer_group_id": "grp-import-2",
                },
            ],
        },
    )

    assert import_response.status_code == 200
    import_payload = import_response.json()
    assert [panel["panel_id"] for panel in import_payload["panels"]] == [
        "panel-main",
        "panel-compare",
    ]
    assert [item["content"] for item in import_payload["panel_messages"]["panel-main"]] == [
        "请给出调研结论",
        "主面板结论",
        "再补充风险项",
    ]
    assert [item["content"] for item in import_payload["panel_messages"]["panel-compare"]] == [
        "请给出调研结论",
        "再补充风险项",
    ]
    assert import_payload["panel_messages"]["panel-main"][1]["sources"][0]["title"] == "结论简报"
    assert (
        import_payload["panel_messages"]["panel-main"][1]["workflow_nodes"][0]["toolName"]
        == "query_knowledge"
    )
    assert import_payload["panel_messages"]["panel-main"][1]["task_id"] == "task-import-fork"

    messages_response = client.get("/api/sessions/session-import-fork/messages")
    assert messages_response.status_code == 200
    payload = messages_response.json()
    assert [item["content"] for item in payload["panel_messages"]["panel-main"]] == [
        "请给出调研结论",
        "主面板结论",
        "再补充风险项",
    ]
    assert [item["content"] for item in payload["panel_messages"]["panel-compare"]] == [
        "请给出调研结论",
        "再补充风险项",
    ]

    duplicate_response = client.post(
        "/api/sessions/session-import-fork/messages/import",
        json={"panels": [], "messages": []},
    )
    assert duplicate_response.status_code == 400
    assert "empty sessions" in duplicate_response.json()["detail"]


def test_promote_answer_group_updates_primary_panel(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    test_history_cls = _history_cls_for_db(db_path)

    monkeypatch.setattr(chat_store, "SQLiteChatMessageHistory", test_history_cls)

    history = test_history_cls("session-promote")
    history.add_user_message("帮我总结", answer_group_id="grp-promote")
    history.add_ai_message(
        "主面板旧回答",
        model_id="qwen-main",
        panel_id="panel-main",
        answer_group_id="grp-promote",
    )
    history.add_ai_message(
        "对照面板更好回答",
        model_id="qwen-compare",
        panel_id="panel-compare",
        answer_group_id="grp-promote",
    )

    chat_store.replace_session_panels(
        "session-promote",
        [
            {
                "panel_id": "panel-main",
                "provider": "ollama",
                "connection_type": "ollama",
                "model": "qwen-main",
                "base_url": "http://localhost:11434",
                "temperature": 0.3,
                "agent_mode": "auto",
            },
            {
                "panel_id": "panel-compare",
                "provider": "ollama",
                "connection_type": "ollama",
                "model": "qwen-compare",
                "base_url": "http://localhost:11434",
                "temperature": 0.4,
                "agent_mode": "auto",
            },
        ],
        db_path=str(db_path),
    )

    client = TestClient(api_server.app)
    promote_response = client.post(
        "/api/sessions/session-promote/answer-groups/grp-promote/promote",
        params={"panel_id": "panel-compare"},
    )

    assert promote_response.status_code == 200
    promote_payload = promote_response.json()
    assert promote_payload["target_panel_id"] == "panel-main"
    assert promote_payload["content"] == "对照面板更好回答"

    messages_response = client.get("/api/sessions/session-promote/messages")
    assert messages_response.status_code == 200
    payload = messages_response.json()

    assert [item["content"] for item in payload["panel_messages"]["panel-main"]] == [
        "帮我总结",
        "对照面板更好回答",
    ]
    assert [item["content"] for item in payload["panel_messages"]["panel-compare"]] == [
        "帮我总结",
        "对照面板更好回答",
    ]


def test_promote_answer_group_copies_assistant_metadata(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    test_history_cls = _history_cls_for_db(db_path)

    monkeypatch.setattr(chat_store, "SQLiteChatMessageHistory", test_history_cls)

    history = test_history_cls("session-promote-metadata")
    history.add_user_message("Promote the better answer", answer_group_id="grp-promote-meta")
    history.add_ai_message(
        "Primary answer",
        model_id="qwen-main",
        panel_id="panel-main",
        answer_group_id="grp-promote-meta",
        sources=[
            {
                "type": "doc",
                "title": "Primary Brief",
                "snippet": "Primary panel source",
            }
        ],
    )
    history.add_ai_message(
        "Compare answer",
        model_id="qwen-compare",
        panel_id="panel-compare",
        answer_group_id="grp-promote-meta",
        sources=[
            {
                "type": "doc",
                "title": "Better Brief",
                "snippet": "Compare panel source",
            }
        ],
        workflow_nodes=[
            {
                "id": "classify_intent",
                "name": "classify_intent",
                "displayName": "Intent Classification",
                "status": "completed",
            },
            {
                "id": "execute_tool",
                "name": "execute_tool",
                "displayName": "Tool Execution",
                "status": "completed",
                "toolName": "query_knowledge",
                "toolResult": "Compare panel evidence",
            },
        ],
        task_id="task-promote-compare",
        task_type="promote_demo",
    )

    chat_store.replace_session_panels(
        "session-promote-metadata",
        [
            {
                "panel_id": "panel-main",
                "provider": "ollama",
                "connection_type": "ollama",
                "model": "qwen-main",
                "base_url": "http://localhost:11434",
                "temperature": 0.3,
                "agent_mode": "auto",
            },
            {
                "panel_id": "panel-compare",
                "provider": "ollama",
                "connection_type": "ollama",
                "model": "qwen-compare",
                "base_url": "http://localhost:11434",
                "temperature": 0.4,
                "agent_mode": "auto",
            },
        ],
        db_path=str(db_path),
    )

    client = TestClient(api_server.app)
    promote_response = client.post(
        "/api/sessions/session-promote-metadata/answer-groups/grp-promote-meta/promote",
        params={"panel_id": "panel-compare"},
    )

    assert promote_response.status_code == 200
    promote_payload = promote_response.json()
    assert promote_payload["content"] == "Compare answer"
    assert promote_payload["sources"][0]["title"] == "Better Brief"
    assert promote_payload["workflow_nodes"][1]["toolName"] == "query_knowledge"
    assert promote_payload["task_id"] == "task-promote-compare"
    assert promote_payload["task_type"] == "promote_demo"

    messages_response = client.get("/api/sessions/session-promote-metadata/messages")
    assert messages_response.status_code == 200
    payload = messages_response.json()

    assistant_message = payload["panel_messages"]["panel-main"][1]
    assert assistant_message["content"] == "Compare answer"
    assert assistant_message["sources"][0]["title"] == "Better Brief"
    assert assistant_message["workflow_nodes"][1]["toolName"] == "query_knowledge"
    assert assistant_message["task_id"] == "task-promote-compare"


def test_answer_group_review_and_promote_recommended(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    test_history_cls = _history_cls_for_db(db_path)

    monkeypatch.setattr(chat_store, "SQLiteChatMessageHistory", test_history_cls)

    history = test_history_cls("session-review-promote")
    history.add_user_message("Which answer is stronger?", answer_group_id="grp-review")
    history.add_ai_message(
        "Short draft.",
        model_id="qwen-main",
        panel_id="panel-main",
        answer_group_id="grp-review",
    )
    history.add_ai_message(
        "Recommendation:\n1. Use the supported option.\n2. Validate with evidence.\n3. Execute the rollout with the documented guardrails.",
        model_id="qwen-compare",
        panel_id="panel-compare",
        answer_group_id="grp-review",
        sources=[
            {
                "type": "doc",
                "title": "Decision Brief",
                "snippet": "Supported recommendation",
            },
            {
                "type": "doc",
                "title": "Runbook",
                "snippet": "Execution guidance",
            },
        ],
        workflow_nodes=[
            {"id": "classify_intent", "status": "completed"},
            {"id": "execute_tool", "status": "completed", "toolName": "query_knowledge"},
        ],
        task_id="task-review-compare",
        task_type="analysis",
    )

    chat_store.replace_session_panels(
        "session-review-promote",
        [
            {
                "panel_id": "panel-main",
                "provider": "ollama",
                "connection_type": "ollama",
                "model": "qwen-main",
                "base_url": "http://localhost:11434",
                "temperature": 0.3,
                "agent_mode": "auto",
            },
            {
                "panel_id": "panel-compare",
                "provider": "ollama",
                "connection_type": "ollama",
                "model": "qwen-compare",
                "base_url": "http://localhost:11434",
                "temperature": 0.4,
                "agent_mode": "auto",
            },
        ],
        db_path=str(db_path),
    )

    client = TestClient(api_server.app)
    review_response = client.get(
        "/api/sessions/session-review-promote/answer-groups/grp-review/review"
    )

    assert review_response.status_code == 200
    review_payload = review_response.json()
    assert review_payload["recommended_panel_id"] == "panel-compare"
    assert review_payload["responses"][0]["panel_id"] == "panel-compare"
    assert review_payload["responses"][0]["source_count"] == 2
    assert review_payload["comparisons"][0]["against_panel_id"] == "panel-main"
    assert review_payload["decision_factors"]

    promote_response = client.post(
        "/api/sessions/session-review-promote/answer-groups/grp-review/promote/recommended"
    )

    assert promote_response.status_code == 200
    promote_payload = promote_response.json()
    assert promote_payload["review"]["recommended_panel_id"] == "panel-compare"
    assert promote_payload["target_panel_id"] == "panel-main"
    assert promote_payload["content"].startswith("Recommendation:")
    assert promote_payload["sources"][0]["title"] == "Decision Brief"
    assert promote_payload["workflow_nodes"][0]["id"] == "classify_intent"

    messages_response = client.get("/api/sessions/session-review-promote/messages")
    payload = messages_response.json()
    assistant_message = payload["panel_messages"]["panel-main"][1]
    assert assistant_message["content"].startswith("Recommendation:")
    assert assistant_message["sources"][0]["title"] == "Decision Brief"


def test_session_messages_restore_attachment_payloads(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    test_history_cls = _history_cls_for_db(db_path)

    monkeypatch.setattr(chat_store, "SQLiteChatMessageHistory", test_history_cls)

    history = test_history_cls("session-attachments")
    history.add_user_message_once(
        "请总结这份材料",
        answer_group_id="grp-attachments",
        images=[
            {
                "name": "chart.png",
                "media_type": "image/png",
                "data_url": "data:image/png;base64,ZmFrZQ==",
            }
        ],
        files=[
            {
                "name": "notes.txt",
                "media_type": "text/plain",
                "data_url": "data:text/plain;base64,SGVsbG8=",
                "size_bytes": 5,
                "extracted_text": "第一段内容\n第二段内容",
            }
        ],
    )
    history.add_ai_message(
        "这是总结结果",
        model_id="qwen-main",
        panel_id="panel-main",
        answer_group_id="grp-attachments",
    )

    chat_store.replace_session_panels(
        "session-attachments",
        [
            {
                "panel_id": "panel-main",
                "provider": "ollama",
                "connection_type": "ollama",
                "model": "qwen-main",
                "base_url": "http://localhost:11434",
                "temperature": 0.3,
                "agent_mode": "auto",
            }
        ],
        db_path=str(db_path),
    )

    client = TestClient(api_server.app)
    response = client.get("/api/sessions/session-attachments/messages")

    assert response.status_code == 200
    payload = response.json()
    first_message = payload["messages"][0]

    assert first_message["content"] == "请总结这份材料"
    assert first_message["images"][0]["name"] == "chart.png"
    assert first_message["files"][0]["name"] == "notes.txt"
    assert first_message["files"][0]["extracted_text"] == "第一段内容\n第二段内容"

    model_history = history.get_all_messages()
    assert model_history[0].content.startswith("请总结这份材料")
    assert "File name: notes.txt" in model_history[0].content
    assert "第一段内容" in model_history[0].content
    assert "[用户上传了 1 张图片]" in model_history[0].content


def test_session_attachments_endpoint_builds_workspace_view(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    test_history_cls = _history_cls_for_db(db_path)

    monkeypatch.setattr(chat_store, "SQLiteChatMessageHistory", test_history_cls)
    monkeypatch.setattr(api_server, "_task_store", api_server.SQLiteTaskStore(db_path=str(db_path)))
    monkeypatch.setattr(api_server, "_effective_vector_store_path", lambda path=None: "vector_store_test")

    history = test_history_cls("session-workspace")
    history.add_user_message_once(
        "Analyze this brief",
        answer_group_id="grp-1",
        images=[
            {
                "name": "chart.png",
                "media_type": "image/png",
                "data_url": "data:image/png;base64,ZmFrZQ==",
            }
        ],
        files=[
            {
                "name": "brief.txt",
                "media_type": "text/plain",
                "data_url": "data:text/plain;base64,QnJpZWY=",
                "size_bytes": 5,
                "extracted_text": "Alpha section\nBeta section",
            }
        ],
    )
    history.add_user_message_once(
        "Reuse the same brief",
        answer_group_id="grp-2",
        files=[
            {
                "name": "brief.txt",
                "media_type": "text/plain",
                "data_url": "data:text/plain;base64,QnJpZWY=",
                "size_bytes": 5,
                "extracted_text": "Alpha section\nBeta section",
            }
        ],
    )

    client = TestClient(api_server.app)
    response = client.get("/api/sessions/session-workspace/attachments")

    assert response.status_code == 200
    payload = response.json()

    assert payload["summary"] == {
        "total_attachments": 2,
        "file_count": 1,
        "image_count": 1,
        "text_ready_count": 1,
        "reusable_count": 2,
        "total_size_bytes": 5,
        "indexed_in_current_kb_count": 0,
        "indexing_in_current_kb_count": 0,
    }
    assert payload["current_vector_store_path"] == "vector_store_test"

    brief = next(item for item in payload["attachments"] if item["name"] == "brief.txt")
    assert brief["kind"] == "file"
    assert brief["occurrence_count"] == 2
    assert brief["turn_count"] == 2
    assert brief["latest_answer_group_id"] == "grp-2"
    assert brief["preview_text"].startswith("Alpha section")
    assert brief["promotion_status"] == "idle"
    assert brief["is_in_current_kb"] is False

    chart = next(item for item in payload["attachments"] if item["name"] == "chart.png")
    assert chart["kind"] == "image"
    assert chart["occurrence_count"] == 1
    assert chart["turn_count"] == 1


def test_session_attachments_endpoint_marks_current_kb_status(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    test_history_cls = _history_cls_for_db(db_path)
    task_store = api_server.SQLiteTaskStore(db_path=str(db_path))

    monkeypatch.setattr(chat_store, "SQLiteChatMessageHistory", test_history_cls)
    monkeypatch.setattr(api_server, "_task_store", task_store)
    monkeypatch.setattr(api_server, "_effective_vector_store_path", lambda path=None: "vector_store_test")

    history = test_history_cls("session-workspace-kb")
    history.add_user_message_once(
        "Store this brief",
        answer_group_id="grp-kb",
        files=[
            {
                "name": "brief.txt",
                "media_type": "text/plain",
                "data_url": "data:text/plain;base64,QnJpZWY=",
                "size_bytes": 5,
                "extracted_text": "Alpha section",
            }
        ],
    )

    client = TestClient(api_server.app)
    attachment_response = client.get("/api/sessions/session-workspace-kb/attachments")
    attachment = attachment_response.json()["attachments"][0]

    task_store.save(
        api_server.TaskRecord(
            task_id="task-promoted-brief",
            task_type="promote_attachment_to_kb",
            status=api_server.TaskStatus.COMPLETED,
            params={
                "attachment_id": attachment["attachment_id"],
                "attachment_name": "brief.txt",
                "attachment_kind": "file",
                "attachment_data_url": "data:text/plain;base64,QnJpZWY=",
                "vector_store_path": "vector_store_test",
            },
            session_id="session-workspace-kb",
            created_at=10.0,
            updated_at=12.0,
            result="already indexed",
            progress=100,
        )
    )

    response = client.get("/api/sessions/session-workspace-kb/attachments")
    payload = response.json()
    brief = payload["attachments"][0]

    assert payload["current_vector_store_path"] == "vector_store_test"
    assert brief["promotion_status"] == "completed"
    assert brief["promotion_task_id"] == "task-promoted-brief"
    assert brief["is_in_current_kb"] is True
    assert payload["summary"]["indexed_in_current_kb_count"] == 1
    assert payload["summary"]["indexing_in_current_kb_count"] == 0


def test_session_attachments_endpoint_accepts_target_kb_override(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    test_history_cls = _history_cls_for_db(db_path)
    task_store = api_server.SQLiteTaskStore(db_path=str(db_path))

    monkeypatch.setattr(chat_store, "SQLiteChatMessageHistory", test_history_cls)
    monkeypatch.setattr(api_server, "_task_store", task_store)
    monkeypatch.setattr(api_server, "_effective_vector_store_path", lambda path=None: f"resolved::{path or 'current'}")

    history = test_history_cls("session-workspace-target")
    history.add_user_message_once(
        "Store this brief elsewhere",
        answer_group_id="grp-target",
        files=[
            {
                "name": "brief.txt",
                "media_type": "text/plain",
                "data_url": "data:text/plain;base64,QnJpZWY=",
                "size_bytes": 5,
                "extracted_text": "Alpha section",
            }
        ],
    )

    client = TestClient(api_server.app)
    response = client.get(
        "/api/sessions/session-workspace-target/attachments",
        params={"vector_store_path": "kb_custom"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_vector_store_path"] == "resolved::kb_custom"
    assert payload["attachments"][0]["current_vector_store_path"] == "resolved::kb_custom"


def test_promote_attachment_endpoint_enqueues_kb_task(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    test_history_cls = _history_cls_for_db(db_path)
    scheduled: list[object] = []

    monkeypatch.setattr(chat_store, "SQLiteChatMessageHistory", test_history_cls)
    monkeypatch.setattr(api_server, "_task_store", api_server.SQLiteTaskStore(db_path=str(db_path)))
    monkeypatch.setattr(api_server, "_effective_vector_store_path", lambda path=None: "vector_store_test")
    monkeypatch.setattr(api_server.asyncio, "create_task", lambda coro: scheduled.append(coro) or object())

    history = test_history_cls("session-promote-attachment")
    history.add_user_message_once(
        "Use this brief",
        answer_group_id="grp-brief",
        files=[
            {
                "name": "brief.txt",
                "media_type": "text/plain",
                "data_url": "data:text/plain;base64,QnJpZWY=",
                "size_bytes": 5,
                "extracted_text": "Alpha section",
            }
        ],
    )

    client = TestClient(api_server.app)
    attachments_response = client.get("/api/sessions/session-promote-attachment/attachments")
    attachment_id = attachments_response.json()["attachments"][0]["attachment_id"]

    response = client.post(
        f"/api/sessions/session-promote-attachment/attachments/{attachment_id}/promote"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_type"] == "promote_attachment_to_kb"
    assert payload["session_id"] == "session-promote-attachment"
    assert payload["params"]["attachment_id"] == attachment_id
    assert payload["params"]["attachment_name"] == "brief.txt"
    assert payload["params"]["vector_store_path"] == "vector_store_test"
    for coro in scheduled:
        coro.close()


def test_promote_attachment_endpoint_enqueues_selected_kb_task(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    test_history_cls = _history_cls_for_db(db_path)
    scheduled: list[object] = []

    monkeypatch.setattr(chat_store, "SQLiteChatMessageHistory", test_history_cls)
    monkeypatch.setattr(api_server, "_task_store", api_server.SQLiteTaskStore(db_path=str(db_path)))
    monkeypatch.setattr(api_server, "_effective_vector_store_path", lambda path=None: f"resolved::{path or 'current'}")
    monkeypatch.setattr(api_server.asyncio, "create_task", lambda coro: scheduled.append(coro) or object())

    history = test_history_cls("session-promote-custom-kb")
    history.add_user_message_once(
        "Use this brief",
        answer_group_id="grp-brief",
        files=[
            {
                "name": "brief.txt",
                "media_type": "text/plain",
                "data_url": "data:text/plain;base64,QnJpZWY=",
                "size_bytes": 5,
                "extracted_text": "Alpha section",
            }
        ],
    )

    client = TestClient(api_server.app)
    attachments_response = client.get("/api/sessions/session-promote-custom-kb/attachments")
    attachment_id = attachments_response.json()["attachments"][0]["attachment_id"]

    response = client.post(
        f"/api/sessions/session-promote-custom-kb/attachments/{attachment_id}/promote",
        params={"vector_store_path": "kb_custom"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["params"]["vector_store_path"] == "resolved::kb_custom"
    for coro in scheduled:
        coro.close()


def test_promote_attachment_endpoint_rejects_images(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    test_history_cls = _history_cls_for_db(db_path)

    monkeypatch.setattr(chat_store, "SQLiteChatMessageHistory", test_history_cls)
    monkeypatch.setattr(api_server, "_task_store", api_server.SQLiteTaskStore(db_path=str(db_path)))
    monkeypatch.setattr(api_server, "_effective_vector_store_path", lambda path=None: "vector_store_test")
    monkeypatch.setattr(api_server.asyncio, "create_task", lambda coro: object())

    history = test_history_cls("session-promote-image")
    history.add_user_message_once(
        "Use this image",
        answer_group_id="grp-image",
        images=[
            {
                "name": "chart.png",
                "media_type": "image/png",
                "data_url": "data:image/png;base64,ZmFrZQ==",
            }
        ],
    )

    client = TestClient(api_server.app)
    attachments_response = client.get("/api/sessions/session-promote-image/attachments")
    attachment_id = attachments_response.json()["attachments"][0]["attachment_id"]

    response = client.post(
        f"/api/sessions/session-promote-image/attachments/{attachment_id}/promote"
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only file attachments can be promoted to the knowledge base."


def test_promote_attachment_endpoint_reuses_existing_completed_promotion(
    monkeypatch,
    tmp_path,
):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    test_history_cls = _history_cls_for_db(db_path)
    task_store = api_server.SQLiteTaskStore(db_path=str(db_path))
    scheduled: list[object] = []

    monkeypatch.setattr(chat_store, "SQLiteChatMessageHistory", test_history_cls)
    monkeypatch.setattr(api_server, "_task_store", task_store)
    monkeypatch.setattr(api_server, "_effective_vector_store_path", lambda path=None: "vector_store_test")
    monkeypatch.setattr(api_server.asyncio, "create_task", lambda coro: scheduled.append(coro) or object())

    history = test_history_cls("session-promote-reuse")
    history.add_user_message_once(
        "Use this brief",
        answer_group_id="grp-brief",
        files=[
            {
                "name": "brief.txt",
                "media_type": "text/plain",
                "data_url": "data:text/plain;base64,QnJpZWY=",
                "size_bytes": 5,
                "extracted_text": "Alpha section",
            }
        ],
    )

    client = TestClient(api_server.app)
    attachments_response = client.get("/api/sessions/session-promote-reuse/attachments")
    attachment = attachments_response.json()["attachments"][0]
    attachment_id = attachment["attachment_id"]

    task_store.save(
        api_server.TaskRecord(
            task_id="task-existing-promotion",
            task_type="promote_attachment_to_kb",
            status=api_server.TaskStatus.COMPLETED,
            params={
                "attachment_id": attachment_id,
                "attachment_name": "brief.txt",
                "attachment_kind": "file",
                "attachment_data_url": "data:text/plain;base64,QnJpZWY=",
                "vector_store_path": "vector_store_test",
            },
            session_id="session-other",
            created_at=20.0,
            updated_at=21.0,
            result="already indexed",
            progress=100,
        )
    )

    response = client.post(
        f"/api/sessions/session-promote-reuse/attachments/{attachment_id}/promote"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == "task-existing-promotion"
    assert payload["status"] == "completed"
    assert payload["params"]["dedupe_hit"] is True
    assert scheduled == []


def test_get_ollama_models_uses_async_http_client(monkeypatch):
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"models": [{"name": "qwen2.5:7b"}, {"name": "llama3.2:3b"}]}

    class FakeAsyncClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url):
            captured["url"] = url
            return FakeResponse()

    monkeypatch.setattr(api_server.httpx, "AsyncClient", FakeAsyncClient)

    payload = asyncio.run(api_server.get_ollama_models("http://example.test:11434"))

    assert payload == {"models": ["qwen2.5:7b", "llama3.2:3b"]}
    assert captured == {
        "timeout": 5.0,
        "url": "http://example.test:11434/api/tags",
    }


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


def test_update_prompt_clears_agent_cache(monkeypatch):
    api_server._agent_cache.clear()
    api_server._agent_cache["cached-agent"] = object()

    def fake_update_system_prompt(prompt_id, name, content, vector_store_id="", dashboard_template=None):
        return {
            "id": prompt_id,
            "name": name,
            "content": content,
            "vector_store_id": vector_store_id,
            "dashboard_template": dashboard_template or {},
        }

    monkeypatch.setattr(chat_store, "update_system_prompt", fake_update_system_prompt)

    client = TestClient(api_server.app)

    result = client.put(
        "/api/prompts/prompt-1",
        json={
            "name": "Prompt",
            "content": "updated",
            "vector_store_id": "kb-1",
            "dashboard_template": {"layout": "briefing"},
        },
    )
    assert result.status_code == 200
    result = result.json()

    assert result["id"] == "prompt-1"
    assert api_server._agent_cache == {}


def test_sqlite_task_store_marks_incomplete_tasks_failed_after_restart(tmp_path):
    db_path = tmp_path / "chat_history.db"

    store = api_server.SQLiteTaskStore(db_path=str(db_path))
    store.save(
        api_server.TaskRecord(
            task_id="pending-task",
            task_type="upload_documents",
            status=api_server.TaskStatus.PENDING,
            params={},
            session_id=None,
            created_at=1.0,
            updated_at=1.0,
            progress=25,
        )
    )

    restarted_store = api_server.SQLiteTaskStore(db_path=str(db_path))
    reloaded = restarted_store.get("pending-task")

    assert reloaded is not None
    assert reloaded.status == api_server.TaskStatus.FAILED
    assert reloaded.error == "服务已重启，任务未能继续执行，请重新发起。"


def test_list_tasks_can_fall_back_to_persisted_store(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    task_store = api_server.SQLiteTaskStore(db_path=str(db_path))
    now = time.time()
    task_store.save(
        api_server.TaskRecord(
            task_id="persisted-task",
            task_type="generate_report",
            status=api_server.TaskStatus.COMPLETED,
            params={"topic": "demo"},
            session_id="session-1",
            created_at=now,
            updated_at=now,
            result="done",
            progress=100,
        )
    )

    monkeypatch.setattr(api_server, "_task_store", task_store)
    monkeypatch.setattr(api_server, "_tasks", {})

    payload = asyncio.run(api_server.list_tasks(limit=5))

    assert len(payload["tasks"]) == 1
    assert payload["tasks"][0]["task_id"] == "persisted-task"
    assert payload["tasks"][0]["status"] == api_server.TaskStatus.COMPLETED
    assert payload["tasks"][0]["params"] == {"topic": "demo"}
    assert payload["tasks"][0]["session_id"] == "session-1"


def test_attachment_promotion_lookup_survives_task_row_cleanup(tmp_path):
    db_path = tmp_path / "chat_history.db"
    task_store = api_server.SQLiteTaskStore(db_path=str(db_path))
    record = api_server.TaskRecord(
        task_id="attachment-promotion-task",
        task_type="promote_attachment_to_kb",
        status=api_server.TaskStatus.COMPLETED,
        params={
            "attachment_id": "att-brief",
            "attachment_name": "brief.txt",
            "vector_store_path": "vector_store_test",
        },
        session_id="session-1",
        created_at=5.0,
        updated_at=7.0,
        result="indexed",
        progress=100,
    )
    task_store.save(record)

    with chat_store.connect_sqlite(str(db_path)) as conn:
        conn.execute("DELETE FROM tasks WHERE task_id = ?", (record.task_id,))
        conn.commit()

    recovered = task_store.get_attachment_promotion_task(
        "att-brief",
        "vector_store_test",
    )

    assert recovered is not None
    assert recovered.task_id == "attachment-promotion-task"
    assert recovered.status == api_server.TaskStatus.COMPLETED
    assert recovered.result == "indexed"
    assert recovered.params["attachment_id"] == "att-brief"


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
    monkeypatch.setattr(
        agent_core,
        "DocPipeline",
        lambda *args, **kwargs: object(),
    )

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


def test_build_agent_auto_routes_local_to_langgraph(monkeypatch):
    langgraph_calls: list[dict] = []

    monkeypatch.setattr(agent_core, "get_llm", lambda *args, **kwargs: object())
    monkeypatch.setattr(
        agent_core,
        "DocPipeline",
        lambda *args, **kwargs: object(),
    )

    async def fake_build_langgraph_agent(*args, **kwargs):
        langgraph_calls.append(kwargs)
        return object()

    monkeypatch.setattr(agent_core, "build_langgraph_agent", fake_build_langgraph_agent)
    monkeypatch.setattr(agent_core, "create_tools", lambda *args, **kwargs: [])

    agent = asyncio.run(
        agent_core.build_agent(
            provider="local",
            agent_mode="auto",
            knowledge_base_enabled=False,
            web_search_enabled=False,
        )
    )

    assert agent.__class__.__name__ == "LangGraphAgentWrapper"
    assert len(langgraph_calls) == 1


def test_plain_chat_wrapper_astream_uses_native_model_stream(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    test_history_cls = _history_cls_for_db(db_path)

    class FakeLLM:
        def __init__(self):
            self.stream_payload = None

        async def astream(self, payload):
            self.stream_payload = payload
            yield types.SimpleNamespace(content="从前")
            yield types.SimpleNamespace(content="有座山")

        async def ainvoke(self, payload):
            raise AssertionError("plain chat streaming should not fall back to ainvoke")

    async def fake_build_runtime_tools(*args, **kwargs):
        return []

    monkeypatch.setattr(agent_core, "SQLiteChatMessageHistory", test_history_cls)
    monkeypatch.setattr(agent_core, "get_llm", lambda *args, **kwargs: FakeLLM())
    monkeypatch.setattr(agent_core, "DocPipeline", lambda *args, **kwargs: object())
    monkeypatch.setattr(agent_core, "build_runtime_tools", fake_build_runtime_tools)

    agent = asyncio.run(
        agent_core.build_agent(
            provider="cloud",
            agent_mode="auto",
            knowledge_base_enabled=False,
            web_search_enabled=False,
        )
    )

    async def collect():
        return [
            item
            async for item in agent.astream_answer(
                "写一个短故事",
                config={"configurable": {"session_id": "native-stream-plain", "persist_history": True}},
            )
        ]

    items = asyncio.run(collect())

    assert items == ["从前", "有座山"]
    persisted_messages = test_history_cls("native-stream-plain").get_all_messages()
    assert [message.content for message in persisted_messages] == ["写一个短故事", "从前有座山"]


def test_function_calling_wrapper_astream_bypasses_tools_for_plain_text(monkeypatch):
    class FakeLLM:
        async def astream(self, payload):
            yield types.SimpleNamespace(content="第一段")
            yield types.SimpleNamespace(content="第二段")

        async def ainvoke(self, payload):
            raise AssertionError("plain-text bypass should stream directly from the model")

    class FakeExecutor:
        def __init__(self, *args, **kwargs):
            pass

        async def ainvoke(self, payload):
            raise AssertionError("tool executor should not run for plain-text bypass")

    async def fake_build_runtime_tools(*args, **kwargs):
        return [types.SimpleNamespace(name="query_knowledge")]

    monkeypatch.setattr(agent_core, "get_llm", lambda *args, **kwargs: FakeLLM())
    monkeypatch.setattr(agent_core, "DocPipeline", lambda *args, **kwargs: object())
    monkeypatch.setattr(agent_core, "build_runtime_tools", fake_build_runtime_tools)
    monkeypatch.setattr(agent_core, "create_tool_calling_agent", lambda *args, **kwargs: object())
    monkeypatch.setattr(agent_core, "AgentExecutor", FakeExecutor)

    agent = asyncio.run(
        agent_core.build_agent(
            provider="cloud",
            agent_mode="function_calling",
            knowledge_base_enabled=True,
            web_search_enabled=True,
        )
    )

    async def collect():
        return [
            item
            async for item in agent.astream_answer(
                "写一个三段式故事",
                config={"configurable": {"session_id": "native-stream-fc", "persist_history": False}},
            )
        ]

    items = asyncio.run(collect())

    assert items == ["第一段", "第二段"]


def test_plain_chat_wrapper_astream_filters_think_tags(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    test_history_cls = _history_cls_for_db(db_path)

    class FakeLLM:
        async def astream(self, payload):
            yield types.SimpleNamespace(content="答案前缀")
            yield types.SimpleNamespace(content="<thi")
            yield types.SimpleNamespace(content="nk>内部思考</thi")
            yield types.SimpleNamespace(content="nk>答案后缀")
            yield types.SimpleNamespace(content="<think>未闭合思考")

        async def ainvoke(self, payload):
            raise AssertionError("plain chat streaming should not fall back to ainvoke")

    async def fake_build_runtime_tools(*args, **kwargs):
        return []

    monkeypatch.setattr(agent_core, "SQLiteChatMessageHistory", test_history_cls)
    monkeypatch.setattr(agent_core, "get_llm", lambda *args, **kwargs: FakeLLM())
    monkeypatch.setattr(agent_core, "DocPipeline", lambda *args, **kwargs: object())
    monkeypatch.setattr(agent_core, "build_runtime_tools", fake_build_runtime_tools)

    agent = asyncio.run(
        agent_core.build_agent(
            provider="cloud",
            agent_mode="auto",
            knowledge_base_enabled=False,
            web_search_enabled=False,
        )
    )

    async def collect():
        return [
            item
            async for item in agent.astream_answer(
                "测试过滤 think 标签",
                config={"configurable": {"session_id": "native-stream-think", "persist_history": True}},
            )
        ]

    items = asyncio.run(collect())

    assert items == ["答案前缀", "答案后缀"]
    persisted_messages = test_history_cls("native-stream-think").get_all_messages()
    assert [message.content for message in persisted_messages] == ["测试过滤 think 标签", "答案前缀答案后缀"]


def test_function_calling_wrapper_ainvoke_filters_think_tags(monkeypatch):
    class FakeLLM:
        async def ainvoke(self, payload):
            return types.SimpleNamespace(content="<think>内部推理</think>最终答案")

    class FakeExecutor:
        def __init__(self, *args, **kwargs):
            pass

        async def ainvoke(self, payload):
            raise AssertionError("tool executor should not run for plain-text bypass")

    async def fake_build_runtime_tools(*args, **kwargs):
        return [types.SimpleNamespace(name="query_knowledge")]

    monkeypatch.setattr(agent_core, "get_llm", lambda *args, **kwargs: FakeLLM())
    monkeypatch.setattr(agent_core, "DocPipeline", lambda *args, **kwargs: object())
    monkeypatch.setattr(agent_core, "build_runtime_tools", fake_build_runtime_tools)
    monkeypatch.setattr(agent_core, "create_tool_calling_agent", lambda *args, **kwargs: object())
    monkeypatch.setattr(agent_core, "AgentExecutor", FakeExecutor)

    agent = asyncio.run(
        agent_core.build_agent(
            provider="cloud",
            agent_mode="function_calling",
            knowledge_base_enabled=True,
            web_search_enabled=True,
        )
    )

    result = asyncio.run(
        agent.ainvoke(
            {"input": "plain-text bypass"},
            config={"configurable": {"session_id": "fc-think-filter", "persist_history": False}},
        )
    )

    assert result["output"] == "最终答案"


def test_query_knowledge_uses_current_default_topk_and_fetch_k(monkeypatch):
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

    assert pipeline.calls == [
        (
            "测试问题",
            agent_core.DEFAULT_KB_TOP_K,
            agent_core.DEFAULT_KB_FETCH_K,
        )
    ]
    assert "【文档 1: doc-a.md】" in result
    assert "__SOURCES__:" in result


def test_query_knowledge_prefers_hybrid_for_keyword_like_queries(monkeypatch):
    class FakePipeline:
        def __init__(self):
            self.vectorstore = object()
            self.vector_store_path = "./vector_store"
            self.hybrid_calls: list[tuple[str, int, int, bool]] = []

        def hybrid_search(self, question: str, k: int, fetch_k: int, use_rerank: bool):
            self.hybrid_calls.append((question, k, fetch_k, use_rerank))
            return [
                Document(
                    page_content="RERANKER_MODEL 当前配置为 BAAI/bge-reranker-base。",
                    metadata={"source": "settings.md"},
                )
            ]

        def search_with_rerank(self, question: str, k: int, fetch_k: int):
            raise AssertionError("keyword-like query should not fall back to semantic rerank")

    pipeline = FakePipeline()
    query_tool = next(
        tool for tool in agent_core.create_tools(pipeline) if tool.name == "query_knowledge"
    )

    result = asyncio.run(query_tool.ainvoke({"question": "RERANKER_MODEL 配置是什么"}))

    assert pipeline.hybrid_calls == [
        (
            "RERANKER_MODEL 配置是什么",
            agent_core.DEFAULT_KB_TOP_K,
            agent_core.DEFAULT_KB_FETCH_K,
            True,
        )
    ]
    assert "settings.md" in result
    assert "retrieval_mode" in result
    assert "search_channel" in result


def test_generate_dashboard_from_knowledge_prefers_hybrid_for_keyword_like_queries(monkeypatch):
    class FakePipeline:
        def __init__(self):
            self.vectorstore = object()
            self.vector_store_path = "./vector_store"
            self.hybrid_calls: list[tuple[str, int, int, bool]] = []

        def hybrid_search(self, query: str, k: int, fetch_k: int, use_rerank: bool):
            self.hybrid_calls.append((query, k, fetch_k, use_rerank))
            return [
                Document(
                    page_content="RERANKER_MODEL 使用 bge-reranker-base，版本 1.0，本周检索成功率 92%，平均耗时 210ms。",
                    metadata={
                        "source": "ops.md",
                        "feedback_boost": 0.14,
                        "feedback_net": 1,
                        "feedback_positive_count": 2,
                        "feedback_negative_count": 1,
                    },
                ),
                Document(
                    page_content="启用重排后，Top3 命中率从 71% 提升到 86%，用于搜索增强 v1 的重排阶段。",
                    metadata={
                        "source": "metrics.md",
                        "feedback_boost": 0.0,
                        "feedback_net": 0,
                        "feedback_positive_count": 0,
                        "feedback_negative_count": 0,
                    },
                ),
            ]

        def search_with_rerank(self, query: str, k: int, fetch_k: int):
            raise AssertionError("dashboard keyword-like query should not fall back to semantic rerank")

    monkeypatch.setattr(agent_core, "_should_generate_dashboard", lambda _: True)
    monkeypatch.setattr(
        agent_core,
        "_ainvoke_llm_with_timeout",
        lambda *args, **kwargs: asyncio.sleep(0, result=types.SimpleNamespace(content=json.dumps({
            "title": "配置看板",
            "summary": "ok",
            "metrics": [],
            "charts": [],
            "table": {"title": "明细", "columns": [], "rows": [], "evidence_ids": []},
            "evidence": [],
            "warnings": [],
        }, ensure_ascii=False))),
    )

    pipeline = FakePipeline()
    result = asyncio.run(
        agent_core._generate_dashboard_from_knowledge(
            object(),
            pipeline,
            "请根据 RERANKER_MODEL 配置生成仪表盘",
            knowledge_base_enabled=True,
        )
    )

    assert result is not None
    assert pipeline.hybrid_calls == [
        (
            "请根据 RERANKER_MODEL 配置生成仪表盘",
            4,
            12,
            True,
        )
    ]
    assert "证据主要是描述性文本" in result["output"]
    assert [item["title"] for item in result["sources"]] == ["ops.md", "metrics.md"]
    assert all(item["retrieval_mode"] == "hybrid_rerank" for item in result["sources"])
    assert result["sources"][0]["feedback_positive_count"] == 2
    assert result["sources"][0]["feedback_negative_count"] == 1
    assert result["sources"][0]["feedback_net"] == 1
    assert result["sources"][0]["feedback_boost"] == 0.14


def test_build_retrieval_meta_from_sources_summarizes_modes_and_terms():
    meta = agent_core._build_retrieval_meta_from_sources(
        [
            {
                "title": "ops.md",
                "retrieval_mode": "hybrid_rerank",
                "search_channel": "hybrid_rerank",
                "score": 0.91,
                "matched_terms": ["reranker_model", "配置"],
            },
            {
                "title": "metrics.md",
                "retrieval_mode": "hybrid_rerank",
                "search_channel": "hybrid_rerank",
                "score": 0.84,
                "matched_terms": ["配置", "命中率"],
            },
        ]
    )

    assert meta == {
        "primary_mode": "hybrid_rerank",
        "modes": ["hybrid_rerank"],
        "channels": ["hybrid_rerank"],
        "source_count": 2,
        "source_titles": ["ops.md", "metrics.md"],
        "matched_terms": ["reranker_model", "配置", "命中率"],
        "top_score": 0.91,
    }

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


def test_chat_parallel_only_primary_panel_persists_history(monkeypatch):
    calls: list[tuple[str, bool]] = []

    async def fake_invoke_agent_stream(
        panel_id,
        mc,
        user_input,
        session_id,
        web_search_enabled,
        knowledge_base_enabled,
        **kwargs,
    ):
        calls.append((panel_id, bool(kwargs.get("persist_history"))))
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
    assert calls == [("panel-1", True), ("panel-2", False)]


def test_chat_single_passes_rerun_flags_and_upserts_panel(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    original_connect_sqlite = chat_store.connect_sqlite
    captured: list[dict[str, object]] = []

    def test_connect_sqlite(_db_path: str = chat_store.DB_PATH):
        return original_connect_sqlite(str(db_path))

    monkeypatch.setattr(chat_store, "connect_sqlite", test_connect_sqlite)
    monkeypatch.setattr(chat_store, "get_active_system_prompt", lambda: None)

    chat_store.replace_session_panels(
        "single-rerun",
        [
            {
                "panel_id": "panel-main",
                "provider": "ollama",
                "connection_type": "ollama",
                "model": "qwen-main",
                "base_url": "http://localhost:11434",
                "temperature": 0.3,
                "agent_mode": "auto",
            },
            {
                "panel_id": "panel-compare",
                "provider": "ollama",
                "connection_type": "ollama",
                "model": "qwen-compare-old",
                "base_url": "http://localhost:11434",
                "temperature": 0.4,
                "agent_mode": "auto",
            },
        ],
        db_path=str(db_path),
    )

    async def fake_invoke_agent_stream(
        panel_id,
        mc,
        user_input,
        session_id,
        web_search_enabled,
        knowledge_base_enabled,
        **kwargs,
    ):
        captured.append(
            {
                "panel_id": panel_id,
                "model": mc.model,
                "session_id": session_id,
                "user_input": user_input,
                "web_search_enabled": web_search_enabled,
                "knowledge_base_enabled": knowledge_base_enabled,
                **kwargs,
            }
        )
        yield f"data: {json.dumps({'panel_id': panel_id, 'type': 'done'})}\n\n"

    monkeypatch.setattr(api_server, "_invoke_agent_stream", fake_invoke_agent_stream)

    client = TestClient(api_server.app)
    response = client.post(
        "/api/chat/single",
        json={
            "session_id": "single-rerun",
            "message": "rerun this answer",
            "images": [],
            "files": [],
            "panel_config": {
                "panel_id": "panel-compare",
                "provider": "ollama",
                "model": "qwen-compare-new",
                "base_url": "http://localhost:11434",
                "api_key": "",
                "temperature": 0.65,
                "agent_mode": "auto",
            },
            "web_search_enabled": True,
            "knowledge_base_enabled": False,
            "answer_group_id": "grp-rerun",
            "persist_user_history": False,
            "persist_ai_history": True,
            "replace_ai_history": True,
            "exclude_ai_answer_group_id": "grp-rerun",
        },
    )

    assert response.status_code == 200
    assert '"type": "all_done"' in response.text
    assert len(captured) == 1
    assert captured[0]["panel_id"] == "panel-compare"
    assert captured[0]["model"] == "qwen-compare-new"
    assert captured[0]["session_id"] == "single-rerun"
    assert captured[0]["user_input"] == "rerun this answer"
    assert captured[0]["web_search_enabled"] is True
    assert captured[0]["knowledge_base_enabled"] is False
    assert captured[0]["persist_history"] is True
    assert captured[0]["persist_user_history"] is False
    assert captured[0]["persist_ai_history"] is True
    assert captured[0]["replace_ai_history"] is True
    assert captured[0]["exclude_ai_answer_group_id"] == "grp-rerun"
    assert captured[0]["answer_group_id"] == "grp-rerun"

    panels = chat_store.get_session_panels("single-rerun", db_path=str(db_path))
    assert [panel["panel_id"] for panel in panels] == ["panel-main", "panel-compare"]
    assert panels[1]["model_config"]["model"] == "qwen-compare-new"
    assert panels[1]["model_config"]["temperature"] == 0.65


def test_effective_vector_store_path_prefers_active_prompt_binding(monkeypatch, tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    bound_kb = project_root / "kb_bound"
    bound_kb.mkdir()

    monkeypatch.setattr(api_server, "PROJECT_ROOT", project_root.resolve())
    monkeypatch.setattr(api_server, "_active_vector_store_id", lambda: str(bound_kb.resolve()))
    monkeypatch.setenv("VECTOR_STORE_PATH", "vector_store_default")

    resolved = api_server._effective_vector_store_path()

    assert resolved == "kb_bound"


def test_analyze_knowledge_base_task_loads_store_before_stats(monkeypatch, tmp_path):
    import backend.doc_pipeline as doc_pipeline

    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "vector_store").mkdir()
    monkeypatch.setattr(api_server, "PROJECT_ROOT", project_root.resolve())

    events: list[tuple[str, object]] = []

    class FakePipeline:
        def __init__(self, vector_store_path=None):
            self.vector_store_path = vector_store_path
            self.loaded = False

        def load_store(self):
            events.append(("load_store", self.vector_store_path))
            self.loaded = True
            return True

        def get_stats(self):
            events.append(("get_stats", self.loaded))
            return {"total_docs": 7, "store_path": self.vector_store_path}

    monkeypatch.setattr(doc_pipeline, "DocPipeline", FakePipeline)

    record = api_server.TaskRecord(
        task_id="task-analyze",
        task_type="analyze_knowledge_base",
        status=api_server.TaskStatus.PENDING,
        params={"vector_store_path": "vector_store"},
        session_id=None,
        created_at=time.time(),
        updated_at=time.time(),
    )

    asyncio.run(api_server._run_task(record))

    assert events == [("load_store", "vector_store"), ("get_stats", True)]
    assert record.status == api_server.TaskStatus.COMPLETED
    assert "7" in (record.result or "")


def test_promote_attachment_to_kb_task_ingests_attachment(monkeypatch, tmp_path):
    import backend.doc_pipeline as doc_pipeline

    events: list[tuple[str, object]] = []

    class FakePipeline:
        def __init__(self, vector_store_path=None):
            self.vector_store_path = vector_store_path

        def ingest(self, file_paths, progress_callback=None):
            payload = Path(file_paths[0]).read_text(encoding="utf-8")
            events.append(("ingest", self.vector_store_path))
            events.append(("payload", payload))
            if progress_callback is not None:
                progress_callback(67)
            return 3

    async def fake_clear_agent_cache():
        events.append(("clear_cache", None))

    monkeypatch.setattr(doc_pipeline, "DocPipeline", FakePipeline)
    monkeypatch.setattr(api_server, "_clear_agent_cache", fake_clear_agent_cache)
    monkeypatch.setattr(
        api_server,
        "_task_store",
        api_server.SQLiteTaskStore(db_path=str(tmp_path / "chat_history.db")),
    )

    record = api_server.TaskRecord(
        task_id="task-attachment-kb",
        task_type="promote_attachment_to_kb",
        status=api_server.TaskStatus.PENDING,
        params={
            "attachment_name": "brief.txt",
            "attachment_kind": "file",
            "attachment_data_url": "data:text/plain;base64,QWxwaGEgYnJpZWY=",
            "vector_store_path": "vector_store_target",
        },
        session_id="session-attachment-kb",
        created_at=time.time(),
        updated_at=time.time(),
    )

    asyncio.run(api_server._run_task(record))

    assert ("ingest", "vector_store_target") in events
    assert ("payload", "Alpha brief") in events
    assert ("clear_cache", None) in events
    assert record.status == api_server.TaskStatus.COMPLETED
    assert record.progress == 100
    assert "brief.txt" in (record.result or "")


def test_prune_task_records_keeps_active_and_newest_terminal(monkeypatch):
    monkeypatch.setattr(api_server, "TASK_HISTORY_LIMIT", 2)
    monkeypatch.setattr(api_server, "TASK_HISTORY_TTL_SECONDS", 10_000)
    monkeypatch.setattr(
        api_server,
        "_tasks",
        {
            "done-oldest": api_server.TaskRecord(
                task_id="done-oldest",
                task_type="demo",
                status=api_server.TaskStatus.COMPLETED,
                params={},
                session_id=None,
                created_at=1.0,
                updated_at=1.0,
            ),
            "failed-middle": api_server.TaskRecord(
                task_id="failed-middle",
                task_type="demo",
                status=api_server.TaskStatus.FAILED,
                params={},
                session_id=None,
                created_at=2.0,
                updated_at=2.0,
            ),
            "done-newest": api_server.TaskRecord(
                task_id="done-newest",
                task_type="demo",
                status=api_server.TaskStatus.COMPLETED,
                params={},
                session_id=None,
                created_at=3.0,
                updated_at=3.0,
            ),
            "running": api_server.TaskRecord(
                task_id="running",
                task_type="demo",
                status=api_server.TaskStatus.RUNNING,
                params={},
                session_id=None,
                created_at=4.0,
                updated_at=4.0,
            ),
        },
    )

    api_server._prune_task_records_locked(now=5.0)

    assert set(api_server._tasks) == {"done-newest", "running"}


def test_create_task_persists_record_before_background_execution(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    monkeypatch.setattr(api_server, "_task_store", api_server.SQLiteTaskStore(db_path=str(db_path)))
    monkeypatch.setattr(api_server, "_tasks", {})

    scheduled: list[object] = []

    def fake_create_task(coro):
        scheduled.append(coro)
        return object()

    monkeypatch.setattr(api_server.asyncio, "create_task", fake_create_task)

    payload = asyncio.run(
        api_server.create_task(
            api_server.CreateTaskRequest(
                task_type="generate_report",
                params={"mode": "demo"},
                session_id="session-xyz",
            )
        )
    )

    for coro in scheduled:
        coro.close()

    stored = api_server._task_store.get(payload["task_id"])

    assert stored is not None
    assert stored.task_type == "generate_report"
    assert stored.status == api_server.TaskStatus.PENDING
    assert stored.session_id == "session-xyz"
    assert payload["params"] == {"mode": "demo"}
    assert payload["session_id"] == "session-xyz"


def test_deep_research_task_waits_for_concurrency_slot(monkeypatch):
    record = api_server.TaskRecord(
        task_id="task-deep-queued",
        task_type="web_research",
        status=api_server.TaskStatus.PENDING,
        params={"query": "AI", "research_mode": "deep", "panel_config": {"provider": "ollama"}},
        session_id="session-1",
        created_at=time.time(),
        updated_at=time.time(),
        progress=0,
    )
    persisted_statuses: list[tuple[str, int]] = []

    async def fake_run_web_research_task(*args, **kwargs):
        await kwargs["set_progress"](15)
        await kwargs["set_progress"](55)
        record.result = "deep done"

    async def fake_drop_suppressed_task(_record):
        return False

    monkeypatch.setattr(
        api_server,
        "_persist_task_record",
        lambda current: persisted_statuses.append((current.status.value, current.progress)),
    )
    monkeypatch.setattr(api_server, "_prune_persisted_tasks", lambda: None)
    monkeypatch.setattr(api_server, "_prune_task_records_locked", lambda now=None: None)
    monkeypatch.setattr(api_server, "_drop_suppressed_task", fake_drop_suppressed_task)
    monkeypatch.setattr(api_server, "run_web_research_task", fake_run_web_research_task)

    async def exercise() -> None:
        gate = asyncio.Semaphore(1)
        await gate.acquire()
        monkeypatch.setattr(api_server, "_get_deep_research_semaphore", lambda: gate)
        task = asyncio.create_task(api_server._run_task(record))
        await asyncio.sleep(0.05)
        assert record.status == api_server.TaskStatus.PENDING
        assert record.progress == 0
        gate.release()
        await task

    asyncio.run(exercise())

    assert record.status == api_server.TaskStatus.COMPLETED
    assert record.progress == 100
    assert ("running", 10) in persisted_statuses
    assert ("completed", 100) in persisted_statuses


def test_get_task_includes_retry_context(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    task_store = api_server.SQLiteTaskStore(db_path=str(db_path))
    record = api_server.TaskRecord(
        task_id="task-retry-context",
        task_type="generate_report",
        status=api_server.TaskStatus.FAILED,
        params={"mode": "retry"},
        session_id="session-retry",
        created_at=time.time(),
        updated_at=time.time(),
        error="boom",
        progress=40,
    )
    task_store.save(record)

    monkeypatch.setattr(api_server, "_task_store", task_store)
    monkeypatch.setattr(api_server, "_tasks", {})

    payload = asyncio.run(api_server.get_task("task-retry-context"))

    assert payload["params"] == {"mode": "retry"}
    assert payload["session_id"] == "session-retry"


def test_langgraph_wrapper_respects_persist_history_flag(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    test_history_cls = _history_cls_for_db(db_path)

    monkeypatch.setattr(agent_core, "SQLiteChatMessageHistory", test_history_cls)
    monkeypatch.setattr(agent_core, "get_llm", lambda *args, **kwargs: object())
    monkeypatch.setattr(agent_core, "DocPipeline", lambda *args, **kwargs: object())

    async def fake_build_langgraph_agent(*args, **kwargs):
        class FakeApp:
            async def ainvoke(self, state):
                return {"output": f"reply:{state['input']}", "sources": []}

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

    asyncio.run(
        agent.ainvoke(
            {"input": "hello"},
            config={"configurable": {"session_id": "persist-test", "persist_history": False}},
        )
    )
    assert test_history_cls("persist-test").get_all_messages() == []

    asyncio.run(
        agent.ainvoke(
            {"input": "hello"},
            config={"configurable": {"session_id": "persist-test", "persist_history": True}},
        )
    )
    persisted_messages = test_history_cls("persist-test").get_all_messages()
    assert [message.content for message in persisted_messages] == ["hello", "reply:hello"]


def test_langgraph_wrapper_merges_attachment_sources(monkeypatch):
    monkeypatch.setattr(agent_core, "get_llm", lambda *args, **kwargs: object())
    monkeypatch.setattr(agent_core, "DocPipeline", lambda *args, **kwargs: object())

    async def fake_build_langgraph_agent(*args, **kwargs):
        class FakeApp:
            async def ainvoke(self, state):
                return {
                    "output": "done",
                    "sources": [
                        {
                            "type": "doc",
                            "title": "kb.md",
                            "snippet": "knowledge snippet",
                            "index": 1,
                        }
                    ],
                }

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
            {"input": "summarize"},
            config={
                "configurable": {
                    "session_id": "attachment-source-test",
                    "persist_history": False,
                    "answer_group_id": "grp-attachment",
                    "raw_files": [
                        {
                            "name": "brief.txt",
                            "media_type": "text/plain",
                            "data_url": "data:text/plain;base64,QnJpZWY=",
                            "size_bytes": 5,
                            "extracted_text": "Alpha section\nBeta section",
                        }
                    ],
                    "raw_images": [
                        {
                            "name": "chart.png",
                            "media_type": "image/png",
                            "data_url": "data:image/png;base64,ZmFrZQ==",
                        }
                    ],
                }
            },
        )
    )

    assert [source["type"] for source in result["sources"]] == ["doc", "attachment", "attachment"]
    attachment_titles = [source["title"] for source in result["sources"] if source["type"] == "attachment"]
    assert attachment_titles == ["brief.txt", "chart.png"]
    file_source = next(
        source for source in result["sources"]
        if source["type"] == "attachment" and source["title"] == "brief.txt"
    )
    assert file_source["answer_group_id"] == "grp-attachment"
    assert "Alpha section" in file_source["snippet"]


def test_langgraph_wrapper_persists_configured_task_metadata(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    test_history_cls = _history_cls_for_db(db_path)

    monkeypatch.setattr(agent_core, "SQLiteChatMessageHistory", test_history_cls)
    monkeypatch.setattr(agent_core, "get_llm", lambda *args, **kwargs: object())
    monkeypatch.setattr(agent_core, "DocPipeline", lambda *args, **kwargs: object())

    async def fake_build_langgraph_agent(*args, **kwargs):
        class FakeApp:
            async def ainvoke(self, state, config=None):
                return {"output": "dashboard ready", "sources": []}

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

    asyncio.run(
        agent.ainvoke(
            {"input": "make a dashboard"},
            config={
                "configurable": {
                    "session_id": "task-metadata-test",
                    "persist_history": True,
                    "task_id": "task-dashboard-1",
                    "task_type": "generate_dashboard",
                }
            },
        )
    )

    records = test_history_cls("task-metadata-test").get_all_message_records()
    assistant_records = [record for record in records if record["type"] == "ai"]

    assert len(assistant_records) == 1
    assert assistant_records[0]["task_id"] == "task-dashboard-1"
    assert assistant_records[0]["task_type"] == "generate_dashboard"


def test_invoke_agent_stream_emits_dashboard_task_created_event(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    task_store = api_server.SQLiteTaskStore(db_path=str(db_path))

    monkeypatch.setattr(api_server, "_task_store", task_store)
    monkeypatch.setattr(api_server, "_tasks", {})
    monkeypatch.setattr(agent_core, "_should_generate_dashboard", lambda _: True)

    async def fake_get_or_build_agent(*args, **kwargs):
        class FakeAgent:
            async def astream_answer(self, message, config=None):
                configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
                assert configurable["task_type"] == "generate_dashboard"
                assert configurable["task_id"]
                yield (
                    "已根据当前角色绑定的知识库整理出可证据化的仪表盘：营收看板\n\n"
                    ":::dashboard-card\n"
                    '{"title":"营收看板","summary":"ok","metrics":[],"charts":[],"table":{"title":"数据明细","columns":[],"rows":[],"evidence_ids":[]},"evidence":[],"warnings":[]}\n'
                    ":::"
                )

        return FakeAgent()

    monkeypatch.setattr(api_server, "_get_or_build_agent", fake_get_or_build_agent)

    model_config = api_server.ModelConfig(
        panel_id="panel-1",
        provider="local",
        model="qwen2.5:7b",
        base_url="http://localhost:11434",
        api_key="",
        temperature=0.3,
        agent_mode="langgraph",
    )

    async def collect():
        items = []
        async for item in api_server._invoke_agent_stream(
            "panel-1",
            model_config,
            "请根据知识库生成仪表盘",
            "dashboard-task-session",
            False,
            True,
            raw_user_message="请根据知识库生成仪表盘",
        ):
            items.append(item)
        return items

    items = asyncio.run(collect())
    payloads = [
        json.loads(item.removeprefix("data: ").strip())
        for item in items
        if item.startswith("data: ")
    ]

    task_payload = next(payload for payload in payloads if payload.get("type") == "task_created")
    assert task_payload["task_type"] == "generate_dashboard"
    assert payloads[-1]["type"] == "done"

    stored = task_store.get(task_payload["task_id"])
    assert stored is not None
    assert stored.status == api_server.TaskStatus.COMPLETED
    assert stored.progress == 100
    assert stored.result == "知识看板已生成：营收看板"


def test_invoke_agent_stream_marks_dashboard_task_failed_on_nonstream_max_iterations(
    monkeypatch, tmp_path
):
    db_path = tmp_path / "chat_history.db"
    task_store = api_server.SQLiteTaskStore(db_path=str(db_path))

    monkeypatch.setattr(api_server, "_task_store", task_store)
    monkeypatch.setattr(api_server, "_tasks", {})
    monkeypatch.setattr(agent_core, "_should_generate_dashboard", lambda _: True)

    async def fake_get_or_build_agent(*args, **kwargs):
        class FakeAgent:
            async def ainvoke(self, payload, config=None):
                assert payload == {"input": "请根据知识库生成仪表盘"}
                return {
                    "output": "Agent stopped due to max iterations.",
                    "sources": [],
                }

        return FakeAgent()

    monkeypatch.setattr(api_server, "_get_or_build_agent", fake_get_or_build_agent)

    model_config = api_server.ModelConfig(
        panel_id="panel-1",
        provider="local",
        model="qwen2.5:7b",
        base_url="http://localhost:11434",
        api_key="",
        temperature=0.3,
        agent_mode="langgraph",
    )

    async def collect():
        items = []
        async for item in api_server._invoke_agent_stream(
            "panel-1",
            model_config,
            "请根据知识库生成仪表盘",
            "dashboard-task-session-failed",
            False,
            True,
            raw_user_message="请根据知识库生成仪表盘",
        ):
            items.append(item)
        return items

    items = asyncio.run(collect())
    payloads = [
        json.loads(item.removeprefix("data: ").strip())
        for item in items
        if item.startswith("data: ")
    ]

    assert [payload["type"] for payload in payloads] == ["task_created", "error", "done"]
    assert payloads[1]["error_code"] == "MAX_ITERATIONS"

    stored = task_store.get(payloads[0]["task_id"])
    assert stored is not None
    assert stored.status == api_server.TaskStatus.FAILED
    assert stored.progress == 100
    assert stored.error == "模型工具调用次数超限，无法完成知识库仪表盘生成。"


def test_langgraph_stream_emits_workflow_state_events(monkeypatch):
    monkeypatch.setattr(agent_core, "get_llm", lambda *args, **kwargs: object())
    monkeypatch.setattr(agent_core, "DocPipeline", lambda *args, **kwargs: object())

    async def fake_build_langgraph_agent(*args, **kwargs):
        class FakeApp:
            async def ainvoke(self, state, config=None):
                workflow_sink = (
                    config.get("configurable", {}).get("workflow_event_sink")
                    if isinstance(config, dict)
                    else None
                )
                if callable(workflow_sink):
                    workflow_sink(
                        {
                            "type": "workflow_state",
                            "node_name": "classify_intent",
                            "status": "running",
                            "timestamp": 1,
                        }
                    )
                    workflow_sink(
                        {
                            "type": "workflow_state",
                            "node_name": "classify_intent",
                            "status": "completed",
                            "timestamp": 2,
                            "duration_ms": 5,
                        }
                    )
                return {"output": "hello world", "sources": []}

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

    async def collect_items():
        items = []
        async for item in agent.astream_answer(
            "hello",
            config={
                "configurable": {
                    "session_id": "workflow-stream-test",
                    "persist_history": False,
                }
            },
        ):
            items.append(item)
        return items

    items = asyncio.run(collect_items())

    workflow_items = [
        item for item in items if isinstance(item, dict) and item.get("type") == "workflow_state"
    ]
    chunk_items = [item for item in items if isinstance(item, str)]

    assert [item["status"] for item in workflow_items] == ["running", "completed"]
    assert "".join(chunk_items) == "hello world"


def test_langgraph_wrapper_streams_native_tokens_without_duplicate_chunking(monkeypatch):
    monkeypatch.setattr(agent_core, "get_llm", lambda *args, **kwargs: object())
    monkeypatch.setattr(agent_core, "DocPipeline", lambda *args, **kwargs: object())

    async def fake_build_langgraph_agent(*args, **kwargs):
        class FakeApp:
            async def ainvoke(self, state, config=None):
                configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
                workflow_sink = configurable.get("workflow_event_sink")
                stream_item_sink = configurable.get("stream_item_sink")
                if callable(workflow_sink):
                    workflow_sink(
                        {
                            "type": "workflow_state",
                            "node_name": "generate_answer",
                            "status": "running",
                            "timestamp": 1,
                        }
                    )
                if callable(stream_item_sink):
                    stream_item_sink("原生")
                    stream_item_sink("流式")
                if callable(workflow_sink):
                    workflow_sink(
                        {
                            "type": "workflow_state",
                            "node_name": "generate_answer",
                            "status": "completed",
                            "timestamp": 2,
                            "duration_ms": 5,
                        }
                    )
                return {"output": "原生流式", "sources": []}

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

    async def collect_items():
        items = []
        async for item in agent.astream_answer(
            "hello",
            config={
                "configurable": {
                    "session_id": "workflow-native-stream-test",
                    "persist_history": False,
                }
            },
        ):
            items.append(item)
        return items

    items = asyncio.run(collect_items())
    text_items = [item for item in items if isinstance(item, str)]

    assert text_items == ["原生", "流式"]
    assert any(
        isinstance(item, dict)
        and item.get("type") == "workflow_state"
        and item.get("status") == "completed"
        for item in items
    )


def test_real_langgraph_agent_streams_tokens_and_workflow_events(monkeypatch):
    class FakeLLM:
        async def ainvoke(self, payload):
            payload_text = str(payload)
            if "请只输出一个数字" not in payload_text:
                raise AssertionError("generate_answer should use native streaming")

            class Response:
                content = "0"

            return Response()

        async def astream(self, payload):
            yield "你好，"
            await asyncio.sleep(0)
            yield "世界"

    async def fake_build_runtime_tools(*args, **kwargs):
        return []

    monkeypatch.setattr(agent_core, "get_llm", lambda *args, **kwargs: FakeLLM())
    monkeypatch.setattr(agent_core, "DocPipeline", lambda *args, **kwargs: object())
    monkeypatch.setattr(agent_core, "build_runtime_tools", fake_build_runtime_tools)

    agent = asyncio.run(
        agent_core.build_agent(
            provider="local",
            agent_mode="langgraph",
            knowledge_base_enabled=False,
            web_search_enabled=False,
        )
    )

    async def collect_items():
        items = []
        async for item in agent.astream_answer(
            "hello",
            config={
                "configurable": {
                    "session_id": "real-langgraph-native-stream",
                    "persist_history": False,
                }
            },
        ):
            items.append(item)
        return items

    items = asyncio.run(collect_items())
    workflow_items = [
        item for item in items
        if isinstance(item, dict) and item.get("type") == "workflow_state"
    ]
    text_items = [item for item in items if isinstance(item, str)]

    assert text_items == ["你好，", "世界"]
    assert any(item["node_name"] == "classify_intent" for item in workflow_items)
    assert any(
        item["node_name"] == "generate_answer" and item["status"] == "completed"
        for item in workflow_items
    )


def test_session_share_link_renders_read_only_transcript(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    session_id = "shared-session"
    history = chat_store.SQLiteChatMessageHistory(session_id)
    chat_store.update_session_meta(session_id, title="Quarterly Share")
    history.add_user_message(
        "Summarize the quarter",
        images=[
            {
                "name": "chart.png",
                "media_type": "image/png",
                "data_url": "data:image/png;base64,ZmFrZQ==",
            }
        ],
    )
    history.add_ai_message(
        "Revenue improved and churn declined.",
        sources=[
            {
                "type": "doc",
                "title": "Quarterly Brief",
                "snippet": "Revenue improved by 18% quarter over quarter.",
            }
        ],
    )

    client = TestClient(api_server.app)
    response = client.post(f"/api/sessions/{session_id}/share")

    assert response.status_code == 200
    payload = response.json()
    assert payload["resource_type"] == "session"
    assert payload["share_url"].startswith("http://testserver/shared/")
    assert payload["expires_at"] > 0

    shared_path = payload["share_url"].replace("http://testserver", "")
    shared_response = client.get(shared_path)

    assert shared_response.status_code == 200
    assert "Quarterly Share" in shared_response.text
    assert "Summarize the quarter" in shared_response.text
    assert "Revenue improved and churn declined." in shared_response.text
    assert "Quarterly Brief" in shared_response.text


def test_deck_share_link_renders_read_only_deck(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    deck = deck_service.DeckSpec(
        deck_id="deck-share",
        meta=deck_service.DeckMeta(
            title="Board Update",
            subtitle="Q2 snapshot",
            theme="midnight",
            created_at="2026-04-11T10:00:00+0800",
            session_id="session-share",
            source_mode="kb_plus_chat",
            generator_panel_id="panel-main",
            author="tester",
            audience="leaders",
            purpose="review",
        ),
        generation=deck_service.DeckGeneration(
            source="kb_plus_chat",
            target_slide_count=2,
            actual_slide_count=2,
        ),
        slides=[
            deck_service.DeckSlide(
                id="cover",
                type="cover",
                title="Board Update",
                subtitle="Q2 snapshot",
                layout="hero-title",
                blocks=[
                    deck_service.DeckBlock(
                        id="cover-block",
                        kind="paragraph",
                        role="summary",
                        content={"text": "Executive summary"},
                    )
                ],
            ),
            deck_service.DeckSlide(
                id="content-1",
                type="content",
                title="Growth Signals",
                subtitle="What changed",
                layout="title-bullets",
                blocks=[
                    deck_service.DeckBlock(
                        id="content-block",
                        kind="bullet_list",
                        role="main_points",
                        content={"items": ["Revenue +18%", "Churn -4%"]},
                    )
                ],
                speaker_notes="Highlight the durable trend.",
                quality_state="supported",
            ),
        ],
        source_registry=[],
    )
    api_server._deck_store.save(deck)

    client = TestClient(api_server.app)
    response = client.post("/api/decks/deck-share/share")

    assert response.status_code == 200
    payload = response.json()
    assert payload["resource_type"] == "deck"
    assert payload["share_url"].startswith("http://testserver/shared/")
    assert payload["expires_at"] > 0

    shared_path = payload["share_url"].replace("http://testserver", "")
    shared_response = client.get(shared_path)

    assert shared_response.status_code == 200
    assert "Board Update" in shared_response.text
    assert "Growth Signals" in shared_response.text
    assert "Revenue +18%" in shared_response.text
    assert "midnight" in shared_response.text


def test_revoked_share_link_returns_404(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    session_id = "shared-session-revoke"
    history = chat_store.SQLiteChatMessageHistory(session_id)
    history.add_user_message("hello")

    client = TestClient(api_server.app)
    created = client.post(f"/api/sessions/{session_id}/share")
    assert created.status_code == 200
    payload = created.json()

    revoked = client.delete(f"/api/share-links/{payload['share_token']}")
    assert revoked.status_code == 200
    assert revoked.json() == {"ok": True}

    shared_path = payload["share_url"].replace("http://testserver", "")
    shared_response = client.get(shared_path)
    assert shared_response.status_code == 404


def test_expired_share_link_returns_404(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(api_server, "SHARE_LINK_TTL_SECONDS", -1)

    session_id = "shared-session-expired"
    history = chat_store.SQLiteChatMessageHistory(session_id)
    history.add_user_message("hello")

    client = TestClient(api_server.app)
    created = client.post(f"/api/sessions/{session_id}/share")
    assert created.status_code == 200
    payload = created.json()

    shared_path = payload["share_url"].replace("http://testserver", "")
    shared_response = client.get(shared_path)
    assert shared_response.status_code == 404


def test_invalid_share_token_returns_404():
    client = TestClient(api_server.app)
    response = client.get("/shared/not-a-valid-token")

    assert response.status_code == 404


def test_share_missing_session_returns_404():
    client = TestClient(api_server.app)
    response = client.post("/api/sessions/session-does-not-exist/share")

    assert response.status_code == 404
