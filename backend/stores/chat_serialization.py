"""Shared chat-store serialization helpers."""

from __future__ import annotations

import json
from typing import Any


def normalize_content(content: Any) -> str:
    """Convert LangChain message content to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
            else:
                parts.append(str(item))
        return "\n".join(p for p in parts if p).strip()
    return str(content)


def parse_json_list(raw: Any) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        parsed = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def parse_string_list(raw: Any) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, list):
        return []

    values: list[str] = []
    for item in parsed:
        if not isinstance(item, str):
            continue
        normalized = item.strip()
        if normalized:
            values.append(normalized)
    return values


def parse_json_object(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def normalize_token_usage(value: Any = None) -> dict[str, Any]:
    payload = value if isinstance(value, dict) else parse_json_object(value)

    def as_int(key: str) -> int:
        try:
            return max(0, int(payload.get(key) or 0))
        except (TypeError, ValueError):
            return 0

    prompt_tokens = as_int("prompt_tokens")
    completion_tokens = as_int("completion_tokens")
    total_tokens = as_int("total_tokens") or prompt_tokens + completion_tokens
    normalized: dict[str, Any] = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "estimated": bool(payload.get("estimated", False)),
    }
    for key in (
        "panel_id",
        "model_id",
        "estimation_method",
        "call_count",
        "real_count",
        "estimated_count",
    ):
        if key in payload:
            normalized[key] = payload[key]
    return normalized if any((prompt_tokens, completion_tokens, total_tokens, payload)) else {}


def normalize_metadata_list(
    items: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in items or []:
        if isinstance(item, dict):
            normalized.append(item)
    return normalized


def normalize_images(
    images: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for image in images or []:
        if not isinstance(image, dict):
            continue
        data_url = str(image.get("data_url") or "").strip()
        if not data_url:
            continue
        normalized.append(
            {
                "name": str(image.get("name") or "").strip(),
                "media_type": str(image.get("media_type") or "image/png").strip(),
                "data_url": data_url,
            }
        )
    return normalized


def normalize_files(
    files: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for file in files or []:
        if not isinstance(file, dict):
            continue
        normalized.append(
            {
                "name": str(file.get("name") or "").strip(),
                "media_type": str(
                    file.get("media_type") or "application/octet-stream"
                ).strip(),
                "data_url": str(file.get("data_url") or "").strip(),
                "size_bytes": int(file.get("size_bytes") or 0),
                "extracted_text": str(file.get("extracted_text") or "").strip(),
            }
        )
    return normalized


__all__ = [
    "normalize_content",
    "normalize_files",
    "normalize_images",
    "normalize_metadata_list",
    "normalize_token_usage",
    "parse_json_list",
    "parse_json_object",
    "parse_string_list",
]
