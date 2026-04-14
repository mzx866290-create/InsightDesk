from typing import Any, Callable


def create_share_link_payload(
    resource_type: str,
    resource_id: str,
    request: Any,
    *,
    secret: str,
    encode_share_token: Callable[[str, str, str], str],
    build_share_url: Callable[[Any, str], str],
) -> dict[str, Any]:
    share_token = encode_share_token(resource_type, resource_id, secret)
    return {
        "resource_type": resource_type,
        "resource_id": resource_id,
        "share_token": share_token,
        "share_url": build_share_url(request, share_token),
    }


def build_create_deck_kwargs(
    request: Any,
    *,
    resolve_active_prompt_runtime: Callable[[bool], tuple[Any, Any, Any]],
    normalize_deck_theme: Callable[[str], str],
) -> dict[str, Any]:
    system_prompt_content, vector_store_path, _ = resolve_active_prompt_runtime(
        request.knowledge_base_enabled
    )
    return {
        "session_id": request.session_id,
        "panel_config": request.panel_config,
        "knowledge_base_enabled": request.knowledge_base_enabled,
        "target_slide_count": request.target_slide_count,
        "vector_store_path": vector_store_path,
        "system_prompt": system_prompt_content,
        "theme": normalize_deck_theme(request.theme),
    }


def apply_deck_update(
    deck: Any,
    request: Any,
    *,
    normalize_deck_theme: Callable[[str], str],
) -> Any:
    next_title = None
    if request.title is not None and request.title.strip():
        next_title = request.title.strip()
        deck.meta.title = next_title
        if deck.slides and deck.slides[0].type == "cover":
            deck.slides[0].title = next_title

    if request.theme is not None:
        deck.meta.theme = normalize_deck_theme(request.theme)

    if request.slides is not None:
        deck.slides = request.slides
        deck.generation.actual_slide_count = len(deck.slides)
        if next_title and deck.slides and deck.slides[0].type == "cover":
            deck.slides[0].title = next_title

    return deck


def build_regenerate_deck_kwargs(
    deck: Any,
    request: Any,
    *,
    normalize_model_config: Callable[[Any], Any],
    resolve_active_prompt_runtime: Callable[[bool], tuple[Any, Any, Any]],
) -> dict[str, Any]:
    normalized_panel_config = normalize_model_config(request.panel_config)
    knowledge_base_enabled = (
        request.knowledge_base_enabled
        if request.knowledge_base_enabled is not None
        else deck.meta.source_mode == "kb_plus_chat"
    )
    system_prompt_content, vector_store_path, _ = resolve_active_prompt_runtime(
        knowledge_base_enabled
    )
    return {
        "panel_config": normalized_panel_config,
        "knowledge_base_enabled": knowledge_base_enabled,
        "vector_store_path": vector_store_path,
        "system_prompt": system_prompt_content,
    }


def replace_deck_slide(deck: Any, regenerated_slide: Any) -> Any:
    deck.slides = [
        regenerated_slide if slide.id == regenerated_slide.id else slide
        for slide in deck.slides
    ]
    return deck


def export_deck_payload(
    deck: Any,
    *,
    export_deck_to_pptx: Callable[[Any], bytes],
    build_export_filename: Callable[[Any, str], str],
) -> dict[str, Any]:
    return {
        "content": export_deck_to_pptx(deck),
        "filename": build_export_filename(deck, "pptx"),
    }


def report_markdown_payload(
    messages: list[Any],
    *,
    ensure_deckable_chat: Callable[[list[Any]], Any],
    build_chat_report_title: Callable[[list[Any]], str],
    build_report_markdown: Callable[[list[Any], str], str],
) -> dict[str, Any]:
    ensure_deckable_chat(messages)
    title = build_chat_report_title(messages)
    return {
        "markdown": build_report_markdown(messages, title),
        "title": title,
    }


def report_download_payload(
    messages: list[Any],
    *,
    ensure_deckable_chat: Callable[[list[Any]], list[tuple[str, str]]],
    build_chat_report_title: Callable[[list[Any]], str],
    presentation_factory: Callable[[], Any],
    body_font_size: Any,
    populate_chat_report_presentation: Callable[..., None],
    safe_report_filename: Callable[[str], str],
) -> dict[str, Any]:
    qa_pairs = ensure_deckable_chat(messages)
    title = build_chat_report_title(messages)
    presentation = presentation_factory()
    populate_chat_report_presentation(
        presentation,
        title=title,
        qa_pairs=qa_pairs,
        body_font_size=body_font_size,
    )
    return {
        "presentation": presentation,
        "filename": f"{safe_report_filename(title)}.pptx",
        "title": title,
    }
