from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.helpers.share_link_route_helpers import (
    SHARE_LINK_INVALID_OR_EXPIRED_DETAIL,
    SHARE_LINK_NOT_FOUND_DETAIL,
    SHARE_LINK_RESOURCE_MISMATCH_DETAIL,
    list_share_links_payload,
    open_shared_resource_response,
    revoke_share_link_result,
)


def test_list_share_links_payload_summarizes_records_and_audits():
    request = SimpleNamespace(name="request")
    records = [
        SimpleNamespace(resource_type="session", resource_id="session-1", is_active=True),
        SimpleNamespace(resource_type="deck", resource_id="deck-1", is_active=False),
    ]
    list_calls = []
    audits = []

    class ShareStore:
        def list_links(self, **kwargs):
            list_calls.append(kwargs)
            return records

    payload = list_share_links_payload(
        request=request,
        resource_type="session",
        active_only=True,
        limit=20,
        offset=5,
        share_link_store=ShareStore(),
        share_link_audit_payload=lambda record: {
            "resource_type": record.resource_type,
            "resource_id": record.resource_id,
            "is_active": record.is_active,
        },
        audit_security_event=lambda *args, **kwargs: audits.append((args, kwargs)),
    )

    assert payload == {
        "share_links": [
            {
                "resource_type": "session",
                "resource_id": "session-1",
                "is_active": True,
            },
            {
                "resource_type": "deck",
                "resource_id": "deck-1",
                "is_active": False,
            },
        ],
        "total": 2,
        "active_count": 1,
    }
    assert list_calls == [
        {
            "resource_type": "session",
            "active_only": True,
            "limit": 20,
            "offset": 5,
        }
    ]
    assert audits == [
        (
            ("list_share_links", request),
            {"details": "resource_type=session active_only=True total=2"},
        )
    ]


def test_list_share_links_payload_uses_all_label_for_empty_resource_type():
    audits = []

    class ShareStore:
        def list_links(self, **kwargs):
            return []

    payload = list_share_links_payload(
        request="request",
        resource_type="",
        active_only=False,
        limit=100,
        offset=0,
        share_link_store=ShareStore(),
        share_link_audit_payload=lambda record: {},
        audit_security_event=lambda *args, **kwargs: audits.append((args, kwargs)),
    )

    assert payload == {"share_links": [], "total": 0, "active_count": 0}
    assert audits == [
        (
            ("list_share_links", "request"),
            {"details": "resource_type=<all> active_only=False total=0"},
        )
    ]


def test_revoke_share_link_result_revokes_and_audits_fingerprint():
    revokes = []
    audits = []
    request = SimpleNamespace(name="request")

    class ShareStore:
        def revoke(self, share_token):
            revokes.append(share_token)
            return True

    result = revoke_share_link_result(
        share_token="raw-token",
        request=request,
        share_link_store=ShareStore(),
        token_fingerprint=lambda token: f"fp:{token}",
        audit_security_event=lambda *args, **kwargs: audits.append((args, kwargs)),
        revoke_share_link_response_model=SimpleNamespace,
    )

    assert result.ok is True
    assert revokes == ["raw-token"]
    assert audits == [
        (
            ("revoke_share_link", request),
            {"details": "share_token_fp=fp:raw-token"},
        )
    ]


def test_revoke_share_link_result_maps_missing_token_to_404():
    audits = []

    class ShareStore:
        def revoke(self, share_token):
            return False

    with pytest.raises(HTTPException) as exc:
        revoke_share_link_result(
            share_token="missing-token",
            request="request",
            share_link_store=ShareStore(),
            token_fingerprint=lambda token: f"fp:{token}",
            audit_security_event=lambda *args, **kwargs: audits.append((args, kwargs)),
            revoke_share_link_response_model=SimpleNamespace,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == SHARE_LINK_NOT_FOUND_DETAIL
    assert audits == []


def test_open_shared_resource_response_records_access_and_returns_html():
    request = SimpleNamespace(name="request")
    calls = []
    audits = []

    class ShareStore:
        def get_active(self, share_token):
            calls.append(("get-active", share_token))
            return SimpleNamespace(resource_type="session", resource_id="session-1")

        def record_access(self, share_token, **kwargs):
            calls.append(("record-access", share_token, kwargs))

    def payload_builder(share_token, payload_request, **kwargs):
        calls.append(("payload", share_token, payload_request, kwargs["secret"]))
        return {
            "content": "<html>shared</html>",
            "media_type": "text/html; charset=utf-8",
        }

    response = open_shared_resource_response(
        share_token="share-token",
        request=request,
        share_secret="secret",
        share_link_store=ShareStore(),
        decode_share_token=lambda token, secret: ("session", "session-1"),
        build_share_url=lambda req, token: f"https://app.example/shared/{token}",
        build_session_messages_payload=lambda session_id: {"session_id": session_id},
        render_shared_session_html=lambda payload, share_url: "unused",
        get_deck=lambda deck_id: None,
        render_shared_deck_html=lambda deck, share_url: "unused",
        request_client_ip=lambda req: "127.0.0.1",
        request_user_agent=lambda req: "pytest",
        audit_security_event=lambda *args, **kwargs: audits.append((args, kwargs)),
        token_fingerprint=lambda token: f"fp:{token}",
        open_shared_resource_payload=payload_builder,
    )

    assert response.body == b"<html>shared</html>"
    assert response.media_type == "text/html; charset=utf-8"
    assert calls == [
        ("get-active", "share-token"),
        ("payload", "share-token", request, "secret"),
        (
            "record-access",
            "share-token",
            {"accessed_ip": "127.0.0.1", "accessed_user_agent": "pytest"},
        ),
    ]
    assert audits == [
        (
            ("open_shared_resource", request),
            {"details": "resource_type=session share_token_fp=fp:share-token"},
        )
    ]


def test_open_shared_resource_response_maps_invalid_and_mismatched_links_to_404():
    class MissingShareStore:
        def get_active(self, share_token):
            return None

    with pytest.raises(HTTPException) as missing_exc:
        open_shared_resource_response(
            share_token="missing",
            request="request",
            share_secret="secret",
            share_link_store=MissingShareStore(),
            decode_share_token=lambda token, secret: ("session", "session-1"),
            build_share_url=lambda req, token: "",
            build_session_messages_payload=lambda session_id: {},
            render_shared_session_html=lambda payload, share_url: "",
            get_deck=lambda deck_id: None,
            render_shared_deck_html=lambda deck, share_url: "",
            request_client_ip=lambda req: "",
            request_user_agent=lambda req: "",
            audit_security_event=lambda *args, **kwargs: None,
            token_fingerprint=lambda token: "",
            open_shared_resource_payload=lambda *args, **kwargs: {},
        )

    assert missing_exc.value.status_code == 404
    assert missing_exc.value.detail == SHARE_LINK_INVALID_OR_EXPIRED_DETAIL

    class MismatchedShareStore:
        def get_active(self, share_token):
            return SimpleNamespace(resource_type="deck", resource_id="deck-1")

    with pytest.raises(HTTPException) as mismatch_exc:
        open_shared_resource_response(
            share_token="mismatch",
            request="request",
            share_secret="secret",
            share_link_store=MismatchedShareStore(),
            decode_share_token=lambda token, secret: ("session", "session-1"),
            build_share_url=lambda req, token: "",
            build_session_messages_payload=lambda session_id: {},
            render_shared_session_html=lambda payload, share_url: "",
            get_deck=lambda deck_id: None,
            render_shared_deck_html=lambda deck, share_url: "",
            request_client_ip=lambda req: "",
            request_user_agent=lambda req: "",
            audit_security_event=lambda *args, **kwargs: None,
            token_fingerprint=lambda token: "",
            open_shared_resource_payload=lambda *args, **kwargs: {},
        )

    assert mismatch_exc.value.status_code == 404
    assert mismatch_exc.value.detail == SHARE_LINK_RESOURCE_MISMATCH_DETAIL


def test_open_shared_resource_response_maps_payload_key_error_to_404():
    class ShareStore:
        def get_active(self, share_token):
            return SimpleNamespace(resource_type="session", resource_id="session-1")

    with pytest.raises(HTTPException) as exc:
        open_shared_resource_response(
            share_token="share-token",
            request="request",
            share_secret="secret",
            share_link_store=ShareStore(),
            decode_share_token=lambda token, secret: ("session", "session-1"),
            build_share_url=lambda req, token: "",
            build_session_messages_payload=lambda session_id: {},
            render_shared_session_html=lambda payload, share_url: "",
            get_deck=lambda deck_id: None,
            render_shared_deck_html=lambda deck, share_url: "",
            request_client_ip=lambda req: "",
            request_user_agent=lambda req: "",
            audit_security_event=lambda *args, **kwargs: None,
            token_fingerprint=lambda token: "",
            open_shared_resource_payload=lambda *args, **kwargs: (
                (_ for _ in ()).throw(KeyError("Session was not found."))
            ),
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Session was not found."
