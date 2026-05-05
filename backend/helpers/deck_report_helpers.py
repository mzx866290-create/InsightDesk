"""Deck and report helper utilities."""

from typing import Any, Callable

from backend.deck_service import (
    normalize_deck_chart_blocks,
    validate_deck_citation_consistency,
)


class DeckExportGateError(RuntimeError):
    """Raised when deck export is blocked by failed citation validation."""

    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__("Deck export blocked by citation validation gate.")
        self.payload = payload


def _normalize_scope_value(value: Any) -> str:
    return str(value or "").strip()


def _compact_source_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _format_report_source_lines(
    sources: list[dict[str, Any]] | None,
    *,
    limit: int = 4,
) -> list[str]:
    if not sources:
        return []

    lines: list[str] = []
    for index, source in enumerate(sources[: max(1, limit)], start=1):
        title = _compact_source_text(source.get("title"))
        url = _compact_source_text(source.get("url"))
        snippet = _compact_source_text(source.get("snippet"))[:160]

        label = title or url or f"来源 {index}"
        line = f"- {label}"
        if url and url != label:
            line += f" ({url})"
        if snippet:
            line += f": {snippet}"
        lines.append(line)
    return lines


def _append_report_sources(
    answer_content: str,
    sources: list[dict[str, Any]] | None,
) -> str:
    source_lines = _format_report_source_lines(sources)
    if not source_lines:
        return answer_content

    base = str(answer_content or "").strip()
    lines = [base] if base else []
    if lines:
        lines.append("")
    lines.append("参考来源")
    lines.extend(source_lines)
    return "\n".join(lines).strip()


def _attach_message_metadata(message: Any, metadata: dict[str, Any]) -> Any:
    if not metadata:
        return message
    existing = getattr(message, "additional_kwargs", None)
    if isinstance(existing, dict):
        existing.update(metadata)
        return message
    try:
        setattr(message, "additional_kwargs", dict(metadata))
    except Exception:
        pass
    return message


def build_scoped_report_messages(
    message_records: list[dict[str, Any]],
    *,
    answer_group_id: str,
    panel_id: str = "",
    human_message_factory: Callable[[str], Any],
    ai_message_factory: Callable[[str], Any],
) -> list[Any]:
    normalized_answer_group_id = _normalize_scope_value(answer_group_id)
    normalized_panel_id = _normalize_scope_value(panel_id)
    if not normalized_answer_group_id:
        raise ValueError("必须提供 answer_group_id。")

    user_record = next(
        (
            record
            for record in message_records
            if _normalize_scope_value(record.get("type")) == "human"
            and _normalize_scope_value(record.get("answer_group_id"))
            == normalized_answer_group_id
            and str(record.get("content") or "").strip()
        ),
        None,
    )
    if user_record is None:
        raise KeyError(normalized_answer_group_id)

    ai_candidates = [
        record
        for record in message_records
        if _normalize_scope_value(record.get("type")) == "ai"
        and _normalize_scope_value(record.get("answer_group_id"))
        == normalized_answer_group_id
        and str(record.get("content") or "").strip()
    ]
    if normalized_panel_id:
        ai_candidates = [
            record
            for record in ai_candidates
            if _normalize_scope_value(record.get("panel_id")) == normalized_panel_id
        ]
    if not ai_candidates:
        raise KeyError(normalized_answer_group_id)

    def _candidate_rank(record: dict[str, Any]) -> tuple[int, int, int, float]:
        return (
            int(_normalize_scope_value(record.get("task_type")) == "web_research"),
            int(_normalize_scope_value(record.get("model_id")) == "web_research"),
            int(bool(record.get("sources"))),
            float(record.get("timestamp") or 0),
        )

    ai_record = max(ai_candidates, key=_candidate_rank)
    question = str(user_record.get("content") or "").strip()
    answer = _append_report_sources(
        str(ai_record.get("content") or "").strip(),
        ai_record.get("sources")
        if isinstance(ai_record.get("sources"), list)
        else None,
    )
    metadata: dict[str, Any] = {}
    if isinstance(ai_record.get("sources"), list):
        metadata["sources"] = ai_record.get("sources")
    if isinstance(ai_record.get("claim_evidence_chains"), list):
        metadata["claim_evidence_chains"] = ai_record.get("claim_evidence_chains")

    return [
        human_message_factory(question),
        _attach_message_metadata(ai_message_factory(answer), metadata),
    ]


def resolve_report_messages(
    history: Any,
    *,
    answer_group_id: str = "",
    panel_id: str = "",
    human_message_factory: Callable[[str], Any],
    ai_message_factory: Callable[[str], Any],
) -> list[Any]:
    normalized_answer_group_id = _normalize_scope_value(answer_group_id)
    normalized_panel_id = _normalize_scope_value(panel_id)
    if not normalized_answer_group_id:
        return history.get_all_messages()

    return build_scoped_report_messages(
        history.get_all_message_records(),
        answer_group_id=normalized_answer_group_id,
        panel_id=normalized_panel_id,
        human_message_factory=human_message_factory,
        ai_message_factory=ai_message_factory,
    )


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
        "source_answer_group_id": _normalize_scope_value(
            getattr(request, "answer_group_id", "")
        ),
        "source_panel_id": _normalize_scope_value(getattr(request, "panel_id", "")),
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

    normalize_deck_chart_blocks(deck)
    return attach_deck_delivery_audit(deck)


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
    normalize_deck_chart_blocks(deck)
    return attach_deck_delivery_audit(deck)


def _clean_ref_ids(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, list | tuple | set):
        items = list(value)
    else:
        items = [value]
    return list(dict.fromkeys(str(item or "").strip() for item in items if str(item or "").strip()))


def _request_ref_ids(request: Any, key: str) -> list[str] | None:
    if isinstance(request, dict):
        if key not in request:
            return None
        return _clean_ref_ids(request.get(key))
    if not hasattr(request, key):
        return None
    return _clean_ref_ids(getattr(request, key))


def update_deck_block_refs(
    deck: Any,
    slide_id: str,
    block_id: str,
    request: Any,
    *,
    allow_unsafe_export: bool = False,
    override_reason: str = "",
) -> dict[str, Any]:
    """Update a block's citation bindings and return refreshed gate metadata."""

    normalized_slide_id = str(slide_id or "").strip()
    normalized_block_id = str(block_id or "").strip()
    target_slide = next(
        (
            slide
            for slide in list(getattr(deck, "slides", []) or [])
            if str(getattr(slide, "id", "") or "").strip() == normalized_slide_id
        ),
        None,
    )
    if target_slide is None:
        raise KeyError(normalized_slide_id)

    target_block = next(
        (
            block
            for block in list(getattr(target_slide, "blocks", []) or [])
            if str(getattr(block, "id", "") or "").strip() == normalized_block_id
        ),
        None,
    )
    if target_block is None:
        raise KeyError(normalized_block_id)

    content = dict(getattr(target_block, "content", {}) or {})
    for request_key, content_key in (
        ("evidence_ref_ids", "evidence_ref_ids"),
        ("evidence_refs", "evidence_ref_ids"),
        ("source_ref_ids", "evidence_source_ids"),
        ("evidence_source_ids", "evidence_source_ids"),
        ("evidence_excerpt_ids", "evidence_excerpt_ids"),
    ):
        ref_ids = _request_ref_ids(request, request_key)
        if ref_ids is not None:
            content[content_key] = ref_ids

    target_block.content = content
    status = getattr(target_slide, "status", None)
    if status is not None:
        try:
            status.dirty = True
            status.review_state = "draft"
        except Exception:
            pass

    normalize_deck_chart_blocks(deck)
    attach_deck_delivery_audit(deck)
    citation_validation = _citation_validation_payload(deck)
    evidence_review = build_deck_evidence_review_payload(deck)
    export_gate = _deck_export_gate_payload(
        citation_validation,
        allow_unsafe_export=allow_unsafe_export,
        override_reason=override_reason,
    )
    slide_delivery = build_deck_slide_delivery_payload(
        deck,
        normalized_slide_id,
        citation_validation=citation_validation,
        evidence_review=evidence_review,
        export_gate=export_gate,
    )
    return {
        "deck": deck,
        "slide_id": normalized_slide_id,
        "block_id": normalized_block_id,
        "block": target_block,
        "citation_validation": citation_validation,
        "evidence_review": evidence_review,
        "export_gate": export_gate,
        "slide_delivery": slide_delivery,
    }


def _refresh_deck_evidence_coverage(deck: Any) -> Any:
    refresh = getattr(deck, "refresh_evidence_coverage", None)
    if callable(refresh):
        refresh()
    return deck


def _deck_evidence_coverage_payload(deck: Any) -> dict[str, Any]:
    _refresh_deck_evidence_coverage(deck)
    coverage = getattr(getattr(deck, "generation", None), "evidence_coverage", None)
    if hasattr(coverage, "model_dump"):
        return coverage.model_dump(mode="json")
    if isinstance(coverage, dict):
        return coverage
    return {}


def _citation_validation_payload(deck: Any) -> dict[str, Any]:
    validation = validate_deck_citation_consistency(deck)
    return validation.model_dump(mode="json")


def attach_deck_delivery_audit(deck: Any) -> Any:
    """Persist regenerated review/export metadata beside the deck itself."""

    _refresh_deck_evidence_coverage(deck)
    citation_validation = validate_deck_citation_consistency(deck)
    evidence_review = build_deck_evidence_review_payload(deck)
    generation = getattr(deck, "generation", None)
    if generation is not None:
        try:
            generation.evidence_review = evidence_review
            generation.citation_validation = citation_validation
        except Exception:
            pass
    try:
        deck.citation_validation = citation_validation
    except Exception:
        pass
    return deck


def _deck_export_gate_payload(
    citation_validation: dict[str, Any],
    *,
    allow_unsafe_export: bool,
    override_reason: str,
) -> dict[str, Any]:
    can_export = bool(citation_validation.get("can_export"))
    overridden = not can_export and bool(allow_unsafe_export)
    blocked = not can_export and not overridden
    return {
        "blocked": blocked,
        "overridden": overridden,
        "can_export": can_export,
        "reason": str(override_reason or "").strip() if overridden else "",
        "message": (
            "Deck export is blocked because citation validation failed."
            if blocked
            else ""
        ),
    }


def _citation_issue_slide_ids(citation_validation: dict[str, Any]) -> list[str]:
    issue_slide_ids: list[str] = []
    for issue in list(citation_validation.get("issues") or []):
        if not isinstance(issue, dict):
            continue
        slide_id = str(issue.get("slide_id") or "").strip()
        if slide_id:
            issue_slide_ids.append(slide_id)
    return list(dict.fromkeys(issue_slide_ids))


def build_deck_slide_delivery_payload(
    deck: Any,
    slide_id: str,
    *,
    citation_validation: dict[str, Any] | None = None,
    evidence_review: dict[str, Any] | None = None,
    export_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the review/export state for one slide after an editor action."""

    normalized_slide_id = str(slide_id or "").strip()
    citation_validation = citation_validation or _citation_validation_payload(deck)
    evidence_review = evidence_review or build_deck_evidence_review_payload(deck)
    export_gate = export_gate or _deck_export_gate_payload(
        citation_validation,
        allow_unsafe_export=False,
        override_reason="",
    )
    slide = next(
        (
            item
            for item in list(getattr(deck, "slides", []) or [])
            if str(getattr(item, "id", "") or "").strip() == normalized_slide_id
        ),
        None,
    )
    if slide is None:
        return {"slide_id": normalized_slide_id, "found": False}

    status = getattr(slide, "status", None)
    slide_review = next(
        (
            item
            for item in list(evidence_review.get("slides") or [])
            if isinstance(item, dict)
            and str(item.get("slide_id") or "").strip() == normalized_slide_id
        ),
        {},
    )
    slide_issues = [
        issue
        for issue in list(citation_validation.get("issues") or [])
        if isinstance(issue, dict)
        and str(issue.get("slide_id") or "").strip() == normalized_slide_id
    ]
    blocks_export = bool(slide_issues)
    return {
        "slide_id": normalized_slide_id,
        "found": True,
        "review_state": str(getattr(status, "review_state", "") or ""),
        "dirty": bool(getattr(status, "dirty", False)),
        "locked": bool(getattr(status, "locked", False)),
        "quality_state": str(getattr(slide, "quality_state", "") or ""),
        "evidence_ref_count": len(list(getattr(slide, "evidence_refs", []) or [])),
        "needs_review": bool(slide_review.get("needs_review")) or blocks_export,
        "source_ids": list(slide_review.get("source_ids") or []),
        "source_titles": list(slide_review.get("source_titles") or []),
        "citation_issue_count": len(slide_issues),
        "citation_issue_codes": list(
            dict.fromkeys(
                code
                for code in (str(issue.get("code") or "") for issue in slide_issues)
                if code
            )
        ),
        "blocks_export": blocks_export,
        "deck_can_export": bool(citation_validation.get("can_export")),
        "export_blocked": bool(export_gate.get("blocked")),
    }


def build_deck_delivery_response(deck: Any, *, focus_slide_id: str = "") -> dict[str, Any]:
    """Return a deck plus review/export gate fields for editor routes."""

    attach_deck_delivery_audit(deck)
    citation_validation = _citation_validation_payload(deck)
    evidence_review = build_deck_evidence_review_payload(deck)
    export_gate = _deck_export_gate_payload(
        citation_validation,
        allow_unsafe_export=False,
        override_reason="",
    )
    payload = {
        "deck": deck.model_dump(mode="json") if hasattr(deck, "model_dump") else deck,
        "citation_validation": citation_validation,
        "evidence_review": evidence_review,
        "export_gate": export_gate,
    }
    if str(focus_slide_id or "").strip():
        payload["slide_delivery"] = build_deck_slide_delivery_payload(
            deck,
            focus_slide_id,
            citation_validation=citation_validation,
            evidence_review=evidence_review,
            export_gate=export_gate,
        )
    return payload


def _deck_source_title(source: Any) -> str:
    return str(getattr(source, "title", "") or "").strip()


def _deck_source_id(source: Any) -> str:
    return str(getattr(source, "id", "") or "").strip()


def _slide_title(slide: Any) -> str:
    return str(getattr(slide, "title", "") or "").strip()


def build_deck_evidence_review_payload(deck: Any) -> dict[str, Any]:
    """Build a UI-friendly evidence review summary for deck audit panels."""

    coverage = _deck_evidence_coverage_payload(deck)
    citation_validation = _citation_validation_payload(deck)
    slides_by_id = {
        str(getattr(slide, "id", "") or ""): slide
        for slide in list(getattr(deck, "slides", []) or [])
    }
    source_registry = list(getattr(deck, "source_registry", []) or [])
    source_titles_by_id = {
        _deck_source_id(source): _deck_source_title(source)
        for source in source_registry
        if _deck_source_id(source)
    }
    slide_reviews: list[dict[str, Any]] = []
    weak_slide_ids: list[str] = []

    for item in list(coverage.get("slides") or []):
        if not isinstance(item, dict):
            continue
        slide_id = str(item.get("slide_id") or "")
        slide = slides_by_id.get(slide_id)
        refs = list(getattr(slide, "evidence_refs", []) or []) if slide is not None else []
        source_ids: list[str] = []
        source_titles: list[str] = []
        for ref in refs:
            source_id = str(getattr(ref, "source_id", "") or "").strip()
            if source_id:
                source_ids.append(source_id)
            title = (
                str(getattr(ref, "source_title", "") or "").strip()
                or source_titles_by_id.get(source_id, "")
            )
            if title:
                source_titles.append(title)
        source_titles = [title for title in dict.fromkeys(source_titles) if title]
        quality_state = str(item.get("quality_state") or "weak_support")
        is_coverable = bool(item.get("is_coverable"))
        has_evidence = bool(item.get("has_evidence"))
        needs_review = is_coverable and (not has_evidence or quality_state == "weak_support")
        if needs_review:
            weak_slide_ids.append(slide_id)
        slide_reviews.append(
            {
                "slide_id": slide_id,
                "title": _slide_title(slide),
                "slide_type": str(item.get("slide_type") or ""),
                "is_coverable": is_coverable,
                "has_evidence": has_evidence,
                "evidence_ref_count": int(item.get("evidence_ref_count", 0) or 0),
                "quality_state": quality_state,
                "needs_review": needs_review,
                "source_ids": list(dict.fromkeys(source_ids)),
                "source_titles": source_titles,
            }
        )

    coverable_count = int(coverage.get("coverable_slide_count", 0) or 0)
    unsupported_ids = list(coverage.get("unsupported_slide_ids") or [])
    total_evidence_refs = int(coverage.get("total_evidence_refs", 0) or 0)
    coverage_ratio = float(coverage.get("coverage_ratio", 0.0) or 0.0)
    status = "not_applicable"
    if coverable_count > 0:
        status = "supported" if not unsupported_ids and coverage_ratio >= 1.0 else "needs_review"

    action_items: list[dict[str, Any]] = []
    if unsupported_ids:
        action_items.append(
            {
                "code": "add_missing_slide_evidence",
                "severity": "warning",
                "message": "Add evidence references to unsupported slides.",
                "slide_ids": unsupported_ids,
            }
        )
    if coverable_count > 0 and total_evidence_refs == 0:
        action_items.append(
            {
                "code": "attach_deck_sources",
                "severity": "warning",
                "message": "Attach at least one source before final export.",
                "slide_ids": unsupported_ids,
            }
        )
    weak_supported_ids = [
        item["slide_id"]
        for item in slide_reviews
        if item["is_coverable"] and item["has_evidence"] and item["quality_state"] == "weak_support"
    ]
    if weak_supported_ids:
        action_items.append(
            {
                "code": "review_weak_support",
                "severity": "info",
                "message": "Review slides marked as weakly supported.",
                "slide_ids": weak_supported_ids,
            }
        )

    return {
        "status": status,
        "coverage_ratio": coverage_ratio,
        "coverable_slide_count": coverable_count,
        "slides_with_evidence": int(coverage.get("slides_with_evidence", 0) or 0),
        "unsupported_slide_ids": unsupported_ids,
        "needs_review_slide_ids": list(dict.fromkeys(weak_slide_ids)),
        "action_count": len(action_items),
        "action_items": action_items,
        "slides": slide_reviews,
        "citation_validation": citation_validation,
    }


def export_deck_payload(
    deck: Any,
    *,
    export_deck_to_pptx: Callable[[Any], bytes],
    build_export_filename: Callable[[Any, str], str],
    allow_unsafe_export: bool = False,
    override_reason: str = "",
) -> dict[str, Any]:
    attach_deck_delivery_audit(deck)
    citation_validation = _citation_validation_payload(deck)
    evidence_review = build_deck_evidence_review_payload(deck)
    export_gate = _deck_export_gate_payload(
        citation_validation,
        allow_unsafe_export=allow_unsafe_export,
        override_reason=override_reason,
    )
    if export_gate["blocked"]:
        raise DeckExportGateError(
            {
                "message": export_gate["message"],
                "export_gate": export_gate,
                "citation_validation": citation_validation,
                "evidence_review": evidence_review,
                "blocking_slide_ids": _citation_issue_slide_ids(citation_validation),
            }
        )
    return {
        "content": export_deck_to_pptx(deck),
        "filename": build_export_filename(deck, "pptx"),
        "evidence_coverage": _deck_evidence_coverage_payload(deck),
        "evidence_review": evidence_review,
        "citation_validation": citation_validation,
        "export_gate": export_gate,
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


__all__ = [
    "DeckExportGateError",
    "build_scoped_report_messages",
    "resolve_report_messages",
    "create_share_link_payload",
    "build_create_deck_kwargs",
    "apply_deck_update",
    "build_regenerate_deck_kwargs",
    "replace_deck_slide",
    "attach_deck_delivery_audit",
    "update_deck_block_refs",
    "build_deck_delivery_response",
    "build_deck_slide_delivery_payload",
    "build_deck_evidence_review_payload",
    "export_deck_payload",
    "report_markdown_payload",
    "report_download_payload",
]
