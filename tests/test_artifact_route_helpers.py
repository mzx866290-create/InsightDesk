from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.helpers.artifact_route_helpers import (
    DECK_ARTIFACT_MARKDOWN_UNSUPPORTED_DETAIL,
    DECK_ARTIFACT_MISSING_DECK_ID_DETAIL,
    UNSUPPORTED_ARTIFACT_TYPE_DETAIL,
    update_artifact_result,
)


def _request(**overrides):
    values = {"title": None, "markdown": None}
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
