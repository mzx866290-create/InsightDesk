from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.helpers.scoped_message_route_helpers import (
    DEFAULT_SESSION_MESSAGES_NOT_FOUND_DETAIL,
    load_scoped_session_messages,
)


def test_load_scoped_session_messages_checks_access_and_loads_history():
    calls = []

    messages = load_scoped_session_messages(
        request="request",
        session_id="session-1",
        minimum_role="editor",
        answer_group_id="group-1",
        panel_id="panel-a",
        require_session_access=lambda req, session_id, role: calls.append(
            ("access", req, session_id, role)
        )
        or {"role": role},
        create_chat_message_history=lambda *, session_id: calls.append(
            ("history", session_id)
        )
        or "history",
        resolve_report_messages=lambda history, *, answer_group_id, panel_id: calls.append(
            ("resolve", history, answer_group_id, panel_id)
        )
        or ["message"],
        scope_not_found_detail="scope-missing",
    )

    assert messages == ["message"]
    assert calls == [
        ("access", "request", "session-1", "editor"),
        ("history", "session-1"),
        ("resolve", "history", "group-1", "panel-a"),
    ]


def test_load_scoped_session_messages_maps_scope_and_empty_errors():
    with pytest.raises(HTTPException) as scope_exc:
        load_scoped_session_messages(
            request=SimpleNamespace(),
            session_id="session-1",
            minimum_role="viewer",
            answer_group_id=None,
            panel_id=None,
            require_session_access=None,
            create_chat_message_history=lambda *, session_id: "history",
            resolve_report_messages=lambda *args, **kwargs: (_ for _ in ()).throw(
                KeyError("missing")
            ),
            scope_not_found_detail="scope-missing",
        )

    assert scope_exc.value.status_code == 404
    assert scope_exc.value.detail == "scope-missing"

    with pytest.raises(HTTPException) as empty_exc:
        load_scoped_session_messages(
            request=SimpleNamespace(),
            session_id="session-1",
            minimum_role="viewer",
            answer_group_id=None,
            panel_id=None,
            require_session_access=None,
            create_chat_message_history=lambda *, session_id: "history",
            resolve_report_messages=lambda *args, **kwargs: [],
            scope_not_found_detail="scope-missing",
        )

    assert empty_exc.value.status_code == 400
    assert empty_exc.value.detail == DEFAULT_SESSION_MESSAGES_NOT_FOUND_DETAIL
