import logging
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from fastapi import HTTPException

from api_chat_input_helpers import (
    chat_file_suffix,
    clip_attachment_preview_text,
    decode_data_url,
)


@dataclass(frozen=True)
class ChatFileConfig:
    context_end_marker: str
    context_start_marker: str
    max_bytes: int
    max_chars_per_file: int
    max_count: int
    max_total_chars: int
    preview_chars: int
    supported_extensions: frozenset[str]


def _extract_text_parts(
    temp_path: str,
    suffix: str,
    chat_file: Any,
    pipeline: Any,
) -> list[str]:
    try:
        docs = pipeline.load_file(temp_path)
        return [
            str(getattr(doc, "page_content", "")).strip()
            for doc in docs
            if str(getattr(doc, "page_content", "")).strip()
        ]
    except Exception as exc:
        if suffix in {".txt", ".md", ".csv"}:
            for encoding in ("utf-8", "utf-8-sig", "gb18030"):
                try:
                    direct_text = Path(temp_path).read_text(encoding=encoding)
                    if direct_text.strip():
                        return [direct_text.strip()]
                except UnicodeDecodeError:
                    continue
        raise HTTPException(
            status_code=400,
            detail=f"解析附件失败：{chat_file.name}",
        ) from exc


def prepare_chat_files(
    files: Iterable[Any],
    *,
    config: ChatFileConfig,
    logger: logging.Logger | None = None,
    pipeline_factory: Callable[[], Any] | None = None,
) -> tuple[list[dict[str, Any]], str]:
    file_list = list(files)
    if not file_list:
        return [], ""
    if len(file_list) > config.max_count:
        raise HTTPException(
            status_code=400,
            detail=f"每条消息最多只能附加 {config.max_count} 个文件。",
        )

    active_logger = logger or logging.getLogger(__name__)
    if pipeline_factory is None:
        from doc_pipeline import DocPipeline

        pipeline = DocPipeline()
    else:
        pipeline = pipeline_factory()

    prepared_files: list[dict[str, Any]] = []
    sections: list[str] = []
    remaining_chars = config.max_total_chars

    for index, chat_file in enumerate(file_list, start=1):
        suffix = chat_file_suffix(chat_file.name)
        if suffix not in config.supported_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的附件类型：{chat_file.name}",
            )

        payload = decode_data_url(chat_file.data_url, chat_file.name)
        if not payload:
            raise HTTPException(
                status_code=400,
                detail=f"附件为空：{chat_file.name}",
            )
        if len(payload) > config.max_bytes:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"附件过大：{chat_file.name} "
                    f"（最大 {config.max_bytes // (1024 * 1024)} MB）"
                ),
            )

        fd, temp_path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)

        try:
            text_parts = _extract_text_parts(temp_path, suffix, chat_file, pipeline)
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                active_logger.warning(
                    "Failed to delete chat attachment temp file: %s", temp_path
                )

        extracted_text = re.sub(r"\n{3,}", "\n\n", "\n\n".join(text_parts)).strip()
        if not extracted_text:
            raise HTTPException(
                status_code=400,
                detail=f"附件中未提取到可读文本：{chat_file.name}",
            )

        prepared_files.append(
            {
                "name": str(chat_file.name or "").strip(),
                "media_type": str(
                    chat_file.media_type or "application/octet-stream"
                ).strip(),
                "data_url": str(chat_file.data_url or "").strip(),
                "size_bytes": int(chat_file.size_bytes or len(payload)),
                "extracted_text": clip_attachment_preview_text(
                    extracted_text, config.preview_chars
                ),
            }
        )

        allowed_chars = min(config.max_chars_per_file, remaining_chars)
        if allowed_chars <= 0:
            break

        clipped_text = extracted_text[:allowed_chars].rstrip()
        if len(extracted_text) > allowed_chars:
            clipped_text += "\n...[附件内容已截断]"
        sections.append(
            "\n".join(
                [
                    f"[附件 {index}]",
                    f"文件名：{chat_file.name}",
                    "内容：",
                    clipped_text,
                ]
            )
        )
        remaining_chars -= len(clipped_text)

    if not sections:
        raise HTTPException(
            status_code=400,
            detail="所选附件未提供可读文本。",
        )

    attachment_context = (
        f"{config.context_start_marker}\n"
        "以下文本提取自用户上传的附件。"
        "回答时请将其作为高优先级上下文。\n\n"
        + "\n\n---\n\n".join(sections)
        + f"\n{config.context_end_marker}"
    )
    return prepared_files, attachment_context
