import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import backend.api_server as api_server
import backend.chat_store as chat_store
import backend.deck_service as deck_service


def _history_cls_for_db(db_path: Path):
    class TestSQLiteChatMessageHistory(chat_store.SQLiteChatMessageHistory):
        def __init__(self, session_id: str, db_path_arg: str = "./chat_history.db"):
            super().__init__(session_id=session_id, db_path=str(db_path))

    return TestSQLiteChatMessageHistory


def test_workspaces_list_create_and_activate(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)
    client = TestClient(api_server.app)

    initial = client.get("/api/workspaces")
    assert initial.status_code == 200
    initial_payload = initial.json()
    default_workspace = next(
        item
        for item in initial_payload["workspaces"]
        if item["workspace_id"] == chat_store.DEFAULT_WORKSPACE_ID
    )

    assert initial_payload["active_workspace_id"] == chat_store.DEFAULT_WORKSPACE_ID
    assert default_workspace["name"] == chat_store.DEFAULT_WORKSPACE_NAME
    assert default_workspace["is_active"] is True

    created = client.post(
        "/api/workspaces",
        json={
            "name": "Strategy",
            "description": "Quarter planning",
            "color": "green",
            "activate": False,
        },
    )
    assert created.status_code == 200
    created_workspace = created.json()["workspace"]

    assert created_workspace["name"] == "Strategy"
    assert created_workspace["description"] == "Quarter planning"
    assert created_workspace["color"] == "green"
    assert created_workspace["is_active"] is False
    assert created_workspace["session_count"] == 0

    activated = client.post(
        f"/api/workspaces/{created_workspace['workspace_id']}/activate"
    )
    assert activated.status_code == 200
    activated_workspace = activated.json()["workspace"]
    assert activated_workspace["workspace_id"] == created_workspace["workspace_id"]
    assert activated_workspace["is_active"] is True

    history_cls("session-implicit-workspace")
    stored_session = chat_store.get_session(
        "session-implicit-workspace",
        db_path=str(db_path),
    )
    assert stored_session is not None
    assert stored_session["workspace_id"] == created_workspace["workspace_id"]


def test_workspace_preset_roundtrip(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_server.app)

    created = client.post(
        "/api/workspaces",
        json={
            "name": "Research",
            "color": "blue",
            "activate": True,
            "preset": {
                "default_panels": [
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
                        "provider": "openai_compatible",
                        "connection_type": "openai_compatible",
                        "model": "openai/gpt-4o-mini",
                        "base_url": "https://openrouter.ai/api/v1",
                        "api_key": "",
                        "api_key_ref": "cmk-workspace-test",
                        "temperature": 0.6,
                        "agent_mode": "langgraph",
                    },
                ],
                "tool_config": {
                    "web_search_enabled": True,
                    "knowledge_base_enabled": False,
                    "mcp_servers_enabled": ["web-search"],
                },
                "output_preset": {
                    "deck_theme": "midnight",
                    "target_slide_count": 6,
                },
            },
        },
    )

    assert created.status_code == 200

    workspace = created.json()["workspace"]
    assert workspace["preset"]["tool_config"] == {
        "web_search_enabled": True,
        "knowledge_base_enabled": False,
        "mcp_servers_enabled": ["web-search"],
    }
    assert workspace["preset"]["output_preset"] == {
        "deck_theme": "midnight",
        "target_slide_count": 6,
    }
    assert [item["panel_id"] for item in workspace["preset"]["default_panels"]] == [
        "panel-main",
        "panel-compare",
    ]
    assert workspace["preset"]["default_panels"][1]["api_key_ref"] == "cmk-workspace-test"

    updated = client.patch(
        f"/api/workspaces/{workspace['workspace_id']}",
        json={
            "preset": {
                "default_panels": [
                    {
                        "panel_id": "panel-main",
                        "provider": "ollama",
                        "connection_type": "ollama",
                        "model": "qwen-updated",
                        "base_url": "http://localhost:11434",
                        "api_key": "",
                        "temperature": 0.4,
                        "agent_mode": "plain_chat",
                    }
                ],
                "tool_config": {
                    "web_search_enabled": False,
                    "knowledge_base_enabled": True,
                    "mcp_servers_enabled": ["knowledge-base", "custom-crm"],
                },
                "output_preset": {
                    "deck_theme": "sunrise",
                    "target_slide_count": 9,
                },
            }
        },
    )

    assert updated.status_code == 200
    updated_workspace = updated.json()["workspace"]
    assert updated_workspace["preset"]["tool_config"] == {
        "web_search_enabled": False,
        "knowledge_base_enabled": True,
        "mcp_servers_enabled": ["knowledge-base", "custom-crm"],
    }
    assert updated_workspace["preset"]["output_preset"] == {
        "deck_theme": "sunrise",
        "target_slide_count": 9,
    }
    assert [item["model"] for item in updated_workspace["preset"]["default_panels"]] == [
        "qwen-updated"
    ]

    listed = client.get("/api/workspaces")
    assert listed.status_code == 200
    listed_workspace = next(
        item
        for item in listed.json()["workspaces"]
        if item["workspace_id"] == workspace["workspace_id"]
    )
    assert listed_workspace["preset"]["output_preset"]["deck_theme"] == "sunrise"
    assert listed_workspace["preset"]["tool_config"]["mcp_servers_enabled"] == [
        "knowledge-base",
        "custom-crm",
    ]


def test_normalize_model_config_accepts_plain_dict():
    normalized = api_server._normalize_model_config(
        {
            "panel_id": "panel-main",
            "provider": "ollama",
            "connection_type": "ollama",
            "model": "qwen3.5-2B:latest",
            "base_url": "http://localhost:11434",
            "api_key": "",
            "temperature": 0.3,
            "agent_mode": "auto",
        }
    )

    assert normalized.panel_id == "panel-main"
    assert normalized.connection_type == "ollama"
    assert normalized.provider == "ollama"
    assert normalized.model == "qwen3.5-2B:latest"


def test_mcp_connector_catalog_endpoint(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        api_server,
        "list_mcp_server_catalog",
        lambda: [
            {
                "name": "knowledge-base",
                "label": "Knowledge Base",
                "description": "Internal KB",
                "category": "knowledge",
                "builtin": True,
                "transport": "stdio",
                "source": "default",
            },
            {
                "name": "custom-crm",
                "label": "CRM",
                "description": "CRM records",
                "category": "business",
                "builtin": False,
                "transport": "stdio",
                "source": "config",
            },
        ],
    )
    monkeypatch.setattr(
        api_server,
        "default_mcp_server_names",
        lambda: ["knowledge-base"],
    )

    client = TestClient(api_server.app)
    response = client.get("/api/connectors/mcp")

    assert response.status_code == 200
    assert response.json() == {
        "connectors": [
            {
                "name": "knowledge-base",
                "label": "Knowledge Base",
                "description": "Internal KB",
                "category": "knowledge",
                "builtin": True,
                "transport": "stdio",
                "source": "default",
            },
            {
                "name": "custom-crm",
                "label": "CRM",
                "description": "CRM records",
                "category": "business",
                "builtin": False,
                "transport": "stdio",
                "source": "config",
            },
        ],
        "default_enabled": ["knowledge-base"],
    }


def test_mcp_connector_runtime_health_endpoint(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    async def fake_runtime_health():
        return {
            "status": "ok",
            "servers": [
                {
                    "name": "knowledge-base",
                    "status": "healthy",
                    "healthy": True,
                    "tool_count": 1,
                    "tools": ["knowledge_query"],
                    "duration_ms": 12.5,
                    "error": None,
                }
            ],
            "summary": {
                "total": 1,
                "healthy": 1,
                "unhealthy": 0,
                "tool_count": 1,
            },
        }

    monkeypatch.setattr(
        api_server,
        "list_mcp_server_runtime_health",
        fake_runtime_health,
    )

    client = TestClient(api_server.app)
    response = client.get("/api/connectors/mcp/runtime-health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["summary"]["tool_count"] == 1


def test_mcp_connector_runtime_health_history_persists_limit_and_redacts(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    store = api_server.SQLiteAppConfigStore(db_path=str(tmp_path / "config.db"))
    monkeypatch.setattr(api_server, "_app_config_store", store)
    counter = {"value": 0}

    async def fake_runtime_health(**kwargs):
        counter["value"] += 1
        name = f"connector-{counter['value']}"
        snapshot = {
            "timestamp": 100.0 + counter["value"],
            "status": "ok",
            "servers": [
                {
                    "name": name,
                    "status": "healthy",
                    "healthy": True,
                    "tool_count": 1,
                    "duration_ms": 5.0,
                    "error": None,
                    "tools": ["raw_tool_result"],
                    "env": {"API_KEY": "secret"},
                    "args": ["--secret"],
                    "secret": "hidden",
                }
            ],
            "summary": {
                "total": 1,
                "healthy": 1,
                "unhealthy": 0,
                "tool_count": 1,
                "status_counts": {"healthy": 1},
                "alert_count": 0,
            },
        }
        kwargs["history_recorder"](snapshot, 2)
        history = kwargs["history_reader"](2)
        return {
            "status": "ok",
            "servers": snapshot["servers"],
            "summary": snapshot["summary"],
            "history": history,
            "history_limit": 2,
        }

    monkeypatch.setattr(api_server, "_list_mcp_server_runtime_health", fake_runtime_health)

    client = TestClient(api_server.app)
    first = client.get("/api/connectors/mcp/runtime-health")
    second = client.get("/api/connectors/mcp/runtime-health")
    history_response = client.get(
        "/api/connectors/mcp/runtime-health/history?limit=1"
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert history_response.status_code == 200
    history = history_response.json()["history"]
    assert [item["servers"][0]["name"] for item in history] == ["connector-2"]
    persisted_json = store.get_value(
        api_server.MCP_RUNTIME_HEALTH_HISTORY_CONFIG_KEY,
        "[]",
    )
    assert "connector-2" in persisted_json
    assert "raw_tool_result" not in persisted_json
    assert "API_KEY" not in persisted_json
    assert "--secret" not in persisted_json
    assert "hidden" not in persisted_json


def test_mcp_connector_approval_endpoint_payload(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    store = api_server.SQLiteAppConfigStore(db_path=str(tmp_path / "config.db"))
    monkeypatch.setattr(api_server, "_app_config_store", store)
    monkeypatch.setenv("MCP_APPROVED_CONNECTORS", "knowledge-base")
    api_server.set_runtime_mcp_approved_connectors(["custom-crm"])
    client = TestClient(api_server.app)

    try:
        response = client.get("/api/connectors/mcp/approvals")

        assert response.status_code == 200
        assert response.json() == {
            "approved_connectors": ["knowledge-base", "custom-crm"],
            "env_connectors": ["knowledge-base"],
            "runtime_connectors": ["custom-crm"],
            "persisted_connectors": ["custom-crm"],
            "sources": {
                "knowledge-base": ["env"],
                "custom-crm": ["runtime"],
            },
            "persistence": {
                "enabled": True,
                "config_key": "mcp_approved_connectors",
            },
            "total": 2,
        }
    finally:
        api_server.clear_runtime_mcp_approved_connectors()


def test_mcp_connector_approval_endpoint_hydrates_persisted_names(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    store = api_server.SQLiteAppConfigStore(db_path=str(tmp_path / "config.db"))
    store.set("mcp_approved_connectors", "crm-sync")
    monkeypatch.setattr(api_server, "_app_config_store", store)
    monkeypatch.delenv("MCP_APPROVED_CONNECTORS", raising=False)
    api_server._set_runtime_mcp_approved_connectors([])
    client = TestClient(api_server.app)

    try:
        response = client.get("/api/connectors/mcp/approvals")

        assert response.status_code == 200
        payload = response.json()
        assert payload["approved_connectors"] == ["crm-sync"]
        assert payload["runtime_connectors"] == ["crm-sync"]
        assert payload["persisted_connectors"] == ["crm-sync"]
    finally:
        api_server.clear_runtime_mcp_approved_connectors()


def test_mcp_connector_approval_endpoint_enforces_viewer_and_admin_roles(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    store = api_server.SQLiteAppConfigStore(db_path=str(tmp_path / "config.db"))
    monkeypatch.setattr(api_server, "_app_config_store", store)
    monkeypatch.delenv("MCP_APPROVED_CONNECTORS", raising=False)
    monkeypatch.setattr(api_server, "ALLOW_REMOTE_CLIENTS", True)
    monkeypatch.setattr(api_server, "_request_is_local", lambda request: False)
    monkeypatch.setenv(
        "APP_AUTH_TOKENS_JSON",
        json.dumps(
            [
                {
                    "token": "viewer-token",
                    "user_id": "viewer.user",
                    "role": "viewer",
                    "auth_source": "viewer_catalog",
                },
                {
                    "token": "admin-token",
                    "user_id": "admin.user",
                    "role": "admin",
                    "auth_source": "admin_catalog",
                },
            ]
        ),
    )
    api_server.clear_runtime_mcp_approved_connectors()
    client = TestClient(api_server.app)

    try:
        viewer_headers = {"X-API-Token": "viewer-token"}
        admin_headers = {"X-API-Token": "admin-token"}

        listed = client.get("/api/connectors/mcp/approvals", headers=viewer_headers)
        assert listed.status_code == 200
        assert listed.json()["approved_connectors"] == []

        denied = client.post(
            "/api/connectors/mcp/approvals",
            headers=viewer_headers,
            json={"name": "crm-sync"},
        )
        assert denied.status_code == 403
        assert denied.json()["detail"] == "Insufficient role: admin required."

        approved = client.post(
            "/api/connectors/mcp/approvals",
            headers=admin_headers,
            json={"name": "crm-sync"},
        )
        assert approved.status_code == 200
        approval_payload = approved.json()
        assert approval_payload["connector"] == {
            "name": "crm-sync",
            "changed": True,
            "runtime_approved": True,
            "effective_approved": True,
        }
        assert approval_payload["runtime_connectors"] == ["crm-sync"]
        assert approval_payload["persisted_connectors"] == ["crm-sync"]
        assert store.get_value("mcp_approved_connectors") == "crm-sync"

        revoked = client.delete(
            "/api/connectors/mcp/approvals/crm-sync",
            headers=admin_headers,
        )
        assert revoked.status_code == 200
        revoke_payload = revoked.json()
        assert revoke_payload["connector"] == {
            "name": "crm-sync",
            "removed": True,
            "runtime_approved": False,
            "effective_approved": False,
        }
        assert revoke_payload["runtime_connectors"] == []
        assert revoke_payload["persisted_connectors"] == []
        assert store.get_value("mcp_approved_connectors") == ""
    finally:
        api_server.clear_runtime_mcp_approved_connectors()


def test_sessions_support_workspace_filters_and_move(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)
    client = TestClient(api_server.app)

    history_cls("session-default-workspace")

    created_workspace = client.post(
        "/api/workspaces",
        json={"name": "Delivery", "color": "amber", "activate": True},
    )
    assert created_workspace.status_code == 200
    workspace = created_workspace.json()["workspace"]

    created_session = client.post(
        "/api/sessions",
        json={"title": "Launch checklist", "workspace_id": workspace["workspace_id"]},
    )
    assert created_session.status_code == 200
    created_session_payload = created_session.json()

    assert created_session_payload["title"] == "Launch checklist"
    assert created_session_payload["workspace_id"] == workspace["workspace_id"]

    workspace_sessions = client.get(
        "/api/sessions",
        params={"workspace_id": workspace["workspace_id"]},
    )
    assert workspace_sessions.status_code == 200
    assert [item["session_id"] for item in workspace_sessions.json()["sessions"]] == [
        created_session_payload["session_id"]
    ]

    default_sessions_before_move = client.get(
        "/api/sessions",
        params={"workspace_id": chat_store.DEFAULT_WORKSPACE_ID},
    )
    assert default_sessions_before_move.status_code == 200
    assert {
        item["session_id"]
        for item in default_sessions_before_move.json()["sessions"]
    } == {"session-default-workspace"}

    moved = client.patch(
        f"/api/sessions/{created_session_payload['session_id']}",
        json={"workspace_id": chat_store.DEFAULT_WORKSPACE_ID},
    )
    assert moved.status_code == 200
    moved_session = moved.json()["session"]
    assert moved_session["workspace_id"] == chat_store.DEFAULT_WORKSPACE_ID

    workspace_sessions_after_move = client.get(
        "/api/sessions",
        params={"workspace_id": workspace["workspace_id"]},
    )
    assert workspace_sessions_after_move.status_code == 200
    assert workspace_sessions_after_move.json()["sessions"] == []

    default_sessions_after_move = client.get(
        "/api/sessions",
        params={"workspace_id": chat_store.DEFAULT_WORKSPACE_ID},
    )
    assert default_sessions_after_move.status_code == 200
    assert {
        item["session_id"] for item in default_sessions_after_move.json()["sessions"]
    } == {
        "session-default-workspace",
        created_session_payload["session_id"],
    }


def test_create_session_rejects_missing_workspace_without_side_effects(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    client = TestClient(api_server.app)

    response = client.post(
        "/api/sessions",
        json={"title": "Bad workspace", "workspace_id": "workspace-missing"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "工作区不存在"

    assert chat_store.get_all_sessions(db_path=str(db_path)) == []


def test_delete_session_endpoint_removes_session(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)
    client = TestClient(api_server.app)

    session_id = "session-delete-route"
    history = history_cls(session_id)
    history.add_user_message("hello")

    before = chat_store.get_session(session_id, db_path=str(db_path))
    assert before is not None

    response = client.delete(f"/api/sessions/{session_id}")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert chat_store.get_session(session_id, db_path=str(db_path)) is None


def test_delete_session_endpoint_is_idempotent_on_fresh_db(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_server.app)

    response = client.delete("/api/sessions/session-missing")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_delete_session_removes_retrieval_feedback(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)
    client = TestClient(api_server.app)

    session_id = "session-delete-feedback"
    history = history_cls(session_id)
    history.add_user_message("Need sources", answer_group_id="grp-feedback")
    history.add_ai_message(
        "Here are the sources",
        panel_id="panel-main",
        answer_group_id="grp-feedback",
    )
    chat_store.set_retrieval_feedback(
        session_id,
        panel_id="panel-main",
        answer_group_id="grp-feedback",
        source={"type": "web", "title": "Doc", "url": "https://example.com/doc"},
        feedback_value=1,
        db_path=str(db_path),
    )

    before = chat_store.list_retrieval_feedback(
        session_id,
        panel_id="panel-main",
        answer_group_id="grp-feedback",
        db_path=str(db_path),
    )
    assert len(before) == 1

    response = client.delete(f"/api/sessions/{session_id}")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert chat_store.get_session(session_id, db_path=str(db_path)) is None
    assert (
        chat_store.list_retrieval_feedback(
            session_id,
            panel_id="panel-main",
            answer_group_id="grp-feedback",
            db_path=str(db_path),
        )
        == []
    )


def test_delete_session_endpoint_cascades_to_decks_and_tasks(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)
    task_store = api_server.SQLiteTaskStore(db_path=str(db_path))
    deck_store = deck_service.SQLiteDeckStore(db_path=str(db_path))
    in_memory_task = api_server.TaskRecord(
        task_id="task-in-memory-session-delete",
        task_type="generate_report",
        status=api_server.TaskStatus.RUNNING,
        params={"mode": "demo"},
        session_id="session-delete-cascade",
        created_at=10.0,
        updated_at=12.0,
        progress=60,
    )

    monkeypatch.setattr(api_server, "_task_store", task_store)
    monkeypatch.setattr(api_server, "_deck_store", deck_store)
    monkeypatch.setattr(api_server, "_tasks", {in_memory_task.task_id: in_memory_task})

    client = TestClient(api_server.app)
    session_id = "session-delete-cascade"
    history = history_cls(session_id)
    history.add_user_message("hello")

    task_store.save(
        api_server.TaskRecord(
            task_id="task-persisted-session-delete",
            task_type="promote_attachment_to_kb",
            status=api_server.TaskStatus.COMPLETED,
            params={
                "attachment_id": "att-brief",
                "attachment_name": "brief.txt",
                "vector_store_path": "vector_store_test",
            },
            session_id=session_id,
            created_at=5.0,
            updated_at=7.0,
            result="indexed",
            progress=100,
        )
    )
    deck_store.save(
        deck_service.DeckSpec(
            deck_id="deck-session-delete",
            meta=deck_service.DeckMeta(
                title="Delete Me",
                created_at="2026-04-14T10:00:00+0800",
                session_id=session_id,
                source_mode="chat_only",
                generator_panel_id="panel-main",
            ),
            generation=deck_service.DeckGeneration(
                source="chat_only",
                target_slide_count=1,
                actual_slide_count=1,
            ),
            slides=[
                deck_service.DeckSlide(
                    id="slide-1",
                    type="content",
                    title="Slide",
                    layout="title-bullets",
                    blocks=[
                        deck_service.DeckBlock(
                            id="block-1",
                            kind="paragraph",
                            role="summary",
                            content={"text": "Delete me too"},
                        )
                    ],
                )
            ],
            source_registry=[],
        )
    )

    response = client.delete(f"/api/sessions/{session_id}")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert chat_store.get_session(session_id, db_path=str(db_path)) is None
    assert task_store.get("task-persisted-session-delete") is None
    assert task_store.get_attachment_promotion("att-brief", "vector_store_test") is None
    assert api_server._tasks == {}
    with pytest.raises(KeyError):
        deck_store.get("deck-session-delete")


def test_delete_session_suppresses_late_task_writeback(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)
    task_store = api_server.SQLiteTaskStore(db_path=str(db_path))
    late_record = api_server.TaskRecord(
        task_id="task-late-writeback",
        task_type="generate_dashboard",
        status=api_server.TaskStatus.RUNNING,
        params={"prompt_excerpt": "demo"},
        session_id="session-delete-late-writeback",
        created_at=10.0,
        updated_at=12.0,
        progress=60,
    )

    monkeypatch.setattr(api_server, "_task_store", task_store)
    monkeypatch.setattr(api_server, "_tasks", {late_record.task_id: late_record})

    client = TestClient(api_server.app)
    history = history_cls("session-delete-late-writeback")
    history.add_user_message("hello")

    response = client.delete("/api/sessions/session-delete-late-writeback")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert task_store.get(late_record.task_id) is None
    assert api_server._tasks == {}

    late_record.progress = 90
    late_record.updated_at = 20.0
    api_server._persist_task_record(late_record)
    assert task_store.get(late_record.task_id) is None

    asyncio.run(
        api_server._set_inline_task_state(
            late_record,
            status=api_server.TaskStatus.COMPLETED,
            progress=100,
            result="too late",
        )
    )
    assert task_store.get(late_record.task_id) is None
    assert api_server._tasks == {}


def test_attachment_workspace_endpoints_require_session_in_current_workspace(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)
    client = TestClient(api_server.app)

    created_workspace = client.post(
        "/api/workspaces",
        json={"name": "Ops", "color": "green", "activate": True},
    )
    assert created_workspace.status_code == 200
    workspace = created_workspace.json()["workspace"]

    other_workspace = client.post(
        "/api/workspaces",
        json={"name": "Finance", "color": "amber", "activate": False},
    )
    assert other_workspace.status_code == 200
    wrong_workspace = other_workspace.json()["workspace"]

    session_id = "session-attachment-workspace"
    history = history_cls(session_id)
    history.add_user_message(
        "Use this brief",
        answer_group_id="grp-brief",
        files=[
            {
                "name": "brief.txt",
                "media_type": "text/plain",
                "data_url": "data:text/plain;base64,QnJpZWY=",
                "size_bytes": 5,
                "extracted_text": "Workspace isolated brief",
            }
        ],
    )

    stored_session = chat_store.get_session(session_id, db_path=str(db_path))
    assert stored_session is not None
    assert stored_session["workspace_id"] == workspace["workspace_id"]

    ok_response = client.get(
        f"/api/sessions/{session_id}/attachments",
        params={"workspace_id": workspace["workspace_id"]},
    )
    assert ok_response.status_code == 200
    attachment_id = ok_response.json()["attachments"][0]["attachment_id"]

    blocked_list = client.get(
        f"/api/sessions/{session_id}/attachments",
        params={"workspace_id": wrong_workspace["workspace_id"]},
    )
    assert blocked_list.status_code == 404
    assert blocked_list.json()["detail"] == "当前工作区中不存在该会话"

    blocked_promote = client.post(
        f"/api/sessions/{session_id}/attachments/{attachment_id}/promote",
        params={"workspace_id": wrong_workspace["workspace_id"]},
    )
    assert blocked_promote.status_code == 404
    assert blocked_promote.json()["detail"] == "当前工作区中不存在该会话"


def test_delete_session_invalidates_session_and_deck_share_links(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)
    deck_store = deck_service.SQLiteDeckStore(db_path=str(db_path))
    monkeypatch.setattr(api_server, "_deck_store", deck_store)

    session_id = "session-delete-share-links"
    history = history_cls(session_id)
    history.add_user_message("share me")

    deck_store.save(
        deck_service.DeckSpec(
            deck_id="deck-delete-share-links",
            meta=deck_service.DeckMeta(
                title="Delete Share Links",
                created_at="2026-04-14T10:00:00+0800",
                session_id=session_id,
                source_mode="chat_only",
                generator_panel_id="panel-main",
            ),
            generation=deck_service.DeckGeneration(
                source="chat_only",
                target_slide_count=1,
                actual_slide_count=1,
            ),
            slides=[
                deck_service.DeckSlide(
                    id="slide-1",
                    type="content",
                    title="Slide",
                    layout="title-bullets",
                    blocks=[],
                )
            ],
            source_registry=[],
        )
    )

    client = TestClient(api_server.app)
    session_share = client.post(f"/api/sessions/{session_id}/share").json()
    deck_share = client.post("/api/decks/deck-delete-share-links/share").json()

    deleted = client.delete(f"/api/sessions/{session_id}")
    assert deleted.status_code == 200

    session_shared_response = client.get(
        session_share["share_url"].replace("http://testserver", "")
    )
    deck_shared_response = client.get(
        deck_share["share_url"].replace("http://testserver", "")
    )

    assert session_shared_response.status_code == 404
    assert deck_shared_response.status_code == 404


def test_delete_workspace_moves_sessions_and_reactivates_target(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)
    client = TestClient(api_server.app)

    created = client.post(
        "/api/workspaces",
        json={"name": "Operations", "color": "rose", "activate": True},
    )
    assert created.status_code == 200
    workspace = created.json()["workspace"]

    history = history_cls("session-delete-workspace")
    stored_before = chat_store.get_session(history.session_id, db_path=str(db_path))
    assert stored_before is not None
    assert stored_before["workspace_id"] == workspace["workspace_id"]

    deleted = client.delete(f"/api/workspaces/{workspace['workspace_id']}")
    assert deleted.status_code == 200
    deleted_payload = deleted.json()

    assert deleted_payload["deleted_workspace_id"] == workspace["workspace_id"]
    assert deleted_payload["target_workspace_id"] == chat_store.DEFAULT_WORKSPACE_ID
    assert deleted_payload["target_workspace"]["workspace_id"] == chat_store.DEFAULT_WORKSPACE_ID
    assert deleted_payload["target_workspace"]["is_active"] is True

    stored_after = chat_store.get_session(history.session_id, db_path=str(db_path))
    assert stored_after is not None
    assert stored_after["workspace_id"] == chat_store.DEFAULT_WORKSPACE_ID

    listed = client.get("/api/workspaces")
    assert listed.status_code == 200
    workspace_ids = {item["workspace_id"] for item in listed.json()["workspaces"]}
    assert workspace["workspace_id"] not in workspace_ids
    assert chat_store.DEFAULT_WORKSPACE_ID in workspace_ids


def test_delete_workspace_rejects_default_workspace(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api_server.app)

    response = client.delete(f"/api/workspaces/{chat_store.DEFAULT_WORKSPACE_ID}")
    assert response.status_code == 400
    assert response.json()["detail"] == "默认工作区不能删除"
