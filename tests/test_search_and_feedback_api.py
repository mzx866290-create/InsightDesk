from pathlib import Path

from fastapi.testclient import TestClient

import api_server
import chat_store


def _history_cls_for_db(db_path: Path):
    class TestSQLiteChatMessageHistory(chat_store.SQLiteChatMessageHistory):
        def __init__(self, session_id: str, db_path_arg: str = "./chat_history.db"):
            super().__init__(session_id=session_id, db_path=str(db_path))

    return TestSQLiteChatMessageHistory


def test_session_query_matches_message_content_and_returns_preview(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)

    budget_history = history_cls("session-budget-search")
    budget_history.add_user_message("Let's discuss launch planning")
    budget_history.add_ai_message("The budget approval is pending final review.")
    chat_store.update_session_meta(
        "session-budget-search",
        title="Launch plan",
        db_path=str(db_path),
    )

    other_history = history_cls("session-other-search")
    other_history.add_user_message("Roadmap overview")
    other_history.add_ai_message("The roadmap is on track.")
    chat_store.update_session_meta(
        "session-other-search",
        title="Roadmap",
        db_path=str(db_path),
    )

    client = TestClient(api_server.app)
    response = client.get("/api/sessions", params={"query": "budget"})

    assert response.status_code == 200
    payload = response.json()
    assert [item["session_id"] for item in payload["sessions"]] == ["session-budget-search"]
    matched = payload["sessions"][0]
    assert matched["search_source"] == "message"
    assert "budget" in matched["search_preview"].lower()


def test_session_query_updates_after_message_truncation(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)

    history = history_cls("session-search-sync")
    history.add_user_message("Please summarize the budget status", answer_group_id="grp-search-sync")
    history.add_ai_message(
        "Budget approval is pending with finance.",
        panel_id="panel-main",
        answer_group_id="grp-search-sync",
    )
    chat_store.update_session_meta(
        "session-search-sync",
        title="Search sync",
        db_path=str(db_path),
    )

    assert [
        item["session_id"]
        for item in chat_store.get_all_sessions(query="budget", db_path=str(db_path))
    ] == ["session-search-sync"]

    result = chat_store.truncate_session_from_answer_group(
        "session-search-sync",
        answer_group_id="grp-search-sync",
        content="Please summarize the timeline status",
        db_path=str(db_path),
    )

    assert result is not None
    assert chat_store.get_all_sessions(query="budget", db_path=str(db_path)) == []


def test_session_pin_can_be_toggled_and_prioritized(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)

    older_history = history_cls("session-pin-older")
    older_history.add_user_message("Older thread")
    chat_store.update_session_meta(
        "session-pin-older",
        title="Older",
        db_path=str(db_path),
    )

    newer_history = history_cls("session-pin-newer")
    newer_history.add_user_message("Newer thread")
    chat_store.update_session_meta(
        "session-pin-newer",
        title="Newer",
        db_path=str(db_path),
    )

    client = TestClient(api_server.app)
    baseline = client.get("/api/sessions")
    assert baseline.status_code == 200
    baseline_ids = [item["session_id"] for item in baseline.json()["sessions"]]
    assert baseline_ids[0] == "session-pin-newer"

    pin = client.patch(
        "/api/sessions/session-pin-older",
        json={"is_pinned": True},
    )
    assert pin.status_code == 200
    assert pin.json()["session"]["is_pinned"] is True

    pinned_list = client.get("/api/sessions")
    assert pinned_list.status_code == 200
    sessions = pinned_list.json()["sessions"]
    assert sessions[0]["session_id"] == "session-pin-older"
    assert sessions[0]["is_pinned"] is True

    unpin = client.patch(
        "/api/sessions/session-pin-older",
        json={"is_pinned": False},
    )
    assert unpin.status_code == 200
    assert unpin.json()["session"]["is_pinned"] is False


def test_session_reorder_endpoint_updates_session_order(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)

    first_history = history_cls("session-order-first")
    first_history.add_user_message("First thread")
    chat_store.update_session_meta(
        "session-order-first",
        title="First",
        db_path=str(db_path),
    )

    second_history = history_cls("session-order-second")
    second_history.add_user_message("Second thread")
    chat_store.update_session_meta(
        "session-order-second",
        title="Second",
        db_path=str(db_path),
    )

    third_history = history_cls("session-order-third")
    third_history.add_user_message("Third thread")
    chat_store.update_session_meta(
        "session-order-third",
        title="Third",
        db_path=str(db_path),
    )

    client = TestClient(api_server.app)
    reorder = client.post(
        "/api/sessions/reorder",
        json={
            "session_ids": [
                "session-order-second",
                "session-order-first",
                "session-order-third",
            ]
        },
    )
    assert reorder.status_code == 200
    payload = reorder.json()
    assert payload["ok"] is True
    ordered_ids = [item["session_id"] for item in payload["sessions"][:3]]
    assert ordered_ids == [
        "session-order-second",
        "session-order-first",
        "session-order-third",
    ]


def test_message_feedback_persists_and_is_restored(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)

    history = history_cls("session-feedback")
    history.add_user_message("Summarize the update", answer_group_id="grp-feedback")
    history.add_ai_message(
        "The quarterly update is ready.",
        panel_id="panel-main",
        answer_group_id="grp-feedback",
        model_id="qwen-main",
    )
    chat_store.replace_session_panels(
        "session-feedback",
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
    initial = client.get("/api/sessions/session-feedback/messages")
    assert initial.status_code == 200
    assistant = initial.json()["panel_messages"]["panel-main"][1]

    assert isinstance(assistant["id"], int)
    assert assistant["feedback_value"] == 0
    assert assistant["timestamp"] > 0

    positive = client.post(
        "/api/sessions/session-feedback/messages/feedback",
        json={"message_id": assistant["id"], "value": 1},
    )
    assert positive.status_code == 200
    assert positive.json()["feedback"]["feedback_value"] == 1

    reloaded = client.get("/api/sessions/session-feedback/messages")
    assert reloaded.status_code == 200
    assert reloaded.json()["panel_messages"]["panel-main"][1]["feedback_value"] == 1

    negative = client.post(
        "/api/sessions/session-feedback/messages/feedback",
        json={
            "panel_id": "panel-main",
            "answer_group_id": "grp-feedback",
            "value": -1,
        },
    )
    assert negative.status_code == 200
    assert negative.json()["feedback"]["feedback_value"] == -1

    invalid = client.post(
        "/api/sessions/session-feedback/messages/feedback",
        json={"message_id": assistant["id"], "value": 2},
    )
    assert invalid.status_code == 400
    assert invalid.json()["detail"] == "消息反馈值只能是 -1、0 或 1"


def test_truncate_answer_group_rewrites_user_turn_and_drops_following_history(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)

    history = history_cls("session-edit-rerun")
    history.add_user_message("Original question", answer_group_id="grp-edit")
    history.add_ai_message(
        "Original answer",
        panel_id="panel-main",
        answer_group_id="grp-edit",
        model_id="qwen-main",
    )
    history.add_user_message("Later question", answer_group_id="grp-later")
    history.add_ai_message(
        "Later answer",
        panel_id="panel-main",
        answer_group_id="grp-later",
        model_id="qwen-main",
    )

    client = TestClient(api_server.app)
    truncate = client.post(
        "/api/sessions/session-edit-rerun/messages/truncate",
        json={
            "answer_group_id": "grp-edit",
            "content": "Edited question",
            "images": [],
            "files": [],
        },
    )
    assert truncate.status_code == 200
    result = truncate.json()["result"]
    assert result["answer_group_id"] == "grp-edit"
    assert result["deleted_count"] >= 3

    reloaded = client.get("/api/sessions/session-edit-rerun/messages")
    assert reloaded.status_code == 200
    messages = reloaded.json()["messages"]
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Edited question"
    assert messages[0]["answer_group_id"] == "grp-edit"


def test_retrieval_feedback_can_be_saved_and_listed(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)

    history = history_cls("session-retrieval-feedback")
    history.add_user_message("Need references", answer_group_id="grp-ref")
    history.add_ai_message(
        "Reference answer",
        panel_id="panel-main",
        answer_group_id="grp-ref",
        model_id="qwen-main",
    )

    client = TestClient(api_server.app)
    source_payload = {
        "type": "doc",
        "title": "Quarterly report",
        "url": "",
        "snippet": "Revenue grew 15% year over year.",
        "index": 1,
    }

    upvote = client.post(
        "/api/sessions/session-retrieval-feedback/retrieval-feedback",
        json={
            "panel_id": "panel-main",
            "answer_group_id": "grp-ref",
            "source": source_payload,
            "value": 1,
        },
    )
    assert upvote.status_code == 200
    assert upvote.json()["feedback"]["feedback_value"] == 1

    listed = client.get(
        "/api/sessions/session-retrieval-feedback/retrieval-feedback",
        params={
            "panel_id": "panel-main",
            "answer_group_id": "grp-ref",
        },
    )
    assert listed.status_code == 200
    feedback_items = listed.json()["feedback"]
    assert len(feedback_items) == 1
    assert feedback_items[0]["feedback_value"] == 1

    downvote = client.post(
        "/api/sessions/session-retrieval-feedback/retrieval-feedback",
        json={
            "panel_id": "panel-main",
            "answer_group_id": "grp-ref",
            "source": source_payload,
            "value": -1,
        },
    )
    assert downvote.status_code == 200
    assert downvote.json()["feedback"]["feedback_value"] == -1

    invalid = client.post(
        "/api/sessions/session-retrieval-feedback/retrieval-feedback",
        json={
            "panel_id": "panel-main",
            "answer_group_id": "grp-ref",
            "source": source_payload,
            "value": 2,
        },
    )
    assert invalid.status_code == 400
    assert invalid.json()["detail"] == "消息反馈值只能是 -1、0 或 1"
