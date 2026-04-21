from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.api_chat_file_helpers import ChatFileConfig, prepare_chat_files


def _config(**overrides):
    base = ChatFileConfig(
        context_end_marker="[[END]]",
        context_start_marker="[[START]]",
        max_bytes=1024 * 1024,
        max_chars_per_file=24,
        max_count=3,
        max_total_chars=48,
        preview_chars=14,
        supported_extensions=frozenset({".txt", ".md"}),
    )
    if not overrides:
        return base
    return ChatFileConfig(**{**base.__dict__, **overrides})


def test_prepare_chat_files_returns_empty_result_for_no_files():
    assert prepare_chat_files([], config=_config()) == ([], "")


def test_prepare_chat_files_rejects_too_many_files():
    files = [
        SimpleNamespace(
            name=f"note-{index}.txt",
            media_type="text/plain",
            data_url="data:text/plain;base64,SGVsbG8=",
            size_bytes=5,
        )
        for index in range(4)
    ]

    with pytest.raises(HTTPException) as exc:
        prepare_chat_files(files, config=_config(max_count=3))

    assert exc.value.status_code == 400
    assert exc.value.detail == "每条消息最多只能附加 3 个文件。"


def test_prepare_chat_files_extracts_preview_and_context_from_pipeline_docs():
    files = [
        SimpleNamespace(
            name="brief.txt",
            media_type="text/plain",
            data_url="data:text/plain;base64,SGVsbG8gd29ybGQ=",
            size_bytes=11,
        )
    ]

    prepared_files, attachment_context = prepare_chat_files(
        files,
        config=_config(max_chars_per_file=10, max_total_chars=10, preview_chars=12),
        pipeline_factory=lambda: SimpleNamespace(
            load_file=lambda _: [
                SimpleNamespace(page_content="Alpha section"),
                SimpleNamespace(page_content="Beta"),
            ]
        ),
    )

    assert prepared_files == [
        {
            "name": "brief.txt",
            "media_type": "text/plain",
            "data_url": "data:text/plain;base64,SGVsbG8gd29ybGQ=",
            "size_bytes": 11,
            "extracted_text": "Alpha sectio\n...[附件预览已截断]",
        }
    ]
    assert attachment_context == (
        "[[START]]\n"
        "以下文本提取自用户上传的附件。回答时请将其作为高优先级上下文。\n\n"
        "[附件 1]\n"
        "文件名：brief.txt\n"
        "内容：\n"
        "Alpha sect\n...[附件内容已截断]\n"
        "[[END]]"
    )


def test_prepare_chat_files_falls_back_to_direct_text_decoding_for_plain_text():
    files = [
        SimpleNamespace(
            name="notes.txt",
            media_type="text/plain",
            data_url="data:text/plain,hello%20world",
            size_bytes=11,
        )
    ]

    prepared_files, attachment_context = prepare_chat_files(
        files,
        config=_config(),
        pipeline_factory=lambda: SimpleNamespace(
            load_file=lambda _: (_ for _ in ()).throw(RuntimeError("parse failed"))
        ),
    )

    assert prepared_files[0]["extracted_text"] == "hello world"
    assert "hello world" in attachment_context


def test_prepare_chat_files_rejects_unsupported_extensions():
    files = [
        SimpleNamespace(
            name="image.png",
            media_type="image/png",
            data_url="data:image/png;base64,AAA=",
            size_bytes=3,
        )
    ]

    with pytest.raises(HTTPException) as exc:
        prepare_chat_files(files, config=_config())

    assert exc.value.status_code == 400
    assert exc.value.detail == "不支持的附件类型：image.png"
