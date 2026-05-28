"""Route-level helpers for deck artifact creation."""

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, cast

from fastapi import HTTPException
from fastapi.responses import Response

from backend.delivery_templates import validate_delivery_template_selection
from backend.helpers.artifact_export_route_helpers import (
    PPTX_MEDIA_TYPE,
    build_download_response,
)
from backend.helpers.deck_report_helpers import (
    DeckExportGateError,
    apply_deck_template_metadata,
    attach_deck_delivery_audit,
)


DECK_MUST_KEEP_SLIDE_DETAIL = "Deck must keep at least one slide."
DECK_EXPORT_UNSUPPORTED_DETAIL = "Deck export only supports pptx."
DECK_SOURCE_SCOPE_NOT_FOUND_DETAIL = "Requested deck scope was not found."
DECK_SOURCE_MESSAGES_NOT_FOUND_DETAIL = "No messages were found in this session."
DECK_SLIDE_NOT_FOUND_DETAIL = "Slide was not found."


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


def grant_created_deck_artifact_access(
    *,
    request: Any,
    session_id: str,
    deck_id: str,
    artifact_id: str,
    access_store: Any,
    require_remote_editor: Callable[[Any], Any],
    audit_security_event: Callable[..., Any],
    inherit_resource_grants: Callable[..., Any],
    grant_resource_owner: Callable[..., Any],
    now: Callable[[], float],
) -> None:
    for resource_type, resource_id in (
        ("deck", deck_id),
        ("artifact", artifact_id),
    ):
        inherit_resource_grants(
            source_resource_type="session",
            source_resource_id=session_id,
            target_resource_type=resource_type,
            target_resource_id=resource_id,
            access_store=access_store,
            now=now,
            audit_security_event=audit_security_event,
            request=request,
        )
        grant_resource_owner(
            request,
            resource_type=resource_type,
            resource_id=resource_id,
            require_remote_role=require_remote_editor,
            access_store=access_store,
            now=now,
            audit_security_event=audit_security_event,
        )


def update_deck_result(
    *,
    deck: Any,
    request: Any,
    apply_deck_update: Callable[..., Any],
    normalize_deck_theme: Callable[[str], str],
    save_deck: Callable[[Any], Any],
    sync_deck_artifacts: Callable[[Any], None],
) -> dict[str, Any]:
    if getattr(request, "slides", None) is not None and not getattr(request, "slides"):
        raise HTTPException(status_code=400, detail=DECK_MUST_KEEP_SLIDE_DETAIL)

    apply_deck_update(deck, request, normalize_deck_theme=normalize_deck_theme)
    save_deck(deck)
    sync_deck_artifacts(deck)
    return cast(dict[str, Any], _model_payload(deck))


def update_deck_block_refs_result(
    *,
    deck: Any,
    slide_id: str,
    block_id: str,
    payload: dict[str, Any],
    update_deck_block_refs: Callable[..., dict[str, Any]],
    save_deck: Callable[[Any], Any],
    sync_deck_artifacts: Callable[[Any], None],
) -> dict[str, Any]:
    result = update_deck_block_refs(deck, slide_id, block_id, payload)
    save_deck(deck)
    sync_deck_artifacts(deck)
    block = result["block"]
    return {
        "deck": _model_payload(deck),
        "slide_id": result["slide_id"],
        "block_id": result["block_id"],
        "block": _model_payload(block),
        "citation_validation": result["citation_validation"],
        "evidence_review": result["evidence_review"],
        "export_gate": result["export_gate"],
        "slide_delivery": result["slide_delivery"],
    }


async def regenerate_deck_slide_result(
    *,
    deck: Any,
    slide_id: str,
    request: Any,
    create_chat_message_history: Callable[..., Any],
    resolve_report_messages: Callable[..., list[Any]],
    build_regenerate_deck_kwargs: Callable[..., dict[str, Any]],
    normalize_model_config: Callable[[Any], Any],
    resolve_active_prompt_runtime: Callable[[bool], tuple[Any, Any, Any]],
    regenerate_deck_slide: Callable[..., Awaitable[Any]],
    replace_deck_slide: Callable[[Any, Any], Any],
    save_deck: Callable[[Any], Any],
    sync_deck_artifacts: Callable[[Any], None],
    build_deck_delivery_response: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    history = create_chat_message_history(session_id=deck.meta.session_id)
    try:
        messages = resolve_report_messages(
            history,
            answer_group_id=getattr(deck.meta, "source_answer_group_id", None),
            panel_id=getattr(deck.meta, "source_panel_id", None),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=DECK_SOURCE_SCOPE_NOT_FOUND_DETAIL) from exc
    if not messages:
        raise HTTPException(status_code=400, detail=DECK_SOURCE_MESSAGES_NOT_FOUND_DETAIL)

    regenerate_kwargs = build_regenerate_deck_kwargs(
        deck,
        request,
        normalize_model_config=normalize_model_config,
        resolve_active_prompt_runtime=resolve_active_prompt_runtime,
    )
    try:
        regenerated_slide = await regenerate_deck_slide(
            deck=deck,
            slide_id=slide_id,
            messages=messages,
            **regenerate_kwargs,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=DECK_SLIDE_NOT_FOUND_DETAIL) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    replace_deck_slide(deck, regenerated_slide)
    save_deck(deck)
    sync_deck_artifacts(deck)
    return build_deck_delivery_response(deck, focus_slide_id=slide_id)


def export_deck_response(
    *,
    deck: Any,
    export_format: str,
    export_deck_payload: Callable[..., dict[str, Any]],
    export_deck_to_pptx: Callable[[Any], bytes],
    build_export_filename: Callable[..., str],
    build_download_content_disposition: Callable[[str], str],
    allow_unsafe_export: bool = False,
    override_reason: str = "",
) -> Response:
    if str(export_format or "pptx").strip().lower() != "pptx":
        raise HTTPException(status_code=400, detail=DECK_EXPORT_UNSUPPORTED_DETAIL)
    try:
        export_payload = export_deck_payload(
            deck,
            export_deck_to_pptx=export_deck_to_pptx,
            build_export_filename=build_export_filename,
            allow_unsafe_export=allow_unsafe_export,
            override_reason=override_reason,
        )
    except DeckExportGateError as exc:
        raise HTTPException(status_code=409, detail=exc.payload) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return build_download_response(
        content=export_payload["content"],
        media_type=PPTX_MEDIA_TYPE,
        filename=export_payload["filename"],
        build_download_content_disposition=build_download_content_disposition,
    )


def create_deck_share_link_result(
    *,
    deck_id: str,
    request: Any,
    share_secret: str,
    create_share_link_payload: Callable[..., dict[str, Any]],
    encode_share_token: Callable[..., str],
    build_share_url: Callable[..., str],
    share_link_store: Any,
    share_link_ttl_seconds: int,
    request_client_ip: Callable[[Any], str],
    request_user_agent: Callable[[Any], str],
    audit_security_event: Callable[..., Any],
    share_link_response_model: type,
    now: Callable[[], float],
) -> Any:
    payload = create_share_link_payload(
        "deck",
        deck_id,
        request,
        secret=share_secret,
        encode_share_token=encode_share_token,
        build_share_url=build_share_url,
    )
    record = share_link_store.upsert(
        share_token=payload["share_token"],
        resource_type="deck",
        resource_id=deck_id,
        expires_at=now() + share_link_ttl_seconds,
        created_by_ip=request_client_ip(request),
        created_user_agent=request_user_agent(request),
    )
    audit_security_event("create_deck_share_link", request, details=f"deck_id={deck_id}")
    return share_link_response_model(**payload, expires_at=record.expires_at)


def _model_payload(value: Any) -> Any:
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")
    return value
