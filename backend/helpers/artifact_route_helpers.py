"""Route-level helpers for artifact updates."""

from typing import Any, Callable

from fastapi import HTTPException


DECK_ARTIFACT_MARKDOWN_UNSUPPORTED_DETAIL = (
    "Deck artifact does not support markdown patching."
)
DECK_ARTIFACT_MISSING_DECK_ID_DETAIL = "Deck artifact is missing deck_id."
UNSUPPORTED_ARTIFACT_TYPE_DETAIL = "Unsupported artifact type."


def update_artifact_result(
    *,
    artifact_id: str,
    artifact: Any,
    request: Any,
    save_artifact: Callable[[Any], Any],
    get_artifact: Callable[[str], Any],
    get_deck: Callable[[str], Any],
    save_deck: Callable[[Any], Any],
    sync_deck_artifacts: Callable[[Any], None],
    artifact_payload: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    next_title = str(getattr(request, "title", "") or "").strip()

    if artifact.artifact_type == "report":
        if next_title:
            artifact.title = next_title
        if getattr(request, "markdown", None) is not None:
            artifact.content["markdown"] = str(getattr(request, "markdown") or "").strip()
        save_artifact(artifact)
        return artifact_payload(artifact)

    if artifact.artifact_type == "deck":
        if getattr(request, "markdown", None) is not None:
            raise HTTPException(
                status_code=400,
                detail=DECK_ARTIFACT_MARKDOWN_UNSUPPORTED_DETAIL,
            )
        deck_id = _deck_id_for_artifact(artifact)
        if not deck_id:
            raise HTTPException(status_code=400, detail=DECK_ARTIFACT_MISSING_DECK_ID_DETAIL)
        try:
            deck = get_deck(deck_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Deck was not found.") from exc
        if next_title:
            deck.meta.title = next_title
            if deck.slides and deck.slides[0].type == "cover":
                deck.slides[0].title = next_title
            save_deck(deck)
        sync_deck_artifacts(deck)
        return artifact_payload(get_artifact(artifact_id))

    raise HTTPException(status_code=400, detail=UNSUPPORTED_ARTIFACT_TYPE_DETAIL)


def _deck_id_for_artifact(artifact: Any) -> str:
    content = artifact.content if isinstance(getattr(artifact, "content", None), dict) else {}
    return str(getattr(artifact, "linked_resource_id", "") or content.get("deck_id") or "").strip()
