"""结构化日志配置与 Prometheus 指标端点的单元测试。"""

import json
import logging
from types import ModuleType

from fastapi.testclient import TestClient

import backend.api_server as api_server
from backend.core.logging_config import JsonFormatter, _merge_trace_context, configure_logging, get_logger
from backend.core.tracing import reset_otel_initialization_for_tests, trace_span
from backend.core.runtime_metrics import (
    RuntimeMetricsExporterConfig,
    build_runtime_metrics_exporter_contract,
    initialize_runtime_metrics_exporter,
    resolve_runtime_metrics_exporter_config,
    reset_runtime_metrics_initialization_for_tests,
)
from backend.logging_config import JsonFormatter as CompatJsonFormatter


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


def test_legacy_logging_config_path_reexports_core_formatter():
    assert CompatJsonFormatter is JsonFormatter


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


def test_configure_logging_initializes_env_gated_otel_tracing(monkeypatch):
    reset_otel_initialization_for_tests()
    calls = []

    class FakeReport:
        initialized = False
        exporter = "console"
        protocol = "http/protobuf"
        reason = "missing_opentelemetry_dependency"

        def to_dict(self):
            return {
                "initialized": self.initialized,
                "exporter": self.exporter,
                "protocol": self.protocol,
                "reason": self.reason,
            }

    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "console")
    monkeypatch.setattr(
        "backend.core.tracing.initialize_otel_tracing",
        lambda: calls.append("called") or FakeReport(),
    )

    result = configure_logging(log_format="text", service_name="unit-api")

    assert result == "text"
    assert calls == ["called"]
    configure_logging(log_format="text")


# ── /api/operations/metrics 端点测试 ─────────────


def test_configure_logging_initializes_env_gated_otel_metrics(monkeypatch):
    reset_runtime_metrics_initialization_for_tests()
    calls = []

    class FakeReport:
        initialized = False
        exporter = "console"
        protocol = "http/protobuf"
        reason = "missing_opentelemetry_dependency"

        def to_dict(self):
            return {
                "initialized": self.initialized,
                "exporter": self.exporter,
                "protocol": self.protocol,
                "reason": self.reason,
            }

    monkeypatch.setenv("OTEL_METRICS_EXPORTER", "console")
    monkeypatch.setattr(
        "backend.core.runtime_metrics.initialize_runtime_metrics_exporter",
        lambda: calls.append("called") or FakeReport(),
    )

    result = configure_logging(log_format="text", service_name="unit-api")

    assert result == "text"
    assert calls == ["called"]
    configure_logging(log_format="text")


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
    assert "insightdesk_task_queue_health" in body
    assert "insightdesk_llm_calls_total" in body
    assert "insightdesk_llm_tokens_total" in body


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

def test_get_logger_supports_structlog_like_bind():
    configure_logging(log_format="json")
    records = []

    class ListHandler(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = ListHandler()
    logging.getLogger("tests.logging").addHandler(handler)
    logger = get_logger("tests.logging").bind(request_id="req-1", component="unit")
    try:
        logger.info("hello", status_code=200)
        assert records[-1].request_id == "req-1"
        assert records[-1].component == "unit"
        assert records[-1].status_code == 200
    finally:
        logging.getLogger("tests.logging").removeHandler(handler)
        configure_logging(log_format="text")


def test_get_logger_adds_active_trace_context_to_records():
    configure_logging(log_format="json")
    records = []

    class ListHandler(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = ListHandler()
    logging.getLogger("tests.trace_logging").addHandler(handler)
    logger = get_logger("tests.trace_logging").bind(component="unit")
    try:
        with trace_span("unit.trace_logging"):
            logger.info("inside trace")
        assert records[-1].component == "unit"
        assert records[-1].trace_id
        assert records[-1].span_id
    finally:
        logging.getLogger("tests.trace_logging").removeHandler(handler)
        configure_logging(log_format="text")


def test_structlog_processor_merges_active_trace_context_without_overrides():
    with trace_span("unit.structlog_processor") as span:
        event = _merge_trace_context(None, "info", {"trace_id": "manual"})

    assert event["trace_id"] == "manual"
    assert event["span_id"] == span.span_id


def test_runtime_metrics_exporter_contract_is_env_gated(monkeypatch):
    reset_runtime_metrics_initialization_for_tests()
    monkeypatch.setenv("OTEL_METRICS_EXPORTER", "otlp")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "http://collector:4318/v1/metrics")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", "delta")

    config = resolve_runtime_metrics_exporter_config()
    contract = build_runtime_metrics_exporter_contract(config)

    assert contract["exporter"] == "otlp"
    assert contract["endpoint"] == "http://collector:4318/v1/metrics"
    assert contract["temporality_preference"] == "delta"
    assert contract["env_gated"] is True
    assert contract["network_send"] is False
    assert contract["initialization"]["initialized"] is False
    assert contract["prometheus_endpoint"] == "/api/operations/metrics"


def test_runtime_metrics_exporter_contract_accepts_explicit_config():
    contract = build_runtime_metrics_exporter_contract(
        RuntimeMetricsExporterConfig(
            enabled=False,
            exporter="prometheus",
            endpoint=None,
            temporality_preference="cumulative",
            dependency_available=False,
            env_gated=True,
        )
    )

    assert contract["exporter"] == "prometheus"
    assert contract["enabled"] is False
    assert contract["required_env"]


def test_initialize_runtime_metrics_exporter_installs_console_reader(monkeypatch):
    reset_runtime_metrics_initialization_for_tests()
    calls = {"providers": [], "readers": []}

    class FakeResource:
        @classmethod
        def create(cls, attributes):
            return {"attributes": attributes}

    class FakeMeterProvider:
        def __init__(self, resource=None, metric_readers=None):
            self.resource = resource
            self.metric_readers = list(metric_readers or [])
            calls["providers"].append(self)

    class FakeConsoleMetricExporter:
        pass

    class FakePeriodicExportingMetricReader:
        def __init__(self, exporter):
            self.exporter = exporter
            calls["readers"].append(self)

    metrics_module = ModuleType("opentelemetry.metrics")

    def set_meter_provider(provider):
        calls["set_provider"] = provider

    metrics_module.set_meter_provider = set_meter_provider

    opentelemetry_module = ModuleType("opentelemetry")
    opentelemetry_module.metrics = metrics_module

    resources_module = ModuleType("opentelemetry.sdk.resources")
    resources_module.Resource = FakeResource

    sdk_metrics_module = ModuleType("opentelemetry.sdk.metrics")
    sdk_metrics_module.MeterProvider = FakeMeterProvider

    sdk_metrics_export_module = ModuleType("opentelemetry.sdk.metrics.export")
    sdk_metrics_export_module.ConsoleMetricExporter = FakeConsoleMetricExporter
    sdk_metrics_export_module.PeriodicExportingMetricReader = FakePeriodicExportingMetricReader

    for name, module in {
        "opentelemetry": opentelemetry_module,
        "opentelemetry.metrics": metrics_module,
        "opentelemetry.sdk": ModuleType("opentelemetry.sdk"),
        "opentelemetry.sdk.resources": resources_module,
        "opentelemetry.sdk.metrics": sdk_metrics_module,
        "opentelemetry.sdk.metrics.export": sdk_metrics_export_module,
    }.items():
        monkeypatch.setitem(__import__("sys").modules, name, module)

    config = RuntimeMetricsExporterConfig(
        enabled=True,
        exporter="console",
        endpoint=None,
        temporality_preference="cumulative",
        dependency_available=True,
        env_gated=True,
        service_name="unit-api",
    )

    report = initialize_runtime_metrics_exporter(config, force=True)
    second_report = initialize_runtime_metrics_exporter(config)

    assert report.status == "initialized"
    assert report.initialized is True
    assert report.provider == "FakeMeterProvider"
    assert report.reader == "FakePeriodicExportingMetricReader"
    assert calls["set_provider"] is calls["providers"][0]
    assert calls["providers"][0].resource["attributes"]["service.name"] == "unit-api"
    assert second_report.status == "already_initialized"
