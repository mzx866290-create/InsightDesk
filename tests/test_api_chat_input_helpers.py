import base64
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.helpers.chat_input_helpers import (
    ChatImageConfig,
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


def test_validate_chat_payload_rejects_fully_empty_request():
    with pytest.raises(HTTPException) as exc:
        validate_chat_payload("   ", [], [])

    assert exc.value.status_code == 400
    assert exc.value.detail == "消息内容、图片和文件不能同时为空。"


def test_validate_chat_payload_allows_any_non_empty_channel():
    validate_chat_payload("hello", [], [])
    validate_chat_payload(
        "   ",
        [
            SimpleNamespace(
                name="chart.png",
                media_type="image/png",
                data_url="data:image/png;base64,ZmFrZQ==",
            )
        ],
        [],
    )
    validate_chat_payload("   ", [], [SimpleNamespace(data_url="data:text/plain;base64,QQ==")])


def test_chat_image_config_uses_safe_defaults():
    config = ChatImageConfig()

    assert config.max_count == 4
    assert config.max_bytes == 10 * 1024 * 1024
    assert config.max_total_bytes == 20 * 1024 * 1024


def _image_input(
    payload: bytes,
    *,
    name: str = "chart.png",
    media_type: str = "image/png",
    data_url_media_type: str = "image/png",
) -> SimpleNamespace:
    encoded = base64.b64encode(payload).decode("ascii")
    return SimpleNamespace(
        name=name,
        media_type=media_type,
        data_url=f"data:{data_url_media_type};base64,{encoded}",
    )


def test_validate_chat_payload_enforces_image_count_and_types():
    config = ChatImageConfig(max_count=1)
    with pytest.raises(HTTPException, match="最多只能附加 1 张图片"):
        validate_chat_payload(
            "hello",
            [_image_input(b"one"), _image_input(b"two", name="second.png")],
            [],
            image_config=config,
        )

    with pytest.raises(HTTPException, match="不支持的图片类型"):
        validate_chat_payload(
            "hello",
            [_image_input(b"svg", data_url_media_type="image/svg+xml")],
            [],
        )

    with pytest.raises(HTTPException, match="媒体类型与 data URL 不一致"):
        validate_chat_payload(
            "hello",
            [_image_input(b"jpeg", data_url_media_type="image/jpeg")],
            [],
        )


def test_validate_chat_payload_rejects_invalid_or_non_base64_image_data():
    corrupted = SimpleNamespace(
        name="bad.png",
        media_type="image/png",
        data_url="data:image/png;base64,***",
    )
    with pytest.raises(HTTPException, match="图片数据已损坏"):
        validate_chat_payload("hello", [corrupted], [])

    not_base64 = SimpleNamespace(
        name="raw.png",
        media_type="image/png",
        data_url="data:image/png,%89PNG",
    )
    with pytest.raises(HTTPException, match="必须使用 Base64 data URL"):
        validate_chat_payload("hello", [not_base64], [])


def test_validate_chat_payload_enforces_decoded_image_size_limits():
    with pytest.raises(HTTPException, match="图片过大"):
        validate_chat_payload(
            "hello",
            [_image_input(b"1234")],
            [],
            image_config=ChatImageConfig(max_bytes=3, max_total_bytes=10),
        )

    with pytest.raises(HTTPException, match="图片总大小超过限制"):
        validate_chat_payload(
            "hello",
            [_image_input(b"123"), _image_input(b"456", name="second.png")],
            [],
            image_config=ChatImageConfig(max_bytes=4, max_total_bytes=5),
        )


def test_chat_file_suffix_normalizes_windows_paths_and_missing_extensions():
    assert chat_file_suffix(r"C:\docs\report.PDF") == ".pdf"
    assert chat_file_suffix("/tmp/archive.tar.gz") == ".gz"
    assert chat_file_suffix("README") == ""


def test_decode_data_url_supports_base64_and_percent_encoded_payloads():
    assert decode_data_url("data:text/plain;base64,SGVsbG8=", "hello.txt") == b"Hello"
    assert decode_data_url("data:text/plain,hello%20world", "hello.txt") == b"hello world"


def test_decode_data_url_rejects_invalid_payloads():
    with pytest.raises(HTTPException) as invalid_exc:
        decode_data_url("not-a-data-url", "bad.txt")
    assert invalid_exc.value.detail == "附件数据无效：bad.txt"

    with pytest.raises(HTTPException) as corrupted_exc:
        decode_data_url("data:text/plain;base64,***", "bad.txt")
    assert corrupted_exc.value.detail == "附件数据已损坏：bad.txt"


def test_clip_attachment_preview_text_collapses_blank_lines_and_truncates():
    preview = clip_attachment_preview_text("alpha\n\n\n\nbeta", 8)

    assert preview == "alpha\n\nb\n...[附件预览已截断]"


def test_build_message_with_files_includes_default_prompt_for_file_only_message():
    message = build_message_with_files("   ", "[[FILE_CONTEXT]]")

    assert message == (
        "请阅读附件内容，并基于附件信息进行回答。\n\n"
        "[[FILE_CONTEXT]]"
    )


def test_build_user_input_returns_string_without_images():
    assert build_user_input("hello", [], "ctx") == "hello\n\nctx"


def test_build_user_input_builds_multimodal_payload_with_objects_and_dicts():
    payload = build_user_input(
        "hello",
        [
            SimpleNamespace(data_url="data:image/png;base64,AAA"),
            {"data_url": "data:image/png;base64,BBB"},
        ],
        "ctx",
    )

    assert payload == [
        {"type": "text", "text": "hello\n\nctx"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,BBB"}},
    ]


def test_user_input_has_images_detects_multimodal_payloads():
    assert not user_input_has_images("plain text")
    assert not user_input_has_images([{"type": "text", "text": "hello"}])
    assert user_input_has_images(
        [{"type": "text", "text": "hello"}, {"type": "image_url", "image_url": {"url": "x"}}]
    )


def test_model_supports_images_matches_known_vision_models():
    assert model_supports_images("openai", "gpt-4o-mini")
    assert model_supports_images("ollama", "qwen2.5-vl:7b")
    assert not model_supports_images("openai", "gpt-3.5-turbo")
    assert not model_supports_images("ollama", "qwen2.5:7b")


def test_stringify_user_input_summarizes_text_and_image_count():
    assert stringify_user_input("hello") == "hello"
    assert stringify_user_input(
        [
            {"type": "text", "text": "alpha"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,BBB"}},
        ]
    ) == "alpha\n[用户上传了 2 张图片]"
