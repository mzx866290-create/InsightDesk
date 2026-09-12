from backend.agent import builder_history


def test_load_chat_history_omits_persisted_history_and_memory(monkeypatch):
    def fail_create_history(*args, **kwargs):
        raise AssertionError("history storage should not be touched when omit_history=True")

    monkeypatch.setattr(
        builder_history.runtime_support,
        "create_chat_message_history",
        fail_create_history,
    )

    assert builder_history._load_chat_history("session-1", omit_history=True) == []


def test_load_chat_history_never_passes_postgres_dsn_to_sqlite_memory(monkeypatch):
    class FakeHistory:
        db_path = "postgresql://app:secret@postgres/db"
        messages = []

    calls = []
    monkeypatch.setenv("DATABASE_PROVIDER", "postgres")
    monkeypatch.setattr(
        builder_history.runtime_support,
        "create_chat_message_history",
        lambda **kwargs: FakeHistory(),
    )
    monkeypatch.setattr(
        builder_history.runtime_support,
        "list_session_memory",
        lambda session_id, **kwargs: calls.append((session_id, kwargs)) or [],
    )
    monkeypatch.setattr(
        builder_history.runtime_support,
        "_build_session_memory_message",
        lambda memories: None,
    )

    assert builder_history._load_chat_history("session-pg") == []
    assert calls == [("session-pg", {"limit": 10, "db_path": None})]
