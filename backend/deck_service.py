"""
Deck generation, persistence, and export helpers.
"""

from __future__ import annotations

import io
import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Literal

from langchain_core.documents import Document
from pydantic import BaseModel, Field

from backend.agent_core import get_llm
from backend.chat_store import connect_sqlite
from backend.doc_pipeline import DocPipeline


DeckSourceMode = Literal["kb_plus_chat", "chat_only"]
DeckQualityState = Literal["supported", "weak_support", "manual"]
DeckThemeName = Literal["default", "midnight", "sunrise"]
DeckChartType = Literal["bar", "line", "pie"]

_DASHBOARD_CARD_BLOCK_RE = re.compile(
    r":::dashboard-card\s*\n([\s\S]*?)\n:::",
    flags=re.IGNORECASE,
)

DECK_THEME_PALETTES: dict[str, dict[str, str]] = {
    "default": {
        "bg": "F6F8FC",
        "surface": "FFFFFF",
        "surface_alt": "EEF4FF",
        "border": "D8E0EE",
        "title": "162033",
        "body": "2A3547",
        "muted": "60708A",
        "accent": "2563EB",
        "accent_soft": "DBEAFE",
        "success": "1F9D68",
        "warning": "D97706",
        "danger": "C2410C",
    },
    "midnight": {
        "bg": "0F172A",
        "surface": "111827",
        "surface_alt": "1E293B",
        "border": "334155",
        "title": "F8FAFC",
        "body": "E2E8F0",
        "muted": "94A3B8",
        "accent": "38BDF8",
        "accent_soft": "082F49",
        "success": "34D399",
        "warning": "FBBF24",
        "danger": "F87171",
    },
    "sunrise": {
        "bg": "FFF7ED",
        "surface": "FFFBF5",
        "surface_alt": "FDE7D6",
        "border": "F4C7A1",
        "title": "7C2D12",
        "body": "9A3412",
        "muted": "C2410C",
        "accent": "EA580C",
        "accent_soft": "FED7AA",
        "success": "2F855A",
        "warning": "D97706",
        "danger": "C2410C",
    },
}


class DeckWarning(BaseModel):
    code: str
    message: str


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


class DeckGeneration(BaseModel):
    source: DeckSourceMode
    target_slide_count: int
    actual_slide_count: int = 0
    warnings: list[DeckWarning] = Field(default_factory=list)


class DeckBlock(BaseModel):
    id: str
    kind: str
    role: str
    content: dict[str, Any] = Field(default_factory=dict)
    editable: bool = True


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


_FALLBACK_SECTION_TITLES = ["主题概览", "关键拆解", "结论与建议"]
_FALLBACK_SLIDE_TITLES = [
    "主题概览与核心结论",
    "关键信息拆解",
    "适用场景与行动建议",
    "后续重点与风险提示",
    "补充观察",
]


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _clean_text(text: Any) -> str:
    return " ".join(str(text).strip().split())


def normalize_deck_theme(theme: Any) -> DeckThemeName:
    raw = _clean_text(theme).lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "": "default",
        "default": "default",
        "classic": "default",
        "midnight": "midnight",
        "night": "midnight",
        "dark": "midnight",
        "sunrise": "sunrise",
        "warm": "sunrise",
    }
    return aliases.get(raw, "default")


def _truncate(text: str, limit: int) -> str:
    cleaned = _clean_text(text)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _truncate_multiline(text: Any, limit: int) -> str:
    normalized = str(text).replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def _stringify_llm_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
            else:
                parts.append(str(item))
        return "\n".join(parts).strip()
    return str(content).strip()


def _normalize_message_text(content: Any) -> str:
    return (
        _stringify_llm_content(content)
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .strip()
    )


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


def _coerce_chart_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = _clean_text(value).replace(",", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _normalize_chart_labels(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    labels: list[str] = []
    for index, value in enumerate(values, start=1):
        cleaned = _clean_text(value)
        labels.append(cleaned or f"类别 {index}")
    return labels


def _normalize_chart_datasets(values: Any, label_count: int) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []

    datasets: list[dict[str, Any]] = []
    for dataset_index, value in enumerate(values, start=1):
        if not isinstance(value, dict):
            continue

        raw_points = value.get("data")
        if not isinstance(raw_points, list):
            continue

        clean_points = [
            _coerce_chart_number(item)
            for item in raw_points
        ]
        if not any(item is not None for item in clean_points):
            continue

        target_size = label_count or len(clean_points)
        normalized_points = [
            _coerce_chart_number(item) or 0.0
            for item in raw_points[:target_size]
        ]
        if len(normalized_points) < target_size:
            normalized_points.extend([0.0] * (target_size - len(normalized_points)))

        label = _clean_text(value.get("label")) or f"系列 {dataset_index}"
        datasets.append(
            {
                "label": label,
                "data": normalized_points,
            }
        )
    return datasets


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
        labels = [f"类别 {index + 1}" for index in range(len(datasets[0]['data']))]
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


def _extract_qa_pairs(messages: list[Any]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    pending_question = ""
    for message in messages:
        role = getattr(message, "__class__", type(message)).__name__
        content = _normalize_message_text(getattr(message, "content", ""))
        if not content:
            continue
        if role == "HumanMessage":
            pending_question = _clean_text(content)
            continue
        if role == "AIMessage" and pending_question:
            pairs.append((pending_question, content))
            pending_question = ""
    return pairs


def _is_failed_answer(answer: str) -> bool:
    normalized = answer.strip().lower()
    if not normalized:
        return True
    failure_markers = (
        "agent stopped due to max iterations",
        "agent stopped due to iteration limit",
        "生成回答失败",
        "无法完成任务",
        "处理请求时发生异常",
        "模型工具调用次数超限",
        "internal_error",
    )
    return any(marker in normalized for marker in failure_markers)


def extract_successful_qa_pairs(messages: list[Any]) -> list[tuple[str, str]]:
    return [
        (question, answer)
        for question, answer in _extract_qa_pairs(messages)
        if not _is_failed_answer(answer)
    ]


def ensure_deckable_chat(messages: list[Any]) -> list[tuple[str, str]]:
    raw_pairs = _extract_qa_pairs(messages)
    qa_pairs = extract_successful_qa_pairs(messages)
    if qa_pairs:
        return qa_pairs
    if raw_pairs:
        raise ValueError(
            "该会话最近没有成功回答，当前只有失败结果，不能生成演示稿。"
        )
    raise ValueError("该会话没有可用于生成演示稿的成功问答内容。")


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
        "无效的令牌",
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
        for part in re.split(r"[。！？!?]\s+|\n+", answer)
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
            evidence_source_ids = [pack.excerpts[min(index, len(pack.excerpts) - 1)].source_id]

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
        core_message=core_message or "基于当前会话整理的核心结论",
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
            points = [_truncate(_first_non_empty(plain_answer, question, plan.objective), 72)]

        evidence_excerpt_ids: list[str] = []
        evidence_source_ids: list[str] = []
        quality_state: DeckQualityState = "manual"

        if pack.source_mode == "kb_plus_chat" and pack.excerpts:
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
) -> SourcePack:
    return SourcePack(
        title_hint=title_hint,
        source_mode="chat_only",
        qa_pairs=qa_pairs,
        chat_notes=chat_notes,
        excerpts=[],
        source_registry=[],
        warnings=[
            *warnings,
            DeckWarning(
                code="chat_only_mode",
                message=chat_only_message,
            ),
        ],
    )


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
        f"问题：{_truncate(question, 80)}\n回答摘要：{_truncate(answer, 180)}"
        for question, answer in qa_pairs[-4:]
    ]

    chat_notes = [
        f"问题：{_truncate(question, 80)}\n回答摘要：{_truncate(_answer_plaintext(answer), 180)}"
        for question, answer in qa_pairs[-4:]
    ]

    if not knowledge_base_enabled:
        return _build_chat_only_source_pack(
            title_hint=title_hint,
            qa_pairs=qa_pairs,
            chat_notes=chat_notes,
            warnings=warnings,
            chat_only_message="当前未启用知识库，本次演示稿将仅基于成功聊天答案生成，证据强度低于知识库模式。",
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
                message="当前知识库暂时无法加载，已自动改为仅基于回答内容生成演示稿。",
            )
        )
        return _build_chat_only_source_pack(
            title_hint=title_hint,
            qa_pairs=qa_pairs,
            chat_notes=chat_notes,
            warnings=warnings,
            chat_only_message="当前演示稿将仅基于成功聊天答案生成，证据强度低于知识库模式。",
        )

    if not vector_store_path:
        warnings.append(
            DeckWarning(
                code="kb_fallback_default",
                message="当前角色未绑定专属知识库，已自动回退到默认知识库生成演示稿。",
            )
        )
    elif resolved_store_path != vector_store_path:
        warnings.append(
            DeckWarning(
                code="kb_fallback_default",
                message="当前角色绑定知识库加载失败，已自动回退到默认知识库生成演示稿。",
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
                message="当前知识库检索到的有效材料不足，已自动改为仅基于回答内容生成演示稿。",
            )
        )
        return _build_chat_only_source_pack(
            title_hint=title_hint,
            qa_pairs=qa_pairs,
            chat_notes=chat_notes,
            warnings=warnings,
            chat_only_message="当前演示稿将仅基于成功聊天答案生成，证据强度低于知识库模式。",
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
                message="当前知识库检索结果覆盖的来源文档不足，已自动改为仅基于回答内容生成演示稿。",
            )
        )
        return _build_chat_only_source_pack(
            title_hint=title_hint,
            qa_pairs=qa_pairs,
            chat_notes=chat_notes,
            warnings=warnings,
            chat_only_message="当前演示稿将仅基于成功聊天答案生成，证据强度低于知识库模式。",
        )

    if len(excerpts) < target_slide_count - 2:
        warnings.append(
            DeckWarning(
                code="evidence_sparse",
                message="知识库证据量有限，本次会优先保证内容扎实，实际页数可能少于目标页数。",
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
    recent_qa_pairs = "\n\n---\n\n".join(
        (
            f"问题：{_truncate(question, 120)}\n"
            f"回答原文：\n{_truncate_multiline(_answer_plaintext(answer), 5000 if pack.source_mode == 'chat_only' else 2400)}"
        )
        for question, answer in pack.qa_pairs[-2:]
    )

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
            f"问题：{_truncate(question, 120)}\n"
            f"回答原文：\n{_truncate_multiline(answer, 5000 if pack.source_mode == 'chat_only' else 2400)}"
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
            f"最近成功问答原文:\n{recent_qa_pairs}\n\n"
            f"来源清单:\n{sources}\n\n"
            f"知识库片段:\n{excerpts}"
        )
    return "最近成功问答原文:\n" + recent_qa_pairs


async def _generate_outline(
    llm,
    pack: SourcePack,
    target_slide_count: int,
    content_slide_count: int,
    system_prompt: str | None,
) -> OutlinePlan:
    evidence_rule = (
        "每个内容页必须从可用 source_id 中选择 1-2 个 evidence_source_ids。"
        if pack.source_mode == "kb_plus_chat"
        else "因为当前是 chat_only 模式，evidence_source_ids 统一返回空数组。"
    )
    structure_rule = (
        "结合问答摘要与知识库证据，组织为正式汇报结构。"
        if pack.source_mode == "kb_plus_chat"
        else "优先沿用回答原文已有的章节标题、列表层次和关键措辞，不要新增原回答中没有的结论。"
    )
    prompt = f"""
你是一个专业的中文商业演示稿策划助手。请基于给定材料规划一个 PPT 大纲。

硬性要求：
1. 只输出 JSON，不要输出解释。
2. 不要使用 Q1、Q2、Part 这类问答标题。
3. 总体采用“主题页”结构，而不是复述聊天记录。
4. 内容页数量必须是 {content_slide_count} 页。
5. section 数量控制在 3-5 个。
6. {evidence_rule}
7. {structure_rule}
8. 标题必须像正式汇报标题，不要直接把用户原问题原样拿来当页标题。
9. 页数策略是宁少勿水，不要补空话。

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
- 角色上下文: {system_prompt or "无"}

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
        "每个内容页必须选择至少 1 个 evidence_excerpt_ids，并保证它们来自可用片段。quality_state 只能是 supported。"
        if pack.source_mode == "kb_plus_chat"
        else "当前是 chat_only 模式，evidence_excerpt_ids 和 evidence_source_ids 返回空数组，quality_state 统一使用 manual。"
    )
    fidelity_rule = (
        "结合知识库证据与问答内容生成适合汇报展示的表达。"
        if pack.source_mode == "kb_plus_chat"
        else "如果原回答已经有分节标题、子标题或 bullet 列表，优先直接复用其结构、顺序和关键措辞，不要改写成另一套主题。"
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

角色上下文：{system_prompt or "无"}

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
    cleaned = cleaned.strip(" -:：")
    return _truncate(cleaned or fallback, 48)


def _build_blocks(points: list[str], fallback: str) -> list[DeckBlock]:
    clean_points = [_truncate(point, 72) for point in points if _clean_text(point)]
    if clean_points:
        return [
            DeckBlock(
                id=f"block_{uuid.uuid4().hex[:8]}",
                kind="bullet_list",
                role="main_points",
                content={"items": clean_points[:5]},
            )
        ]
    return [
        DeckBlock(
            id=f"block_{uuid.uuid4().hex[:8]}",
            kind="paragraph",
            role="summary",
            content={"text": _truncate(fallback, 220)},
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
        excerpt = next((item for item in pack.excerpts if item.source_id == source_id), None)
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

    if pack.source_mode == "kb_plus_chat" and pack.excerpts:
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
    if source_mode == "chat_only":
        return "manual"
    if evidence_refs:
        return "supported"
    if drafted_slide.quality_state in {"supported", "weak_support", "manual"}:
        return drafted_slide.quality_state
    return "weak_support"


def _build_appendix_slide(source_registry: list[DeckSourceItem]) -> DeckSlide:
    items = [source.title for source in source_registry]
    return DeckSlide(
        id="slide_appendix_sources",
        type="appendix_sources",
        title="附录：来源清单",
        subtitle="本次演示稿引用的知识库来源",
        layout="title-bullets",
        intent="appendix_sources",
        speaker_notes="附录页，供复核来源。",
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
            speaker_notes="封面页，用于建立整体主题。",
            blocks=[
                DeckBlock(
                    id="block_cover_message",
                    kind="paragraph",
                    role="core_message",
                    content={"text": _truncate(outline.core_message, 180)},
                )
            ],
            evidence_refs=[],
            quality_state="weak_support" if pack.source_mode == "kb_plus_chat" else "manual",
            status=DeckSlideStatus(review_state="draft"),
        ),
        DeckSlide(
            id="slide_outline",
            type="outline",
            title="汇报结构",
            subtitle="本次演示的核心章节",
            layout="title-bullets",
            intent="outline",
            speaker_notes="目录页，帮助听众理解结构。",
            blocks=[
                DeckBlock(
                    id="block_outline",
                    kind="bullet_list",
                    role="outline",
                    content={"items": [_truncate(section, 40) for section in outline.sections[:5]]},
                )
            ],
            evidence_refs=[],
            quality_state="weak_support" if pack.source_mode == "kb_plus_chat" else "manual",
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
        quality_state = _resolve_quality_state(pack.source_mode, drafted_slide, evidence_refs)
        title = _sanitize_slide_title(drafted_slide.title, plan.title)
        subtitle = _truncate(drafted_slide.subtitle or plan.objective, 72)
        blocks = _build_blocks(drafted_slide.key_points, plan.objective)
        blocks.extend(_extract_dashboard_chart_blocks(raw_answer, limit=1))
        slides.append(
            DeckSlide(
                id=f"slide_content_{index + 1}",
                type="content",
                title=title,
                subtitle=subtitle,
                layout="title-bullets",
                intent=plan.objective,
                speaker_notes=_truncate(drafted_slide.speaker_notes or plan.objective, 180),
                blocks=blocks,
                evidence_refs=evidence_refs,
                quality_state=quality_state,
                status=DeckSlideStatus(review_state="draft"),
            )
        )

    if pack.source_mode == "kb_plus_chat":
        slides.append(_build_appendix_slide(pack.source_registry))

    warnings = list(pack.warnings)
    if pack.source_mode == "chat_only":
        warnings.append(
            DeckWarning(
                code="manual_review_required",
                message="当前为仅聊天模式，导出前请重点人工复核结论和措辞。",
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
    return deck


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
        raise ValueError("该会话没有可用于生成演示稿的成功问答内容。")
    content_slide_count = _decide_content_slide_count(pack, target_slide_count)

    async def run_generation(active_panel_config: Any) -> tuple[OutlinePlan, DraftedSlideBundle]:
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
        outline, drafted = await run_generation(_local_ollama_panel_config(panel_config))
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
        (index for index, slide in enumerate(current_deck.slides) if slide.id == target_slide_id),
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
            (slide for slide in regenerated_deck.slides if slide.type.startswith("appendix")),
            regenerated_deck.slides[-1],
        )
        return current_index, appendix_slide

    current_content_index = sum(
        1
        for slide in current_deck.slides[:current_index]
        if slide.type == "content"
    )
    regenerated_content = [
        slide for slide in regenerated_deck.slides if slide.type == "content"
    ]
    if not regenerated_content:
        raise ValueError("Regenerated deck did not contain any content slides.")

    target_content_index = min(current_content_index, len(regenerated_content) - 1)
    return current_index, regenerated_content[target_content_index]


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
    current_index, replacement = _select_regenerated_slide(deck, regenerated_deck, slide_id)
    current_slide = deck.slides[current_index]
    replacement = replacement.model_copy(deep=True)
    replacement.id = current_slide.id
    replacement.status = DeckSlideStatus(
        locked=current_slide.status.locked,
        dirty=False,
        review_state="regenerated",
    )
    return replacement


def build_report_markdown(messages: list[Any], title: str) -> str:
    qa_pairs = ensure_deckable_chat(messages)
    lines = [
        "---",
        "theme: default",
        f"title: {title}",
        "class: text-center",
        "---",
        "",
        f"# {title}",
        "",
        "AI 对话报告",
        "",
    ]
    for index, (question, answer) in enumerate(qa_pairs, start=1):
        lines.append("---")
        lines.append("")
        lines.append(f"## 主题 {index}: {_truncate(question, 72)}")
        lines.append("")
        lines.append(answer)
        lines.append("")
    return "\n".join(lines)


def _slide_text(slide: DeckSlide) -> str:
    lines: list[str] = []
    for block in slide.blocks:
        if block.kind == "bullet_list":
            for item in block.content.get("items", []):
                value = _clean_text(item)
                if value:
                    lines.append(f"• {value}")
        elif block.kind == "chart":
            title = _clean_text(block.content.get("title")) or "图表"
            chart_type = _clean_text(block.content.get("chart_type")).lower()
            lines.append(f"[图表] {title} ({chart_type or 'chart'})")
        else:
            text = _clean_text(block.content.get("text", ""))
            if text:
                lines.append(text)
    chart_specs = _extract_chart_specs(slide)
    if chart_specs:
        lines.append("")
        lines.append("图表")
        for chart in chart_specs:
            chart_line = f"- {chart['title']} [{chart['chart_type']}]"
            if chart["description"]:
                chart_line += f": {chart['description']}"
            lines.append(chart_line)

    if slide.evidence_refs:
        lines.append("")
        lines.append(
            "Sources: "
            + ", ".join(ref.source_title for ref in slide.evidence_refs[:3])
        )
    return "\n".join(lines).strip()


def _quality_state_color_key(quality_state: DeckQualityState) -> str:
    if quality_state == "supported":
        return "success"
    if quality_state == "manual":
        return "danger"
    return "warning"


def _is_slide_manually_confirmed(slide: DeckSlide) -> bool:
    return slide.quality_state != "supported" and slide.status.review_state == "confirmed"


def _slide_quality_label(slide: DeckSlide) -> str:
    if _is_slide_manually_confirmed(slide):
        return "已人工确认"
    return _quality_state_label(slide.quality_state)


def _slide_quality_color_key(slide: DeckSlide) -> str:
    if _is_slide_manually_confirmed(slide):
        return "success"
    return _quality_state_color_key(slide.quality_state)


def _extract_chart_specs(slide: DeckSlide) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for block in slide.blocks:
        if block.kind != "chart":
            continue
        chart_type = _clean_text(
            block.content.get("chart_type") or block.content.get("type")
        ).lower()
        if chart_type not in {"bar", "line", "pie"}:
            continue

        labels = _normalize_chart_labels(block.content.get("labels"))
        datasets = _normalize_chart_datasets(block.content.get("datasets"), len(labels))
        if not datasets:
            continue

        if not labels:
            labels = [f"类别 {index + 1}" for index in range(len(datasets[0]['data']))]
            datasets = _normalize_chart_datasets(block.content.get("datasets"), len(labels))
            if not datasets:
                continue

        specs.append(
            {
                "title": _clean_text(block.content.get("title")) or "数据图表",
                "description": _clean_text(block.content.get("description")),
                "chart_type": chart_type,
                "labels": labels[:12],
                "datasets": datasets[:4],
            }
        )
    return specs


def _extract_slide_sections(slide: DeckSlide) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for block in slide.blocks:
        if block.kind == "bullet_list":
            items = [
                _clean_text(item)
                for item in block.content.get("items", [])
                if _clean_text(item)
            ]
            if items:
                sections.append(
                    {
                        "kind": "bullet_list",
                        "role": block.role,
                        "items": items,
                    }
                )
        else:
            text = _clean_text(block.content.get("text", ""))
            if text:
                sections.append(
                    {
                        "kind": "paragraph",
                        "role": block.role,
                        "text": text,
                    }
                )
    return sections


def _quality_state_label(quality_state: DeckQualityState) -> str:
    if quality_state == "supported":
        return "证据充分"
    if quality_state == "manual":
        return "需人工确认"
    return "证据偏弱"


def _split_evenly(items: list[str], column_count: int = 2) -> list[list[str]]:
    if column_count <= 1:
        return [items]
    if not items:
        return [[] for _ in range(column_count)]

    per_column = (len(items) + column_count - 1) // column_count
    return [
        items[index * per_column : (index + 1) * per_column]
        for index in range(column_count)
    ]


def _compose_export_notes(slide: DeckSlide) -> str:
    lines: list[str] = [slide.title.strip() or "Untitled Slide"]

    if slide.subtitle.strip():
        lines.append(slide.subtitle.strip())

    lines.append(f"质量状态: {_quality_state_label(slide.quality_state)}")

    lines[-1] = f"质量状态: {_slide_quality_label(slide)}"
    if slide.speaker_notes.strip():
        lines.extend(["", "讲述备注", slide.speaker_notes.strip()])

    sections = _extract_slide_sections(slide)
    if sections:
        lines.append("")
        lines.append("页面内容")
        for section in sections:
            role = _clean_text(section.get("role", ""))
            if role and role not in {"main_points", "summary", "outline", "sources"}:
                lines.append(f"[{role}]")
            if section["kind"] == "bullet_list":
                lines.extend(f"- {item}" for item in section["items"])
            else:
                lines.append(section["text"])

    if slide.evidence_refs:
        lines.append("")
        lines.append("证据来源")
        for ref in slide.evidence_refs:
            confidence = (
                f" ({round(ref.confidence * 100)}%)"
                if ref.confidence and ref.confidence > 0
                else ""
            )
            snippet = _truncate(_clean_text(ref.snippet), 220)
            if snippet:
                lines.append(f"- {ref.source_title}{confidence}: {snippet}")
            else:
                lines.append(f"- {ref.source_title}{confidence}")

    return "\n".join(line for line in lines if line is not None).strip()


def export_deck_to_pptx(deck: DeckSpec) -> bytes:
    try:
        from pptx import Presentation
        from pptx.chart.data import CategoryChartData
        from pptx.dml.color import RGBColor
        from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
        from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
        from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
        from pptx.util import Pt
    except ImportError as exc:
        raise RuntimeError(
            "python-pptx 未安装，请在 requirements.txt 中添加 python-pptx 并重新安装依赖"
        ) from exc

    theme = DECK_THEME_PALETTES[normalize_deck_theme(deck.meta.theme)]

    def rgb(color_key: str) -> RGBColor:
        return RGBColor.from_string(theme.get(color_key, color_key))

    def set_slide_background(ppt_slide, color_key: str = "bg") -> None:
        fill = ppt_slide.background.fill
        fill.solid()
        fill.fore_color.rgb = rgb(color_key)

    def add_textbox(
        ppt_slide,
        x: float,
        y: float,
        w: float,
        h: float,
        *,
        fill_color: str | None = None,
        line_color: str | None = None,
        margins: tuple[float, float, float, float] = (0.08, 0.05, 0.08, 0.05),
        vertical_anchor=MSO_ANCHOR.TOP,
    ):
        from pptx.util import Inches

        shape = ppt_slide.shapes.add_textbox(
            Inches(x), Inches(y), Inches(w), Inches(h)
        )
        text_frame = shape.text_frame
        text_frame.clear()
        text_frame.word_wrap = True
        text_frame.auto_size = MSO_AUTO_SIZE.NONE
        text_frame.vertical_anchor = vertical_anchor
        text_frame.margin_left = Inches(margins[0])
        text_frame.margin_top = Inches(margins[1])
        text_frame.margin_right = Inches(margins[2])
        text_frame.margin_bottom = Inches(margins[3])

        if fill_color:
            shape.fill.solid()
            shape.fill.fore_color.rgb = rgb(fill_color)
        else:
            shape.fill.background()

        if line_color:
            shape.line.color.rgb = rgb(line_color)
            shape.line.width = Pt(1)
        else:
            shape.line.fill.background()

        return shape, text_frame

    def set_text_frame_content(text_frame, paragraphs: list[dict[str, Any]]) -> None:
        text_frame.clear()
        if not paragraphs:
            return

        for index, spec in enumerate(paragraphs):
            paragraph = text_frame.paragraphs[0] if index == 0 else text_frame.add_paragraph()
            paragraph.text = spec.get("text", "")
            paragraph.alignment = spec.get("align", PP_ALIGN.LEFT)
            paragraph.space_after = Pt(spec.get("space_after", 6))
            paragraph.space_before = Pt(spec.get("space_before", 0))
            paragraph.line_spacing = spec.get("line_spacing", 1.15)
            font = paragraph.font
            font.name = spec.get("font_name", "Microsoft YaHei")
            font.size = Pt(spec.get("font_size", 18))
            font.bold = spec.get("bold", False)
            font.italic = spec.get("italic", False)
            font.color.rgb = rgb(spec.get("color", "body"))

    def add_badge(
        ppt_slide,
        text: str,
        x: float,
        y: float,
        w: float,
        h: float,
        *,
        fill_color: str,
        text_color: str = "surface",
    ) -> None:
        from pptx.util import Inches

        shape = ppt_slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
            Inches(x),
            Inches(y),
            Inches(w),
            Inches(h),
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = rgb(fill_color)
        shape.line.fill.background()
        text_frame = shape.text_frame
        text_frame.word_wrap = False
        text_frame.auto_size = MSO_AUTO_SIZE.NONE
        text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        text_frame.margin_left = Pt(4)
        text_frame.margin_right = Pt(4)
        set_text_frame_content(
            text_frame,
            [
                {
                    "text": text,
                    "font_size": 10,
                    "bold": True,
                    "color": text_color,
                    "align": PP_ALIGN.CENTER,
                    "space_after": 0,
                }
            ],
        )

    def quality_color(slide: DeckSlide) -> str:
        return _slide_quality_color_key(slide)

    def add_chart_panel(
        ppt_slide,
        chart: dict[str, Any],
        x: float,
        y: float,
        w: float,
        h: float,
    ) -> None:
        from pptx.util import Inches

        panel = ppt_slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
            Inches(x),
            Inches(y),
            Inches(w),
            Inches(h),
        )
        panel.fill.solid()
        panel.fill.fore_color.rgb = rgb("surface_alt")
        panel.line.color.rgb = rgb("border")
        panel.line.width = Pt(1)

        title_height = 0.36
        description_height = 0.0
        description = _clean_text(chart.get("description"))
        if description:
            description_height = 0.36

        _, title_box = add_textbox(
            ppt_slide,
            x + 0.18,
            y + 0.12,
            w - 0.36,
            title_height,
            margins=(0.0, 0.0, 0.0, 0.0),
        )
        set_text_frame_content(
            title_box,
            [
                {
                    "text": chart["title"],
                    "font_size": 11.5,
                    "bold": True,
                    "color": "title",
                    "space_after": 0,
                }
            ],
        )

        if description:
            _, desc_box = add_textbox(
                ppt_slide,
                x + 0.18,
                y + 0.46,
                w - 0.36,
                description_height,
                margins=(0.0, 0.0, 0.0, 0.0),
            )
            set_text_frame_content(
                desc_box,
                [
                    {
                        "text": _truncate(description, 110),
                        "font_size": 9.5,
                        "color": "muted",
                        "space_after": 0,
                    }
                ],
            )

        chart_box_y = y + 0.56 + description_height
        chart_box_h = max(1.2, h - (chart_box_y - y) - 0.18)
        chart_data = CategoryChartData()
        chart_data.categories = chart["labels"]
        datasets = chart["datasets"]
        if chart["chart_type"] == "pie":
            datasets = datasets[:1]
        for dataset in datasets:
            chart_data.add_series(dataset["label"], tuple(dataset["data"]))

        chart_type_map = {
            "bar": XL_CHART_TYPE.COLUMN_CLUSTERED,
            "line": XL_CHART_TYPE.LINE_MARKERS,
            "pie": XL_CHART_TYPE.PIE,
        }
        graphic_frame = ppt_slide.shapes.add_chart(
            chart_type_map[chart["chart_type"]],
            Inches(x + 0.16),
            Inches(chart_box_y),
            Inches(w - 0.32),
            Inches(chart_box_h),
            chart_data,
        )
        ppt_chart = graphic_frame.chart
        ppt_chart.has_title = False
        ppt_chart.has_legend = len(datasets) > 1 or chart["chart_type"] == "pie"
        if ppt_chart.has_legend:
            ppt_chart.legend.position = XL_LEGEND_POSITION.BOTTOM
            ppt_chart.legend.font.size = Pt(9)

        palette = ["accent", "success", "warning", "danger"]
        try:
            if chart["chart_type"] == "pie":
                series = ppt_chart.series[0]
                for point_index, point in enumerate(series.points):
                    color_key = palette[point_index % len(palette)]
                    point.format.fill.solid()
                    point.format.fill.fore_color.rgb = rgb(color_key)
                    point.format.line.color.rgb = rgb("surface")
            else:
                for series_index, series in enumerate(ppt_chart.series):
                    color_key = palette[series_index % len(palette)]
                    series.format.fill.solid()
                    series.format.fill.fore_color.rgb = rgb(color_key)
                    series.format.line.color.rgb = rgb(color_key)
        except Exception:
            pass

    def add_footer(
        ppt_slide,
        slide_index: int,
        total_slides: int,
        slide: DeckSlide,
    ) -> None:
        from pptx.util import Inches

        divider = ppt_slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.RECTANGLE,
            Inches(0.75),
            Inches(6.78),
            Inches(11.85),
            Inches(0.02),
        )
        divider.fill.solid()
        divider.fill.fore_color.rgb = rgb("border")
        divider.line.fill.background()

        _, left_footer = add_textbox(
            ppt_slide,
            0.78,
            6.84,
            7.6,
            0.28,
            margins=(0.0, 0.0, 0.0, 0.0),
        )
        set_text_frame_content(
            left_footer,
            [
                {
                    "text": f"{deck.meta.source_mode} | {slide.type} | {slide.layout}",
                    "font_size": 9.5,
                    "color": "muted",
                    "space_after": 0,
                }
            ],
        )

        _, right_footer = add_textbox(
            ppt_slide,
            10.55,
            6.82,
            1.75,
            0.3,
            margins=(0.0, 0.0, 0.0, 0.0),
        )
        set_text_frame_content(
            right_footer,
            [
                {
                    "text": f"{slide_index + 1}/{total_slides}",
                    "font_size": 10,
                    "bold": True,
                    "color": "muted",
                    "align": PP_ALIGN.RIGHT,
                    "space_after": 0,
                }
            ],
        )

    def add_notes(ppt_slide, slide: DeckSlide) -> None:
        notes_text = _compose_export_notes(slide)
        if notes_text:
            ppt_slide.notes_slide.notes_text_frame.text = notes_text

    def format_date_label(raw_value: str) -> str:
        raw = _clean_text(raw_value)
        if not raw:
            return "未知时间"
        if "T" in raw:
            return raw.split("T", 1)[0]
        return raw[:10]

    def collect_bullet_items(slide: DeckSlide) -> list[str]:
        items: list[str] = []
        for section in _extract_slide_sections(slide):
            if section["kind"] == "bullet_list":
                items.extend(section["items"])
        return items

    def collect_paragraph_texts(slide: DeckSlide) -> list[str]:
        items: list[str] = []
        for section in _extract_slide_sections(slide):
            if section["kind"] == "paragraph":
                items.append(section["text"])
        return items

    def render_cover_slide(ppt_slide, slide_index: int, slide: DeckSlide) -> None:
        from pptx.util import Inches

        set_slide_background(ppt_slide, "surface")
        top_bar = ppt_slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.RECTANGLE,
            Inches(0),
            Inches(0),
            Inches(13.333),
            Inches(0.22),
        )
        top_bar.fill.solid()
        top_bar.fill.fore_color.rgb = rgb("accent")
        top_bar.line.fill.background()

        accent_panel = ppt_slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
            Inches(10.85),
            Inches(0.45),
            Inches(1.85),
            Inches(5.55),
        )
        accent_panel.fill.solid()
        accent_panel.fill.fore_color.rgb = rgb("surface_alt")
        accent_panel.line.fill.background()

        core_message = ""
        for section in _extract_slide_sections(slide):
            if section["kind"] == "paragraph":
                core_message = section["text"]
                break
            if section["kind"] == "bullet_list":
                core_message = "；".join(section["items"][:2])
                break

        _, eyebrow = add_textbox(
            ppt_slide,
            0.9,
            0.55,
            3.4,
            0.35,
            margins=(0.0, 0.0, 0.0, 0.0),
        )
        set_text_frame_content(
            eyebrow,
            [
                {
                    "text": "AI Knowledge Base Deck",
                    "font_size": 11,
                    "bold": True,
                    "color": "accent",
                    "space_after": 0,
                }
            ],
        )

        _, title_box = add_textbox(
            ppt_slide,
            0.9,
            1.0,
            10.9,
            1.4,
            margins=(0.0, 0.0, 0.0, 0.0),
        )
        set_text_frame_content(
            title_box,
            [
                {
                    "text": slide.title or deck.meta.title,
                    "font_size": 26,
                    "bold": True,
                    "color": "title",
                    "line_spacing": 1.05,
                    "space_after": 0,
                }
            ],
        )

        _, subtitle_box = add_textbox(
            ppt_slide,
            0.92,
            2.35,
            9.1,
            0.75,
            margins=(0.0, 0.0, 0.0, 0.0),
        )
        set_text_frame_content(
            subtitle_box,
            [
                {
                    "text": slide.subtitle or deck.meta.subtitle or "AI 自动生成的结构化汇报草稿",
                    "font_size": 16,
                    "color": "muted",
                    "line_spacing": 1.15,
                    "space_after": 0,
                }
            ],
        )

        if core_message:
            _, message_box = add_textbox(
                ppt_slide,
                0.9,
                3.25,
                6.7,
                1.45,
                fill_color="surface_alt",
                line_color="accent_soft",
                margins=(0.18, 0.12, 0.18, 0.12),
            )
            set_text_frame_content(
                message_box,
                [
                    {
                        "text": "核心结论",
                        "font_size": 11,
                        "bold": True,
                        "color": "accent",
                        "space_after": 6,
                    },
                    {
                        "text": core_message,
                        "font_size": 15,
                        "color": "body",
                        "line_spacing": 1.18,
                        "space_after": 0,
                    },
                ],
            )

        _, meta_box = add_textbox(
            ppt_slide,
            8.4,
            3.28,
            3.9,
            2.05,
            fill_color="bg",
            line_color="border",
            margins=(0.16, 0.12, 0.16, 0.12),
        )
        set_text_frame_content(
            meta_box,
            [
                {
                    "text": "导出摘要",
                    "font_size": 11,
                    "bold": True,
                    "color": "title",
                    "space_after": 8,
                },
                {
                    "text": f"来源模式: {deck.meta.source_mode}",
                    "font_size": 11,
                    "color": "body",
                    "space_after": 4,
                },
                {
                    "text": f"受众: {deck.meta.audience}",
                    "font_size": 11,
                    "color": "body",
                    "space_after": 4,
                },
                {
                    "text": f"页数: {deck.generation.actual_slide_count}",
                    "font_size": 11,
                    "color": "body",
                    "space_after": 4,
                },
                {
                    "text": f"生成面板: {deck.meta.generator_panel_id}",
                    "font_size": 11,
                    "color": "body",
                    "space_after": 4,
                },
                {
                    "text": f"日期: {format_date_label(deck.meta.created_at)}",
                    "font_size": 11,
                    "color": "body",
                    "space_after": 0,
                },
            ],
        )

        add_badge(
            ppt_slide,
            _slide_quality_label(slide),
            10.55,
            0.62,
            1.72,
            0.38,
            fill_color=quality_color(slide),
        )
        add_footer(ppt_slide, slide_index, len(deck.slides), slide)
        add_notes(ppt_slide, slide)

    def render_outline_slide(ppt_slide, slide_index: int, slide: DeckSlide) -> None:
        set_slide_background(ppt_slide)
        add_badge(
            ppt_slide,
            _slide_quality_label(slide),
            10.55,
            0.55,
            1.72,
            0.38,
            fill_color=quality_color(slide),
        )

        _, title_box = add_textbox(
            ppt_slide,
            0.8,
            0.65,
            8.9,
            0.65,
            margins=(0.0, 0.0, 0.0, 0.0),
        )
        set_text_frame_content(
            title_box,
            [
                {
                    "text": slide.title,
                    "font_size": 24,
                    "bold": True,
                    "color": "title",
                    "space_after": 0,
                }
            ],
        )

        if slide.subtitle:
            _, subtitle_box = add_textbox(
                ppt_slide,
                0.82,
                1.18,
                8.8,
                0.45,
                margins=(0.0, 0.0, 0.0, 0.0),
            )
            set_text_frame_content(
                subtitle_box,
                [
                    {
                        "text": slide.subtitle,
                        "font_size": 13,
                        "color": "muted",
                        "space_after": 0,
                    }
                ],
            )

        outline_items: list[str] = []
        for section in _extract_slide_sections(slide):
            if section["kind"] == "bullet_list":
                outline_items.extend(section["items"])

        visible_items = outline_items[:6]
        card_width = 3.35
        card_height = 1.08
        gap_x = 0.25
        gap_y = 0.22
        start_x = 0.82
        start_y = 1.86

        if not visible_items:
            _, body_box = add_textbox(
                ppt_slide,
                0.82,
                1.8,
                7.1,
                4.55,
                fill_color="surface",
                line_color="border",
                margins=(0.18, 0.14, 0.18, 0.12),
            )
            set_text_frame_content(
                body_box,
                [
                    {
                        "text": "当前未生成目录信息。",
                        "font_size": 16,
                        "color": "muted",
                        "space_after": 0,
                    }
                ],
            )
        else:
            for item_index, item in enumerate(visible_items, start=1):
                row = (item_index - 1) // 2
                col = (item_index - 1) % 2
                x = start_x + col * (card_width + gap_x)
                y = start_y + row * (card_height + gap_y)
                fill_color = "surface_alt" if item_index == 1 else "surface"
                line_color = "accent_soft" if item_index == 1 else "border"
                _, card_box = add_textbox(
                    ppt_slide,
                    x,
                    y,
                    card_width,
                    card_height,
                    fill_color=fill_color,
                    line_color=line_color,
                    margins=(0.18, 0.14, 0.18, 0.12),
                )
                set_text_frame_content(
                    card_box,
                    [
                        {
                            "text": f"Part {item_index}",
                            "font_size": 10.5,
                            "bold": True,
                            "color": "accent",
                            "space_after": 8,
                        },
                        {
                            "text": item,
                            "font_size": 15.5,
                            "bold": item_index == 1,
                            "color": "body",
                            "line_spacing": 1.12,
                            "space_after": 0,
                        },
                    ],
                )

        _, info_box = add_textbox(
            ppt_slide,
            8.3,
            1.8,
            4.05,
            4.55,
            fill_color="surface_alt",
            line_color="border",
            margins=(0.16, 0.14, 0.16, 0.12),
        )
        warnings_text = (
            "；".join(w.message for w in deck.generation.warnings[:2])
            if deck.generation.warnings
            else "当前导出使用 DeckSpec 结构化渲染。"
        )
        set_text_frame_content(
            info_box,
            [
                {
                    "text": "导出信息",
                    "font_size": 12,
                    "bold": True,
                    "color": "title",
                    "space_after": 10,
                },
                {
                    "text": f"受众: {deck.meta.audience}",
                    "font_size": 11,
                    "color": "body",
                    "space_after": 6,
                },
                {
                    "text": f"目的: {deck.meta.purpose}",
                    "font_size": 11,
                    "color": "body",
                    "space_after": 6,
                },
                {
                    "text": f"来源模式: {deck.meta.source_mode}",
                    "font_size": 11,
                    "color": "body",
                    "space_after": 6,
                },
                {
                    "text": f"风险提示: {warnings_text}",
                    "font_size": 10.5,
                    "color": "muted",
                    "line_spacing": 1.2,
                    "space_after": 0,
                },
            ],
        )

        add_footer(ppt_slide, slide_index, len(deck.slides), slide)
        add_notes(ppt_slide, slide)

    def render_content_slide(ppt_slide, slide_index: int, slide: DeckSlide) -> None:
        set_slide_background(ppt_slide, "surface")
        add_badge(
            ppt_slide,
            _slide_quality_label(slide),
            10.55,
            0.48,
            1.72,
            0.38,
            fill_color=quality_color(slide),
        )

        from pptx.util import Inches

        accent_rule = ppt_slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.RECTANGLE,
            Inches(0.8),
            Inches(0.48),
            Inches(0.09),
            Inches(0.82),
        )
        accent_rule.fill.solid()
        accent_rule.fill.fore_color.rgb = rgb("accent")
        accent_rule.line.fill.background()

        _, title_box = add_textbox(
            ppt_slide,
            1.0,
            0.56,
            9.1,
            0.65,
            margins=(0.0, 0.0, 0.0, 0.0),
        )
        set_text_frame_content(
            title_box,
            [
                {
                    "text": slide.title,
                    "font_size": 23,
                    "bold": True,
                    "color": "title",
                    "space_after": 0,
                }
            ],
        )

        if slide.subtitle:
            _, subtitle_box = add_textbox(
                ppt_slide,
                1.02,
                1.08,
                8.7,
                0.42,
                margins=(0.0, 0.0, 0.0, 0.0),
            )
            set_text_frame_content(
                subtitle_box,
                [
                    {
                        "text": slide.subtitle,
                        "font_size": 12.5,
                        "color": "muted",
                        "space_after": 0,
                    }
                ],
            )

        sections = _extract_slide_sections(slide)
        chart_specs = _extract_chart_specs(slide)
        primary_chart = chart_specs[0] if chart_specs else None
        bullet_items = collect_bullet_items(slide)
        paragraph_texts = collect_paragraph_texts(slide)
        summary_text = (
            paragraph_texts[0]
            if paragraph_texts
            else _clean_text(slide.subtitle or slide.intent)
        )

        body_x = 0.8
        body_y = 1.65
        body_width = 7.85 if slide.evidence_refs else 11.45
        body_height = 4.95

        if summary_text:
            _, summary_box = add_textbox(
                ppt_slide,
                body_x,
                1.62,
                body_width,
                0.78,
                fill_color="surface_alt",
                line_color="accent_soft",
                margins=(0.18, 0.12, 0.18, 0.1),
            )
            set_text_frame_content(
                summary_box,
                [
                    {
                        "text": "关键摘要",
                        "font_size": 10.5,
                        "bold": True,
                        "color": "accent",
                        "space_after": 5,
                    },
                    {
                        "text": _truncate(summary_text, 120),
                        "font_size": 13.5,
                        "color": "body",
                        "line_spacing": 1.15,
                        "space_after": 0,
                    },
                ],
            )
            body_y = 2.55
            body_height = 4.05

        chart_panel: tuple[float, float, float, float] | None = None
        if primary_chart and slide.evidence_refs:
            body_height = 1.55
            chart_panel = (0.8, 4.15, 7.85, 2.25)
        elif primary_chart:
            body_width = 5.15
            chart_panel = (6.2, body_y, 6.05, body_height)

        bullet_count = len(bullet_items)
        max_bullet_length = max((len(item) for item in bullet_items), default=0)
        use_cards = (
            not slide.evidence_refs
            and primary_chart is None
            and 1 < bullet_count <= 4
            and max_bullet_length <= 34
        )
        use_two_columns = not slide.evidence_refs and primary_chart is None and bullet_count >= 5

        if use_cards:
            card_width = 5.55
            card_height = 1.24 if bullet_count <= 2 else 1.08
            gap_x = 0.35
            gap_y = 0.22
            for item_index, item in enumerate(bullet_items[:4], start=1):
                row = (item_index - 1) // 2
                col = (item_index - 1) % 2
                x = body_x + col * (card_width + gap_x)
                y = body_y + row * (card_height + gap_y)
                _, card_box = add_textbox(
                    ppt_slide,
                    x,
                    y,
                    card_width,
                    card_height,
                    fill_color="bg" if item_index % 2 == 1 else "surface_alt",
                    line_color="border",
                    margins=(0.16, 0.12, 0.16, 0.1),
                )
                set_text_frame_content(
                    card_box,
                    [
                        {
                            "text": f"要点 {item_index}",
                            "font_size": 10.5,
                            "bold": True,
                            "color": "accent",
                            "space_after": 7,
                        },
                        {
                            "text": item,
                            "font_size": 16,
                            "color": "body",
                            "line_spacing": 1.15,
                            "space_after": 0,
                        },
                    ],
                )
        elif use_two_columns:
            split_columns = _split_evenly(bullet_items, column_count=2)
            column_width = 5.55
            gap_x = 0.35
            for column_index, items in enumerate(split_columns):
                x = body_x + column_index * (column_width + gap_x)
                _, column_box = add_textbox(
                    ppt_slide,
                    x,
                    body_y,
                    column_width,
                    body_height,
                    fill_color="bg",
                    line_color="border",
                    margins=(0.18, 0.14, 0.18, 0.12),
                )
                column_paragraphs: list[dict[str, Any]] = [
                    {
                        "text": f"关键要点 {column_index + 1}",
                        "font_size": 10.5,
                        "bold": True,
                        "color": "accent",
                        "space_after": 8,
                    }
                ]
                for item in items:
                    column_paragraphs.append(
                        {
                            "text": f"• {item}",
                            "font_size": 14.5,
                            "color": "body",
                            "line_spacing": 1.16,
                            "space_after": 8,
                        }
                    )
                set_text_frame_content(column_box, column_paragraphs)
        else:
            _, body_box = add_textbox(
                ppt_slide,
                body_x,
                body_y,
                body_width,
                body_height,
                fill_color="bg",
                line_color="border",
                margins=(0.18, 0.14, 0.18, 0.12),
            )

            body_font_size = 17 if bullet_count <= 4 else 15
            body_paragraphs: list[dict[str, Any]] = []
            for section in sections:
                role = _clean_text(section.get("role", ""))
                if role and role not in {"main_points", "summary"}:
                    body_paragraphs.append(
                        {
                            "text": role.replace("_", " ").title(),
                            "font_size": 10.5,
                            "bold": True,
                            "color": "accent",
                            "space_after": 6,
                        }
                    )
                if section["kind"] == "bullet_list":
                    for item in section["items"]:
                        body_paragraphs.append(
                            {
                                "text": f"• {item}",
                                "font_size": body_font_size,
                                "color": "body",
                                "line_spacing": 1.18,
                                "space_after": 10,
                            }
                        )
                else:
                    body_paragraphs.append(
                        {
                            "text": section["text"],
                            "font_size": 15,
                            "color": "body",
                            "line_spacing": 1.2,
                            "space_after": 10,
                        }
                    )
            set_text_frame_content(body_box, body_paragraphs)

        if primary_chart and chart_panel:
            add_chart_panel(
                ppt_slide,
                primary_chart,
                chart_panel[0],
                chart_panel[1],
                chart_panel[2],
                chart_panel[3],
            )

        if slide.evidence_refs:
            _, evidence_box = add_textbox(
                ppt_slide,
                8.95,
                1.62,
                3.55,
                4.98,
                fill_color="surface_alt",
                line_color="border",
                margins=(0.16, 0.14, 0.16, 0.12),
            )
            evidence_paragraphs: list[dict[str, Any]] = [
                {
                    "text": "证据来源",
                    "font_size": 12,
                    "bold": True,
                    "color": "title",
                    "space_after": 8,
                }
            ]
            for ref_index, ref in enumerate(slide.evidence_refs[:3], start=1):
                confidence = (
                    f" ({round(ref.confidence * 100)}%)"
                    if ref.confidence and ref.confidence > 0
                    else ""
                )
                evidence_paragraphs.append(
                    {
                        "text": f"{ref_index}. {ref.source_title}{confidence}",
                        "font_size": 10.5,
                        "bold": True,
                        "color": "body",
                        "space_after": 4,
                    }
                )
                evidence_paragraphs.append(
                    {
                        "text": _truncate(_clean_text(ref.snippet), 150) or "无摘要",
                        "font_size": 9.5,
                        "color": "muted",
                        "line_spacing": 1.2,
                        "space_after": 10,
                    }
                )
            evidence_paragraphs.append(
                {
                    "text": f"状态: {_slide_quality_label(slide)}",
                    "font_size": 10,
                    "bold": True,
                    "color": quality_color(slide),
                    "space_after": 0,
                }
            )
            set_text_frame_content(evidence_box, evidence_paragraphs)

        add_footer(ppt_slide, slide_index, len(deck.slides), slide)
        add_notes(ppt_slide, slide)

    def render_appendix_slide(ppt_slide, slide_index: int, slide: DeckSlide) -> None:
        set_slide_background(ppt_slide)
        add_badge(
            ppt_slide,
            _slide_quality_label(slide),
            10.55,
            0.55,
            1.72,
            0.38,
            fill_color=quality_color(slide),
        )

        _, title_box = add_textbox(
            ppt_slide,
            0.8,
            0.65,
            10.0,
            0.62,
            margins=(0.0, 0.0, 0.0, 0.0),
        )
        set_text_frame_content(
            title_box,
            [
                {
                    "text": slide.title,
                    "font_size": 22,
                    "bold": True,
                    "color": "title",
                    "space_after": 0,
                }
            ],
        )

        if slide.subtitle:
            _, subtitle_box = add_textbox(
                ppt_slide,
                0.82,
                1.14,
                9.4,
                0.4,
                margins=(0.0, 0.0, 0.0, 0.0),
            )
            set_text_frame_content(
                subtitle_box,
                [
                    {
                        "text": slide.subtitle,
                        "font_size": 12.5,
                        "color": "muted",
                        "space_after": 0,
                    }
                ],
            )

        appendix_items: list[str] = []
        for section in _extract_slide_sections(slide):
            if section["kind"] == "bullet_list":
                appendix_items.extend(section["items"])
            else:
                appendix_items.append(section["text"])

        total_items = len(appendix_items)
        _, stat_box = add_textbox(
            ppt_slide,
            9.58,
            0.72,
            2.88,
            0.82,
            fill_color="surface_alt",
            line_color="border",
            margins=(0.14, 0.1, 0.14, 0.08),
        )
        set_text_frame_content(
            stat_box,
            [
                {
                    "text": "来源统计",
                    "font_size": 10.5,
                    "bold": True,
                    "color": "accent",
                    "space_after": 4,
                    "align": PP_ALIGN.CENTER,
                },
                {
                    "text": f"共 {total_items} 个来源",
                    "font_size": 13,
                    "bold": True,
                    "color": "title",
                    "align": PP_ALIGN.CENTER,
                    "space_after": 0,
                },
            ],
        )

        if total_items <= 12:
            card_width = 5.55
            card_height = 0.68 if total_items <= 8 else 0.56
            gap_x = 0.3
            gap_y = 0.16
            for item_index, item in enumerate(appendix_items, start=1):
                row = (item_index - 1) // 2
                col = (item_index - 1) % 2
                x = 0.8 + col * (card_width + gap_x)
                y = 1.78 + row * (card_height + gap_y)
                _, item_box = add_textbox(
                    ppt_slide,
                    x,
                    y,
                    card_width,
                    card_height,
                    fill_color="surface" if item_index % 2 else "bg",
                    line_color="border",
                    margins=(0.14, 0.08, 0.14, 0.06),
                )
                set_text_frame_content(
                    item_box,
                    [
                        {
                            "text": f"{item_index:02d}",
                            "font_size": 9.5,
                            "bold": True,
                            "color": "accent",
                            "space_after": 3,
                        },
                        {
                            "text": item,
                            "font_size": 11.5 if total_items <= 8 else 10.5,
                            "color": "body",
                            "space_after": 0,
                            "line_spacing": 1.05,
                        },
                    ],
                )
        else:
            columns = _split_evenly(appendix_items, column_count=2)
            font_size = 11
            for column_index, items in enumerate(columns):
                x = 0.8 + column_index * 6.1
                _, column_box = add_textbox(
                    ppt_slide,
                    x,
                    1.78,
                    5.45,
                    4.9,
                    fill_color="surface",
                    line_color="border",
                    margins=(0.16, 0.12, 0.16, 0.1),
                )
                column_paragraphs = [
                    {
                        "text": f"来源 {column_index + 1}",
                        "font_size": 11,
                        "bold": True,
                        "color": "accent",
                        "space_after": 8,
                    }
                ]
                column_paragraphs.extend(
                    {
                        "text": f"• {item}",
                        "font_size": font_size,
                        "color": "body",
                        "line_spacing": 1.12,
                        "space_after": 6,
                    }
                    for item in items
                )
                set_text_frame_content(column_box, column_paragraphs)

        add_footer(ppt_slide, slide_index, len(deck.slides), slide)
        add_notes(ppt_slide, slide)

    presentation = Presentation()
    presentation.slide_width = 12192000
    presentation.slide_height = 6858000
    presentation.core_properties.title = deck.meta.title
    presentation.core_properties.author = deck.meta.author or "system"
    presentation.core_properties.subject = deck.meta.subtitle or deck.meta.purpose
    presentation.core_properties.keywords = "deck,pptx,insightdesk"

    blank_layout = presentation.slide_layouts[6]
    for index, slide in enumerate(deck.slides):
        ppt_slide = presentation.slides.add_slide(blank_layout)
        if slide.type == "cover" or index == 0:
            render_cover_slide(ppt_slide, index, slide)
        elif slide.type == "outline":
            render_outline_slide(ppt_slide, index, slide)
        elif slide.type.startswith("appendix"):
            render_appendix_slide(ppt_slide, index, slide)
        else:
            render_content_slide(ppt_slide, index, slide)

    buffer = io.BytesIO()
    presentation.save(buffer)
    buffer.seek(0)
    return buffer.read()


def build_export_filename(deck: DeckSpec, extension: str) -> str:
    safe_title = "".join(
        char for char in deck.meta.title if char.isalnum() or char in (" ", "-", "_")
    ).strip()[:40]
    return f"{safe_title or 'deck'}.{extension}"


class SQLiteDeckStore:
    def __init__(self, db_path: str = "./chat_history.db"):
        self.db_path = db_path
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
        return DeckSpec.model_validate_json(row[0])

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
