"""Route-level artifact export helpers."""

import io
from typing import Any, Callable

from fastapi import HTTPException
from fastapi.responses import Response

from backend.helpers.deck_report_helpers import DeckExportGateError


REPORT_EXPORT_MEDIA_TYPES = {
    "md": "text/markdown; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
PPTX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def build_download_response(
    *,
    content: str | bytes,
    media_type: str,
    filename: str,
    build_download_content_disposition: Callable[[str], str],
) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": build_download_content_disposition(filename),
        },
    )


def report_artifact_qa_pairs(artifact: Any) -> list[tuple[str, str]]:
    raw_pairs = (
        artifact.content.get("qa_pairs")
        if isinstance(artifact.content.get("qa_pairs"), list)
        else []
    )
    return [
        (
            str(item.get("question") or "").strip(),
            str(item.get("answer") or "").strip(),
        )
        for item in raw_pairs
        if isinstance(item, dict)
        and (
            str(item.get("question") or "").strip()
            or str(item.get("answer") or "").strip()
        )
    ]


def export_report_artifact_response(
    *,
    artifact: Any,
    export_format: str,
    safe_report_filename: Callable[[str], str],
    build_download_content_disposition: Callable[[str], str],
    populate_chat_report_presentation: Callable[..., None],
) -> Response:
    normalized_format = str(export_format or "md").strip().lower() or "md"
    filename_stem = safe_report_filename(artifact.title)

    if normalized_format == "md":
        return build_download_response(
            content=str(artifact.content.get("markdown") or ""),
            media_type=REPORT_EXPORT_MEDIA_TYPES["md"],
            filename=f"{filename_stem}.md",
            build_download_content_disposition=build_download_content_disposition,
        )

    if normalized_format == "docx":
        try:
            from backend.artifact_service import export_report_to_docx
        except ImportError as exc:
            raise HTTPException(status_code=500, detail="python-docx is not installed.") from exc
        try:
            content = export_report_to_docx(artifact)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return build_download_response(
            content=content,
            media_type=REPORT_EXPORT_MEDIA_TYPES["docx"],
            filename=f"{filename_stem}.docx",
            build_download_content_disposition=build_download_content_disposition,
        )

    if normalized_format == "xlsx":
        try:
            from backend.artifact_service import export_report_to_xlsx, report_has_tables
        except ImportError as exc:
            raise HTTPException(status_code=500, detail="openpyxl is not installed.") from exc
        if not report_has_tables(artifact):
            raise HTTPException(
                status_code=400,
                detail="Report artifact has no table content to export as xlsx.",
            )
        try:
            content = export_report_to_xlsx(artifact)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return build_download_response(
            content=content,
            media_type=REPORT_EXPORT_MEDIA_TYPES["xlsx"],
            filename=f"{filename_stem}.xlsx",
            build_download_content_disposition=build_download_content_disposition,
        )

    if normalized_format != "pptx":
        raise HTTPException(
            status_code=400,
            detail="Report artifact only supports md / docx / xlsx / pptx.",
        )

    try:
        from pptx import Presentation
        from pptx.util import Pt
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="python-pptx is not installed.") from exc

    qa_pairs = report_artifact_qa_pairs(artifact)
    if not qa_pairs:
        raise HTTPException(status_code=400, detail="Report artifact has no exportable content.")

    presentation = Presentation()
    populate_chat_report_presentation(
        presentation,
        title=artifact.title,
        qa_pairs=qa_pairs,
        body_font_size=Pt(12),
    )
    buffer = io.BytesIO()
    presentation.save(buffer)
    buffer.seek(0)
    return build_download_response(
        content=buffer.read(),
        media_type=REPORT_EXPORT_MEDIA_TYPES["pptx"],
        filename=f"{filename_stem}.pptx",
        build_download_content_disposition=build_download_content_disposition,
    )


def export_deck_artifact_response(
    *,
    artifact: Any,
    export_format: str,
    get_deck: Callable[[str], Any],
    export_deck_payload: Callable[..., dict[str, Any]],
    export_deck_to_pptx: Callable[[Any], bytes],
    build_export_filename: Callable[..., str],
    build_download_content_disposition: Callable[[str], str],
    allow_unsafe_export: bool = False,
    override_reason: str = "",
) -> Response:
    if str(export_format or "pptx").strip().lower() != "pptx":
        raise HTTPException(status_code=400, detail="Deck artifact only supports pptx.")

    deck_id = str(
        getattr(artifact, "linked_resource_id", "") or artifact.content.get("deck_id") or ""
    ).strip()
    if not deck_id:
        raise HTTPException(status_code=400, detail="Deck artifact is missing deck_id.")
    try:
        deck = get_deck(deck_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Deck was not found.") from exc

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

    return build_download_response(
        content=export_payload["content"],
        media_type=PPTX_MEDIA_TYPE,
        filename=export_payload["filename"],
        build_download_content_disposition=build_download_content_disposition,
    )


def export_artifact_response(
    *,
    artifact: Any,
    export_format: str,
    get_deck: Callable[[str], Any],
    export_deck_payload: Callable[..., dict[str, Any]],
    export_deck_to_pptx: Callable[[Any], bytes],
    build_export_filename: Callable[..., str],
    build_download_content_disposition: Callable[[str], str],
    safe_report_filename: Callable[[str], str],
    populate_chat_report_presentation: Callable[..., None],
    allow_unsafe_export: bool = False,
    override_reason: str = "",
) -> Response:
    if artifact.artifact_type == "report":
        return export_report_artifact_response(
            artifact=artifact,
            export_format=export_format,
            safe_report_filename=safe_report_filename,
            build_download_content_disposition=build_download_content_disposition,
            populate_chat_report_presentation=populate_chat_report_presentation,
        )

    if artifact.artifact_type == "deck":
        return export_deck_artifact_response(
            artifact=artifact,
            export_format=export_format,
            get_deck=get_deck,
            export_deck_payload=export_deck_payload,
            export_deck_to_pptx=export_deck_to_pptx,
            build_export_filename=build_export_filename,
            build_download_content_disposition=build_download_content_disposition,
            allow_unsafe_export=allow_unsafe_export,
            override_reason=override_reason,
        )

    raise HTTPException(status_code=400, detail="Unsupported artifact type.")
