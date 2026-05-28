"""Route-level helpers for artifact updates."""

from typing import Any, Callable

from fastapi import HTTPException

from backend.helpers.resource_route_helpers import artifact_for_route

DECK_ARTIFACT_MARKDOWN_UNSUPPORTED_DETAIL = (
    "Deck artifact does not support markdown patching."
)
DECK_ARTIFACT_MISSING_DECK_ID_DETAIL = "Deck artifact is missing deck_id."
UNSUPPORTED_ARTIFACT_TYPE_DETAIL = "Unsupported artifact type."
DECK_ARTIFACT_PANEL_CONFIG_REQUIRED_DETAIL = "Deck artifact requires panel_config."
ARTIFACT_GENERATION_MESSAGES_REQUIRED_DETAIL = (
    "No usable messages were found for artifact generation."
)


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


def update_artifact_route_result(
    *,
    artifact_id: str,
    http_request: Any,
    request: Any,
    artifact_store: Any,
    deck_store: Any,
    require_artifact_access: Callable[[Any, str, str], dict[str, Any]],
    sync_deck_artifacts: Callable[[Any], None],
    artifact_payload: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    artifact = artifact_for_route(
        request=http_request,
        artifact_id=artifact_id,
        minimum_role="editor",
        require_artifact_access=require_artifact_access,
        get_artifact=artifact_store.get,
    )
    return update_artifact_result(
        artifact_id=artifact_id,
        artifact=artifact,
        request=request,
        save_artifact=artifact_store.save,
        get_artifact=artifact_store.get,
        get_deck=deck_store.get,
        save_deck=deck_store.save,
        sync_deck_artifacts=sync_deck_artifacts,
        artifact_payload=artifact_payload,
    )


def export_artifact_route_response(
    *,
    artifact_id: str,
    request: Any,
    export_format: str,
    artifact_store: Any,
    deck_store: Any,
    require_artifact_access: Callable[[Any, str, str], dict[str, Any]],
    export_deck_payload: Callable[..., dict[str, Any]],
    export_deck_to_pptx: Callable[[Any], bytes],
    build_export_filename: Callable[..., str],
    build_download_content_disposition: Callable[[str], str],
    safe_report_filename: Callable[[str], str],
    populate_chat_report_presentation: Callable[..., None],
    allow_unsafe_export: bool = False,
    override_reason: str = "",
) -> Any:
    artifact = artifact_for_route(
        request=request,
        artifact_id=artifact_id,
        minimum_role="viewer",
        require_artifact_access=require_artifact_access,
        get_artifact=artifact_store.get,
    )
    from backend.helpers.artifact_export_route_helpers import export_artifact_response

    return export_artifact_response(
        artifact=artifact,
        export_format=export_format,
        get_deck=deck_store.get,
        export_deck_payload=export_deck_payload,
        export_deck_to_pptx=export_deck_to_pptx,
        build_export_filename=build_export_filename,
        build_download_content_disposition=build_download_content_disposition,
        safe_report_filename=safe_report_filename,
        populate_chat_report_presentation=populate_chat_report_presentation,
        allow_unsafe_export=allow_unsafe_export,
        override_reason=override_reason,
    )


async def generate_artifact_result(
    *,
    http_request: Any,
    request: Any,
    messages: list[Any],
    create_report_artifact_result: Callable[..., Any],
    create_deck_artifact_result: Callable[..., Any],
    ensure_deckable_chat: Callable[[list[Any]], list[Any]],
    build_chat_report_title: Callable[[list[Any]], str],
    build_report_markdown: Callable[[list[Any], str], str],
    build_report_artifact: Callable[..., Any],
    save_artifact: Callable[[Any], Any],
    grant_derived_resource_access: Callable[..., Any],
    build_deck: Any,
    build_create_deck_kwargs: Callable[..., dict[str, Any]],
    resolve_active_prompt_runtime: Callable[..., Any],
    normalize_deck_theme: Callable[[str], str],
    save_deck: Callable[[Any], Any],
    create_deck_artifact: Callable[[Any], Any],
    grant_created_deck_artifact_access: Callable[..., Any],
    artifact_payload: Callable[[Any], dict[str, Any]],
    access_store: Any,
    require_remote_editor: Callable[[Any], dict[str, Any]],
    audit_security_event: Callable[..., Any],
    inherit_resource_grants: Callable[..., Any],
    grant_resource_owner: Callable[..., Any],
    now: Callable[[], float],
) -> dict[str, Any]:
    if not messages:
        raise HTTPException(status_code=400, detail=ARTIFACT_GENERATION_MESSAGES_REQUIRED_DETAIL)

    if request.artifact_type == "report":
        try:
            report_created = create_report_artifact_result(
                request=request,
                messages=messages,
                ensure_deckable_chat=ensure_deckable_chat,
                build_chat_report_title=build_chat_report_title,
                build_report_markdown=build_report_markdown,
                build_report_artifact=build_report_artifact,
                save_artifact=save_artifact,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        grant_derived_resource_access(
            http_request,
            source_resource_type="session",
            source_resource_id=request.session_id,
            target_resource_type="artifact",
            target_resource_id=report_created.artifact_id,
            access_store=access_store,
            require_remote_role=require_remote_editor,
            now=now,
            audit_security_event=audit_security_event,
        )
        return artifact_payload(report_created.artifact)

    if request.artifact_type == "deck":
        if getattr(request, "panel_config", None) is None:
            raise HTTPException(
                status_code=400,
                detail=DECK_ARTIFACT_PANEL_CONFIG_REQUIRED_DETAIL,
            )
        try:
            deck_created = await create_deck_artifact_result(
                request=request,
                messages=messages,
                build_deck=build_deck,
                build_create_deck_kwargs=build_create_deck_kwargs,
                resolve_active_prompt_runtime=resolve_active_prompt_runtime,
                normalize_deck_theme=normalize_deck_theme,
                save_deck=save_deck,
                create_deck_artifact=create_deck_artifact,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        grant_created_deck_artifact_access(
            request=http_request,
            session_id=request.session_id,
            deck_id=deck_created.deck_id,
            artifact_id=deck_created.artifact_id,
            access_store=access_store,
            require_remote_editor=require_remote_editor,
            audit_security_event=audit_security_event,
            inherit_resource_grants=inherit_resource_grants,
            grant_resource_owner=grant_resource_owner,
            now=now,
        )
        return artifact_payload(deck_created.artifact)

    raise HTTPException(status_code=400, detail=UNSUPPORTED_ARTIFACT_TYPE_DETAIL)


def _deck_id_for_artifact(artifact: Any) -> str:
    content = artifact.content if isinstance(getattr(artifact, "content", None), dict) else {}
    return str(getattr(artifact, "linked_resource_id", "") or content.get("deck_id") or "").strip()
