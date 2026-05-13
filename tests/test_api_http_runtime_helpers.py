from backend.helpers.http_runtime_helpers import (
    build_download_content_disposition,
    classify_runtime_error,
)


def test_build_download_content_disposition_quotes_ascii_names():
    assert (
        build_download_content_disposition("Board Update.pptx")
        == 'attachment; filename="Board Update.pptx"'
    )


def test_build_download_content_disposition_escapes_quotes_and_backslashes():
    assert (
        build_download_content_disposition('report "final" \\ v1.txt')
        == 'attachment; filename="report \\"final\\" \\\\ v1.txt"'
    )


def test_build_download_content_disposition_emits_rfc5987_for_non_ascii():
    header = build_download_content_disposition("发布说明.pdf")

    assert header.startswith("attachment; filename=")
    assert "filename*=UTF-8''" in header


def test_build_download_content_disposition_falls_back_to_download():
    assert build_download_content_disposition("   ") == 'attachment; filename="download"'


def test_classify_runtime_error_maps_common_failure_modes():
    assert classify_runtime_error(ConnectionError("Connection refused"))["code"] == "MODEL_UNAVAILABLE"
    assert classify_runtime_error(RuntimeError("401 Unauthorized"))["code"] == "AUTH_FAILED"
    assert classify_runtime_error(TimeoutError("timed out"))["code"] == "TIMEOUT"
    assert classify_runtime_error(RuntimeError("rate limit exceeded"))["code"] == "RATE_LIMIT"
    assert classify_runtime_error(RuntimeError("vision not supported"))["code"] == "MODEL_NO_VISION"
    assert classify_runtime_error(RuntimeError("model not found"))["code"] == "MODEL_NOT_FOUND"
    assert classify_runtime_error(RuntimeError("iteration limit"))["code"] == "MAX_ITERATIONS"


def test_classify_runtime_error_defaults_to_internal_error():
    payload = classify_runtime_error(RuntimeError("unexpected"))

    assert payload["code"] == "INTERNAL_ERROR"
    assert payload["message"] == "处理请求时发生异常"
