import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.helpers.artifact_route_helpers import (
    ARTIFACT_GENERATION_MESSAGES_REQUIRED_DETAIL,
    DECK_ARTIFACT_PANEL_CONFIG_REQUIRED_DETAIL,
    DECK_ARTIFACT_MARKDOWN_UNSUPPORTED_DETAIL,
    DECK_ARTIFACT_MISSING_DECK_ID_DETAIL,
    UNSUPPORTED_ARTIFACT_TYPE_DETAIL,
    generate_artifact_result,
    update_artifact_result,
)


def _request(**overrides):
    values = {"title": None, "markdown": None}
    values.update(overrides)
    return SimpleNamespace(**values)


def _generate_request(**overrides):
    values = {
        "artifact_type": "report",
        "session_id": "session-1",
        "panel_config": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _payload(artifact):
    return {
        "artifact_id": artifact.artifact_id,
        "artifact_type": artifact.artifact_type,
        "title": artifact.title,
        "content": artifact.content,
    }


def test_update_artifact_result_updates_report_title_and_markdown():
    artifact = SimpleNamespace(
        artifact_id="artifact-report",
        artifact_type="report",
        title="Before",
        content={"markdown": "# Before"},
    )
    saved = []

    result = update_artifact_result(
        artifact_id=artifact.artifact_id,
        artifact=artifact,
        request=_request(title=" After ", markdown=" # After "),
        save_artifact=saved.append,
        get_artifact=lambda artifact_id: artifact,
        get_deck=lambda deck_id: None,
        save_deck=lambda deck: None,
        sync_deck_artifacts=lambda deck: None,
        artifact_payload=_payload,
    )

    assert result["title"] == "After"
    assert result["content"]["markdown"] == "# After"
    assert saved == [artifact]


def test_update_artifact_result_updates_deck_title_and_returns_synced_artifact():
    artifact = SimpleNamespace(
        artifact_id="artifact-deck",
        artifact_type="deck",
        title="Before",
        linked_resource_id="deck-1",
        content={"deck_id": "deck-from-content"},
    )
    synced_artifact = SimpleNamespace(
        artifact_id="artifact-deck",
        artifact_type="deck",
        title="After",
        content={"deck_id": "deck-1"},
    )
    cover = SimpleNamespace(type="cover", title="Before")
    deck = SimpleNamespace(
        deck_id="deck-1",
        meta=SimpleNamespace(title="Before"),
        slides=[cover],
    )
    calls = []

    result = update_artifact_result(
        artifact_id=artifact.artifact_id,
        artifact=artifact,
        request=_request(title=" After ", markdown=None),
        save_artifact=lambda artifact: calls.append(("save-artifact", artifact)),
        get_artifact=lambda artifact_id: synced_artifact,
        get_deck=lambda deck_id: deck,
        save_deck=lambda deck_arg: calls.append(("save-deck", deck_arg)),
        sync_deck_artifacts=lambda deck_arg: calls.append(("sync", deck_arg)),
        artifact_payload=_payload,
    )

    assert deck.meta.title == "After"
    assert cover.title == "After"
    assert result["title"] == "After"
    assert calls == [("save-deck", deck), ("sync", deck)]


def test_update_artifact_result_rejects_invalid_deck_artifact_patches():
    artifact = SimpleNamespace(
        artifact_id="artifact-deck",
        artifact_type="deck",
        title="Deck",
        linked_resource_id="deck-1",
        content={"deck_id": "deck-1"},
    )

    with pytest.raises(HTTPException) as markdown_exc:
        update_artifact_result(
            artifact_id=artifact.artifact_id,
            artifact=artifact,
            request=_request(markdown="# Deck"),
            save_artifact=lambda artifact: None,
            get_artifact=lambda artifact_id: artifact,
            get_deck=lambda deck_id: None,
            save_deck=lambda deck: None,
            sync_deck_artifacts=lambda deck: None,
            artifact_payload=_payload,
        )

    assert markdown_exc.value.status_code == 400
    assert markdown_exc.value.detail == DECK_ARTIFACT_MARKDOWN_UNSUPPORTED_DETAIL

    artifact.linked_resource_id = ""
    artifact.content = {}
    with pytest.raises(HTTPException) as deck_id_exc:
        update_artifact_result(
            artifact_id=artifact.artifact_id,
            artifact=artifact,
            request=_request(markdown=None),
            save_artifact=lambda artifact: None,
            get_artifact=lambda artifact_id: artifact,
            get_deck=lambda deck_id: None,
            save_deck=lambda deck: None,
            sync_deck_artifacts=lambda deck: None,
            artifact_payload=_payload,
        )

    assert deck_id_exc.value.status_code == 400
    assert deck_id_exc.value.detail == DECK_ARTIFACT_MISSING_DECK_ID_DETAIL


def test_update_artifact_result_maps_missing_deck_and_unsupported_artifact_type():
    deck_artifact = SimpleNamespace(
        artifact_id="artifact-deck",
        artifact_type="deck",
        title="Deck",
        linked_resource_id="deck-missing",
        content={},
    )

    with pytest.raises(HTTPException) as deck_exc:
        update_artifact_result(
            artifact_id=deck_artifact.artifact_id,
            artifact=deck_artifact,
            request=_request(markdown=None),
            save_artifact=lambda artifact: None,
            get_artifact=lambda artifact_id: deck_artifact,
            get_deck=lambda deck_id: (_ for _ in ()).throw(KeyError(deck_id)),
            save_deck=lambda deck: None,
            sync_deck_artifacts=lambda deck: None,
            artifact_payload=_payload,
        )

    assert deck_exc.value.status_code == 404
    assert deck_exc.value.detail == "Deck was not found."

    unknown_artifact = SimpleNamespace(
        artifact_id="artifact-unknown",
        artifact_type="unknown",
        title="Unknown",
        content={},
    )
    with pytest.raises(HTTPException) as unsupported_exc:
        update_artifact_result(
            artifact_id=unknown_artifact.artifact_id,
            artifact=unknown_artifact,
            request=_request(),
            save_artifact=lambda artifact: None,
            get_artifact=lambda artifact_id: unknown_artifact,
            get_deck=lambda deck_id: None,
            save_deck=lambda deck: None,
            sync_deck_artifacts=lambda deck: None,
            artifact_payload=_payload,
        )

    assert unsupported_exc.value.status_code == 400
    assert unsupported_exc.value.detail == UNSUPPORTED_ARTIFACT_TYPE_DETAIL


def test_generate_artifact_result_creates_report_and_grants_access():
    report_artifact = SimpleNamespace(
        artifact_id="artifact-report",
        artifact_type="report",
        title="Report",
        content={},
    )
    grants = []

    result = asyncio.run(
        generate_artifact_result(
            http_request="request",
            request=_generate_request(artifact_type="report"),
            messages=["message"],
            create_report_artifact_result=lambda **kwargs: SimpleNamespace(
                artifact=report_artifact,
                artifact_id=report_artifact.artifact_id,
            ),
            create_deck_artifact_result=lambda **kwargs: None,
            ensure_deckable_chat=lambda messages: [("Q", "A")],
            build_chat_report_title=lambda messages: "Report",
            build_report_markdown=lambda messages, title: f"# {title}",
            build_report_artifact=lambda **kwargs: report_artifact,
            save_artifact=lambda artifact: None,
            grant_derived_resource_access=lambda *args, **kwargs: grants.append((args, kwargs)),
            build_deck=None,
            build_create_deck_kwargs=lambda *args, **kwargs: {},
            resolve_active_prompt_runtime=lambda enabled: (None, None, None),
            normalize_deck_theme=lambda value: value,
            save_deck=lambda deck: None,
            create_deck_artifact=lambda deck: None,
            grant_created_deck_artifact_access=lambda **kwargs: None,
            artifact_payload=_payload,
            access_store="access-store",
            require_remote_editor=lambda request: {"role": "editor"},
            audit_security_event=lambda *args, **kwargs: None,
            inherit_resource_grants=lambda **kwargs: None,
            grant_resource_owner=lambda *args, **kwargs: None,
            now=lambda: 123.0,
        )
    )

    assert result["artifact_id"] == "artifact-report"
    assert len(grants) == 1
    assert grants[0][0] == ("request",)
    assert grants[0][1]["source_resource_type"] == "session"
    assert grants[0][1]["source_resource_id"] == "session-1"
    assert grants[0][1]["target_resource_type"] == "artifact"
    assert grants[0][1]["target_resource_id"] == "artifact-report"
    assert grants[0][1]["access_store"] == "access-store"


def test_generate_artifact_result_creates_deck_and_grants_access():
    deck_artifact = SimpleNamespace(
        artifact_id="artifact-deck",
        artifact_type="deck",
        title="Deck",
        content={},
    )
    deck_created = SimpleNamespace(
        artifact=deck_artifact,
        artifact_id="artifact-deck",
        deck_id="deck-1",
    )
    grants = []

    async def create_deck_artifact_result(**kwargs):
        assert kwargs["request"].panel_config == {"panel": "main"}
        assert kwargs["messages"] == ["message"]
        return deck_created

    result = asyncio.run(
        generate_artifact_result(
            http_request="request",
            request=_generate_request(
                artifact_type="deck",
                panel_config={"panel": "main"},
            ),
            messages=["message"],
            create_report_artifact_result=lambda **kwargs: None,
            create_deck_artifact_result=create_deck_artifact_result,
            ensure_deckable_chat=lambda messages: [("Q", "A")],
            build_chat_report_title=lambda messages: "Deck",
            build_report_markdown=lambda messages, title: f"# {title}",
            build_report_artifact=lambda **kwargs: None,
            save_artifact=lambda artifact: None,
            grant_derived_resource_access=lambda *args, **kwargs: None,
            build_deck="build-deck",
            build_create_deck_kwargs=lambda *args, **kwargs: {},
            resolve_active_prompt_runtime=lambda enabled: (None, None, None),
            normalize_deck_theme=lambda value: value,
            save_deck=lambda deck: None,
            create_deck_artifact=lambda deck: deck_artifact,
            grant_created_deck_artifact_access=lambda **kwargs: grants.append(kwargs),
            artifact_payload=_payload,
            access_store="access-store",
            require_remote_editor=lambda request: {"role": "editor"},
            audit_security_event=lambda *args, **kwargs: None,
            inherit_resource_grants=lambda **kwargs: None,
            grant_resource_owner=lambda *args, **kwargs: None,
            now=lambda: 123.0,
        )
    )

    assert result["artifact_id"] == "artifact-deck"
    assert grants[0]["request"] == "request"
    assert grants[0]["session_id"] == "session-1"
    assert grants[0]["deck_id"] == "deck-1"
    assert grants[0]["artifact_id"] == "artifact-deck"


def test_generate_artifact_result_validates_messages_and_deck_panel_config():
    common_kwargs = {
        "http_request": "request",
        "create_report_artifact_result": lambda **kwargs: None,
        "create_deck_artifact_result": lambda **kwargs: None,
        "ensure_deckable_chat": lambda messages: [],
        "build_chat_report_title": lambda messages: "",
        "build_report_markdown": lambda messages, title: "",
        "build_report_artifact": lambda **kwargs: None,
        "save_artifact": lambda artifact: None,
        "grant_derived_resource_access": lambda *args, **kwargs: None,
        "build_deck": None,
        "build_create_deck_kwargs": lambda *args, **kwargs: {},
        "resolve_active_prompt_runtime": lambda enabled: (None, None, None),
        "normalize_deck_theme": lambda value: value,
        "save_deck": lambda deck: None,
        "create_deck_artifact": lambda deck: None,
        "grant_created_deck_artifact_access": lambda **kwargs: None,
        "artifact_payload": _payload,
        "access_store": None,
        "require_remote_editor": lambda request: {"role": "editor"},
        "audit_security_event": lambda *args, **kwargs: None,
        "inherit_resource_grants": lambda **kwargs: None,
        "grant_resource_owner": lambda *args, **kwargs: None,
        "now": lambda: 1.0,
    }

    with pytest.raises(HTTPException) as messages_exc:
        asyncio.run(
            generate_artifact_result(
                request=_generate_request(artifact_type="report"),
                messages=[],
                **common_kwargs,
            )
        )
    assert messages_exc.value.status_code == 400
    assert messages_exc.value.detail == ARTIFACT_GENERATION_MESSAGES_REQUIRED_DETAIL

    with pytest.raises(HTTPException) as panel_exc:
        asyncio.run(
            generate_artifact_result(
                request=_generate_request(artifact_type="deck", panel_config=None),
                messages=["message"],
                **common_kwargs,
            )
        )
    assert panel_exc.value.status_code == 400
    assert panel_exc.value.detail == DECK_ARTIFACT_PANEL_CONFIG_REQUIRED_DETAIL
