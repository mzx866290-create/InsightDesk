"""Process-local trace span helpers.

This module intentionally stays dependency-free. It gives the backend a small
in-memory trace event buffer that can be wired into hot paths now and replaced
or exported to OpenTelemetry later without changing call sites.
"""

from __future__ import annotations

import os
import socket
import time
import uuid
from collections import deque
from contextvars import ContextVar, Token
from dataclasses import dataclass
from importlib.util import find_spec
from threading import Lock
from typing import Any, Callable, Literal

TraceEventKind = Literal["start", "end", "error"]
OtelExporterKind = Literal["none", "otlp", "console"]
OtelProtocol = Literal["grpc", "http/protobuf", "http/json"]
OtelInitStatus = Literal["initialized", "disabled", "degraded", "already_initialized"]

DEFAULT_RECENT_TRACE_EVENT_LIMIT = 500
DEFAULT_TRACE_SERVICE_NAME = "insightdesk-api"
_MAX_ATTRIBUTE_DEPTH = 4
_TRACE_EVENT_KINDS: set[str] = {"start", "end", "error"}


@dataclass(frozen=True)
class OtelExporterConfig:
    """Environment-derived OpenTelemetry exporter contract.

    The config is intentionally side-effect free: resolving it never opens a
    socket and never imports exporter packages unless dependency availability is
    queried by module name.
    """

    enabled: bool
    exporter: OtelExporterKind
    service_name: str
    endpoint: str | None
    protocol: OtelProtocol
    insecure: bool
    timeout_seconds: float
    compression: str | None
    header_names: list[str]
    dependency_available: bool
    env_gated: bool
    degradation_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "exporter": self.exporter,
            "service_name": self.service_name,
            "endpoint": self.endpoint,
            "protocol": self.protocol,
            "insecure": self.insecure,
            "timeout_seconds": self.timeout_seconds,
            "compression": self.compression,
            "header_names": list(self.header_names),
            "dependency_available": self.dependency_available,
            "env_gated": self.env_gated,
            "degradation_reason": self.degradation_reason,
        }


@dataclass(frozen=True)
class OtelInitializationReport:
    """Result of attempting to install a real OpenTelemetry trace exporter."""

    status: OtelInitStatus
    initialized: bool
    exporter: OtelExporterKind
    service_name: str
    endpoint: str | None
    protocol: OtelProtocol
    dependency_available: bool
    env_gated: bool
    reason: str | None = None
    provider: str | None = None
    span_processor: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "initialized": self.initialized,
            "exporter": self.exporter,
            "service_name": self.service_name,
            "endpoint": self.endpoint,
            "protocol": self.protocol,
            "dependency_available": self.dependency_available,
            "env_gated": self.env_gated,
            "reason": self.reason,
            "provider": self.provider,
            "span_processor": self.span_processor,
        }


@dataclass(frozen=True)
class TraceEvent:
    """A single lifecycle event emitted by a trace span."""

    event: TraceEventKind
    name: str
    trace_id: str
    span_id: str
    parent_span_id: str | None
    timestamp: float
    duration_ms: float | None
    attributes: dict[str, Any]
    error_type: str | None = None
    error_message: str | None = None
    process_id: str | None = None
    source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "attributes": dict(self.attributes),
            "error_type": self.error_type,
            "error_message": self.error_message,
            "process_id": self.process_id,
            "source": self.source,
        }


def _new_id() -> str:
    return uuid.uuid4().hex


def _default_process_id() -> str:
    return str(os.getpid())


def _default_source() -> str:
    configured = os.getenv("OBSERVABILITY_SOURCE") or os.getenv("HOSTNAME")
    if configured and configured.strip():
        return configured.strip()
    try:
        hostname = socket.gethostname()
    except OSError:
        hostname = ""
    return hostname.strip() or "local"


def _normalize_attribute_value(value: Any, *, depth: int = 0) -> Any:
    if depth >= _MAX_ATTRIBUTE_DEPTH:
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _normalize_attribute_value(item, depth=depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_attribute_value(item, depth=depth + 1) for item in value]
    if isinstance(value, set):
        return sorted(str(item) for item in value)
    return str(value)


def _normalize_attributes(attributes: dict[str, Any] | None) -> dict[str, Any]:
    return {
        str(key): _normalize_attribute_value(value)
        for key, value in dict(attributes or {}).items()
    }


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return default


def _normalize_otel_exporter(raw: str | None) -> OtelExporterKind:
    normalized = str(raw or "none").strip().lower()
    if normalized in {"otlp", "otlp_proto_grpc", "otlp_proto_http"}:
        return "otlp"
    if normalized == "console":
        return "console"
    return "none"


def _normalize_otel_protocol(raw: str | None) -> OtelProtocol:
    normalized = str(raw or "http/protobuf").strip().lower()
    if normalized in {"grpc", "http/protobuf", "http/json"}:
        return normalized  # type: ignore[return-value]
    if normalized in {"http", "protobuf"}:
        return "http/protobuf"
    return "http/protobuf"


def _header_names(raw_headers: str | None) -> list[str]:
    names: list[str] = []
    for item in str(raw_headers or "").split(","):
        key = item.split("=", 1)[0].strip()
        if key:
            names.append(key)
    return sorted(set(names))


def _header_dict(raw_headers: str | None) -> dict[str, str]:
    headers: dict[str, str] = {}
    for item in str(raw_headers or "").split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        normalized_key = key.strip()
        if normalized_key:
            headers[normalized_key] = value.strip()
    return headers


def _module_available(name: str) -> bool:
    try:
        return find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _otel_dependency_available(exporter: OtelExporterKind, protocol: OtelProtocol) -> bool:
    if exporter == "none":
        return True
    if exporter == "console":
        return _module_available("opentelemetry.sdk.trace.export")
    if protocol == "http/json":
        return False
    if protocol == "grpc":
        return _module_available("opentelemetry.exporter.otlp.proto.grpc.trace_exporter")
    return _module_available("opentelemetry.exporter.otlp.proto.http.trace_exporter")


def _otel_degradation_reason(
    *,
    sdk_disabled: bool,
    exporter: OtelExporterKind,
    endpoint: str | None,
    protocol: OtelProtocol,
    dependency_available: bool,
) -> str | None:
    if sdk_disabled:
        return "otel_sdk_disabled"
    if exporter == "none":
        return "exporter_none"
    if protocol == "http/json":
        return "unsupported_protocol_http_json"
    if not dependency_available:
        return "missing_opentelemetry_dependency"
    if exporter == "otlp" and not endpoint:
        return "missing_otlp_endpoint"
    return None


def resolve_otel_exporter_config() -> OtelExporterConfig:
    """Resolve the real OTel exporter contract from environment variables."""

    sdk_disabled = _env_bool("OTEL_SDK_DISABLED")
    exporter = _normalize_otel_exporter(os.getenv("OTEL_TRACES_EXPORTER"))
    service_name = (
        os.getenv("OTEL_SERVICE_NAME")
        or os.getenv("SERVICE_NAME")
        or DEFAULT_TRACE_SERVICE_NAME
    ).strip()
    endpoint = (
        os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        or ""
    ).strip() or None
    protocol = _normalize_otel_protocol(os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL"))
    timeout_seconds = _env_float("OTEL_EXPORTER_OTLP_TIMEOUT", 10.0)
    compression = (os.getenv("OTEL_EXPORTER_OTLP_COMPRESSION") or "").strip() or None
    header_names = _header_names(
        ",".join(
            value
            for value in (
                os.getenv("OTEL_EXPORTER_OTLP_HEADERS"),
                os.getenv("OTEL_EXPORTER_OTLP_TRACES_HEADERS"),
            )
            if value
        )
    )
    dependency_available = _otel_dependency_available(exporter, protocol)
    env_gated = not sdk_disabled and exporter != "none"
    enabled = env_gated and (exporter == "console" or bool(endpoint)) and dependency_available
    degradation_reason = _otel_degradation_reason(
        sdk_disabled=sdk_disabled,
        exporter=exporter,
        endpoint=endpoint,
        protocol=protocol,
        dependency_available=dependency_available,
    )

    return OtelExporterConfig(
        enabled=enabled,
        exporter=exporter,
        service_name=service_name or DEFAULT_TRACE_SERVICE_NAME,
        endpoint=endpoint,
        protocol=protocol,
        insecure=_env_bool("OTEL_EXPORTER_OTLP_INSECURE"),
        timeout_seconds=timeout_seconds,
        compression=compression,
        header_names=header_names,
        dependency_available=dependency_available,
        env_gated=env_gated,
        degradation_reason=degradation_reason if not enabled else None,
    )


def build_otel_exporter_contract(
    config: OtelExporterConfig | None = None,
) -> dict[str, Any]:
    """Return a network-free OTel exporter contract for API/tests/docs."""

    resolved = config or resolve_otel_exporter_config()
    payload = resolved.to_dict()
    payload["network_send"] = False
    payload["initialization"] = current_otel_initialization_report().to_dict()
    payload["required_env"] = [
        "OTEL_TRACES_EXPORTER=otlp|console|none",
        "OTEL_EXPORTER_OTLP_ENDPOINT or OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "OTEL_EXPORTER_OTLP_PROTOCOL=grpc|http/protobuf|http/json",
        "OTEL_SERVICE_NAME",
    ]
    return payload


_OTEL_INITIALIZATION_REPORT: OtelInitializationReport | None = None


def _otel_initialization_report_from_config(
    config: OtelExporterConfig,
    *,
    status: OtelInitStatus,
    initialized: bool,
    reason: str | None = None,
    provider: str | None = None,
    span_processor: str | None = None,
) -> OtelInitializationReport:
    return OtelInitializationReport(
        status=status,
        initialized=initialized,
        exporter=config.exporter,
        service_name=config.service_name,
        endpoint=config.endpoint,
        protocol=config.protocol,
        dependency_available=config.dependency_available,
        env_gated=config.env_gated,
        reason=reason,
        provider=provider,
        span_processor=span_processor,
    )


def _resource_attributes(service_name: str) -> dict[str, str]:
    return {
        "service.name": service_name or DEFAULT_TRACE_SERVICE_NAME,
        "telemetry.sdk.language": "python",
        "deployment.environment": os.getenv("DEPLOYMENT_ENVIRONMENT", "local"),
    }


def _resolve_otel_headers() -> dict[str, str]:
    return _header_dict(
        ",".join(
            value
            for value in (
                os.getenv("OTEL_EXPORTER_OTLP_HEADERS"),
                os.getenv("OTEL_EXPORTER_OTLP_TRACES_HEADERS"),
            )
            if value
        )
    )


def initialize_otel_tracing(
    config: OtelExporterConfig | None = None,
    *,
    force: bool = False,
) -> OtelInitializationReport:
    """Initialize the real OpenTelemetry trace SDK exporter when env-gated.

    Optional dependency imports live inside this function so default local/test
    runs remain dependency-free and never open exporter connections.
    """

    global _OTEL_INITIALIZATION_REPORT

    if _OTEL_INITIALIZATION_REPORT is not None and not force:
        current = _OTEL_INITIALIZATION_REPORT
        if current.initialized:
            return OtelInitializationReport(
                **{**current.to_dict(), "status": "already_initialized"}
            )
        return current

    resolved = config or resolve_otel_exporter_config()
    if not resolved.env_gated:
        report = _otel_initialization_report_from_config(
            resolved,
            status="disabled",
            initialized=False,
            reason=resolved.degradation_reason or "env_not_enabled",
        )
        _OTEL_INITIALIZATION_REPORT = report
        return report
    if not resolved.enabled:
        report = _otel_initialization_report_from_config(
            resolved,
            status="degraded",
            initialized=False,
            reason=resolved.degradation_reason or "exporter_not_ready",
        )
        _OTEL_INITIALIZATION_REPORT = report
        return report

    try:
        from opentelemetry import trace as otel_trace  # type: ignore[import-not-found]
        from opentelemetry.sdk.resources import Resource  # type: ignore[import-not-found]
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import-not-found]
        from opentelemetry.sdk.trace.export import (  # type: ignore[import-not-found]
            BatchSpanProcessor,
            ConsoleSpanExporter,
            SimpleSpanProcessor,
        )

        resource = Resource.create(_resource_attributes(resolved.service_name))
        provider = TracerProvider(resource=resource)

        if resolved.exporter == "console":
            exporter = ConsoleSpanExporter()
            processor = SimpleSpanProcessor(exporter)
            processor_name = "SimpleSpanProcessor"
        elif resolved.protocol == "grpc":
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # type: ignore[import-not-found]
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(
                endpoint=resolved.endpoint,
                insecure=resolved.insecure,
                headers=_resolve_otel_headers() or None,
                timeout=resolved.timeout_seconds,
            )
            processor = BatchSpanProcessor(exporter)
            processor_name = "BatchSpanProcessor"
        else:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # type: ignore[import-not-found]
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(
                endpoint=resolved.endpoint,
                headers=_resolve_otel_headers() or None,
                timeout=resolved.timeout_seconds,
            )
            processor = BatchSpanProcessor(exporter)
            processor_name = "BatchSpanProcessor"

        provider.add_span_processor(processor)
        otel_trace.set_tracer_provider(provider)
    except Exception as exc:
        report = _otel_initialization_report_from_config(
            resolved,
            status="degraded",
            initialized=False,
            reason=f"initialization_failed:{exc.__class__.__name__}",
        )
        _OTEL_INITIALIZATION_REPORT = report
        return report

    report = _otel_initialization_report_from_config(
        resolved,
        status="initialized",
        initialized=True,
        provider=provider.__class__.__name__,
        span_processor=processor_name,
    )
    _OTEL_INITIALIZATION_REPORT = report
    return report


def current_otel_initialization_report() -> OtelInitializationReport:
    """Return the last initialization report, or a disabled report if untouched."""

    if _OTEL_INITIALIZATION_REPORT is not None:
        return _OTEL_INITIALIZATION_REPORT
    config = resolve_otel_exporter_config()
    return _otel_initialization_report_from_config(
        config,
        status="disabled" if not config.env_gated else "degraded",
        initialized=False,
        reason=config.degradation_reason or "not_initialized",
    )


def reset_otel_initialization_for_tests() -> None:
    """Reset process-local OTel initialization report for deterministic tests."""

    global _OTEL_INITIALIZATION_REPORT
    _OTEL_INITIALIZATION_REPORT = None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class InMemoryTraceRecorder:
    """Thread-safe rolling buffer for recent trace lifecycle events."""

    def __init__(
        self,
        *,
        max_events: int = DEFAULT_RECENT_TRACE_EVENT_LIMIT,
        clock: Callable[[], float] | None = None,
        monotonic_clock: Callable[[], float] | None = None,
        process_id: str | None = None,
        source: str | None = None,
    ) -> None:
        self.max_events = max(1, int(max_events))
        self._events: deque[TraceEvent] = deque(maxlen=self.max_events)
        self._lock = Lock()
        self._clock = clock or time.time
        self._monotonic_clock = monotonic_clock or time.perf_counter
        self.process_id = str(process_id or _default_process_id())
        self.source = str(source or _default_source())

    def now(self) -> float:
        return float(self._clock())

    def monotonic_now(self) -> float:
        return float(self._monotonic_clock())

    def record_event(
        self,
        *,
        event: TraceEventKind,
        name: str,
        trace_id: str,
        span_id: str,
        parent_span_id: str | None = None,
        timestamp: float | None = None,
        duration_ms: float | None = None,
        attributes: dict[str, Any] | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
        process_id: str | None = None,
        source: str | None = None,
    ) -> TraceEvent:
        trace_event = TraceEvent(
            event=event,
            name=str(name or "span"),
            trace_id=str(trace_id or ""),
            span_id=str(span_id or ""),
            parent_span_id=str(parent_span_id) if parent_span_id else None,
            timestamp=self.now() if timestamp is None else float(timestamp),
            duration_ms=None if duration_ms is None else round(max(0.0, float(duration_ms)), 6),
            attributes=_normalize_attributes(attributes),
            error_type=str(error_type) if error_type else None,
            error_message=str(error_message) if error_message else None,
            process_id=str(process_id or self.process_id),
            source=str(source or self.source),
        )
        with self._lock:
            self._events.append(trace_event)
        return trace_event

    def ingest_external_events(
        self,
        events: list[dict[str, Any]],
        *,
        source: str | None = None,
        process_id: str | None = None,
    ) -> dict[str, Any]:
        accepted = 0
        rejected = 0
        normalized_source = str(source or "external").strip() or "external"
        normalized_process_id = str(process_id or normalized_source).strip() or normalized_source

        for item in events:
            if not isinstance(item, dict):
                rejected += 1
                continue
            raw_kind = str(item.get("event") or "").strip().lower()
            if raw_kind not in _TRACE_EVENT_KINDS:
                rejected += 1
                continue
            event_kind = raw_kind  # narrowed by the guard above
            self.record_event(
                event=event_kind,  # type: ignore[arg-type]
                name=str(item.get("name") or "external.span"),
                trace_id=str(item.get("trace_id") or _new_id()),
                span_id=str(item.get("span_id") or _new_id()),
                parent_span_id=(
                    str(item.get("parent_span_id"))
                    if item.get("parent_span_id")
                    else None
                ),
                timestamp=_optional_float(item.get("timestamp")),
                duration_ms=_optional_float(item.get("duration_ms")),
                attributes=(
                    item.get("attributes")
                    if isinstance(item.get("attributes"), dict)
                    else {}
                ),
                error_type=(
                    str(item.get("error_type"))
                    if item.get("error_type")
                    else None
                ),
                error_message=(
                    str(item.get("error_message"))
                    if item.get("error_message")
                    else None
                ),
                process_id=str(item.get("process_id") or normalized_process_id),
                source=str(item.get("source") or normalized_source),
            )
            accepted += 1

        return {
            "accepted": accepted,
            "rejected": rejected,
            "source": normalized_source,
            "process_id": normalized_process_id,
        }

    def recent_events(
        self,
        limit: int | None = None,
        *,
        event: TraceEventKind | str | None = None,
        name: str | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            events = list(self._events)
        if event:
            events = [item for item in events if item.event == str(event)]
        if name:
            events = [item for item in events if item.name == str(name)]
        if trace_id:
            events = [item for item in events if item.trace_id == str(trace_id)]
        if span_id:
            events = [item for item in events if item.span_id == str(span_id)]
        if limit is not None:
            safe_limit = max(0, int(limit))
            events = events[-safe_limit:] if safe_limit else []
        return [event.to_dict() for event in events]

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


_CURRENT_TRACE_ID: ContextVar[str | None] = ContextVar("current_trace_id", default=None)
_CURRENT_SPAN_ID: ContextVar[str | None] = ContextVar("current_span_id", default=None)
_TRACE_RECORDER = InMemoryTraceRecorder()


class TraceSpan:
    """Context-manager span that records start/end/error lifecycle events."""

    def __init__(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        *,
        recorder: InMemoryTraceRecorder | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> None:
        self.name = str(name or "span")
        self.attributes = _normalize_attributes(attributes)
        self.recorder = recorder or _TRACE_RECORDER
        self.trace_id = trace_id
        self.span_id = _new_id()
        self.parent_span_id = parent_span_id
        self.started_at: float | None = None
        self._finished = False
        self._trace_token: Token[str | None] | None = None
        self._span_token: Token[str | None] | None = None

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[str(key)] = _normalize_attribute_value(value)

    def set_attributes(self, attributes: dict[str, Any] | None) -> None:
        self.attributes.update(_normalize_attributes(attributes))

    def start(self) -> "TraceSpan":
        if self.started_at is not None:
            return self

        inherited_trace_id = self.trace_id or _CURRENT_TRACE_ID.get() or _new_id()
        inherited_parent_span_id = (
            self.parent_span_id
            if self.parent_span_id is not None
            else _CURRENT_SPAN_ID.get()
        )
        self.trace_id = inherited_trace_id
        self.parent_span_id = inherited_parent_span_id
        self.started_at = self.recorder.monotonic_now()
        self.recorder.record_event(
            event="start",
            name=self.name,
            trace_id=self.trace_id,
            span_id=self.span_id,
            parent_span_id=self.parent_span_id,
            attributes=self.attributes,
        )
        self._trace_token = _CURRENT_TRACE_ID.set(self.trace_id)
        self._span_token = _CURRENT_SPAN_ID.set(self.span_id)
        return self

    def end(self) -> None:
        if self._finished:
            return
        if self.started_at is None:
            self.start()
        self._finished = True
        self.recorder.record_event(
            event="end",
            name=self.name,
            trace_id=self.trace_id or "",
            span_id=self.span_id,
            parent_span_id=self.parent_span_id,
            duration_ms=self._duration_ms(),
            attributes=self.attributes,
        )
        self._reset_context()

    def error(self, exc: BaseException) -> None:
        if self._finished:
            return
        if self.started_at is None:
            self.start()
        self._finished = True
        self.recorder.record_event(
            event="error",
            name=self.name,
            trace_id=self.trace_id or "",
            span_id=self.span_id,
            parent_span_id=self.parent_span_id,
            duration_ms=self._duration_ms(),
            attributes=self.attributes,
            error_type=exc.__class__.__name__,
            error_message=str(exc),
        )
        self._reset_context()

    def _duration_ms(self) -> float:
        started_at = self.started_at if self.started_at is not None else self.recorder.monotonic_now()
        return (self.recorder.monotonic_now() - started_at) * 1000.0

    def _reset_context(self) -> None:
        if self._span_token is not None:
            _CURRENT_SPAN_ID.reset(self._span_token)
            self._span_token = None
        if self._trace_token is not None:
            _CURRENT_TRACE_ID.reset(self._trace_token)
            self._trace_token = None

    def __enter__(self) -> "TraceSpan":
        return self.start()

    def __exit__(self, exc_type: Any, exc: BaseException | None, traceback: Any) -> bool:
        if exc is not None:
            self.error(exc)
        else:
            self.end()
        return False

    async def __aenter__(self) -> "TraceSpan":
        return self.start()

    async def __aexit__(self, exc_type: Any, exc: BaseException | None, traceback: Any) -> bool:
        if exc is not None:
            self.error(exc)
        else:
            self.end()
        return False


def trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    *,
    recorder: InMemoryTraceRecorder | None = None,
    trace_id: str | None = None,
    parent_span_id: str | None = None,
) -> TraceSpan:
    return TraceSpan(
        name,
        attributes,
        recorder=recorder,
        trace_id=trace_id,
        parent_span_id=parent_span_id,
    )


def get_recent_trace_events(
    limit: int | None = None,
    *,
    recorder: InMemoryTraceRecorder | None = None,
    event: TraceEventKind | str | None = None,
    name: str | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
) -> list[dict[str, Any]]:
    return (recorder or _TRACE_RECORDER).recent_events(
        limit,
        event=event,
        name=name,
        trace_id=trace_id,
        span_id=span_id,
    )


def reset_trace_events(*, recorder: InMemoryTraceRecorder | None = None) -> None:
    (recorder or _TRACE_RECORDER).clear()


def get_current_trace_context() -> dict[str, str]:
    """Return the active trace/span ids for log correlation."""

    context: dict[str, str] = {}
    trace_id = _CURRENT_TRACE_ID.get()
    span_id = _CURRENT_SPAN_ID.get()
    if trace_id:
        context["trace_id"] = trace_id
    if span_id:
        context["span_id"] = span_id
    return context


def ingest_external_trace_events(
    payload: dict[str, Any],
    *,
    recorder: InMemoryTraceRecorder | None = None,
) -> dict[str, Any]:
    """Merge trace events produced by another process into the local buffer."""

    events = payload.get("events") if isinstance(payload, dict) else []
    safe_events = [item for item in events if isinstance(item, dict)] if isinstance(events, list) else []
    return (recorder or _TRACE_RECORDER).ingest_external_events(
        safe_events,
        source=str(payload.get("source") or "external") if isinstance(payload, dict) else "external",
        process_id=(
            str(payload.get("process_id"))
            if isinstance(payload, dict) and payload.get("process_id")
            else None
        ),
    )


def _otlp_attributes(attributes: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"key": str(key), "value": _otlp_value(value)}
        for key, value in sorted(attributes.items())
    ]


def _otlp_value(value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"bool_value": value}
    if isinstance(value, int) and not isinstance(value, bool):
        return {"int_value": value}
    if isinstance(value, float):
        return {"double_value": value}
    if value is None:
        return {"string_value": ""}
    return {"string_value": value if isinstance(value, str) else str(value)}


def _unix_nano(timestamp: float | int | None) -> str:
    safe_timestamp = max(0.0, float(timestamp or 0.0))
    return str(int(safe_timestamp * 1_000_000_000))


def _span_status(event: dict[str, Any] | None) -> dict[str, str]:
    if not event:
        return {"code": "STATUS_CODE_UNSET"}
    if event.get("event") == "error":
        status = {"code": "STATUS_CODE_ERROR"}
        message = str(event.get("error_message") or "").strip()
        if message:
            status["message"] = message
        return status
    return {"code": "STATUS_CODE_OK"}


def build_trace_export_payload(
    events: list[dict[str, Any]],
    *,
    service_name: str = DEFAULT_TRACE_SERVICE_NAME,
    exporter_config: OtelExporterConfig | None = None,
) -> dict[str, Any]:
    """Build an OTLP-style JSON payload from recent trace lifecycle events."""

    exporter_contract = build_otel_exporter_contract(exporter_config)
    normalized_events = [dict(event) for event in events if isinstance(event, dict)]
    spans_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for event in normalized_events:
        trace_id = str(event.get("trace_id") or "")
        span_id = str(event.get("span_id") or "")
        if not trace_id or not span_id:
            continue
        spans_by_key.setdefault((trace_id, span_id), []).append(event)

    spans: list[dict[str, Any]] = []
    log_records: list[dict[str, Any]] = []
    source_nodes: dict[str, int] = {}
    process_nodes: dict[str, int] = {}

    for event in normalized_events:
        source = str(event.get("source") or "unknown")
        process_id = str(event.get("process_id") or "unknown")
        source_nodes[source] = source_nodes.get(source, 0) + 1
        process_nodes[process_id] = process_nodes.get(process_id, 0) + 1
        log_attributes = {
            "trace.event": event.get("event"),
            "span.name": event.get("name"),
            "source": source,
            "process.id": process_id,
        }
        if event.get("error_type"):
            log_attributes["error.type"] = event.get("error_type")
        if event.get("error_message"):
            log_attributes["error.message"] = event.get("error_message")
        log_records.append(
            {
                "time_unix_nano": _unix_nano(event.get("timestamp")),
                "trace_id": str(event.get("trace_id") or ""),
                "span_id": str(event.get("span_id") or ""),
                "severity_text": "ERROR" if event.get("event") == "error" else "INFO",
                "body": {"string_value": f"trace.{event.get('event') or 'event'}"},
                "attributes": _otlp_attributes(log_attributes),
            }
        )

    for (trace_id, span_id), span_events in spans_by_key.items():
        span_events.sort(key=lambda item: float(item.get("timestamp") or 0.0))
        start_event = next((item for item in span_events if item.get("event") == "start"), None)
        finish_event = next(
            (
                item
                for item in reversed(span_events)
                if item.get("event") in {"end", "error"}
            ),
            None,
        )
        representative = finish_event or start_event or span_events[-1]
        duration_ms = representative.get("duration_ms")
        end_timestamp = float(representative.get("timestamp") or 0.0)
        if start_event is not None:
            start_timestamp = float(start_event.get("timestamp") or end_timestamp)
        elif isinstance(duration_ms, (int, float)):
            start_timestamp = max(0.0, end_timestamp - (float(duration_ms) / 1000.0))
        else:
            start_timestamp = end_timestamp

        merged_attributes: dict[str, Any] = {}
        for item in span_events:
            if isinstance(item.get("attributes"), dict):
                merged_attributes.update(item["attributes"])
        merged_attributes.update(
            {
                "source": representative.get("source") or "unknown",
                "process.id": representative.get("process_id") or "unknown",
            }
        )
        if representative.get("error_type"):
            merged_attributes["error.type"] = representative.get("error_type")

        spans.append(
            {
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": representative.get("parent_span_id"),
                "name": representative.get("name") or "span",
                "kind": "SPAN_KIND_INTERNAL",
                "start_time_unix_nano": _unix_nano(start_timestamp),
                "end_time_unix_nano": _unix_nano(end_timestamp),
                "attributes": _otlp_attributes(merged_attributes),
                "duration_ms": duration_ms,
                "status": _span_status(finish_event),
                "events": [
                    {
                        "name": f"trace.{item.get('event') or 'event'}",
                        "time_unix_nano": _unix_nano(item.get("timestamp")),
                        "attributes": _otlp_attributes(
                            {
                                "trace.event": item.get("event"),
                                "source": item.get("source") or "unknown",
                                "process.id": item.get("process_id") or "unknown",
                            }
                        ),
                    }
                    for item in span_events
                ],
            }
        )

    spans.sort(key=lambda item: (str(item["trace_id"]), str(item["span_id"])))
    resource_attributes = {
        "service.name": service_name or DEFAULT_TRACE_SERVICE_NAME,
        "telemetry.sdk.language": "python",
        "telemetry.sdk.name": "insightdesk-local",
        "telemetry.exporter": exporter_contract["exporter"],
        "telemetry.exporter.protocol": exporter_contract["protocol"],
    }
    payload = {
        "format": "otlp-json-preview",
        "resource_spans": [
            {
                "resource": {"attributes": _otlp_attributes(resource_attributes)},
                "scope_spans": [
                    {
                        "scope": {
                            "name": "backend.core.tracing",
                            "version": "1",
                        },
                        "spans": spans,
                    }
                ],
            }
        ],
        "resource_logs": [
            {
                "resource": {"attributes": _otlp_attributes(resource_attributes)},
                "scope_logs": [
                    {
                        "scope": {
                            "name": "backend.core.tracing",
                            "version": "1",
                        },
                        "log_records": log_records,
                    }
                ],
            }
        ],
        "summary": {
            "service_name": service_name or DEFAULT_TRACE_SERVICE_NAME,
            "event_count": len(normalized_events),
            "span_count": len(spans),
            "log_record_count": len(log_records),
            "source_nodes": source_nodes,
            "process_nodes": process_nodes,
            "otel_exporter": exporter_contract,
        },
    }
    return payload


def build_trace_dashboard_payload(
    events: list[dict[str, Any]],
    export_payload: dict[str, Any],
) -> dict[str, Any]:
    error_events = sum(1 for event in events if event.get("event") == "error")
    end_durations = [
        float(event["duration_ms"])
        for event in events
        if event.get("event") in {"end", "error"}
        and isinstance(event.get("duration_ms"), (int, float))
    ]
    avg_duration = round(sum(end_durations) / len(end_durations), 3) if end_durations else 0.0
    export_summary = dict(export_payload.get("summary") or {})
    source_nodes = dict(export_summary.get("source_nodes") or {})
    process_nodes = dict(export_summary.get("process_nodes") or {})
    status = "warning" if error_events else "ok"

    return {
        "dashboard_cards": [
            {
                "id": "trace_events",
                "title": "Trace events",
                "value": len(events),
                "unit": "events",
                "severity": "ok",
            },
            {
                "id": "export_spans",
                "title": "OTLP spans",
                "value": int(export_summary.get("span_count") or 0),
                "unit": "spans",
                "severity": "ok",
            },
            {
                "id": "trace_errors",
                "title": "Trace errors",
                "value": error_events,
                "unit": "errors",
                "severity": status,
            },
            {
                "id": "process_nodes",
                "title": "Process nodes",
                "value": len(process_nodes),
                "unit": "nodes",
                "severity": "ok",
            },
        ],
        "panel_templates": [
            {
                "id": "trace_export_preview",
                "title": "OTLP export preview",
                "kind": "json_preview",
                "source": "operations.traces.export",
                "fields": [
                    "service.name",
                    "trace_id",
                    "span_id",
                    "parent_span_id",
                    "name",
                    "attributes",
                    "duration_ms",
                    "status",
                ],
            },
            {
                "id": "trace_process_aggregation",
                "title": "Trace process aggregation",
                "kind": "summary",
                "source": "operations.traces.summary",
                "fields": ["source_nodes", "process_nodes", "error_events", "avg_duration_ms"],
            },
        ],
        "export_preview": {
            "service_name": export_summary.get("service_name") or DEFAULT_TRACE_SERVICE_NAME,
            "span_count": int(export_summary.get("span_count") or 0),
            "log_record_count": int(export_summary.get("log_record_count") or 0),
            "source_nodes": source_nodes,
            "process_nodes": process_nodes,
            "avg_duration_ms": avg_duration,
            "sample_spans": (
                export_payload.get("resource_spans", [{}])[0]
                .get("scope_spans", [{}])[0]
                .get("spans", [])[:3]
            ),
        },
    }


__all__ = [
    "DEFAULT_RECENT_TRACE_EVENT_LIMIT",
    "DEFAULT_TRACE_SERVICE_NAME",
    "InMemoryTraceRecorder",
    "OtelExporterConfig",
    "OtelInitializationReport",
    "TraceEvent",
    "TraceEventKind",
    "TraceSpan",
    "build_otel_exporter_contract",
    "build_trace_dashboard_payload",
    "build_trace_export_payload",
    "current_otel_initialization_report",
    "get_current_trace_context",
    "get_recent_trace_events",
    "initialize_otel_tracing",
    "ingest_external_trace_events",
    "reset_otel_initialization_for_tests",
    "reset_trace_events",
    "resolve_otel_exporter_config",
    "trace_span",
]
