from types import SimpleNamespace

import pytest

from backend.helpers.shared_resource_helpers import open_shared_resource_payload


def test_open_shared_resource_payload_renders_session_html():
    payload = open_shared_resource_payload(
        "token-1",
        SimpleNamespace(base_url="http://testserver/"),
        secret="secret",
        decode_share_token=lambda token, secret: ("session", "session-1"),
        build_share_url=lambda request, token: f"http://testserver/shared/{token}",
        build_session_messages_payload=lambda session_id: {"session_id": session_id},
        render_shared_session_html=lambda payload, share_url: (
            f"session:{payload['session_id']}@{share_url}"
        ),
        get_deck=lambda deck_id: None,
        render_shared_deck_html=lambda deck, share_url: "unused",
    )

    assert payload == {
        "content": "session:session-1@http://testserver/shared/token-1",
        "media_type": "text/html; charset=utf-8",
    }


def test_open_shared_resource_payload_renders_deck_html():
    payload = open_shared_resource_payload(
        "token-2",
        SimpleNamespace(base_url="http://testserver/"),
        secret="secret",
        decode_share_token=lambda token, secret: ("deck", "deck-1"),
        build_share_url=lambda request, token: f"http://testserver/shared/{token}",
        build_session_messages_payload=lambda session_id: {},
        render_shared_session_html=lambda payload, share_url: "unused",
        get_deck=lambda deck_id: {"deck_id": deck_id},
        render_shared_deck_html=lambda deck, share_url: (
            f"deck:{deck['deck_id']}@{share_url}"
        ),
    )

    assert payload == {
        "content": "deck:deck-1@http://testserver/shared/token-2",
        "media_type": "text/html; charset=utf-8",
    }


def test_open_shared_resource_payload_raises_for_unsupported_resource():
    with pytest.raises(ValueError, match="不支持的共享资源类型"):
        open_shared_resource_payload(
            "token-3",
            SimpleNamespace(base_url="http://testserver/"),
            secret="secret",
            decode_share_token=lambda token, secret: ("other", "resource-1"),
            build_share_url=lambda request, token: f"http://testserver/shared/{token}",
            build_session_messages_payload=lambda session_id: {},
            render_shared_session_html=lambda payload, share_url: "unused",
            get_deck=lambda deck_id: {},
            render_shared_deck_html=lambda deck, share_url: "unused",
        )


def test_open_shared_resource_payload_normalizes_missing_session_and_deck_errors():
    with pytest.raises(KeyError, match="未找到会话"):
        open_shared_resource_payload(
            "token-4",
            SimpleNamespace(base_url="http://testserver/"),
            secret="secret",
            decode_share_token=lambda token, secret: ("session", "session-1"),
            build_share_url=lambda request, token: f"http://testserver/shared/{token}",
            build_session_messages_payload=lambda session_id: (_ for _ in ()).throw(
                KeyError(session_id)
            ),
            render_shared_session_html=lambda payload, share_url: "unused",
            get_deck=lambda deck_id: {},
            render_shared_deck_html=lambda deck, share_url: "unused",
        )

    with pytest.raises(KeyError, match="未找到演示稿"):
        open_shared_resource_payload(
            "token-5",
            SimpleNamespace(base_url="http://testserver/"),
            secret="secret",
            decode_share_token=lambda token, secret: ("deck", "deck-1"),
            build_share_url=lambda request, token: f"http://testserver/shared/{token}",
            build_session_messages_payload=lambda session_id: {},
            render_shared_session_html=lambda payload, share_url: "unused",
            get_deck=lambda deck_id: (_ for _ in ()).throw(KeyError(deck_id)),
            render_shared_deck_html=lambda deck, share_url: "unused",
        )
