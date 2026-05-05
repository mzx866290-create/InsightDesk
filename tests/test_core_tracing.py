import pytest
from types import ModuleType

from backend.core.tracing import (
    InMemoryTraceRecorder,
    OtelExporterConfig,
    build_otel_exporter_contract,
    build_trace_dashboard_payload,
    build_trace_export_payload,
    get_recent_trace_events,
    initialize_otel_tracing,
    ingest_external_trace_events,
    reset_otel_initialization_for_tests,
    resolve_otel_exporter_config,
    reset_trace_events,
    trace_span,
)


def test_trace_span_records_start_end_duration_and_attributes():
    reset_trace_events()

    with trace_span("test.span", {"component": "unit"}) as span:
        span.set_attribute("status", "ok")

    events = get_recent_trace_events()

    assert [event["event"] for event in events] == ["start", "end"]
    assert events[0]["name"] == "test.span"
    assert events[0]["attributes"]["component"] == "unit"
    assert events[1]["attributes"]["status"] == "ok"
    assert events[1]["duration_ms"] >= 0
    assert events[1]["trace_id"] == events[0]["trace_id"]
    assert events[1]["span_id"] == events[0]["span_id"]


def test_trace_span_records_error_event_for_exceptions():
    reset_trace_events()

    with pytest.raises(RuntimeError):
        with trace_span("test.error", {"component": "unit"}):
            raise RuntimeError("boom")

    events = get_recent_trace_events()

    assert [event["event"] for event in events] == ["start", "error"]
    assert events[-1]["name"] == "test.error"
    assert events[-1]["duration_ms"] >= 0
    assert events[-1]["error_type"] == "RuntimeError"
    assert events[-1]["error_message"] == "boom"


def test_trace_recorder_keeps_only_recent_events():
    recorder = InMemoryTraceRecorder(max_events=4)

    for index in range(3):
        with trace_span(f"test.span.{index}", recorder=recorder):
            pass

    events = get_recent_trace_events(recorder=recorder)

    assert len(events) == 4
    assert [event["name"] for event in events] == [
        "test.span.1",
        "test.span.1",
        "test.span.2",
        "test.span.2",
    ]


def test_trace_recorder_filters_recent_events_before_applying_limit():
    recorder = InMemoryTraceRecorder(max_events=20)

    with trace_span("test.alpha", recorder=recorder, trace_id="trace-alpha"):
        pass
    with trace_span("test.beta", recorder=recorder, trace_id="trace-beta"):
        pass

    beta_end_events = get_recent_trace_events(
        limit=1,
        recorder=recorder,
        event="end",
        name="test.beta",
    )
    alpha_events = get_recent_trace_events(
        recorder=recorder,
        trace_id="trace-alpha",
    )

    assert len(beta_end_events) == 1
    assert beta_end_events[0]["event"] == "end"
    assert beta_end_events[0]["name"] == "test.beta"
    assert [event["name"] for event in alpha_events] == ["test.alpha", "test.alpha"]


def test_trace_export_payload_builds_otlp_style_spans_and_logs():
    recorder = InMemoryTraceRecorder(process_id="pid-local", source="api-1")

    with trace_span("test.export", {"component": "unit"}, recorder=recorder, trace_id="trace-export"):
        pass

    events = get_recent_trace_events(recorder=recorder)
    payload = build_trace_export_payload(events, service_name="unit-service")
    spans = payload["resource_spans"][0]["scope_spans"][0]["spans"]
    logs = payload["resource_logs"][0]["scope_logs"][0]["log_records"]

    assert payload["format"] == "otlp-json-preview"
    assert payload["summary"]["service_name"] == "unit-service"
    assert payload["summary"]["span_count"] == 1
    assert payload["summary"]["log_record_count"] == 2
    assert payload["summary"]["source_nodes"] == {"api-1": 2}
    assert spans[0]["trace_id"] == "trace-export"
    assert spans[0]["name"] == "test.export"
    assert spans[0]["status"] == {"code": "STATUS_CODE_OK"}
    assert spans[0]["duration_ms"] >= 0
    assert logs[0]["trace_id"] == "trace-export"


def test_external_trace_events_are_merged_with_source_dimensions():
    recorder = InMemoryTraceRecorder(process_id="pid-local", source="api-1")

    result = ingest_external_trace_events(
        {
            "source": "worker-1",
            "process_id": "pid-worker",
            "events": [
                {
                    "event": "end",
                    "name": "worker.job",
                    "trace_id": "trace-worker",
                    "span_id": "span-worker",
                    "timestamp": 1000,
                    "duration_ms": 12.5,
                    "attributes": {"queue": "default"},
                },
                {"event": "invalid", "trace_id": "skip", "span_id": "skip"},
            ],
        },
        recorder=recorder,
    )

    events = get_recent_trace_events(recorder=recorder)
    payload = build_trace_export_payload(events, service_name="unit-service")
    dashboard = build_trace_dashboard_payload(events, payload)

    assert result == {
        "accepted": 1,
        "rejected": 1,
        "source": "worker-1",
        "process_id": "pid-worker",
    }
    assert events[0]["source"] == "worker-1"
    assert events[0]["process_id"] == "pid-worker"
    assert payload["summary"]["source_nodes"] == {"worker-1": 1}
    assert payload["summary"]["process_nodes"] == {"pid-worker": 1}
    assert dashboard["dashboard_cards"][3]["value"] == 1
    assert dashboard["panel_templates"][0]["id"] == "trace_export_preview"


def test_otel_exporter_contract_is_env_gated_and_secret_safe(monkeypatch):
    reset_otel_initialization_for_tests()
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "otlp")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "authorization=Bearer secret,x-tenant=demo")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "unit-api")

    config = resolve_otel_exporter_config()
    contract = build_otel_exporter_contract(config)

    assert contract["exporter"] == "otlp"
    assert contract["endpoint"] == "http://collector:4318"
    assert contract["protocol"] == "http/protobuf"
    assert contract["service_name"] == "unit-api"
    assert contract["env_gated"] is True
    assert contract["network_send"] is False
    assert contract["initialization"]["initialized"] is False
    assert contract["header_names"] == ["authorization", "x-tenant"]
    assert "secret" not in str(contract)


def test_otel_exporter_reports_unsupported_http_json_protocol(monkeypatch):
    reset_otel_initialization_for_tests()
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "otlp")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/json")

    config = resolve_otel_exporter_config()
    report = initialize_otel_tracing(config, force=True)

    assert config.enabled is False
    assert config.env_gated is True
    assert config.dependency_available is False
    assert config.degradation_reason == "unsupported_protocol_http_json"
    assert report.status == "degraded"
    assert report.initialized is False
    assert report.reason == "unsupported_protocol_http_json"


def test_otel_exporter_reports_missing_dependency(monkeypatch):
    reset_otel_initialization_for_tests()
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "console")
    monkeypatch.setattr("backend.core.tracing._module_available", lambda name: False)

    config = resolve_otel_exporter_config()
    report = initialize_otel_tracing(config, force=True)
    contract = build_otel_exporter_contract(config)

    assert config.enabled is False
    assert config.degradation_reason == "missing_opentelemetry_dependency"
    assert report.status == "degraded"
    assert report.reason == "missing_opentelemetry_dependency"
    assert contract["degradation_reason"] == "missing_opentelemetry_dependency"


def test_initialize_otel_tracing_installs_console_exporter(monkeypatch):
    reset_otel_initialization_for_tests()
    calls = {"providers": [], "processors": []}

    class FakeResource:
        @classmethod
        def create(cls, attributes):
            return {"attributes": attributes}

    class FakeTracerProvider:
        def __init__(self, resource=None):
            self.resource = resource
            self.processors = []
            calls["providers"].append(self)

        def add_span_processor(self, processor):
            self.processors.append(processor)
            calls["processors"].append(processor)

    class FakeConsoleSpanExporter:
        pass

    class FakeSimpleSpanProcessor:
        def __init__(self, exporter):
            self.exporter = exporter

    class FakeBatchSpanProcessor:
        def __init__(self, exporter):
            self.exporter = exporter

    trace_module = ModuleType("opentelemetry.trace")

    def set_tracer_provider(provider):
        calls["set_provider"] = provider

    trace_module.set_tracer_provider = set_tracer_provider

    opentelemetry_module = ModuleType("opentelemetry")
    opentelemetry_module.trace = trace_module

    resources_module = ModuleType("opentelemetry.sdk.resources")
    resources_module.Resource = FakeResource

    sdk_trace_module = ModuleType("opentelemetry.sdk.trace")
    sdk_trace_module.TracerProvider = FakeTracerProvider

    sdk_export_module = ModuleType("opentelemetry.sdk.trace.export")
    sdk_export_module.BatchSpanProcessor = FakeBatchSpanProcessor
    sdk_export_module.ConsoleSpanExporter = FakeConsoleSpanExporter
    sdk_export_module.SimpleSpanProcessor = FakeSimpleSpanProcessor

    for name, module in {
        "opentelemetry": opentelemetry_module,
        "opentelemetry.trace": trace_module,
        "opentelemetry.sdk": ModuleType("opentelemetry.sdk"),
        "opentelemetry.sdk.resources": resources_module,
        "opentelemetry.sdk.trace": sdk_trace_module,
        "opentelemetry.sdk.trace.export": sdk_export_module,
    }.items():
        monkeypatch.setitem(__import__("sys").modules, name, module)

    config = OtelExporterConfig(
        enabled=True,
        exporter="console",
        service_name="unit-api",
        endpoint=None,
        protocol="http/protobuf",
        insecure=False,
        timeout_seconds=10.0,
        compression=None,
        header_names=[],
        dependency_available=True,
        env_gated=True,
    )

    report = initialize_otel_tracing(config, force=True)
    second_report = initialize_otel_tracing(config)

    assert report.status == "initialized"
    assert report.initialized is True
    assert report.provider == "FakeTracerProvider"
    assert report.span_processor == "SimpleSpanProcessor"
    assert calls["set_provider"] is calls["providers"][0]
    assert calls["providers"][0].resource["attributes"]["service.name"] == "unit-api"
    assert second_report.status == "already_initialized"


def test_trace_export_payload_includes_otel_exporter_contract():
    recorder = InMemoryTraceRecorder(process_id="pid-local", source="api-1")
    exporter_config = OtelExporterConfig(
        enabled=False,
        exporter="otlp",
        service_name="unit-api",
        endpoint="http://collector:4318",
        protocol="http/protobuf",
        insecure=False,
        timeout_seconds=10.0,
        compression=None,
        header_names=["authorization"],
        dependency_available=False,
        env_gated=True,
    )

    with trace_span("test.export.contract", recorder=recorder, trace_id="trace-contract"):
        pass

    payload = build_trace_export_payload(
        get_recent_trace_events(recorder=recorder),
        service_name="unit-api",
        exporter_config=exporter_config,
    )

    assert payload["summary"]["otel_exporter"]["exporter"] == "otlp"
    assert payload["summary"]["otel_exporter"]["network_send"] is False
    assert payload["summary"]["otel_exporter"]["header_names"] == ["authorization"]
