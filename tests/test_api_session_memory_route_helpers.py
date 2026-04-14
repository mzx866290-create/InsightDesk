from types import SimpleNamespace

import pytest

from api_session_memory_route_helpers import (
    delete_session_memory_payload,
    pin_session_memory_payload,
    session_memory_payload,
    session_memory_updates,
    summarize_session_memory_payload,
    update_session_memory_payload,
)


def test_session_memory_payload_requires_existing_session():
    with pytest.raises(KeyError):
        session_memory_payload(
            session_id="session-1",
            session=None,
            memories=[],
        )

    payload = session_memory_payload(
        session_id="session-1",
        session={"session_id": "session-1"},
        memories=[{"id": "mem-1"}],
    )

    assert payload == {
        "session_id": "session-1",
        "memories": [{"id": "mem-1"}],
    }


def test_pin_session_memory_payload_wraps_result():
    with pytest.raises(KeyError):
        pin_session_memory_payload(None)

    payload = pin_session_memory_payload(
        {"created": True, "memory": {"id": "mem-1", "kind": "decision"}}
    )

    assert payload == {
        "ok": True,
        "created": True,
        "memory": {"id": "mem-1", "kind": "decision"},
    }


def test_session_memory_updates_validates_requested_fields():
    with pytest.raises(ValueError, match="At least one memory field is required"):
        session_memory_updates(
            SimpleNamespace(content=None, kind=None),
            field_set=set(),
        )

    with pytest.raises(ValueError, match="content must be a non-empty string"):
        session_memory_updates(
            SimpleNamespace(content=None, kind=None),
            field_set={"content"},
        )

    with pytest.raises(ValueError, match="kind must be a valid memory kind"):
        session_memory_updates(
            SimpleNamespace(content=None, kind=None),
            field_set={"kind"},
        )

    updates = session_memory_updates(
        SimpleNamespace(content="updated", kind="decision"),
        field_set={"content", "kind"},
    )

    assert updates == {"content": "updated", "kind": "decision"}


def test_update_session_memory_payload_requires_memory():
    with pytest.raises(KeyError):
        update_session_memory_payload(None)

    payload = update_session_memory_payload({"id": "mem-1", "content": "updated"})
    assert payload == {
        "ok": True,
        "memory": {"id": "mem-1", "content": "updated"},
    }


def test_summarize_session_memory_payload_requires_session_and_result():
    with pytest.raises(KeyError):
        summarize_session_memory_payload(session=None, result={"created": True})
    with pytest.raises(KeyError):
        summarize_session_memory_payload(session={"session_id": "s-1"}, result=None)

    payload = summarize_session_memory_payload(
        session={"session_id": "s-1"},
        result={"created": True, "memory": {"id": "mem-summary"}},
    )

    assert payload == {
        "ok": True,
        "created": True,
        "memory": {"id": "mem-summary"},
    }


def test_delete_session_memory_payload_requires_success():
    with pytest.raises(KeyError):
        delete_session_memory_payload(False)

    assert delete_session_memory_payload(True) == {"ok": True}
