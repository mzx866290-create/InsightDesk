"""Compatibility re-export for ``backend.helpers.chat_input_helpers``."""

from backend.helpers.chat_input_helpers import (
    build_message_with_files,
    build_user_input,
    chat_file_suffix,
    clip_attachment_preview_text,
    decode_data_url,
    model_supports_images,
    stringify_user_input,
    user_input_has_images,
    validate_chat_payload,
)

__all__ = [
    "build_message_with_files",
    "build_user_input",
    "chat_file_suffix",
    "clip_attachment_preview_text",
    "decode_data_url",
    "model_supports_images",
    "stringify_user_input",
    "user_input_has_images",
    "validate_chat_payload",
]
