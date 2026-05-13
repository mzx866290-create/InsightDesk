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
