"""?????????????????"""

import json
import re
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

GROUNDING_SOURCE_TYPES = {"doc", "web", "attachment"}

def _clip_attachment_source_snippet(text: str, max_chars: int = 220) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rstrip() + " ...[节选]"


def _build_attachment_sources(
    raw_files: Optional[list[dict[str, Any]]] = None,
    raw_images: Optional[list[dict[str, Any]]] = None,
    answer_group_id: str = "",
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for index, file in enumerate(raw_files or [], start=1):
        if not isinstance(file, dict):
            continue
        title = str(file.get("name") or "").strip() or f"会话附件 {index}"
        snippet = _clip_attachment_source_snippet(str(file.get("extracted_text") or ""))
        if not snippet:
            snippet = "该附件已加入当前会话上下文，可作为回答依据。"
        media_type = str(file.get("media_type") or "application/octet-stream").strip()
        signature = ("attachment", title, snippet)
        if signature in seen:
            continue
        seen.add(signature)
        source: dict[str, Any] = {
            "type": "attachment",
            "title": title,
            "snippet": snippet,
            "attachment_kind": "file",
            "media_type": media_type,
        }
        data_url = str(file.get("data_url") or "").strip()
        if data_url:
            source["data_url"] = data_url
        if answer_group_id:
            source["answer_group_id"] = answer_group_id
        sources.append(source)

    for index, image in enumerate(raw_images or [], start=1):
        if not isinstance(image, dict):
            continue
        title = str(image.get("name") or "").strip() or f"会话图片 {index}"
        snippet = "用户在当前会话上传了这张图片，可结合视觉内容一起理解回答。"
        media_type = str(image.get("media_type") or "image/png").strip()
        signature = ("attachment", title, snippet)
        if signature in seen:
            continue
        seen.add(signature)
        source = {
            "type": "attachment",
            "title": title,
            "snippet": snippet,
            "attachment_kind": "image",
            "media_type": media_type,
        }
        data_url = str(image.get("data_url") or "").strip()
        if data_url:
            source["data_url"] = data_url
        if answer_group_id:
            source["answer_group_id"] = answer_group_id
        sources.append(source)

    return sources


def _merge_sources_with_attachments(
    existing_sources: Optional[list[dict[str, Any]]] = None,
    raw_files: Optional[list[dict[str, Any]]] = None,
    raw_images: Optional[list[dict[str, Any]]] = None,
    answer_group_id: str = "",
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for source in existing_sources or []:
        if not isinstance(source, dict):
            continue
        normalized = dict(source)
        signature = (
            str(normalized.get("type") or "").strip(),
            str(normalized.get("title") or "").strip(),
            str(normalized.get("snippet") or "").strip(),
        )
        if signature in seen:
            continue
        seen.add(signature)
        merged.append(normalized)

    for source in _build_attachment_sources(
        raw_files=raw_files,
        raw_images=raw_images,
        answer_group_id=answer_group_id,
    ):
        signature = (
            str(source.get("type") or "").strip(),
            str(source.get("title") or "").strip(),
            str(source.get("snippet") or "").strip(),
        )
        if signature in seen:
            continue
        seen.add(signature)
        merged.append(source)

    return merged


def _extract_sources_from_marked_result(result: Any) -> tuple[str, list[dict[str, Any]]]:
    text = str(result or "")
    marker = "__SOURCES__:"
    if marker not in text:
        return text.rstrip(), []

    clean_result, _, sources_json = text.partition(marker)
    try:
        raw_sources = json.loads(sources_json)
    except Exception:
        raw_sources = []

    sources = [item for item in raw_sources if isinstance(item, dict)]
    return clean_result.rstrip(), sources


def _extract_sources_from_intermediate_steps(intermediate_steps: Any) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str]] = set()

    for step in intermediate_steps or []:
        if not isinstance(step, (list, tuple)) or len(step) < 2:
            continue
        _, observation = step[0], step[1]
        if not isinstance(observation, str):
            continue
        _, sources = _extract_sources_from_marked_result(observation)
        for source in sources:
            key = (
                str(source.get("type") or "").strip(),
                str(source.get("title") or "").strip(),
                str(source.get("snippet") or "").strip(),
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            merged.append(dict(source))

    return merged


def _source_is_grounding_evidence(source: dict[str, Any]) -> bool:
    source_type = str(source.get("type") or "").strip()
    if source_type not in GROUNDING_SOURCE_TYPES:
        return False
    return bool(str(source.get("title") or "").strip() or str(source.get("snippet") or "").strip())


def _build_retrieval_meta_from_sources(
    sources: Optional[list[dict[str, Any]]],
) -> Optional[dict[str, Any]]:
    items = [source for source in (sources or []) if isinstance(source, dict)]
    if not items:
        return None

    retrieval_modes: list[str] = []
    channels: list[str] = []
    matched_terms: list[str] = []
    scores: list[float] = []
    source_titles: list[str] = []
    for source in items:
        mode = str(source.get("retrieval_mode") or "").strip()
        if mode:
            retrieval_modes.append(mode)
        channel = str(source.get("search_channel") or "").strip()
        if channel:
            channels.append(channel)
        title = str(source.get("title") or "").strip()
        if title:
            source_titles.append(title)
        raw_terms = source.get("matched_terms")
        if isinstance(raw_terms, list):
            matched_terms.extend(
                str(term).strip()
                for term in raw_terms
                if str(term).strip()
            )
        raw_score = source.get("score")
        if isinstance(raw_score, (int, float)):
            scores.append(float(raw_score))

    unique_modes = list(dict.fromkeys(retrieval_modes))
    unique_channels = list(dict.fromkeys(channels))
    unique_titles = list(dict.fromkeys(source_titles))
    unique_terms = list(dict.fromkeys(matched_terms))

    if not unique_modes and not unique_channels and not scores and not unique_terms:
        return None

    return {
        "primary_mode": unique_modes[0] if unique_modes else "",
        "modes": unique_modes,
        "channels": unique_channels,
        "source_count": len(items),
        "source_titles": unique_titles[:3],
        "matched_terms": unique_terms[:6],
        "top_score": round(max(scores), 4) if scores else None,
    }
