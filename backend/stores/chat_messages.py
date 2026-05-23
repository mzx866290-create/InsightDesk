"""Message-level helpers shared by chat stores."""

from __future__ import annotations

import os
import re
from typing import Any

from backend.stores.chat_serialization import (
    normalize_content,
    normalize_files,
    normalize_images,
)

ATTACHMENT_CONTEXT_START_MARKER = "[[CHAT_FILE_CONTEXT_START]]"
ATTACHMENT_CONTEXT_END_MARKER = "[[CHAT_FILE_CONTEXT_END]]"


def env_int(name: str, default: int) -> int:
    """Read integer value from env with fallback."""
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def build_retrieval_source_key(source: Any) -> str:
    if not isinstance(source, dict):
        raise ValueError("source 必须是对象")
    source_type = " ".join(str(source.get("type") or "").strip().split()).lower()
    source_title = " ".join(normalize_content(source.get("title", "")).strip().split())
    source_url = " ".join(normalize_content(source.get("url", "")).strip().split())
    source_snippet = " ".join(
        normalize_content(source.get("snippet", "")).strip().split()
    )
    source_index = source.get("index")
    normalized_index = ""
    if source_index is not None:
        normalized_index = str(source_index).strip()

    return "||".join(
        [
            source_type,
            source_title,
            source_url,
            source_snippet[:200],
            normalized_index,
        ]
    )


def build_search_preview(content: Any, query: str, limit: int = 120) -> str:
    normalized_content = " ".join(normalize_content(content).split())
    if not normalized_content:
        return ""

    normalized_query = query.strip().lower()
    if not normalized_query:
        return normalized_content[:limit]

    lower_content = normalized_content.lower()
    match_index = lower_content.find(normalized_query)
    if match_index < 0:
        preview = normalized_content[:limit]
        return preview + ("..." if len(normalized_content) > limit else "")

    start = max(0, match_index - 28)
    end = min(len(normalized_content), match_index + len(normalized_query) + 72)
    preview = normalized_content[start:end].strip()
    if start > 0:
        preview = "..." + preview
    if end < len(normalized_content):
        preview += "..."
    return preview


def build_message_search_match_query(query: str) -> str:
    terms = [
        token.strip()
        for token in re.findall(
            r"[0-9A-Za-z_]+|[\u4e00-\u9fff]+", str(query or "").lower()
        )
        if token.strip()
    ]
    if not terms:
        return ""
    return " AND ".join(f'"{term.replace('"', '""')}"' for term in terms[:8])


def derive_session_title(
    content_text: str,
    images: list[dict[str, Any]] | None = None,
    files: list[dict[str, Any]] | None = None,
) -> str:
    if content_text.strip():
        title = content_text[:50].strip()
        if len(content_text) > 50:
            title += "..."
        return title

    normalized_files = normalize_files(files)
    if normalized_files:
        name = str(normalized_files[0].get("name") or "").strip() or "附件对话"
        return f"{name[:47]}..." if len(name) > 50 else name

    normalized_images = normalize_images(images)
    if normalized_images:
        return "图片对话"

    return ""


def build_human_message_content_for_model(
    content_text: str,
    images: list[dict[str, Any]] | None = None,
    files: list[dict[str, Any]] | None = None,
) -> str:
    parts: list[str] = []
    base_text = (content_text or "").strip()
    normalized_files = normalize_files(files)
    normalized_images = normalize_images(images)

    if base_text:
        parts.append(base_text)

    file_sections: list[str] = []
    for index, file in enumerate(normalized_files, start=1):
        file_name = str(file.get("name") or "").strip()
        extracted_text = str(file.get("extracted_text") or "").strip()
        section_lines = [f"[附件 {index}]"]
        if file_name:
            section_lines.append(f"文件名：{file_name}")
            # Keep an English label for downstream parsers that already look for it.
            section_lines.append(f"File name: {file_name}")
        if extracted_text:
            section_lines.extend(["内容：", extracted_text])
        file_sections.append("\n".join(section_lines))

    if file_sections:
        if not base_text:
            parts.append("请阅读附件内容，并基于附件信息进行回答。")
        parts.append(
            "\n".join(
                [
                    ATTACHMENT_CONTEXT_START_MARKER,
                    "以下文本提取自用户上传的附件。回答时请将其作为高优先级上下文。",
                    "",
                    "\n\n---\n\n".join(file_sections),
                    ATTACHMENT_CONTEXT_END_MARKER,
                ]
            )
        )

    if normalized_images:
        parts.append(f"[用户上传了 {len(normalized_images)} 张图片]")

    return "\n\n".join(part for part in parts if part).strip()


def group_message_ids_for_history_pruning(
    rows: list[tuple[Any, ...]],
) -> list[list[int]]:
    """
    Group persisted message ids into deletion-safe conversation units.

    Messages that share an answer_group_id are always kept together. Older
    ungrouped history falls back to keeping one human turn with its following
    AI replies so pruning does not leave orphaned half-turns behind.
    """
    grouped_ids: list[list[int]] = []
    answer_group_indexes: dict[str, int] = {}
    current_ungrouped_turn_index: int | None = None

    for row in rows:
        message_id = int(row[0])
        msg_type = str(row[1] or "").strip().lower()
        answer_group_id = str(row[2] or "").strip()

        if answer_group_id:
            group_index = answer_group_indexes.get(answer_group_id)
            if group_index is None:
                group_index = len(grouped_ids)
                grouped_ids.append([])
                answer_group_indexes[answer_group_id] = group_index
            grouped_ids[group_index].append(message_id)
            continue

        if msg_type == "human":
            grouped_ids.append([message_id])
            current_ungrouped_turn_index = len(grouped_ids) - 1
            continue

        if msg_type == "ai" and current_ungrouped_turn_index is not None:
            grouped_ids[current_ungrouped_turn_index].append(message_id)
            continue

        grouped_ids.append([message_id])
        current_ungrouped_turn_index = (
            len(grouped_ids) - 1 if msg_type == "ai" else None
        )

    return grouped_ids


__all__ = [
    "ATTACHMENT_CONTEXT_END_MARKER",
    "ATTACHMENT_CONTEXT_START_MARKER",
    "build_human_message_content_for_model",
    "build_message_search_match_query",
    "build_retrieval_source_key",
    "build_search_preview",
    "derive_session_title",
    "env_int",
    "group_message_ids_for_history_pruning",
]
