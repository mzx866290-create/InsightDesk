"""Route-level helpers for deck artifact creation."""

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from backend.delivery_templates import validate_delivery_template_selection
from backend.helpers.deck_report_helpers import (
    apply_deck_template_metadata,
    attach_deck_delivery_audit,
)


@dataclass(frozen=True)
class CreatedDeckArtifactResult:
    deck: Any
    artifact: Any
    deck_payload: dict[str, Any]

    @property
    def deck_id(self) -> str:
        return str(getattr(self.deck, "deck_id", "") or "")

    @property
    def artifact_id(self) -> str:
        return str(getattr(self.artifact, "artifact_id", "") or "")


async def create_deck_artifact_result(
    *,
    request: Any,
    messages: list[Any],
    build_deck: Callable[..., Awaitable[Any]],
    build_create_deck_kwargs: Callable[..., dict[str, Any]],
    resolve_active_prompt_runtime: Callable[..., Any],
    normalize_deck_theme: Callable[[str], str],
    save_deck: Callable[[Any], Any],
    create_deck_artifact: Callable[[Any], Any],
) -> CreatedDeckArtifactResult:
    template_id = str(getattr(request, "template_id", "") or "").strip()
    template_options = dict(getattr(request, "template_options", {}) or {})
    validate_delivery_template_selection(template_id, artifact_type="deck")

    deck = await build_deck(
        messages=messages,
        **build_create_deck_kwargs(
            request,
            resolve_active_prompt_runtime=resolve_active_prompt_runtime,
            normalize_deck_theme=normalize_deck_theme,
        ),
    )
    apply_deck_template_metadata(
        deck,
        template_id=template_id,
        template_options=template_options,
    )
    attach_deck_delivery_audit(deck)
    save_deck(deck)
    artifact = create_deck_artifact(deck)
    deck_payload = deck.model_dump(mode="json")
    deck_payload["artifact_id"] = getattr(artifact, "artifact_id", "")
    return CreatedDeckArtifactResult(
        deck=deck,
        artifact=artifact,
        deck_payload=deck_payload,
    )
