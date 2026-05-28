"""Deck domain models and validation helpers."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


DeckSourceMode = Literal["kb_plus_chat", "chat_only"]
DeckQualityState = Literal["supported", "weak_support", "manual"]
DeckThemeName = Literal["default", "midnight", "sunrise"]
DeckChartType = Literal["bar", "line", "pie"]


class DeckWarning(BaseModel):
    code: str
    message: str


class DeckSlideEvidenceCoverage(BaseModel):
    slide_id: str
    slide_type: str
    evidence_ref_count: int = 0
    has_evidence: bool = False
    is_coverable: bool = True
    quality_state: DeckQualityState = "weak_support"


class DeckEvidenceCoverage(BaseModel):
    total_slides: int = 0
    coverable_slide_count: int = 0
    slides_with_evidence: int = 0
    total_evidence_refs: int = 0
    coverage_ratio: float = 0.0
    unsupported_slide_ids: list[str] = Field(default_factory=list)
    slides: list[DeckSlideEvidenceCoverage] = Field(default_factory=list)


class DeckCitationValidationIssue(BaseModel):
    code: str
    message: str
    slide_id: str = ""
    block_id: str = ""
    evidence_ref_id: str = ""
    source_id: str = ""


class DeckCitationValidation(BaseModel):
    status: Literal["passed", "failed"] = "passed"
    can_export: bool = True
    issue_count: int = 0
    missing_source_ids: list[str] = Field(default_factory=list)
    missing_block_evidence_ref_ids: list[str] = Field(default_factory=list)
    issues: list[DeckCitationValidationIssue] = Field(default_factory=list)


class DeckMeta(BaseModel):
    title: str
    subtitle: str = ""
    language: str = "zh-CN"
    audience: str = "general"
    purpose: str = "briefing"
    author: str = "system"
    theme: DeckThemeName = "default"
    created_at: str
    session_id: str
    source_mode: DeckSourceMode
    generator_panel_id: str
    source_answer_group_id: str = ""
    source_panel_id: str = ""
    template_id: str = ""
    template_options: dict[str, Any] = Field(default_factory=dict)


class DeckGeneration(BaseModel):
    source: DeckSourceMode
    target_slide_count: int
    actual_slide_count: int = 0
    warnings: list[DeckWarning] = Field(default_factory=list)
    evidence_coverage: DeckEvidenceCoverage = Field(default_factory=DeckEvidenceCoverage)
    evidence_review: dict[str, Any] = Field(default_factory=dict)
    citation_validation: DeckCitationValidation | None = None


class DeckBlock(BaseModel):
    id: str
    kind: str
    role: str
    content: dict[str, Any] = Field(default_factory=dict)
    editable: bool = True


class DeckChartNormalizationReport(BaseModel):
    normalized_block_count: int = 0
    invalid_block_count: int = 0
    normalized_block_ids: list[str] = Field(default_factory=list)
    invalid_block_ids: list[str] = Field(default_factory=list)


class DeckEvidenceRef(BaseModel):
    id: str
    source_id: str
    source_title: str
    excerpt_id: str | None = None
    snippet: str = ""
    confidence: float = 0.0


class DeckSourceItem(BaseModel):
    id: str
    type: str
    title: str
    document_id: str | None = None
    uri: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeckSlideStatus(BaseModel):
    locked: bool = False
    dirty: bool = False
    review_state: str = "draft"


class DeckSlide(BaseModel):
    id: str
    type: str
    title: str
    subtitle: str = ""
    layout: str
    intent: str = ""
    speaker_notes: str = ""
    blocks: list[DeckBlock] = Field(default_factory=list)
    evidence_refs: list[DeckEvidenceRef] = Field(default_factory=list)
    quality_state: DeckQualityState = "weak_support"
    status: DeckSlideStatus = Field(default_factory=DeckSlideStatus)


class DeckSpec(BaseModel):
    version: str = "1.0"
    deck_id: str
    status: str = "draft"
    meta: DeckMeta
    generation: DeckGeneration
    slides: list[DeckSlide]
    source_registry: list[DeckSourceItem] = Field(default_factory=list)
    citation_validation: DeckCitationValidation | None = None

    def refresh_evidence_coverage(self) -> "DeckSpec":
        self.generation.evidence_coverage = build_deck_evidence_coverage(self)
        return self


_EVIDENCE_COVERAGE_EXCLUDED_SLIDE_TYPES = {"cover", "outline", "appendix_sources"}


def _is_evidence_coverable_slide(slide: DeckSlide, evidence_ref_count: int) -> bool:
    if evidence_ref_count > 0:
        return True
    return slide.type not in _EVIDENCE_COVERAGE_EXCLUDED_SLIDE_TYPES


def build_deck_evidence_coverage(deck: DeckSpec) -> DeckEvidenceCoverage:
    slide_stats: list[DeckSlideEvidenceCoverage] = []
    coverable_slide_count = 0
    slides_with_evidence = 0
    total_evidence_refs = 0
    unsupported_slide_ids: list[str] = []

    for slide in deck.slides:
        evidence_ref_count = len(slide.evidence_refs or [])
        has_evidence = evidence_ref_count > 0
        is_coverable = _is_evidence_coverable_slide(slide, evidence_ref_count)

        total_evidence_refs += evidence_ref_count
        if is_coverable:
            coverable_slide_count += 1
            if has_evidence:
                slides_with_evidence += 1
            else:
                unsupported_slide_ids.append(slide.id)

        slide_stats.append(
            DeckSlideEvidenceCoverage(
                slide_id=slide.id,
                slide_type=slide.type,
                evidence_ref_count=evidence_ref_count,
                has_evidence=has_evidence,
                is_coverable=is_coverable,
                quality_state=slide.quality_state,
            )
        )

    coverage_ratio = (
        round(slides_with_evidence / coverable_slide_count, 4)
        if coverable_slide_count
        else 0.0
    )
    return DeckEvidenceCoverage(
        total_slides=len(deck.slides),
        coverable_slide_count=coverable_slide_count,
        slides_with_evidence=slides_with_evidence,
        total_evidence_refs=total_evidence_refs,
        coverage_ratio=coverage_ratio,
        unsupported_slide_ids=unsupported_slide_ids,
        slides=slide_stats,
    )


def refresh_deck_evidence_coverage(deck: DeckSpec) -> DeckSpec:
    return deck.refresh_evidence_coverage()


def _coerce_evidence_id_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, int, float)):
        items = [value]
    elif isinstance(value, list | tuple | set):
        items = list(value)
    else:
        return []
    return [str(item).strip() for item in items if str(item or "").strip()]


def _block_bound_evidence_ref_ids(block: DeckBlock) -> list[str]:
    content = block.content if isinstance(block.content, dict) else {}
    ids = _coerce_evidence_id_list(content.get("evidence_ref_ids"))
    if ids:
        return ids
    return _coerce_evidence_id_list(content.get("evidence_refs"))


def validate_deck_citation_consistency(deck: DeckSpec) -> DeckCitationValidation:
    """Validate citation references before review/export payloads are consumed."""

    source_ids = {
        source.id.strip()
        for source in deck.source_registry
        if isinstance(source.id, str) and source.id.strip()
    }
    issues: list[DeckCitationValidationIssue] = []
    missing_source_ids: list[str] = []
    missing_block_evidence_ref_ids: list[str] = []

    for slide in deck.slides:
        slide_evidence_ids = {
            ref.id.strip()
            for ref in slide.evidence_refs
            if isinstance(ref.id, str) and ref.id.strip()
        }

        for ref in slide.evidence_refs:
            source_id = ref.source_id.strip() if isinstance(ref.source_id, str) else ""
            if source_id and source_id not in source_ids:
                missing_source_ids.append(source_id)
                issues.append(
                    DeckCitationValidationIssue(
                        code="missing_source_registry_entry",
                        message="Evidence reference points to a source_id missing from source_registry.",
                        slide_id=slide.id,
                        evidence_ref_id=ref.id,
                        source_id=source_id,
                    )
                )

        for block in slide.blocks:
            for evidence_ref_id in _block_bound_evidence_ref_ids(block):
                if evidence_ref_id in slide_evidence_ids:
                    continue
                missing_block_evidence_ref_ids.append(evidence_ref_id)
                issues.append(
                    DeckCitationValidationIssue(
                        code="missing_slide_evidence_ref",
                        message="Block evidence_ref_id is not present in the parent slide evidence_refs.",
                        slide_id=slide.id,
                        block_id=block.id,
                        evidence_ref_id=evidence_ref_id,
                    )
                )

    issue_count = len(issues)
    return DeckCitationValidation(
        status="failed" if issue_count else "passed",
        can_export=issue_count == 0,
        issue_count=issue_count,
        missing_source_ids=list(dict.fromkeys(missing_source_ids)),
        missing_block_evidence_ref_ids=list(
            dict.fromkeys(missing_block_evidence_ref_ids)
        ),
        issues=issues,
    )


__all__ = [
    "DeckBlock",
    "DeckChartNormalizationReport",
    "DeckChartType",
    "DeckCitationValidation",
    "DeckCitationValidationIssue",
    "DeckEvidenceCoverage",
    "DeckEvidenceRef",
    "DeckGeneration",
    "DeckMeta",
    "DeckQualityState",
    "DeckSlide",
    "DeckSlideEvidenceCoverage",
    "DeckSlideStatus",
    "DeckSourceItem",
    "DeckSourceMode",
    "DeckSpec",
    "DeckThemeName",
    "DeckWarning",
    "build_deck_evidence_coverage",
    "refresh_deck_evidence_coverage",
    "validate_deck_citation_consistency",
]
