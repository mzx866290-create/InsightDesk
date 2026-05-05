"""Chat input helper utilities."""

import base64
import binascii
import re
from typing import Any
from urllib.parse import unquote_to_bytes

from fastapi import HTTPException


def validate_chat_payload(
    message: str,
    images: list[Any],
    files: list[Any],
) -> None:
    if message.strip() or images or files:
        return
    raise HTTPException(
        status_code=400,
        detail="消息内容、图片和文件不能同时为空。",
    )


def chat_file_suffix(name: str) -> str:
    base_name = (name or "").replace("\\", "/").split("/")[-1]
    parts = base_name.rsplit(".", 1)
    if len(parts) != 2:
        return ""
    return "." + parts[1].lower()


def decode_data_url(data_url: str, file_name: str) -> bytes:
    if not data_url.startswith("data:") or "," not in data_url:
        raise HTTPException(
            status_code=400,
            detail=f"附件数据无效：{file_name}",
        )

    header, encoded = data_url.split(",", 1)
    try:
        if ";base64" in header:
            return base64.b64decode(encoded, validate=True)
        return unquote_to_bytes(encoded)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"附件数据已损坏：{file_name}",
        ) from exc


def clip_attachment_preview_text(text: str, limit: int) -> str:
    cleaned = re.sub(r"\n{3,}", "\n\n", (text or "").strip())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rstrip() + "\n...[附件预览已截断]"


def build_message_with_files(message: str, attachment_context: str = "") -> str:
    base_message = message.strip()
    if not attachment_context:
        return base_message

    parts = []
    if base_message:
        parts.append(base_message)
    else:
        parts.append("请阅读附件内容，并基于附件信息进行回答。")
    parts.append(attachment_context)
    return "\n\n".join(parts).strip()


def build_user_input(
    message: str,
    images: list[Any],
    attachment_context: str = "",
) -> Any:
    message_with_files = build_message_with_files(message, attachment_context)
    if not images:
        return message_with_files

    content: list[dict[str, Any]] = []
    if message_with_files.strip():
        content.append({"type": "text", "text": message_with_files})

    for image in images:
        data_url = str(getattr(image, "data_url", "") or "").strip()
        if not data_url and isinstance(image, dict):
            data_url = str(image.get("data_url") or "").strip()
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": data_url},
            }
        )

    return content


def user_input_has_images(user_input: Any) -> bool:
    if not isinstance(user_input, list):
        return False
    return any(
        isinstance(item, dict) and item.get("type") == "image_url"
        for item in user_input
    )


def model_supports_images(provider: str, model_name: str) -> bool:
    del provider
    model = (model_name or "").strip().lower()
    if not model:
        return False

    positive_hints = (
        "llava",
        "vision",
        "minicpm-v",
        "minicpmv",
        "internvl",
        "qwen-vl",
        "qwen2-vl",
        "qwen2.5-vl",
        "qwen2vl",
        "qwen2.5vl",
        "gpt-4o",
        "gpt-4.1",
        "o4-mini",
        "claude-3",
        "claude-4",
        "gemini-1.5",
        "gemini-2",
        "gemma3",
        "pixtral",
        "moondream",
    )
    return any(hint in model for hint in positive_hints)


def stringify_user_input(user_input: Any) -> str:
    if isinstance(user_input, str):
        return user_input
    if isinstance(user_input, list):
        text_parts: list[str] = []
        image_count = 0
        for item in user_input:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and item.get("text"):
                text_parts.append(str(item["text"]))
            elif item.get("type") == "image_url":
                image_count += 1
        if image_count:
            text_parts.append(f"[用户上传了 {image_count} 张图片]")
        return "\n".join(part for part in text_parts if part).strip()
    return str(user_input)
