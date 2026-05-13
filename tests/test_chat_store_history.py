from pathlib import Path

import backend.chat_store as chat_store


def _history_cls_for_db(db_path: Path):
    class TestSQLiteChatMessageHistory(chat_store.SQLiteChatMessageHistory):
        def __init__(self, session_id: str, db_path_arg: str = "./chat_history.db"):
            super().__init__(session_id=session_id, db_path=str(db_path))

    return TestSQLiteChatMessageHistory


def test_get_session_uses_direct_lookup_and_preserves_summary_fields(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)

    session_id = "session-direct-lookup"
    chat_store.replace_session_panels(
        session_id,
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
                "panel_id": "panel-side",
                "provider": "ollama",
                "connection_type": "ollama",
                "model": "qwen-side",
                "base_url": "http://localhost:11434",
                "temperature": 0.3,
                "agent_mode": "auto",
            },
        ],
        db_path=str(db_path),
    )

    history = history_cls(session_id)
    history.add_user_message("Need launch planning help", answer_group_id="grp-1")
    history.add_ai_message(
        "Primary launch response",
        panel_id="panel-main",
        answer_group_id="grp-1",
        token_usage={
            "prompt_tokens": 12,
            "completion_tokens": 8,
            "total_tokens": 20,
            "estimated": False,
        },
    )
    history.add_ai_message(
        "Secondary launch response",
        panel_id="panel-side",
        answer_group_id="grp-1",
    )
    chat_store.update_session_meta(
        session_id,
        is_favorite=True,
        tags=["launch", "priority"],
        db_path=str(db_path),
    )

    stored = chat_store.get_session(session_id, db_path=str(db_path))

    assert stored is not None
    assert stored["session_id"] == session_id
    assert stored["is_favorite"] is True
    assert stored["tags"] == ["launch", "priority"]
    assert stored["workspace_id"] == chat_store.DEFAULT_WORKSPACE_ID
    assert stored["message_count"] == 2
    records = history.get_all_message_records(panel_id="panel-main")
    assert records[-1]["token_usage"]["total_tokens"] == 20


def test_get_workspace_uses_direct_lookup_and_counts_sessions(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)

    workspace = chat_store.create_workspace(
        "Operations",
        description="Runbooks and delivery",
        color="green",
        activate=True,
        db_path=str(db_path),
    )

    history_cls("session-in-operations")

    stored = chat_store.get_workspace(workspace["workspace_id"], db_path=str(db_path))

    assert stored is not None
    assert stored["workspace_id"] == workspace["workspace_id"]
    assert stored["name"] == "Operations"
    assert stored["description"] == "Runbooks and delivery"
    assert stored["color"] == "green"
    assert stored["is_active"] is True
    assert stored["session_count"] == 1


def test_history_pruning_removes_oldest_whole_answer_group(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MAX_HISTORY_MESSAGES", "4")
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)

    history = history_cls("session-prune-grouped")
    history.add_user_message("First question", answer_group_id="grp-1")
    history.add_ai_message("First answer main", panel_id="panel-main", answer_group_id="grp-1")
    history.add_ai_message("First answer side", panel_id="panel-side", answer_group_id="grp-1")
    history.add_user_message("Second question", answer_group_id="grp-2")
    history.add_ai_message("Second answer", panel_id="panel-main", answer_group_id="grp-2")

    records = history.get_all_message_records()

    assert [record["content"] for record in records] == ["Second question", "Second answer"]
    assert [record["type"] for record in records] == ["human", "ai"]
    assert {record["answer_group_id"] for record in records} == {"grp-2"}


def test_history_pruning_keeps_legacy_human_and_ai_turns_intact(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MAX_HISTORY_MESSAGES", "3")
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)

    history = history_cls("session-prune-legacy")
    history.add_user_message("Old question")
    history.add_ai_message("Old answer")
    history.add_user_message("New question")
    history.add_ai_message("New answer")

    records = history.get_all_message_records()

    assert [record["content"] for record in records] == ["New question", "New answer"]
    assert [record["type"] for record in records] == ["human", "ai"]
