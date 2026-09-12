"""Deck shared utilities, constants, and chat-QA extraction.

This is a leaf module with no dependencies on deck_service or deck_export.
Both of those import from here instead of containing these definitions inline.
"""

from __future__ import annotations

import time
from typing import Any

from backend.deck_models import DeckThemeName

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

_FALLBACK_SECTION_TITLES = ["Topic Overview", "Key Findings", "Recommendations"]
_FALLBACK_SLIDE_TITLES = [
    "Topic overview and core conclusion",
    "关键信息摘要",
    "Use cases and action recommendations",
    "Follow-up priorities and risk notes",
    "补充观察",
]


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _clean_text(text: Any) -> str:
    return " ".join(str(text).strip().split())


def _metadata_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def normalize_deck_theme(theme: Any) -> DeckThemeName:
    raw = _clean_text(theme).lower().replace("-", "_").replace(" ", "_")
    aliases: dict[str, DeckThemeName] = {
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
    return cleaned[: limit - 1].rstrip() + "..."


def _truncate_multiline(text: Any, limit: int) -> str:
    normalized = str(text).replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "..."


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
        "request processing error",
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
        raise ValueError("The latest chat answers are failed results and cannot be converted into a deck.")
    raise ValueError("This session has no successful Q&A content for deck generation.")


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

        clean_points = [_coerce_chart_number(item) for item in raw_points]
        if not any(item is not None for item in clean_points):
            continue

        target_size = label_count or len(clean_points)
        normalized_points = [
            _coerce_chart_number(item) or 0.0 for item in raw_points[:target_size]
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
