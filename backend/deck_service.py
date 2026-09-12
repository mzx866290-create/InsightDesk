"""
Deck generation, persistence, and export helpers.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from langchain_core.documents import Document
from pydantic import BaseModel, Field

from backend.core.storage_runtime import app_database_path
from backend.deck_common import (  # noqa: F401
    _FALLBACK_SECTION_TITLES,
    _FALLBACK_SLIDE_TITLES,
    DECK_THEME_PALETTES,
    _clean_text,
    _coerce_chart_number,
    _extract_qa_pairs,
    _is_failed_answer,
    _metadata_dict,
    _normalize_chart_datasets,
    _normalize_chart_labels,
    _normalize_message_text,
    _now_iso,
    _stringify_llm_content,
    _truncate,
    _truncate_multiline,
    ensure_deckable_chat,
    extract_successful_qa_pairs,
    normalize_deck_theme,
)

# Export helpers live in backend.deck_export -- the single clean copy
# (the previous inline copy was encoding-damaged). Redundant aliases keep
# these as explicit re-exports for api_server and the services proxy.
from backend.deck_export import (
    build_export_filename as build_export_filename,
)
from backend.deck_export import (
    build_report_markdown as build_report_markdown,
)
from backend.deck_export import (
    export_deck_to_pptx as export_deck_to_pptx,
)
from backend.deck_models import (
    DeckBlock,
    DeckChartNormalizationReport,
    DeckEvidenceRef,
    DeckGeneration,
    DeckMeta,
    DeckQualityState,
    DeckSlide,
    DeckSlideStatus,
    DeckSourceItem,
    DeckSourceMode,
    DeckSpec,
    DeckThemeName,
    DeckWarning,
    refresh_deck_evidence_coverage,
)
from backend.deck_models import (
    DeckCitationValidation as DeckCitationValidation,
)
from backend.deck_models import (
    DeckCitationValidationIssue as DeckCitationValidationIssue,
)
from backend.deck_models import (
    DeckEvidenceCoverage as DeckEvidenceCoverage,
)
from backend.deck_models import (
    DeckSlideEvidenceCoverage as DeckSlideEvidenceCoverage,
)
from backend.deck_models import (
    build_deck_evidence_coverage as build_deck_evidence_coverage,
)
from backend.deck_models import (
    validate_deck_citation_consistency as validate_deck_citation_consistency,
)
from backend.doc_pipeline import DocPipeline
from backend.services.agent_core import get_llm
from backend.stores.sqlite_runtime import connect_sqlite

_DASHBOARD_CARD_BLOCK_RE = re.compile(
    r":::dashboard-card\s*\n([\s\S]*?)\n:::",
    flags=re.IGNORECASE,
)


class OutlineSlidePlan(BaseModel):
    title: str
    objective: str
    section: str
    evidence_source_ids: list[str] = Field(default_factory=list)


class OutlinePlan(BaseModel):
    title: str
    subtitle: str
    core_message: str
    sections: list[str]
    content_slides: list[OutlineSlidePlan]


class DraftedContentSlide(BaseModel):
    title: str
    subtitle: str = ""
    key_points: list[str] = Field(default_factory=list)
    speaker_notes: str = ""
    evidence_excerpt_ids: list[str] = Field(default_factory=list)
    evidence_source_ids: list[str] = Field(default_factory=list)
    quality_state: DeckQualityState = "weak_support"


class DraftedSlideBundle(BaseModel):
    content_slides: list[DraftedContentSlide]


class SourceExcerpt(BaseModel):
    id: str
    source_id: str
    source_title: str
    snippet: str
    confidence: float = 0.85


@dataclass
class SourcePack:
    title_hint: str
    source_mode: DeckSourceMode
    qa_pairs: list[tuple[str, str]]
    chat_notes: list[str]
    excerpts: list[SourceExcerpt]
    source_registry: list[DeckSourceItem]
    warnings: list[DeckWarning]


def _strip_dashboard_card_blocks(text: Any) -> str:
    normalized = _normalize_message_text(text)
    if not normalized:
        return ""
    stripped = _DASHBOARD_CARD_BLOCK_RE.sub("", normalized)
    stripped = re.sub(r"\n{3,}", "\n\n", stripped)
    return stripped.strip()


def _extract_dashboard_card_payloads(text: Any) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    normalized = _normalize_message_text(text)
    if not normalized:
        return payloads

    for match in _DASHBOARD_CARD_BLOCK_RE.finditer(normalized):
        raw_payload = match.group(1).strip()
        if not raw_payload:
            continue
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def _chart_summary_from_answer(answer: Any) -> str:
    summaries: list[str] = []
    for payload in _extract_dashboard_card_payloads(answer):
        charts = payload.get("charts")
        if not isinstance(charts, list):
            continue
        for chart in charts:
            if not isinstance(chart, dict):
                continue
            title = _clean_text(chart.get("title"))
            chart_type = _clean_text(chart.get("type")).lower()
            if chart_type in {"bar", "line", "pie"}:
                summaries.append(title or f"{chart_type} 图表")
    if not summaries:
        return ""
    return "包含图表: " + " / ".join(summaries[:3])


def _answer_plaintext(answer: Any) -> str:
    stripped = _strip_dashboard_card_blocks(answer)
    if stripped:
        return stripped
    return _chart_summary_from_answer(answer)


def _build_chart_block(
    chart: dict[str, Any],
    *,
    fallback_title: str,
    block_index: int,
) -> DeckBlock | None:
    chart_data = chart.get("chart_data")
    if not isinstance(chart_data, dict):
        return None

    raw_type = _clean_text(chart_data.get("type") or chart.get("type")).lower()
    if raw_type not in {"bar", "line", "pie"}:
        return None

    labels = _normalize_chart_labels(chart_data.get("labels"))
    datasets = _normalize_chart_datasets(chart_data.get("datasets"), len(labels))
    if not datasets:
        return None

    if not labels:
        labels = [f"类别 {index + 1}" for index in range(len(datasets[0]["data"]))]
        datasets = _normalize_chart_datasets(chart_data.get("datasets"), len(labels))
        if not datasets:
            return None

    return DeckBlock(
        id=f"block_chart_{block_index}_{uuid.uuid4().hex[:6]}",
        kind="chart",
        role="dashboard_chart",
        content={
            "title": _truncate(_clean_text(chart.get("title")) or fallback_title, 48),
            "description": _truncate(_clean_text(chart.get("description")), 120),
            "chart_type": raw_type,
            "labels": labels[:12],
            "datasets": [
                {
                    "label": _truncate(item["label"], 32),
                    "data": item["data"][:12],
                }
                for item in datasets[:4]
            ],
        },
        editable=False,
    )


def normalize_deck_chart_block(block: DeckBlock) -> tuple[DeckBlock, str]:
    """Normalize chart block payloads into the export/frontend contract."""

    if block.kind != "chart":
        return block, "skipped"

    content = block.content if isinstance(block.content, dict) else {}
    raw_type = _clean_text(content.get("chart_type") or content.get("type")).lower()
    if raw_type not in {"bar", "line", "pie"}:
        return (
            block.model_copy(
                update={
                    "content": {
                        **content,
                        "normalization_status": "invalid",
                        "normalization_issues": ["unsupported_chart_type"],
                    }
                },
                deep=True,
            ),
            "invalid",
        )

    labels = _normalize_chart_labels(content.get("labels"))
    datasets = _normalize_chart_datasets(content.get("datasets"), len(labels))
    if not datasets:
        return (
            block.model_copy(
                update={
                    "content": {
                        **content,
                        "chart_type": raw_type,
                        "normalization_status": "invalid",
                        "normalization_issues": ["missing_or_invalid_datasets"],
                    }
                },
                deep=True,
            ),
            "invalid",
        )

    if not labels:
        labels = [f"类别 {index + 1}" for index in range(len(datasets[0]["data"]))]
        datasets = _normalize_chart_datasets(content.get("datasets"), len(labels))
        if not datasets:
            return (
                block.model_copy(
                    update={
                        "content": {
                            **content,
                            "chart_type": raw_type,
                            "normalization_status": "invalid",
                            "normalization_issues": ["missing_or_invalid_datasets"],
                        }
                    },
                    deep=True,
                ),
                "invalid",
            )

    normalized_content = {
        **content,
        "title": _truncate(_clean_text(content.get("title")) or "数据图表", 48),
        "description": _truncate(_clean_text(content.get("description")), 120),
        "chart_type": raw_type,
        "labels": labels[:12],
        "datasets": [
            {
                "label": _truncate(item["label"], 32),
                "data": item["data"][:12],
            }
            for item in datasets[:4]
        ],
        "normalization_status": "normalized",
        "normalization_version": "chart-block-v1",
    }
    normalized_content.pop("normalization_issues", None)
    return block.model_copy(update={"content": normalized_content}, deep=True), "normalized"


def normalize_deck_chart_blocks(deck: DeckSpec) -> DeckChartNormalizationReport:
    report = DeckChartNormalizationReport()
    for slide in deck.slides:
        next_blocks: list[DeckBlock] = []
        for block in slide.blocks:
            normalized_block, status = normalize_deck_chart_block(block)
            next_blocks.append(normalized_block)
            if status == "normalized":
                report.normalized_block_count += 1
                report.normalized_block_ids.append(block.id)
            elif status == "invalid":
                report.invalid_block_count += 1
                report.invalid_block_ids.append(block.id)
        slide.blocks = next_blocks
    return report


def _extract_dashboard_chart_blocks(answer: Any, limit: int = 1) -> list[DeckBlock]:
    blocks: list[DeckBlock] = []
    for payload in _extract_dashboard_card_payloads(answer):
        charts = payload.get("charts")
        if not isinstance(charts, list):
            continue
        fallback_title = _clean_text(payload.get("title")) or "数据图表"
        for chart in charts:
            if not isinstance(chart, dict):
                continue
            block = _build_chart_block(
                chart,
                fallback_title=fallback_title,
                block_index=len(blocks) + 1,
            )
            if block is None:
                continue
            blocks.append(block)
            if len(blocks) >= limit:
                return blocks
    return blocks



def _extract_json_payload(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
        candidate = re.sub(r"\s*```$", "", candidate)

    decoder = json.JSONDecoder()
    try:
        payload, _ = decoder.raw_decode(candidate)
        if not isinstance(payload, dict):
            raise ValueError("LLM JSON payload must be an object.")
        return payload
    except Exception:
        for start_char in ("{", "["):
            start = candidate.find(start_char)
            if start == -1:
                continue
            try:
                payload, _ = decoder.raw_decode(candidate[start:])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        raise


def _is_authentication_failure(exc: Exception) -> bool:
    message = str(exc).lower()
    markers = (
        "authenticationerror",
        "401",
        "invalid api key",
        "invalid token",
        "unauthorized",
        "invalid credential",
        "invalid_api_key",
    )
    return any(marker in message for marker in markers)


def _local_ollama_panel_config(panel_config: Any) -> Any:
    fallback_model = os.getenv("OLLAMA_MODEL", "qwen3.5:4b").strip() or "qwen3.5:4b"
    fallback_base_url = (
        os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
        or "http://localhost:11434"
    )
    return SimpleNamespace(
        panel_id=getattr(panel_config, "panel_id", "panel"),
        provider="ollama",
        connection_type="ollama",
        model=fallback_model,
        base_url=fallback_base_url,
        api_key="",
        temperature=float(getattr(panel_config, "temperature", 0.3) or 0.3),
    )


async def _invoke_json(llm, prompt: str) -> dict[str, Any]:
    response = await llm.ainvoke(prompt)
    text = _stringify_llm_content(response.content)
    try:
        return _extract_json_payload(text)
    except Exception:
        repair_prompt = (
            "请把下面内容修正为合法 JSON。不要补充信息，不要输出解释，只输出 JSON。\n\n"
            f"{text}"
        )
        repaired = await llm.ainvoke(repair_prompt)
        repaired_text = _stringify_llm_content(repaired.content)
        return _extract_json_payload(repaired_text)


def _build_title_hint(session_id: str, messages: list[Any]) -> str:
    for message in messages:
        content = _clean_text(getattr(message, "content", ""))
        if (
            getattr(message, "__class__", type(message)).__name__ == "HumanMessage"
            and content
        ):
            return _truncate(content, 60)
    return f"Deck {session_id[:8]}"


def _first_non_empty(*values: Any) -> str:
    for value in values:
        cleaned = _clean_text(value)
        if cleaned:
            return cleaned
    return ""


def _default_sections() -> list[str]:
    return list(_FALLBACK_SECTION_TITLES)


def _fallback_slide_title(index: int) -> str:
    if index < len(_FALLBACK_SLIDE_TITLES):
        return _FALLBACK_SLIDE_TITLES[index]
    return f"核心主题 {index + 1}"


def _extract_answer_points(answer: str, limit: int = 4) -> list[str]:
    clean_answer = _answer_plaintext(answer)
    answer = clean_answer
    chunks = [
        _truncate(part, 72)
        for part in re.split(r"[銆傦紒锛??]\s+|\n+", answer)
        if _clean_text(part)
    ]
    deduped: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        if chunk in seen:
            continue
        seen.add(chunk)
        deduped.append(chunk)
        if len(deduped) >= limit:
            break
    return deduped


def _fallback_outline(
    pack: SourcePack,
    content_slide_count: int,
) -> OutlinePlan:
    title = _truncate(pack.title_hint, 56)
    subtitle = (
        "基于知识库检索与成功对话整理"
        if pack.source_mode == "kb_plus_chat"
        else "基于成功对话整理"
    )
    core_message = _truncate(
        _first_non_empty(
            _answer_plaintext(pack.qa_pairs[-1][1]) if pack.qa_pairs else "",
            subtitle,
        ),
        120,
    )
    sections = _default_sections()
    content_slides: list[OutlineSlidePlan] = []

    for index in range(content_slide_count):
        question, answer = pack.qa_pairs[min(index, len(pack.qa_pairs) - 1)]
        plain_answer = _answer_plaintext(answer)
        evidence_source_ids: list[str] = []
        if pack.source_mode == "kb_plus_chat" and pack.excerpts:
            evidence_source_ids = [
                pack.excerpts[min(index, len(pack.excerpts) - 1)].source_id
            ]

        content_slides.append(
            OutlineSlidePlan(
                title=_fallback_slide_title(index),
                objective=_truncate(_first_non_empty(plain_answer, question), 100),
                section=sections[min(index, len(sections) - 1)],
                evidence_source_ids=evidence_source_ids,
            )
        )

    return OutlinePlan(
        title=title,
        subtitle=subtitle,
        core_message=core_message or "Core conclusion based on the current conversation.",
        sections=sections,
        content_slides=content_slides,
    )


def _fallback_content_bundle(
    pack: SourcePack,
    outline: OutlinePlan,
) -> DraftedSlideBundle:
    content_slides: list[DraftedContentSlide] = []

    for index, plan in enumerate(outline.content_slides):
        question, answer = pack.qa_pairs[min(index, len(pack.qa_pairs) - 1)]
        plain_answer = _answer_plaintext(answer)
        points = _extract_answer_points(answer)
        if not points:
            points = [
                _truncate(_first_non_empty(plain_answer, question, plan.objective), 72)
            ]

        evidence_excerpt_ids: list[str] = []
        evidence_source_ids: list[str] = []
        quality_state: DeckQualityState = "manual"

        if pack.excerpts:
            excerpt = pack.excerpts[min(index, len(pack.excerpts) - 1)]
            evidence_excerpt_ids = [excerpt.id]
            evidence_source_ids = [excerpt.source_id]
            quality_state = "supported"

        content_slides.append(
            DraftedContentSlide(
                title=plan.title or _fallback_slide_title(index),
                subtitle=_truncate(plan.objective, 72),
                key_points=points[:5],
                speaker_notes=_truncate(
                    _first_non_empty(plain_answer, question, plan.objective),
                    180,
                ),
                evidence_excerpt_ids=evidence_excerpt_ids,
                evidence_source_ids=evidence_source_ids,
                quality_state=quality_state,
            )
        )

    return DraftedSlideBundle(content_slides=content_slides)


def _dedupe_docs(docs: list[Document]) -> list[Document]:
    deduped: list[Document] = []
    seen: set[str] = set()
    for doc in docs:
        snippet = _truncate(doc.page_content, 180)
        key = f"{doc.metadata.get('source', 'unknown')}::{snippet}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(doc)
    return deduped


def _build_chat_only_source_pack(
    title_hint: str,
    qa_pairs: list[tuple[str, str]],
    chat_notes: list[str],
    warnings: list[DeckWarning],
    chat_only_message: str,
    excerpts: list[SourceExcerpt] | None = None,
    source_registry: list[DeckSourceItem] | None = None,
) -> SourcePack:
    return SourcePack(
        title_hint=title_hint,
        source_mode="chat_only",
        qa_pairs=qa_pairs,
        chat_notes=chat_notes,
        excerpts=excerpts or [],
        source_registry=source_registry or [],
        warnings=[
            *warnings,
            DeckWarning(
                code="chat_only_mode",
                message=chat_only_message,
            ),
        ],
    )


def _message_metadata(message: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for attr in ("additional_kwargs", "response_metadata"):
        value = getattr(message, attr, None)
        if isinstance(value, dict):
            metadata.update(value)
    return metadata


def _source_identity(source: dict[str, Any], fallback: str) -> str:
    return _first_non_empty(
        source.get("url"),
        source.get("uri"),
        source.get("source"),
        source.get("title"),
        fallback,
    )


def _source_title(source: dict[str, Any], fallback: str) -> str:
    return _truncate(
        _first_non_empty(
            source.get("title"),
            source.get("name"),
            source.get("domain"),
            source.get("url"),
            source.get("uri"),
            fallback,
        ),
        96,
    )


def _upsert_report_source(
    source: dict[str, Any],
    *,
    source_id_map: dict[str, str],
    source_registry: list[DeckSourceItem],
    fallback_title: str,
) -> tuple[str, str]:
    identity = _source_identity(source, fallback_title)
    source_id = source_id_map.get(identity)
    if source_id:
        existing = next(item for item in source_registry if item.id == source_id)
        return source_id, existing.title

    source_id = f"src_report_{len(source_id_map) + 1}"
    source_id_map[identity] = source_id
    title = _source_title(source, fallback_title)
    uri = _first_non_empty(source.get("url"), source.get("uri"), source.get("source"))
    source_registry.append(
        DeckSourceItem(
            id=source_id,
            type=_first_non_empty(source.get("type"), "web"),
            title=title,
            document_id=_first_non_empty(source.get("document_id"), source.get("doc_id"))
            or None,
            uri=uri or None,
            metadata={
                key: value
                for key, value in source.items()
                if key not in {"title", "name", "url", "uri", "source", "snippet"}
            },
        )
    )
    return source_id, title


def _extract_report_evidence_from_messages(
    messages: list[Any],
) -> tuple[list[SourceExcerpt], list[DeckSourceItem]]:
    source_registry: list[DeckSourceItem] = []
    excerpts: list[SourceExcerpt] = []
    source_id_map: dict[str, str] = {}

    for message in messages:
        if getattr(message, "__class__", type(message)).__name__ != "AIMessage":
            continue

        metadata = _message_metadata(message)
        raw_sources = metadata.get("sources")
        if isinstance(raw_sources, list):
            for source_index, raw_source in enumerate(raw_sources, start=1):
                source = _metadata_dict(raw_source)
                if not source:
                    continue
                source_id, source_title = _upsert_report_source(
                    source,
                    source_id_map=source_id_map,
                    source_registry=source_registry,
                    fallback_title=f"Report Source {source_index}",
                )
                snippet = _truncate(
                    _first_non_empty(
                        source.get("snippet"),
                        source.get("excerpt"),
                        source.get("summary"),
                        source.get("selection_reason"),
                    ),
                    260,
                )
                if snippet:
                    excerpts.append(
                        SourceExcerpt(
                            id=f"ext_report_{len(excerpts) + 1}",
                            source_id=source_id,
                            source_title=source_title,
                            snippet=snippet,
                            confidence=0.82,
                        )
                    )

        raw_chains = metadata.get("claim_evidence_chains")
        if not isinstance(raw_chains, list):
            continue
        for chain_index, raw_chain in enumerate(raw_chains, start=1):
            chain = _metadata_dict(raw_chain)
            chain_sources = chain.get("sources")
            if not isinstance(chain_sources, list):
                continue
            claim_text = _first_non_empty(chain.get("claim_text"), chain.get("claim"))
            verification_note = _first_non_empty(chain.get("verification_note"))
            strength = _clean_text(chain.get("evidence_strength")).lower()
            confidence = 0.9 if strength == "high" else 0.78 if strength == "medium" else 0.65
            for chain_source_index, raw_source in enumerate(chain_sources, start=1):
                source = _metadata_dict(raw_source)
                if not source:
                    continue
                source_id, source_title = _upsert_report_source(
                    source,
                    source_id_map=source_id_map,
                    source_registry=source_registry,
                    fallback_title=f"Claim Source {chain_index}.{chain_source_index}",
                )
                snippet = _truncate(_first_non_empty(claim_text, verification_note), 260)
                if snippet:
                    excerpts.append(
                        SourceExcerpt(
                            id=f"ext_report_{len(excerpts) + 1}",
                            source_id=source_id,
                            source_title=source_title,
                            snippet=snippet,
                            confidence=confidence,
                        )
                    )

    return excerpts[:12], source_registry[:12]


def _build_source_pack(
    session_id: str,
    messages: list[Any],
    knowledge_base_enabled: bool,
    vector_store_path: str | None,
    target_slide_count: int,
) -> SourcePack:
    qa_pairs = ensure_deckable_chat(messages)
    warnings: list[DeckWarning] = []
    title_hint = _build_title_hint(session_id, messages)
    chat_notes = [
        f"Question: {_truncate(question, 80)}\nAnswer summary: {_truncate(answer, 180)}"
        for question, answer in qa_pairs[-4:]
    ]

    chat_notes = [
        f"Question: {_truncate(question, 80)}\nAnswer summary: {_truncate(_answer_plaintext(answer), 180)}"
        for question, answer in qa_pairs[-4:]
    ]

    report_excerpts, report_source_registry = _extract_report_evidence_from_messages(
        messages
    )

    if not knowledge_base_enabled:
        return _build_chat_only_source_pack(
            title_hint=title_hint,
            qa_pairs=qa_pairs,
            chat_notes=chat_notes,
            warnings=warnings,
            chat_only_message="Knowledge base is disabled; the deck will be generated from successful chat answers only.",
            excerpts=report_excerpts,
            source_registry=report_source_registry,
        )

    default_store_path = os.getenv("VECTOR_STORE_PATH", "./vector_store")
    candidate_paths: list[str] = []
    if vector_store_path:
        candidate_paths.append(vector_store_path)
    if default_store_path not in candidate_paths:
        candidate_paths.append(default_store_path)

    pipeline = None
    resolved_store_path = None
    for path in candidate_paths:
        current_pipeline = DocPipeline(vector_store_path=path)
        if current_pipeline.load_store():
            pipeline = current_pipeline
            resolved_store_path = path
            break

    if pipeline is None:
        warnings.append(
            DeckWarning(
                code="kb_unavailable_fallback",
                message="Knowledge base is unavailable, so the deck will be generated from answer content only.",
            )
        )
        return _build_chat_only_source_pack(
            title_hint=title_hint,
            qa_pairs=qa_pairs,
            chat_notes=chat_notes,
            warnings=warnings,
            chat_only_message="The deck will be generated from successful chat answers only; evidence strength is lower than KB mode.",
            excerpts=report_excerpts,
            source_registry=report_source_registry,
        )

    if not vector_store_path:
        warnings.append(
            DeckWarning(
                code="kb_fallback_default",
                message="No role-specific knowledge base is bound; falling back to the default knowledge base.",
            )
        )
    elif resolved_store_path != vector_store_path:
        warnings.append(
            DeckWarning(
                code="kb_fallback_default",
                message="The bound knowledge base failed to load; falling back to the default knowledge base.",
            )
        )

    first_question = qa_pairs[0][0]
    last_answer = qa_pairs[-1][1]
    last_answer = _answer_plaintext(last_answer)
    queries = [
        title_hint,
        _truncate(first_question, 120),
        _truncate(last_answer, 200),
    ]

    collected: list[Document] = []
    for query in queries:
        if not query:
            continue
        collected.extend(pipeline.search_with_rerank(query, k=4, fetch_k=12))

    docs = _dedupe_docs(collected)[:8]
    if len(docs) < 3:
        warnings.append(
            DeckWarning(
                code="kb_insufficient_material_fallback",
                message="Knowledge base retrieval returned insufficient material; falling back to answer content only.",
            )
        )
        return _build_chat_only_source_pack(
            title_hint=title_hint,
            qa_pairs=qa_pairs,
            chat_notes=chat_notes,
            warnings=warnings,
            chat_only_message="The deck will be generated from successful chat answers only; evidence strength is lower than KB mode.",
            excerpts=report_excerpts,
            source_registry=report_source_registry,
        )

    source_id_map: dict[str, str] = {}
    source_registry: list[DeckSourceItem] = []
    excerpts: list[SourceExcerpt] = []

    for index, doc in enumerate(docs, start=1):
        source_title = str(doc.metadata.get("source", f"来源 {index}"))
        source_id = source_id_map.get(source_title)
        if not source_id:
            source_id = f"src_{len(source_id_map) + 1}"
            source_id_map[source_title] = source_id
            source_registry.append(
                DeckSourceItem(
                    id=source_id,
                    type="doc",
                    title=source_title,
                    document_id=str(doc.metadata.get("doc_id") or ""),
                    uri=str(doc.metadata.get("source") or ""),
                    metadata={
                        "page": doc.metadata.get("page"),
                        "chunk_index": doc.metadata.get("chunk_index"),
                    },
                )
            )
        excerpts.append(
            SourceExcerpt(
                id=f"ext_{index}",
                source_id=source_id,
                source_title=source_title,
                snippet=_truncate(doc.page_content, 260),
                confidence=0.88,
            )
        )

    if len(source_registry) < 2:
        warnings.append(
            DeckWarning(
                code="kb_insufficient_source_coverage",
                message="Knowledge base retrieval has insufficient source coverage; falling back to answer content only.",
            )
        )
        return _build_chat_only_source_pack(
            title_hint=title_hint,
            qa_pairs=qa_pairs,
            chat_notes=chat_notes,
            warnings=warnings,
            chat_only_message="The deck will be generated from successful chat answers only; evidence strength is lower than KB mode.",
            excerpts=report_excerpts,
            source_registry=report_source_registry,
        )

    if len(excerpts) < target_slide_count - 2:
        warnings.append(
            DeckWarning(
                code="evidence_sparse",
                message="Knowledge base evidence is sparse; slide count may be lower than requested.",
            )
        )

    return SourcePack(
        title_hint=title_hint,
        source_mode="kb_plus_chat",
        qa_pairs=qa_pairs,
        chat_notes=chat_notes,
        excerpts=excerpts,
        source_registry=source_registry,
        warnings=warnings,
    )


def _decide_content_slide_count(pack: SourcePack, target_slide_count: int) -> int:
    if pack.source_mode == "kb_plus_chat":
        desired = max(2, min(target_slide_count - 3, 5))
        evidence_bound = max(2, min(5, len(pack.excerpts) // 2 + 1))
        return min(desired, evidence_bound)
    desired = max(2, min(target_slide_count - 2, 4))
    chat_bound = max(2, min(4, len(pack.qa_pairs) + 1))
    return min(desired, chat_bound)


def _serialize_source_pack(pack: SourcePack) -> str:
    recent_qa_pairs = "\n\n---\n\n".join(
        (
            f"Question: {_truncate(question, 120)}\n"
            f"回答原文: \n{_truncate_multiline(answer, 5000 if pack.source_mode == 'chat_only' else 2400)}"
        )
        for question, answer in pack.qa_pairs[-2:]
    )
    if pack.source_mode == "kb_plus_chat":
        excerpts = "\n".join(
            f"- {excerpt.id} | {excerpt.source_id} | {excerpt.source_title}: {excerpt.snippet}"
            for excerpt in pack.excerpts
        )
        sources = "\n".join(
            f"- {source.id}: {source.title}" for source in pack.source_registry
        )
        return (
            f"成功问答摘要:\n{chr(10).join(pack.chat_notes)}\n\n"
            f"最近成功问答原文\n{recent_qa_pairs}\n\n"
            f"来源清单:\n{sources}\n\n"
            f"知识库片段\n{excerpts}"
        )
    if pack.excerpts:
        excerpts = "\n".join(
            f"- {excerpt.id} | {excerpt.source_id} | {excerpt.source_title}: {excerpt.snippet}"
            for excerpt in pack.excerpts
        )
        sources = "\n".join(
            f"- {source.id}: {source.title}" for source in pack.source_registry
        )
        return (
            "最近成功问答原文\n"
            f"{recent_qa_pairs}\n\n"
            f"报告来源清单:\n{sources}\n\n"
            f"报告证据片段:\n{excerpts}"
        )
    return "最近成功问答原文\n" + recent_qa_pairs


async def _generate_outline(
    llm,
    pack: SourcePack,
    target_slide_count: int,
    content_slide_count: int,
    system_prompt: str | None,
) -> OutlinePlan:
    evidence_rule = (
        "Each content slide must choose 1-2 available source IDs in evidence_source_ids."
        if pack.source_mode == "kb_plus_chat" or pack.excerpts
        else "Current mode has no structured evidence; return empty evidence_source_ids."
    )
    structure_rule = (
        "Use the Q&A summary and knowledge base evidence to build a formal briefing structure."
        if pack.source_mode == "kb_plus_chat"
        else "Reuse the original answer structure and do not invent unsupported conclusions."
    )
    prompt = f"""
你是一个专业的中文商业演示文稿策划助手。请基于给定材料规划一个 PPT 大纲。

硬性要求：
1. 只输出 JSON，不要输出解释。
2. 不要使用 Q1、Q2、Part 这类问答标题。
3. 总体采用“主题页”结构，而不是复述聊天记录。
4. 内容页数量必须是 {content_slide_count} 页。
5. section 数量控制在 3-5 个。
6. {evidence_rule}
7. {structure_rule}
8. 标题必须像正式汇报标题，不要直接把用户原问原样拿来当页标题。
9. 页数策略是宁少勿滥，不要填充空话。

返回 JSON Schema：
{{
  "title": "演示稿总标题",
  "subtitle": "副标题",
  "core_message": "一句话核心结论",
  "sections": ["章节1", "章节2", "章节3"],
  "content_slides": [
    {{
      "title": "主题页标题",
      "objective": "本页要说明什么",
      "section": "所属章节",
      "evidence_source_ids": ["src_1"]
    }}
  ]
}}

上下文补充：
- source_mode: {pack.source_mode}
- 目标总页数: {target_slide_count}
- 内容页数: {content_slide_count}
- 标题提示: {pack.title_hint}
- Role context: {system_prompt or "None"}

材料：
{_serialize_source_pack(pack)}
"""

    payload = await _invoke_json(llm, prompt)
    try:
        return OutlinePlan.model_validate(payload)
    except Exception:
        return _fallback_outline(pack, content_slide_count)


async def _generate_content_slides(
    llm,
    pack: SourcePack,
    outline: OutlinePlan,
    system_prompt: str | None,
) -> DraftedSlideBundle:
    evidence_rule = (
        "Each content slide must choose at least one available evidence_excerpt_id and use quality_state=supported."
        if pack.source_mode == "kb_plus_chat" or pack.excerpts
        else "Current mode has no structured evidence; return empty evidence fields and use quality_state=manual."
    )
    fidelity_rule = (
        "Combine evidence and answer content into concise briefing-ready slide language."
        if pack.source_mode == "kb_plus_chat"
        else "Reuse the original answer headings, order, and key points when possible."
    )
    prompt = f"""
你是一个专业的中文 PPT 内容撰写助手。请把下面的大纲扩展成内容页。

硬性要求：
1. 只输出 JSON，不要输出解释。
2. 只生成内容页，不生成封面、目录、附录。
3. 标题不能写成 Q1、Part 1 这种问答形式。
4. 每页 key_points 保持 3-5 条，每条一句话。
5. speaker_notes 用 1-2 句话提示讲述重点。
6. {evidence_rule}
7. {fidelity_rule}
8. 不要抄用户问题，不要注水。

返回 JSON Schema：
{{
  "content_slides": [
    {{
      "title": "主题页标题",
      "subtitle": "简短副标题",
      "key_points": ["要点1", "要点2", "要点3"],
      "speaker_notes": "讲述提示",
      "evidence_excerpt_ids": ["ext_1"],
      "evidence_source_ids": ["src_1"],
      "quality_state": "supported"
    }}
  ]
}}

Role context: {system_prompt or "None"}

大纲：
{outline.model_dump_json(indent=2, ensure_ascii=False)}

材料：
{_serialize_source_pack(pack)}
"""

    payload = await _invoke_json(llm, prompt)
    try:
        return DraftedSlideBundle.model_validate(payload)
    except Exception:
        return _fallback_content_bundle(pack, outline)


def _sanitize_slide_title(title: str, fallback: str) -> str:
    cleaned = _clean_text(title)
    cleaned = re.sub(r"^Q\d+[:：\-]\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"^Part\s*\d+[:：\-]?\s*", "", cleaned, flags=re.I)
    cleaned = cleaned.strip(" -:")
    return _truncate(cleaned or fallback, 48)


def _block_evidence_binding_content(
    content: dict[str, Any],
    evidence_refs: list[DeckEvidenceRef] | None = None,
) -> dict[str, Any]:
    refs = list(evidence_refs or [])
    if not refs:
        return content

    bound_content = dict(content)
    bound_content.setdefault("evidence_ref_ids", [ref.id for ref in refs if ref.id])
    bound_content.setdefault(
        "evidence_source_ids",
        list(dict.fromkeys(ref.source_id for ref in refs if ref.source_id)),
    )
    excerpt_ids = [ref.excerpt_id for ref in refs if ref.excerpt_id]
    if excerpt_ids:
        bound_content.setdefault("evidence_excerpt_ids", excerpt_ids)
    return bound_content


def _build_blocks(
    points: list[str],
    fallback: str,
    evidence_refs: list[DeckEvidenceRef] | None = None,
) -> list[DeckBlock]:
    clean_points = [_truncate(point, 72) for point in points if _clean_text(point)]
    if clean_points:
        return [
            DeckBlock(
                id=f"block_{uuid.uuid4().hex[:8]}",
                kind="bullet_list",
                role="main_points",
                content=_block_evidence_binding_content(
                    {"items": clean_points[:5]},
                    evidence_refs,
                ),
            )
        ]
    return [
        DeckBlock(
            id=f"block_{uuid.uuid4().hex[:8]}",
            kind="paragraph",
            role="summary",
            content=_block_evidence_binding_content(
                {"text": _truncate(fallback, 220)},
                evidence_refs,
            ),
        )
    ]


def _pick_evidence_refs(
    slide: DraftedContentSlide,
    pack: SourcePack,
) -> list[DeckEvidenceRef]:
    excerpt_map = {excerpt.id: excerpt for excerpt in pack.excerpts}
    source_map = {source.id: source for source in pack.source_registry}
    refs: list[DeckEvidenceRef] = []

    for excerpt_id in slide.evidence_excerpt_ids:
        excerpt = excerpt_map.get(excerpt_id)
        if not excerpt:
            continue
        refs.append(
            DeckEvidenceRef(
                id=f"ev_{uuid.uuid4().hex[:8]}",
                source_id=excerpt.source_id,
                source_title=excerpt.source_title,
                excerpt_id=excerpt.id,
                snippet=excerpt.snippet,
                confidence=excerpt.confidence,
            )
        )

    if refs:
        return refs[:2]

    for source_id in slide.evidence_source_ids:
        if source_id not in source_map:
            continue
        excerpt = next(
            (item for item in pack.excerpts if item.source_id == source_id), None
        )
        if excerpt is None:
            continue
        refs.append(
            DeckEvidenceRef(
                id=f"ev_{uuid.uuid4().hex[:8]}",
                source_id=excerpt.source_id,
                source_title=excerpt.source_title,
                excerpt_id=excerpt.id,
                snippet=excerpt.snippet,
                confidence=excerpt.confidence,
            )
        )
        if refs:
            return refs[:2]

    if pack.excerpts:
        excerpt = pack.excerpts[0]
        return [
            DeckEvidenceRef(
                id=f"ev_{uuid.uuid4().hex[:8]}",
                source_id=excerpt.source_id,
                source_title=excerpt.source_title,
                excerpt_id=excerpt.id,
                snippet=excerpt.snippet,
                confidence=excerpt.confidence,
            )
        ]

    return []


def _resolve_quality_state(
    source_mode: DeckSourceMode,
    drafted_slide: DraftedContentSlide,
    evidence_refs: list[DeckEvidenceRef],
) -> DeckQualityState:
    if evidence_refs:
        return "supported"
    if source_mode == "chat_only":
        return "manual"
    if drafted_slide.quality_state in {"supported", "weak_support", "manual"}:
        return drafted_slide.quality_state
    return "weak_support"


def _appendix_source_items(source_registry: list[DeckSourceItem]) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for source in source_registry:
        title = _clean_text(source.title)
        if not title or title in seen:
            continue
        items.append(title)
        seen.add(title)
    return items


def _existing_appendix_source_items(slide: DeckSlide) -> list[str]:
    items: list[str] = []
    for block in slide.blocks:
        if block.kind != "bullet_list" or block.role != "sources":
            continue
        raw_items = block.content.get("items")
        if not isinstance(raw_items, list):
            continue
        for item in raw_items:
            cleaned = _clean_text(item)
            if cleaned:
                items.append(cleaned)
    return items


def _merge_appendix_source_items(
    source_registry: list[DeckSourceItem],
    existing_items: list[str] | None = None,
) -> list[str]:
    items = _appendix_source_items(source_registry)
    seen = set(items)
    for item in existing_items or []:
        cleaned = _clean_text(item)
        if not cleaned or cleaned in seen:
            continue
        items.append(cleaned)
        seen.add(cleaned)
    return items


def _build_appendix_slide(
    source_registry: list[DeckSourceItem],
    existing_items: list[str] | None = None,
) -> DeckSlide:
    items = _merge_appendix_source_items(source_registry, existing_items)
    return DeckSlide(
        id="slide_appendix_sources",
        type="appendix_sources",
        title="Appendix: Sources",
        subtitle="Sources cited by this deck",
        layout="title-bullets",
        intent="appendix_sources",
        speaker_notes="Appendix slide for source review.",
        blocks=[
            DeckBlock(
                id="block_appendix_sources",
                kind="bullet_list",
                role="sources",
                content={"items": items},
            )
        ],
        evidence_refs=[],
        quality_state="supported",
        status=DeckSlideStatus(review_state="draft"),
    )


def _source_identity_key(source: DeckSourceItem) -> str:
    uri = _clean_text(source.uri).lower()
    if uri:
        return f"uri:{uri}"
    document_id = _clean_text(source.document_id).lower()
    if document_id:
        return f"document:{document_id}"
    title = _clean_text(source.title).lower()
    if title:
        return f"title:{title}"
    return ""


def _source_items_match(left: DeckSourceItem, right: DeckSourceItem) -> bool:
    left_uri = _clean_text(left.uri).lower()
    right_uri = _clean_text(right.uri).lower()
    if left_uri and right_uri:
        return left_uri == right_uri

    left_document_id = _clean_text(left.document_id).lower()
    right_document_id = _clean_text(right.document_id).lower()
    if left_document_id and right_document_id:
        return left_document_id == right_document_id

    left_title = _clean_text(left.title).lower()
    right_title = _clean_text(right.title).lower()
    if left_title and right_title:
        return left_title == right_title

    return left.id == right.id


def _source_item_from_evidence_ref(ref: DeckEvidenceRef) -> DeckSourceItem:
    title = _truncate(_first_non_empty(ref.source_title, ref.source_id), 96)
    return DeckSourceItem(
        id=_first_non_empty(ref.source_id, f"src_ref_{uuid.uuid4().hex[:8]}"),
        type="evidence",
        title=title or "Regenerated evidence source",
        metadata={
            "from_evidence_ref": True,
            "excerpt_id": ref.excerpt_id,
        },
    )


def _unique_source_id(base_source_id: str, used_source_ids: set[str]) -> str:
    base = _first_non_empty(base_source_id, "src_regenerated")
    if base not in used_source_ids:
        return base

    suffix = 1
    while f"{base}_regen_{suffix}" in used_source_ids:
        suffix += 1
    return f"{base}_regen_{suffix}"


def _align_evidence_ref_source_registry(
    source_registry: list[DeckSourceItem],
    ref: DeckEvidenceRef,
    regenerated_sources_by_id: dict[str, DeckSourceItem],
) -> None:
    used_source_ids = {source.id for source in source_registry}
    existing_sources_by_id = {source.id: source for source in source_registry}
    existing_sources_by_identity = {
        identity: source
        for source in source_registry
        if (identity := _source_identity_key(source))
    }

    candidate = regenerated_sources_by_id.get(ref.source_id)
    if candidate is None:
        candidate = _source_item_from_evidence_ref(ref)

    existing = existing_sources_by_id.get(ref.source_id)
    if existing is not None and _source_items_match(existing, candidate):
        ref.source_title = existing.title or ref.source_title
        return

    identity = _source_identity_key(candidate)
    identity_match = existing_sources_by_identity.get(identity) if identity else None
    if identity_match is not None:
        ref.source_id = identity_match.id
        ref.source_title = identity_match.title or ref.source_title
        return

    next_source_id = _unique_source_id(candidate.id or ref.source_id, used_source_ids)
    next_source = candidate.model_copy(deep=True, update={"id": next_source_id})
    source_registry.append(next_source)
    ref.source_id = next_source.id
    ref.source_title = next_source.title or ref.source_title


def _sync_appendix_sources_slide(deck: DeckSpec) -> None:
    if not deck.source_registry:
        return

    appendix_slide = next(
        (slide for slide in deck.slides if slide.type == "appendix_sources"),
        None,
    )
    if appendix_slide is None:
        deck.slides.append(_build_appendix_slide(deck.source_registry))
        return

    existing_items = _existing_appendix_source_items(appendix_slide)
    refreshed_appendix = _build_appendix_slide(
        deck.source_registry,
        existing_items=existing_items,
    )
    appendix_slide.subtitle = appendix_slide.subtitle or refreshed_appendix.subtitle
    appendix_slide.layout = appendix_slide.layout or refreshed_appendix.layout
    appendix_slide.intent = "appendix_sources"
    appendix_slide.speaker_notes = (
        appendix_slide.speaker_notes or refreshed_appendix.speaker_notes
    )
    appendix_slide.blocks = refreshed_appendix.blocks
    appendix_slide.evidence_refs = []
    appendix_slide.quality_state = "supported"


def _sync_deck_sources_after_regeneration(
    deck: DeckSpec,
    regenerated_deck: DeckSpec,
    replacement: DeckSlide,
) -> None:
    source_registry = [
        source.model_copy(deep=True) for source in (deck.source_registry or [])
    ]
    regenerated_sources_by_id = {
        source.id: source for source in (regenerated_deck.source_registry or [])
    }

    for ref in replacement.evidence_refs or []:
        _align_evidence_ref_source_registry(
            source_registry,
            ref,
            regenerated_sources_by_id,
        )

    deck.source_registry = source_registry
    _sync_appendix_sources_slide(deck)
    deck.generation.actual_slide_count = len(deck.slides)
    refresh_deck_evidence_coverage(deck)


def _build_deck_from_generated(
    session_id: str,
    panel_config: Any,
    target_slide_count: int,
    pack: SourcePack,
    outline: OutlinePlan,
    drafted: DraftedSlideBundle,
    theme: DeckThemeName = "default",
    source_answer_group_id: str = "",
    source_panel_id: str = "",
) -> DeckSpec:
    slides: list[DeckSlide] = [
        DeckSlide(
            id="slide_cover",
            type="cover",
            title=_truncate(outline.title or pack.title_hint, 56),
            subtitle=_truncate(outline.subtitle or outline.core_message, 96),
            layout="hero-title",
            intent="cover",
            speaker_notes="Cover slide for establishing the overall topic.",
            blocks=[
                DeckBlock(
                    id="block_cover_message",
                    kind="paragraph",
                    role="core_message",
                    content={"text": _truncate(outline.core_message, 180)},
                )
            ],
            evidence_refs=[],
            quality_state="weak_support"
            if pack.source_mode == "kb_plus_chat"
            else "manual",
            status=DeckSlideStatus(review_state="draft"),
        ),
        DeckSlide(
            id="slide_outline",
            type="outline",
            title="汇报结构",
            subtitle="Core sections of this deck",
            layout="title-bullets",
            intent="outline",
            speaker_notes="Outline slide for navigation.",
            blocks=[
                DeckBlock(
                    id="block_outline",
                    kind="bullet_list",
                    role="outline",
                    content={
                        "items": [
                            _truncate(section, 40) for section in outline.sections[:5]
                        ]
                    },
                )
            ],
            evidence_refs=[],
            quality_state="weak_support"
            if pack.source_mode == "kb_plus_chat"
            else "manual",
            status=DeckSlideStatus(review_state="draft"),
        ),
    ]

    content_plans = outline.content_slides
    drafted_slides = drafted.content_slides
    content_count = min(len(content_plans), len(drafted_slides))

    for index in range(content_count):
        plan = content_plans[index]
        drafted_slide = drafted_slides[index]
        raw_answer = pack.qa_pairs[min(index, len(pack.qa_pairs) - 1)][1]
        evidence_refs = _pick_evidence_refs(drafted_slide, pack)
        quality_state = _resolve_quality_state(
            pack.source_mode, drafted_slide, evidence_refs
        )
        title = _sanitize_slide_title(drafted_slide.title, plan.title)
        subtitle = _truncate(drafted_slide.subtitle or plan.objective, 72)
        blocks = _build_blocks(drafted_slide.key_points, plan.objective, evidence_refs)
        blocks.extend(_extract_dashboard_chart_blocks(raw_answer, limit=1))
        slides.append(
            DeckSlide(
                id=f"slide_content_{index + 1}",
                type="content",
                title=title,
                subtitle=subtitle,
                layout="title-bullets",
                intent=plan.objective,
                speaker_notes=_truncate(
                    drafted_slide.speaker_notes or plan.objective, 180
                ),
                blocks=blocks,
                evidence_refs=evidence_refs,
                quality_state=quality_state,
                status=DeckSlideStatus(review_state="draft"),
            )
        )

    if pack.source_registry:
        slides.append(_build_appendix_slide(pack.source_registry))

    warnings = list(pack.warnings)
    if pack.source_mode == "chat_only":
        warnings.append(
            DeckWarning(
                code="manual_review_required",
                message="Chat-only mode requires manual review before export.",
            )
        )

    deck = DeckSpec(
        deck_id=f"deck_{uuid.uuid4().hex}",
        meta=DeckMeta(
            title=_truncate(outline.title or pack.title_hint, 56),
            subtitle=_truncate(outline.subtitle, 96),
            theme=normalize_deck_theme(theme),
            created_at=_now_iso(),
            session_id=session_id,
            source_mode=pack.source_mode,
            generator_panel_id=getattr(panel_config, "panel_id", "panel"),
            source_answer_group_id=str(source_answer_group_id or "").strip(),
            source_panel_id=str(source_panel_id or "").strip(),
        ),
        generation=DeckGeneration(
            source=pack.source_mode,
            target_slide_count=target_slide_count,
            actual_slide_count=len(slides),
            warnings=warnings,
        ),
        slides=slides,
        source_registry=pack.source_registry,
    )
    return refresh_deck_evidence_coverage(deck)


async def build_deck(
    session_id: str,
    messages: list[Any],
    panel_config: Any,
    knowledge_base_enabled: bool,
    target_slide_count: int,
    vector_store_path: str | None = None,
    system_prompt: str | None = None,
    theme: DeckThemeName = "default",
    source_answer_group_id: str = "",
    source_panel_id: str = "",
) -> DeckSpec:
    qa_pairs = ensure_deckable_chat(messages)
    pack = _build_source_pack(
        session_id=session_id,
        messages=messages,
        knowledge_base_enabled=knowledge_base_enabled,
        vector_store_path=vector_store_path,
        target_slide_count=target_slide_count,
    )
    if not qa_pairs:
        raise ValueError("This session has no successful Q&A content for deck generation.")
    content_slide_count = _decide_content_slide_count(pack, target_slide_count)

    async def run_generation(
        active_panel_config: Any,
    ) -> tuple[OutlinePlan, DraftedSlideBundle]:
        llm = get_llm(
            provider=getattr(active_panel_config, "provider", "local"),
            model_name=getattr(active_panel_config, "model", None),
            base_url=getattr(active_panel_config, "base_url", None),
            api_key=getattr(active_panel_config, "api_key", None) or None,
            temperature=float(getattr(active_panel_config, "temperature", 0.3) or 0.3),
        )
        outline = await _generate_outline(
            llm=llm,
            pack=pack,
            target_slide_count=target_slide_count,
            content_slide_count=content_slide_count,
            system_prompt=system_prompt,
        )
        drafted = await _generate_content_slides(
            llm=llm,
            pack=pack,
            outline=outline,
            system_prompt=system_prompt,
        )
        return outline, drafted

    try:
        outline, drafted = await run_generation(panel_config)
    except Exception as exc:
        if not _is_authentication_failure(exc):
            raise
        outline, drafted = await run_generation(
            _local_ollama_panel_config(panel_config)
        )
    return _build_deck_from_generated(
        session_id=session_id,
        panel_config=panel_config,
        target_slide_count=target_slide_count,
        pack=pack,
        outline=outline,
        drafted=drafted,
        theme=normalize_deck_theme(theme),
        source_answer_group_id=source_answer_group_id,
        source_panel_id=source_panel_id,
    )


def _select_regenerated_slide(
    current_deck: DeckSpec,
    regenerated_deck: DeckSpec,
    target_slide_id: str,
) -> tuple[int, DeckSlide]:
    current_index = next(
        (
            index
            for index, slide in enumerate(current_deck.slides)
            if slide.id == target_slide_id
        ),
        -1,
    )
    if current_index < 0:
        raise KeyError(target_slide_id)

    current_slide = current_deck.slides[current_index]
    if current_slide.type == "cover":
        return current_index, regenerated_deck.slides[0]

    if current_slide.type == "outline":
        outline_slide = next(
            (slide for slide in regenerated_deck.slides if slide.type == "outline"),
            regenerated_deck.slides[min(1, len(regenerated_deck.slides) - 1)],
        )
        return current_index, outline_slide

    if current_slide.type.startswith("appendix"):
        appendix_slide = next(
            (
                slide
                for slide in regenerated_deck.slides
                if slide.type.startswith("appendix")
            ),
            regenerated_deck.slides[-1],
        )
        return current_index, appendix_slide

    current_content_index = sum(
        1 for slide in current_deck.slides[:current_index] if slide.type == "content"
    )
    regenerated_content = [
        slide for slide in regenerated_deck.slides if slide.type == "content"
    ]
    if not regenerated_content:
        raise ValueError("Regenerated deck did not contain any content slides.")

    target_content_index = min(current_content_index, len(regenerated_content) - 1)
    return current_index, regenerated_content[target_content_index]


def _reconcile_regenerated_slide_evidence(
    current_slide: DeckSlide,
    replacement: DeckSlide,
) -> DeckSlide:
    if replacement.evidence_refs:
        replacement.quality_state = "supported"
        return replacement

    # Single-slide regeneration may rewrite content without being able to cite
    # sources again; keep the previous support state so coverage stays stable.
    replacement.evidence_refs = [
        ref.model_copy(deep=True) for ref in (current_slide.evidence_refs or [])
    ]
    replacement.quality_state = current_slide.quality_state
    return replacement


async def regenerate_deck_slide(
    deck: DeckSpec,
    slide_id: str,
    messages: list[Any],
    panel_config: Any,
    knowledge_base_enabled: bool,
    vector_store_path: str | None = None,
    system_prompt: str | None = None,
) -> DeckSlide:
    regenerated_deck = await build_deck(
        session_id=deck.meta.session_id,
        messages=messages,
        panel_config=panel_config,
        knowledge_base_enabled=knowledge_base_enabled,
        target_slide_count=max(deck.generation.target_slide_count, len(deck.slides)),
        vector_store_path=vector_store_path,
        system_prompt=system_prompt,
        theme=deck.meta.theme,
        source_answer_group_id=deck.meta.source_answer_group_id,
        source_panel_id=deck.meta.source_panel_id,
    )
    current_index, replacement = _select_regenerated_slide(
        deck, regenerated_deck, slide_id
    )
    current_slide = deck.slides[current_index]
    replacement = replacement.model_copy(deep=True)
    replacement.id = current_slide.id
    replacement = _reconcile_regenerated_slide_evidence(current_slide, replacement)
    _sync_deck_sources_after_regeneration(deck, regenerated_deck, replacement)
    replacement.status = DeckSlideStatus(
        locked=current_slide.status.locked,
        dirty=False,
        review_state="regenerated",
    )
    return replacement


class SQLiteDeckStore:
    def __init__(self, db_path: str | None = None):
        self.db_path = str(db_path or app_database_path()).strip()
        self._init_db()

    def _init_db(self) -> None:
        with connect_sqlite(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS decks (
                    deck_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    spec_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_decks_session
                ON decks(session_id)
                """
            )
            conn.commit()

    def save(self, deck: DeckSpec) -> DeckSpec:
        self._init_db()
        refresh_deck_evidence_coverage(deck)
        now = time.time()
        payload = json.dumps(deck.model_dump(mode="json"), ensure_ascii=False)
        with connect_sqlite(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO decks (deck_id, session_id, title, spec_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(deck_id) DO UPDATE SET
                    session_id = excluded.session_id,
                    title = excluded.title,
                    spec_json = excluded.spec_json,
                    updated_at = excluded.updated_at
                """,
                (
                    deck.deck_id,
                    deck.meta.session_id,
                    deck.meta.title,
                    payload,
                    now,
                    now,
                ),
            )
            conn.commit()
        return deck

    def get(self, deck_id: str) -> DeckSpec:
        self._init_db()
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT spec_json FROM decks WHERE deck_id = ?",
                (deck_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise KeyError(deck_id)
        return refresh_deck_evidence_coverage(DeckSpec.model_validate_json(row[0]))

    def list_recent(self, *, limit: int = 100) -> list[DeckSpec]:
        self._init_db()
        safe_limit = max(1, min(500, int(limit or 100)))
        with connect_sqlite(self.db_path) as conn:
            rows = conn.execute(
                "SELECT deck_id FROM decks ORDER BY updated_at DESC, created_at DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        return [self.get(str(row[0] or "")) for row in rows if row and row[0]]

    def list_ids_by_session(self, session_id: str) -> list[str]:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return []

        self._init_db()
        with connect_sqlite(self.db_path) as conn:
            rows = conn.execute(
                "SELECT deck_id FROM decks WHERE session_id = ? ORDER BY updated_at DESC, created_at DESC",
                (normalized_session_id,),
            ).fetchall()
        return [str(row[0] or "") for row in rows if row and row[0]]

    def delete_by_session(self, session_id: str) -> int:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return 0

        self._init_db()
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM decks WHERE session_id = ?",
                (normalized_session_id,),
            )
            conn.commit()
            return int(cursor.rowcount or 0)
