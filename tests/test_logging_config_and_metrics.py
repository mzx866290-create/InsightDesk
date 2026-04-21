"""结构化日志配置与 Prometheus 指标端点的单元测试。"""

import json
import logging

from fastapi.testclient import TestClient

import backend.api_server as api_server
from backend.logging_config import JsonFormatter, configure_logging


# ── JsonFormatter 测试 ──────────────────────────


def test_json_formatter_basic_output():
    formatter = JsonFormatter(service_name="test-svc")
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="你好 %s",
        args=("世界",),
        exc_info=None,
    )
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test.logger"
    assert parsed["service"] == "test-svc"
    assert "你好 世界" in parsed["message"]
    assert "timestamp" in parsed


def test_json_formatter_extra_fields():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname="",
        lineno=0,
        msg="测试消息",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-123"
    record.status_code = 200
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["request_id"] == "req-123"
    assert parsed["status_code"] == 200


def test_json_formatter_exception_info():
    formatter = JsonFormatter()
    try:
        raise ValueError("测试异常")
    except ValueError:
        import sys

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="出错了",
            args=(),
            exc_info=sys.exc_info(),
        )
    output = formatter.format(record)
    parsed = json.loads(output)
    assert "exc_info" in parsed
    assert "ValueError" in parsed["exc_info"]


# ── configure_logging 测试 ──────────────────────


def test_configure_logging_returns_text_by_default():
    result = configure_logging(log_format="text")
    assert result == "text"


def test_configure_logging_returns_json():
    result = configure_logging(log_format="json")
    assert result == "json"
    # 恢复为 text 避免影响其他测试
    configure_logging(log_format="text")


# ── /api/operations/metrics 端点测试 ─────────────


def test_metrics_endpoint_returns_prometheus_format():
    client = TestClient(api_server.app)
    response = client.get("/api/operations/metrics")
    assert response.status_code == 200
    content_type = response.headers.get("content-type", "")
    assert "text/plain" in content_type
    body = response.text
    assert "insightdesk_uptime_seconds" in body
    assert "insightdesk_http_requests_total" in body
    assert "insightdesk_http_errors_total" in body
    assert "insightdesk_http_requests_by_status" in body
    assert "insightdesk_tasks_total" in body
    assert "insightdesk_tasks_by_status" in body


def test_metrics_endpoint_returns_request_trace_headers():
    client = TestClient(api_server.app)
    response = client.get(
        "/api/operations/metrics",
        headers={"X-Request-ID": "metrics-test-001"},
    )
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "metrics-test-001"
    assert float(response.headers["X-Process-Time-Ms"]) >= 0


def test_metrics_values_are_numeric():
    """确保指标值可解析为数字。"""
    client = TestClient(api_server.app)
    response = client.get("/api/operations/metrics")
    for line in response.text.strip().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.rsplit(" ", 1)
        assert len(parts) == 2, f"指标行格式错误: {line}"
        try:
            float(parts[1])
        except ValueError:
            raise AssertionError(f"指标值不是数字: {line}")
