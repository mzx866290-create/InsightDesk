from types import SimpleNamespace

import pytest

from backend.api_workspace_session_helpers import (
    create_session_record,
    fallback_session_payload,
    normalize_workspace_id,
    reorder_sessions_payload,
    session_update_requested,
    workspaces_payload,
)


def test_workspaces_payload_returns_active_workspace_id():
    payload = workspaces_payload(
        [
            {"workspace_id": "ws-1", "is_active": False},
            {"workspace_id": "ws-2", "is_active": True},
        ]
    )

    assert payload == {
        "workspaces": [
            {"workspace_id": "ws-1", "is_active": False},
            {"workspace_id": "ws-2", "is_active": True},
        ],
        "active_workspace_id": "ws-2",
    }


def test_normalize_workspace_id_and_fallback_session_payload():
    assert normalize_workspace_id(None) is None
    assert normalize_workspace_id("  ws-1  ") == "ws-1"
    assert normalize_workspace_id("   ") is None
    assert fallback_session_payload("session-1", title="", workspace_id="ws-1") == {
        "session_id": "session-1",
        "title": "新对话",
        "workspace_id": "ws-1",
    }


def test_session_update_requested_detects_any_mutation_field():
    assert not session_update_requested(
        SimpleNamespace(
            title=None,
            is_archived=None,
            is_favorite=None,
            is_pinned=None,
            tags=None,
            workspace_id=None,
        )
    )
    assert session_update_requested(
        SimpleNamespace(
            title="hello",
            is_archived=None,
            is_favorite=None,
            is_pinned=None,
            tags=None,
            workspace_id=None,
        )
    )


def test_reorder_sessions_payload_wraps_result_and_sessions():
    assert reorder_sessions_payload({"moved": 2}, [{"session_id": "s-1"}]) == {
        "ok": True,
        "result": {"moved": 2},
        "sessions": [{"session_id": "s-1"}],
    }


def test_create_session_record_rejects_missing_workspace():
    request = SimpleNamespace(title="Launch", workspace_id="missing")

    with pytest.raises(ValueError, match="工作区不存在"):
        create_session_record(
            request,
            history_factory=lambda **kwargs: SimpleNamespace(db_path="db.sqlite"),
            connect_sqlite=lambda db_path: _FakeConnectionContext(),
            get_session=lambda session_id, db_path=None: None,
            get_workspace=lambda workspace_id: None,
            update_session_meta=lambda *args, **kwargs: None,
        )


def test_create_session_record_sets_title_and_workspace_and_returns_session():
    executed = []
    updated = []

    request = SimpleNamespace(title="Launch", workspace_id="ws-1")

    session = create_session_record(
        request,
        history_factory=lambda **kwargs: SimpleNamespace(db_path="db.sqlite"),
        connect_sqlite=lambda db_path: _FakeConnectionContext(executed),
        get_session=lambda session_id, db_path=None: {
            "session_id": session_id,
            "title": "Launch",
            "workspace_id": "ws-1",
        },
        get_workspace=lambda workspace_id: {"workspace_id": workspace_id},
        update_session_meta=lambda session_id, **kwargs: updated.append((session_id, kwargs)),
        session_id_factory=lambda: "session-1",
        current_time=lambda: 123.0,
    )

    assert session == {
        "session_id": "session-1",
        "title": "Launch",
        "workspace_id": "ws-1",
    }
    assert executed == [
        (
            "UPDATE sessions SET title = ?, updated_at = ? WHERE session_id = ?",
            ("Launch", 123.0, "session-1"),
        ),
        ("COMMIT", None),
    ]
    assert updated == [("session-1", {"workspace_id": "ws-1", "db_path": "db.sqlite"})]


def test_create_session_record_returns_fallback_payload_when_session_lookup_is_empty():
    request = SimpleNamespace(title="  ", workspace_id=None)

    session = create_session_record(
        request,
        history_factory=lambda **kwargs: SimpleNamespace(db_path="db.sqlite"),
        connect_sqlite=lambda db_path: _FakeConnectionContext(),
        get_session=lambda session_id, db_path=None: None,
        get_workspace=lambda workspace_id: {"workspace_id": workspace_id},
        update_session_meta=lambda *args, **kwargs: None,
        session_id_factory=lambda: "session-2",
    )

    assert session == {
        "session_id": "session-2",
        "title": "新对话",
        "workspace_id": None,
    }


class _FakeConnectionContext:
    def __init__(self, executed=None):
        self.executed = executed if executed is not None else []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params):
        self.executed.append((sql, params))

    def commit(self):
        self.executed.append(("COMMIT", None))
