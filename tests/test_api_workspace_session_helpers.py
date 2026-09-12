from types import SimpleNamespace

import pytest

from backend.helpers.workspace_session_helpers import (
    create_session_record,
    fallback_session_payload,
    normalize_workspace_id,
    reorder_sessions_payload,
    require_workspace_session,
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
            get_session=lambda session_id: None,
            get_workspace=lambda workspace_id: None,
            update_session_meta=lambda *args, **kwargs: None,
        )


def test_create_session_record_sets_title_and_workspace_and_returns_session():
    updated = []

    request = SimpleNamespace(title="Launch", workspace_id="ws-1")

    session = create_session_record(
        request,
        history_factory=lambda **kwargs: SimpleNamespace(db_path="db.sqlite"),
        get_session=lambda session_id: {
            "session_id": session_id,
            "title": "Launch",
            "workspace_id": "ws-1",
        },
        get_workspace=lambda workspace_id: {"workspace_id": workspace_id},
        update_session_meta=lambda session_id, **kwargs: updated.append((session_id, kwargs)),
        session_id_factory=lambda: "session-1",
    )

    assert session == {
        "session_id": "session-1",
        "title": "Launch",
        "workspace_id": "ws-1",
    }
    assert updated == [
        ("session-1", {"title": "Launch", "workspace_id": "ws-1"})
    ]


def test_create_session_record_returns_fallback_payload_when_session_lookup_is_empty():
    request = SimpleNamespace(title="  ", workspace_id=None)

    session = create_session_record(
        request,
        history_factory=lambda **kwargs: SimpleNamespace(db_path="db.sqlite"),
        get_session=lambda session_id: None,
        get_workspace=lambda workspace_id: {"workspace_id": workspace_id},
        update_session_meta=lambda *args, **kwargs: None,
        session_id_factory=lambda: "session-2",
    )

    assert session == {
        "session_id": "session-2",
        "title": "新对话",
        "workspace_id": None,
    }


def test_create_session_record_uses_resolved_active_workspace():
    updated = []

    session = create_session_record(
        SimpleNamespace(title="", workspace_id=None),
        history_factory=lambda **kwargs: SimpleNamespace(),
        get_session=lambda session_id: {
            "session_id": session_id,
            "workspace_id": "ws-active",
        },
        get_workspace=lambda workspace_id: {"workspace_id": workspace_id},
        update_session_meta=lambda session_id, **kwargs: updated.append(
            (session_id, kwargs)
        ),
        resolved_workspace_id="ws-active",
        session_id_factory=lambda: "session-active",
    )

    assert session["workspace_id"] == "ws-active"
    assert updated == [
        ("session-active", {"workspace_id": "ws-active"})
    ]


def test_require_workspace_session_enforces_workspace_membership(monkeypatch):
    from backend import chat_store
    from fastapi import HTTPException

    monkeypatch.setattr(
        chat_store,
        "get_session",
        lambda session_id: {"session_id": session_id, "workspace_id": "ws-1"},
    )
    monkeypatch.setattr(
        chat_store,
        "get_workspace",
        lambda workspace_id: {"workspace_id": workspace_id}
        if workspace_id == "ws-1"
        else None,
    )

    assert require_workspace_session("session-1", "ws-1") == {
        "session_id": "session-1",
        "workspace_id": "ws-1",
    }

    with pytest.raises(HTTPException) as exc_info:
        require_workspace_session("session-1", "missing")
    assert exc_info.value.status_code == 400

    monkeypatch.setattr(
        chat_store,
        "get_workspace",
        lambda workspace_id: {"workspace_id": workspace_id},
    )
    with pytest.raises(HTTPException) as exc_info:
        require_workspace_session("session-1", "ws-2")
    assert exc_info.value.status_code == 404
