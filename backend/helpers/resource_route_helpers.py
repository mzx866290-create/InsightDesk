"""Shared route helpers for protected resource loading."""

from typing import Any, Callable

from fastapi import HTTPException


DECK_NOT_FOUND_DETAIL = "Deck was not found."
ARTIFACT_NOT_FOUND_DETAIL = "Artifact was not found."


def deck_for_route(
    *,
    request: Any,
    deck_id: str,
    minimum_role: str,
    require_deck_access: Callable[[Any, str, str], dict[str, Any]],
    get_deck: Callable[[str], Any],
) -> Any:
    require_deck_access(request, deck_id, minimum_role)
    try:
        return get_deck(deck_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=DECK_NOT_FOUND_DETAIL) from exc


def artifact_for_route(
    *,
    request: Any,
    artifact_id: str,
    minimum_role: str,
    require_artifact_access: Callable[[Any, str, str], dict[str, Any]],
    get_artifact: Callable[[str], Any],
) -> Any:
    require_artifact_access(request, artifact_id, minimum_role)
    try:
        return get_artifact(artifact_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=ARTIFACT_NOT_FOUND_DETAIL) from exc


def list_decks_route_payload(
    *,
    request: Any,
    limit: int,
    list_recent_decks: Callable[..., list[Any]],
    filter_visible_resources: Callable[..., list[Any]],
    require_remote_viewer: Callable[[Any], dict[str, Any]],
    access_store: Any,
    identity_store: Any,
    attach_deck_delivery_audit: Callable[[Any], Any],
) -> dict[str, Any]:
    safe_limit = max(1, min(500, int(limit or 100)))
    decks = list_recent_decks(limit=safe_limit)
    visible_decks = filter_visible_resources(
        request,
        decks,
        resource_type="deck",
        resource_id_getter=lambda deck: str(getattr(deck, "deck_id", "") or ""),
        require_remote_role=require_remote_viewer,
        access_store=access_store,
        identity_store=identity_store,
    )
    return {
        "decks": [
            attach_deck_delivery_audit(deck).model_dump(mode="json")
            for deck in visible_decks
        ],
        "total": len(visible_decks),
        "limit": safe_limit,
    }


def list_artifacts_route_payload(
    *,
    request: Any,
    limit: int,
    artifact_type: str,
    list_recent_artifacts: Callable[..., list[Any]],
    filter_visible_resources: Callable[..., list[Any]],
    require_remote_viewer: Callable[[Any], dict[str, Any]],
    access_store: Any,
    identity_store: Any,
    artifact_payload: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    safe_limit = max(1, min(500, int(limit or 100)))
    artifacts = list_recent_artifacts(
        limit=safe_limit,
        artifact_type=artifact_type,
    )
    visible_artifacts = filter_visible_resources(
        request,
        artifacts,
        resource_type="artifact",
        resource_id_getter=lambda artifact: str(
            getattr(artifact, "artifact_id", "") or ""
        ),
        require_remote_role=require_remote_viewer,
        access_store=access_store,
        identity_store=identity_store,
    )
    return {
        "artifacts": [artifact_payload(artifact) for artifact in visible_artifacts],
        "total": len(visible_artifacts),
        "limit": safe_limit,
    }


__all__ = [
    "ARTIFACT_NOT_FOUND_DETAIL",
    "DECK_NOT_FOUND_DETAIL",
    "artifact_for_route",
    "deck_for_route",
    "list_artifacts_route_payload",
    "list_decks_route_payload",
]
