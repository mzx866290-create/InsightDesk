"""Route-level helpers for report artifact creation."""

from dataclasses import dataclass
from typing import Any, Callable

from backend.delivery_templates import validate_delivery_template_selection
from backend.helpers.deck_report_helpers import apply_report_template_metadata


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
