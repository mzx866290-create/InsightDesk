"""Chat input helper utilities."""

import base64
import binascii
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote_to_bytes

from fastapi import HTTPException

SUPPORTED_CHAT_IMAGE_MEDIA_TYPES = frozenset(
    {
        "image/gif",
        "image/jpeg",
        "image/png",
        "image/webp",
    }
)


@dataclass(frozen=True)
class ChatImageConfig:
    """Limits applied to image attachments before they reach an LLM provider."""

    max_bytes: int = 10 * 1024 * 1024
    max_count: int = 4
    max_total_bytes: int = 20 * 1024 * 1024
    supported_media_types: frozenset[str] = SUPPORTED_CHAT_IMAGE_MEDIA_TYPES


def _chat_input_value(item: Any, field: str) -> str:
    value = item.get(field) if isinstance(item, dict) else getattr(item, field, "")
    return str(value or "").strip()


def _parse_data_url(data_url: str, file_name: str) -> tuple[str, str, bool]:
    if not data_url.startswith("data:") or "," not in data_url:
        raise HTTPException(
            status_code=400,
            detail=f"附件数据无效：{file_name}",
        )

    header, encoded = data_url.split(",", 1)
    metadata = header[5:].split(";")
    media_type = metadata[0].strip().lower()
    is_base64 = any(part.strip().lower() == "base64" for part in metadata[1:])
    return media_type, encoded, is_base64


def _estimated_base64_size(encoded: str) -> int:
    padding = 2 if encoded.endswith("==") else 1 if encoded.endswith("=") else 0
    return max(0, (len(encoded) // 4) * 3 - padding)


def validate_chat_images(
    images: list[Any],
    *,
    config: ChatImageConfig | None = None,
) -> None:
    """Validate image count, type and decoded payload size before model dispatch."""

    image_config = config or ChatImageConfig()
    if len(images) > image_config.max_count:
        raise HTTPException(
            status_code=400,
            detail=f"每条消息最多只能附加 {image_config.max_count} 张图片。",
        )

    estimated_total_bytes = 0
    decoded_total_bytes = 0
    supported_types_label = "PNG、JPEG、WebP 和 GIF"

    for index, image in enumerate(images, start=1):
        name = _chat_input_value(image, "name") or f"图片 {index}"
        declared_media_type = (
            _chat_input_value(image, "media_type").lower().split(";", 1)[0].strip()
        )
        data_url = _chat_input_value(image, "data_url")

        try:
            data_url_media_type, encoded, is_base64 = _parse_data_url(data_url, name)
        except HTTPException as exc:
            raise HTTPException(
                status_code=400,
                detail=f"图片数据无效：{name}",
            ) from exc

        if (
            declared_media_type not in image_config.supported_media_types
            or data_url_media_type not in image_config.supported_media_types
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"不支持的图片类型：{name}"
                    f"（仅支持 {supported_types_label}）"
                ),
            )
        if declared_media_type != data_url_media_type:
            raise HTTPException(
                status_code=400,
                detail=f"图片媒体类型与 data URL 不一致：{name}",
            )
        if not is_base64:
            raise HTTPException(
                status_code=400,
                detail=f"图片必须使用 Base64 data URL：{name}",
            )
        if not encoded:
            raise HTTPException(
                status_code=400,
                detail=f"图片内容为空：{name}",
            )

        estimated_bytes = _estimated_base64_size(encoded)
        if estimated_bytes > image_config.max_bytes:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"图片过大：{name}"
                    f"（单张最大 {image_config.max_bytes // (1024 * 1024)} MB）"
                ),
            )
        estimated_total_bytes += estimated_bytes
        if estimated_total_bytes > image_config.max_total_bytes:
            raise HTTPException(
                status_code=400,
                detail=(
                    "图片总大小超过限制"
                    f"（最大 {image_config.max_total_bytes // (1024 * 1024)} MB）。"
                ),
            )

        try:
            payload = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail=f"图片数据已损坏：{name}",
            ) from exc

        decoded_bytes = len(payload)
        if decoded_bytes == 0:
            raise HTTPException(
                status_code=400,
                detail=f"图片内容为空：{name}",
            )
        if decoded_bytes > image_config.max_bytes:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"图片过大：{name}"
                    f"（单张最大 {image_config.max_bytes // (1024 * 1024)} MB）"
                ),
            )
        decoded_total_bytes += decoded_bytes
        if decoded_total_bytes > image_config.max_total_bytes:
            raise HTTPException(
                status_code=400,
                detail=(
                    "图片总大小超过限制"
                    f"（最大 {image_config.max_total_bytes // (1024 * 1024)} MB）。"
                ),
            )


def validate_chat_payload(
    message: str,
    images: list[Any],
    files: list[Any],
    *,
    image_config: ChatImageConfig | None = None,
) -> None:
    if not (message.strip() or images or files):
        raise HTTPException(
            status_code=400,
            detail="消息内容、图片和文件不能同时为空。",
        )
    validate_chat_images(images, config=image_config)


def chat_file_suffix(name: str) -> str:
    base_name = (name or "").replace("\\", "/").split("/")[-1]
    parts = base_name.rsplit(".", 1)
    if len(parts) != 2:
        return ""
    return "." + parts[1].lower()


def decode_data_url(data_url: str, file_name: str) -> bytes:
    _, encoded, is_base64 = _parse_data_url(data_url, file_name)
    try:
        if is_base64:
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
