"""Route-level helpers for report artifact creation."""

import io
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import HTTPException
from fastapi.responses import Response

from backend.delivery_templates import validate_delivery_template_selection
from backend.helpers.deck_report_helpers import apply_report_template_metadata


PPTX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


@dataclass(frozen=True)
class CreatedReportArtifactResult:
    artifact: Any
    title: str
    markdown: str

    @property
    def artifact_id(self) -> str:
        return str(getattr(self.artifact, "artifact_id", "") or "")


def create_report_artifact_result(
    *,
    request: Any,
    messages: list[Any],
    ensure_deckable_chat: Callable[[list[Any]], list[Any]],
    build_chat_report_title: Callable[[list[Any]], str],
    build_report_markdown: Callable[[list[Any], str], str],
    build_report_artifact: Callable[..., Any],
    save_artifact: Callable[[Any], Any],
) -> CreatedReportArtifactResult:
    qa_pairs = ensure_deckable_chat(messages)
    title = build_chat_report_title(messages)
    template_id = str(getattr(request, "template_id", "") or "").strip()
    template_options = dict(getattr(request, "template_options", {}) or {})
    validate_delivery_template_selection(template_id, artifact_type="report")
    markdown = apply_report_template_metadata(
        build_report_markdown(messages, title),
        template_id=template_id,
        template_options=template_options,
    )
    artifact = build_report_artifact(
        session_id=str(getattr(request, "session_id", "") or ""),
        title=title,
        markdown=markdown,
        qa_pairs=qa_pairs,
        answer_group_id=str(getattr(request, "answer_group_id", "") or "").strip(),
        panel_id=str(getattr(request, "panel_id", "") or "").strip(),
        template_id=template_id,
        template_options=template_options,
    )
    save_artifact(artifact)
    return CreatedReportArtifactResult(
        artifact=artifact,
        title=title,
        markdown=markdown,
    )


def build_report_download_response(
    messages: list[Any],
    *,
    report_download_payload: Callable[..., dict[str, Any]],
    ensure_deckable_chat: Callable[[list[Any]], list[tuple[str, str]]],
    build_chat_report_title: Callable[[list[Any]], str],
    populate_chat_report_presentation: Callable[..., None],
    safe_report_filename: Callable[[str], str],
    build_download_content_disposition: Callable[[str], str],
) -> Response:
    try:
        from pptx import Presentation
        from pptx.util import Pt
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail="python-pptx is not installed. Please install it and try again.",
        ) from exc

    try:
        ensure_deckable_chat(messages)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not messages:
        raise HTTPException(status_code=400, detail="No messages were found in this session.")

    payload = report_download_payload(
        messages,
        ensure_deckable_chat=ensure_deckable_chat,
        build_chat_report_title=build_chat_report_title,
        presentation_factory=Presentation,
        body_font_size=Pt(12),
        populate_chat_report_presentation=populate_chat_report_presentation,
        safe_report_filename=safe_report_filename,
    )
    buffer = io.BytesIO()
    payload["presentation"].save(buffer)
    buffer.seek(0)
    return Response(
        content=buffer.read(),
        media_type=PPTX_MEDIA_TYPE,
        headers={
            "Content-Disposition": build_download_content_disposition(payload["filename"]),
        },
    )
