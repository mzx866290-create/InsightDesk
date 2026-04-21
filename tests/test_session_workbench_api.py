from pathlib import Path

from fastapi.testclient import TestClient

import backend.api_server as api_server
import backend.chat_store as chat_store


def _history_cls_for_db(db_path: Path):
    class TestSQLiteChatMessageHistory(chat_store.SQLiteChatMessageHistory):
        def __init__(self, session_id: str, db_path_arg: str = "./chat_history.db"):
            super().__init__(session_id=session_id, db_path=str(db_path))

    return TestSQLiteChatMessageHistory


def test_get_sessions_returns_metadata_and_supports_filters(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)

    favorite_history = history_cls("session-favorite")
    favorite_history.add_user_message("采购方案")
    favorite_history.add_ai_message("采购方案回答", panel_id="panel-main")
    chat_store.replace_session_panels(
        "session-favorite",
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
    chat_store.update_session_meta(
        "session-favorite",
        is_favorite=True,
        tags=["采购", "重点"],
        db_path=str(db_path),
    )

    archived_history = history_cls("session-archived")
    archived_history.add_user_message("历史项目")
    chat_store.update_session_meta(
        "session-archived",
        title="归档项目",
        is_archived=True,
        tags=["历史"],
        db_path=str(db_path),
    )

    normal_history = history_cls("session-normal")
    normal_history.add_user_message("预算分析")
    chat_store.update_session_meta(
        "session-normal",
        title="季度预算分析",
        tags=["财务"],
        db_path=str(db_path),
    )

    client = TestClient(api_server.app)

    response = client.get("/api/sessions")
    assert response.status_code == 200
    payload = response.json()
    sessions = {item["session_id"]: item for item in payload["sessions"]}

    assert sessions["session-favorite"]["is_favorite"] is True
    assert sessions["session-favorite"]["is_archived"] is False
    assert sessions["session-favorite"]["tags"] == ["采购", "重点"]
    assert sessions["session-favorite"]["message_count"] == 2

    favorite_response = client.get("/api/sessions", params={"favorite": True})
    assert favorite_response.status_code == 200
    assert [item["session_id"] for item in favorite_response.json()["sessions"]] == [
        "session-favorite"
    ]

    archived_response = client.get("/api/sessions", params={"archived": True})
    assert archived_response.status_code == 200
    assert [item["session_id"] for item in archived_response.json()["sessions"]] == [
        "session-archived"
    ]

    tag_response = client.get("/api/sessions", params={"tag": "采购"})
    assert tag_response.status_code == 200
    assert [item["session_id"] for item in tag_response.json()["sessions"]] == [
        "session-favorite"
    ]

    query_response = client.get("/api/sessions", params={"query": "预算"})
    assert query_response.status_code == 200
    assert [item["session_id"] for item in query_response.json()["sessions"]] == [
        "session-normal"
    ]


def test_patch_session_updates_metadata(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)

    history = history_cls("session-update")
    history.add_user_message("原始标题")

    client = TestClient(api_server.app)
    response = client.patch(
        "/api/sessions/session-update",
        json={
            "title": "新的会话标题",
            "is_favorite": True,
            "is_archived": True,
            "tags": ["知识库", "周报", "知识库"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    session = payload["session"]

    assert payload["ok"] is True
    assert session["title"] == "新的会话标题"
    assert session["is_favorite"] is True
    assert session["is_archived"] is True
    assert session["tags"] == ["知识库", "周报"]

    stored = chat_store.get_session("session-update", db_path=str(db_path))
    assert stored is not None
    assert stored["title"] == "新的会话标题"
    assert stored["is_favorite"] is True
    assert stored["is_archived"] is True
    assert stored["tags"] == ["知识库", "周报"]


def test_patch_session_rejects_empty_payload(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)

    history_cls("session-empty-payload")

    client = TestClient(api_server.app)
    response = client.patch("/api/sessions/session-empty-payload", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == "至少需要提供一个可更新字段"
