from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.helpers.resource_route_helpers import (
    ARTIFACT_NOT_FOUND_DETAIL,
    DECK_NOT_FOUND_DETAIL,
    artifact_for_route,
    deck_for_route,
    list_artifacts_route_payload,
    list_decks_route_payload,
)


class _Dumpable:
    def __init__(self, payload):
        self.payload = payload

    def model_dump(self, *, mode):
        assert mode == "json"
        return self.payload


def test_deck_for_route_checks_access_and_returns_deck():
    calls = []
    deck = SimpleNamespace(deck_id="deck-1")

    result = deck_for_route(
        request="request",
        deck_id="deck-1",
        minimum_role="viewer",
        require_deck_access=lambda req, deck_id, role: calls.append(
            ("access", req, deck_id, role)
        )
        or {"role": role},
        get_deck=lambda deck_id: calls.append(("get", deck_id)) or deck,
    )

    assert result is deck
    assert calls == [
        ("access", "request", "deck-1", "viewer"),
        ("get", "deck-1"),
    ]


def test_deck_for_route_maps_missing_deck_to_404_after_access_check():
    calls = []

    with pytest.raises(HTTPException) as exc:
        deck_for_route(
            request="request",
            deck_id="missing",
            minimum_role="editor",
            require_deck_access=lambda req, deck_id, role: calls.append(
                ("access", req, deck_id, role)
            )
            or {"role": role},
            get_deck=lambda deck_id: (_ for _ in ()).throw(KeyError(deck_id)),
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == DECK_NOT_FOUND_DETAIL
    assert calls == [("access", "request", "missing", "editor")]


def test_artifact_for_route_checks_access_and_maps_missing_artifact():
    artifact = SimpleNamespace(artifact_id="artifact-1")

    result = artifact_for_route(
        request="request",
        artifact_id="artifact-1",
        minimum_role="viewer",
        require_artifact_access=lambda req, artifact_id, role: {"role": role},
        get_artifact=lambda artifact_id: artifact,
    )

    assert result is artifact

    with pytest.raises(HTTPException) as exc:
        artifact_for_route(
            request="request",
            artifact_id="missing",
            minimum_role="editor",
            require_artifact_access=lambda req, artifact_id, role: {"role": role},
            get_artifact=lambda artifact_id: (_ for _ in ()).throw(
                KeyError(artifact_id)
            ),
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == ARTIFACT_NOT_FOUND_DETAIL


def test_list_decks_route_payload_clamps_limit_filters_and_dumps_decks():
    calls = []
    decks = [
        SimpleNamespace(deck_id="deck-1", title="One"),
        SimpleNamespace(deck_id="deck-2", title="Two"),
    ]

    def filter_visible_resources(request, records, **kwargs):
        calls.append(
            (
                "filter",
                request,
                [kwargs["resource_id_getter"](record) for record in records],
                kwargs["resource_type"],
                kwargs["access_store"],
                kwargs["identity_store"],
            )
        )
        return records[:1]

    payload = list_decks_route_payload(
        request="request",
        limit=900,
        list_recent_decks=lambda **kwargs: calls.append(("list", kwargs)) or decks,
        filter_visible_resources=filter_visible_resources,
        require_remote_viewer=lambda request: {"role": "viewer"},
        access_store="access-store",
        identity_store="identity-store",
        attach_deck_delivery_audit=lambda deck: _Dumpable({"deck_id": deck.deck_id}),
    )

    assert payload == {
        "decks": [{"deck_id": "deck-1"}],
        "total": 1,
        "limit": 500,
    }
    assert calls == [
        ("list", {"limit": 500}),
        (
            "filter",
            "request",
            ["deck-1", "deck-2"],
            "deck",
            "access-store",
            "identity-store",
        ),
    ]


def test_list_artifacts_route_payload_clamps_limit_filters_and_maps_payloads():
    calls = []
    artifacts = [
        SimpleNamespace(artifact_id="artifact-1"),
        SimpleNamespace(artifact_id="artifact-2"),
    ]

    def filter_visible_resources(request, records, **kwargs):
        calls.append(
            (
                "filter",
                request,
                [kwargs["resource_id_getter"](record) for record in records],
                kwargs["resource_type"],
            )
        )
        return records[1:]

    payload = list_artifacts_route_payload(
        request="request",
        limit=0,
        artifact_type="report",
        list_recent_artifacts=lambda **kwargs: calls.append(("list", kwargs))
        or artifacts,
        filter_visible_resources=filter_visible_resources,
        require_remote_viewer=lambda request: {"role": "viewer"},
        access_store="access-store",
        identity_store="identity-store",
        artifact_payload=lambda artifact: {"artifact_id": artifact.artifact_id},
    )

    assert payload == {
        "artifacts": [{"artifact_id": "artifact-2"}],
        "total": 1,
        "limit": 100,
    }
    assert calls == [
        ("list", {"limit": 100, "artifact_type": "report"}),
        (
            "filter",
            "request",
            ["artifact-1", "artifact-2"],
            "artifact",
        ),
    ]
