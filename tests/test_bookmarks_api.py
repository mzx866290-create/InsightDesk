from pathlib import Path

from fastapi.testclient import TestClient

import api_server
import chat_store


def _history_cls_for_db(db_path: Path):
    class TestSQLiteChatMessageHistory(chat_store.SQLiteChatMessageHistory):
        def __init__(self, session_id: str, db_path_arg: str = "./chat_history.db"):
            super().__init__(session_id=session_id, db_path=str(db_path))

    return TestSQLiteChatMessageHistory


def test_bookmarks_persist_list_and_delete(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)

    history = history_cls("session-bookmarks")
    history.add_user_message("Need a concise summary", answer_group_id="grp-bookmark")
    history.add_ai_message(
        "Here is the saved answer.",
        panel_id="panel-main",
        answer_group_id="grp-bookmark",
        model_id="qwen-main",
    )
    chat_store.update_session_meta(
        "session-bookmarks",
        title="Bookmark Session",
        db_path=str(db_path),
    )

    client = TestClient(api_server.app)
    created = client.post(
        "/api/bookmarks",
        json={
            "session_id": "session-bookmarks",
            "role": "assistant",
            "panel_id": "panel-main",
            "answer_group_id": "grp-bookmark",
            "content": "Here is the saved answer.",
            "model_id": "qwen-main",
        },
    )
    assert created.status_code == 200
    bookmark = created.json()["bookmark"]
    assert bookmark["session_title"] == "Bookmark Session"
    assert bookmark["panel_id"] == "panel-main"
    assert bookmark["answer_group_id"] == "grp-bookmark"

    listed = client.get("/api/bookmarks")
    assert listed.status_code == 200
    listed_bookmarks = listed.json()["bookmarks"]
    assert len(listed_bookmarks) == 1
    assert listed_bookmarks[0]["id"] == bookmark["id"]

    removed = client.delete(f"/api/bookmarks/{bookmark['id']}")
    assert removed.status_code == 200

    relisted = client.get("/api/bookmarks")
    assert relisted.status_code == 200
    assert relisted.json()["bookmarks"] == []


def test_bookmarks_upsert_same_message_without_duplicates(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)

    history = history_cls("session-bookmarks-upsert")
    history.add_user_message("Track this answer", answer_group_id="grp-upsert")
    history.add_ai_message(
        "Original answer snapshot",
        panel_id="panel-main",
        answer_group_id="grp-upsert",
        model_id="qwen-main",
    )

    assistant_records = history.get_all_message_records(panel_id="panel-main")
    assistant_message = next(
        record for record in assistant_records if record["type"] == "ai"
    )

    client = TestClient(api_server.app)
    first = client.post(
        "/api/bookmarks",
        json={
            "session_id": "session-bookmarks-upsert",
            "role": "assistant",
            "message_id": assistant_message["id"],
            "content": "Original answer snapshot",
        },
    )
    assert first.status_code == 200
    first_bookmark = first.json()["bookmark"]

    second = client.post(
        "/api/bookmarks",
        json={
            "session_id": "session-bookmarks-upsert",
            "role": "assistant",
            "message_id": assistant_message["id"],
            "content": "Updated answer snapshot",
        },
    )
    assert second.status_code == 200
    second_bookmark = second.json()["bookmark"]

    assert second_bookmark["id"] == first_bookmark["id"]
    assert second_bookmark["content"] == "Updated answer snapshot"

    listed = client.get("/api/bookmarks")
    assert listed.status_code == 200
    listed_bookmarks = listed.json()["bookmarks"]
    assert len(listed_bookmarks) == 1
    assert listed_bookmarks[0]["content"] == "Updated answer snapshot"
