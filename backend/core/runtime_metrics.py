"""Runtime request/error metrics helpers."""

from __future__ import annotations

import time
import os
from dataclasses import dataclass, field
from importlib.util import find_spec
from threading import Lock
from typing import Any, Callable, Literal

MetricsExporterKind = Literal["none", "otlp", "prometheus", "console"]
MetricsOtelProtocol = Literal["grpc", "http/protobuf"]
MetricsInitStatus = Literal["initialized", "disabled", "degraded", "already_initialized"]


@dataclass(frozen=True)
class RuntimeMetricsExporterConfig:
    """Environment-derived metrics exporter contract without network side effects."""

    enabled: bool
    exporter: MetricsExporterKind
    endpoint: str | None
    temporality_preference: str
    dependency_available: bool
    env_gated: bool
    service_name: str = "insightdesk-api"
    protocol: MetricsOtelProtocol = "http/protobuf"
    insecure: bool = False
    timeout_seconds: float = 10.0
    header_names: list[str] = field(default_factory=list)
    degradation_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "exporter": self.exporter,
            "endpoint": self.endpoint,
            "temporality_preference": self.temporality_preference,
            "dependency_available": self.dependency_available,
            "env_gated": self.env_gated,
            "service_name": self.service_name,
            "protocol": self.protocol,
            "insecure": self.insecure,
            "timeout_seconds": self.timeout_seconds,
            "header_names": list(self.header_names),
            "degradation_reason": self.degradation_reason,
        }


@dataclass(frozen=True)
class RuntimeMetricsInitializationReport:
    status: MetricsInitStatus
    initialized: bool
    exporter: MetricsExporterKind
    endpoint: str | None
    protocol: MetricsOtelProtocol
    dependency_available: bool
    env_gated: bool
    reason: str | None = None
    provider: str | None = None
    reader: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "initialized": self.initialized,
            "exporter": self.exporter,
            "endpoint": self.endpoint,
            "protocol": self.protocol,
            "dependency_available": self.dependency_available,
            "env_gated": self.env_gated,
            "reason": self.reason,
            "provider": self.provider,
            "reader": self.reader,
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


def _normalize_metrics_exporter(raw: str | None) -> MetricsExporterKind:
    normalized = str(raw or "none").strip().lower()
    if normalized in {"otlp", "prometheus", "console"}:
        return normalized  # type: ignore[return-value]
    return "none"


def _normalize_metrics_protocol(raw: str | None) -> MetricsOtelProtocol:
    normalized = str(raw or "http/protobuf").strip().lower()
    if normalized == "grpc":
        return "grpc"
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


def _metrics_dependency_available(
    exporter: MetricsExporterKind,
    protocol: MetricsOtelProtocol,
) -> bool:
    if exporter == "none":
        return True
    if exporter == "prometheus":
        return _module_available("opentelemetry.exporter.prometheus")
    if exporter == "console":
        return _module_available("opentelemetry.sdk.metrics.export")
    if protocol == "grpc":
        return _module_available("opentelemetry.exporter.otlp.proto.grpc.metric_exporter")
    return _module_available("opentelemetry.exporter.otlp.proto.http.metric_exporter")


def _metrics_degradation_reason(
    *,
    sdk_disabled: bool,
    exporter: MetricsExporterKind,
    endpoint: str | None,
    dependency_available: bool,
) -> str | None:
    if sdk_disabled:
        return "otel_sdk_disabled"
    if exporter == "none":
        return "exporter_none"
    if not dependency_available:
        return "missing_opentelemetry_dependency"
    if exporter == "otlp" and not endpoint:
        return "missing_otlp_endpoint"
    return None


def resolve_runtime_metrics_exporter_config() -> RuntimeMetricsExporterConfig:
    """Resolve OTel metrics exporter contract from env without sending data."""

    sdk_disabled = _env_bool("OTEL_SDK_DISABLED")
    exporter = _normalize_metrics_exporter(os.getenv("OTEL_METRICS_EXPORTER"))
    endpoint = (
        os.getenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT")
        or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        or ""
    ).strip() or None
    protocol = _normalize_metrics_protocol(os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL"))
    dependency_available = _metrics_dependency_available(exporter, protocol)
    env_gated = not sdk_disabled and exporter != "none"
    enabled = env_gated and dependency_available and (
        exporter in {"prometheus", "console"} or bool(endpoint)
    )
    degradation_reason = _metrics_degradation_reason(
        sdk_disabled=sdk_disabled,
        exporter=exporter,
        endpoint=endpoint,
        dependency_available=dependency_available,
    )
    return RuntimeMetricsExporterConfig(
        enabled=enabled,
        exporter=exporter,
        endpoint=endpoint,
        temporality_preference=(
            os.getenv("OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE")
            or "cumulative"
        ).strip().lower()
        or "cumulative",
        dependency_available=dependency_available,
        env_gated=env_gated,
        service_name=(
            os.getenv("OTEL_SERVICE_NAME")
            or os.getenv("SERVICE_NAME")
            or "insightdesk-api"
        ).strip()
        or "insightdesk-api",
        protocol=protocol,
        insecure=_env_bool("OTEL_EXPORTER_OTLP_INSECURE"),
        timeout_seconds=_env_float("OTEL_EXPORTER_OTLP_TIMEOUT", 10.0),
        header_names=_header_names(
            ",".join(
                value
                for value in (
                    os.getenv("OTEL_EXPORTER_OTLP_HEADERS"),
                    os.getenv("OTEL_EXPORTER_OTLP_METRICS_HEADERS"),
                )
                if value
            )
        ),
        degradation_reason=degradation_reason if not enabled else None,
    )


def build_runtime_metrics_exporter_contract(
    config: RuntimeMetricsExporterConfig | None = None,
) -> dict[str, Any]:
    resolved = config or resolve_runtime_metrics_exporter_config()
    payload = resolved.to_dict()
    payload["network_send"] = False
    payload["initialization"] = current_runtime_metrics_initialization_report().to_dict()
    payload["prometheus_endpoint"] = "/api/operations/metrics"
    payload["required_env"] = [
        "OTEL_METRICS_EXPORTER=otlp|prometheus|console|none",
        "OTEL_EXPORTER_OTLP_ENDPOINT or OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
        "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE",
        "OTEL_EXPORTER_OTLP_PROTOCOL=grpc|http/protobuf",
    ]
    return payload


_RUNTIME_METRICS_INITIALIZATION_REPORT: RuntimeMetricsInitializationReport | None = None


def _runtime_metrics_report_from_config(
    config: RuntimeMetricsExporterConfig,
    *,
    status: MetricsInitStatus,
    initialized: bool,
    reason: str | None = None,
    provider: str | None = None,
    reader: str | None = None,
) -> RuntimeMetricsInitializationReport:
    return RuntimeMetricsInitializationReport(
        status=status,
        initialized=initialized,
        exporter=config.exporter,
        endpoint=config.endpoint,
        protocol=config.protocol,
        dependency_available=config.dependency_available,
        env_gated=config.env_gated,
        reason=reason,
        provider=provider,
        reader=reader,
    )


def _runtime_metrics_resource_attributes(service_name: str) -> dict[str, str]:
    return {
        "service.name": service_name or "insightdesk-api",
        "telemetry.sdk.language": "python",
        "deployment.environment": os.getenv("DEPLOYMENT_ENVIRONMENT", "local"),
    }


def _resolve_otel_metrics_headers() -> dict[str, str]:
    return _header_dict(
        ",".join(
            value
            for value in (
                os.getenv("OTEL_EXPORTER_OTLP_HEADERS"),
                os.getenv("OTEL_EXPORTER_OTLP_METRICS_HEADERS"),
            )
            if value
        )
    )


def initialize_runtime_metrics_exporter(
    config: RuntimeMetricsExporterConfig | None = None,
    *,
    force: bool = False,
) -> RuntimeMetricsInitializationReport:
    """Install the real OpenTelemetry metrics SDK exporter when env-gated."""

    global _RUNTIME_METRICS_INITIALIZATION_REPORT

    if _RUNTIME_METRICS_INITIALIZATION_REPORT is not None and not force:
        current = _RUNTIME_METRICS_INITIALIZATION_REPORT
        if current.initialized:
            return RuntimeMetricsInitializationReport(
                **{**current.to_dict(), "status": "already_initialized"}
            )
        return current

    resolved = config or resolve_runtime_metrics_exporter_config()
    if not resolved.env_gated:
        report = _runtime_metrics_report_from_config(
            resolved,
            status="disabled",
            initialized=False,
            reason=resolved.degradation_reason or "env_not_enabled",
        )
        _RUNTIME_METRICS_INITIALIZATION_REPORT = report
        return report
    if not resolved.enabled:
        report = _runtime_metrics_report_from_config(
            resolved,
            status="degraded",
            initialized=False,
            reason=resolved.degradation_reason or "exporter_not_ready",
        )
        _RUNTIME_METRICS_INITIALIZATION_REPORT = report
        return report

    try:
        from opentelemetry import metrics as otel_metrics  # type: ignore[import-not-found]
        from opentelemetry.sdk.metrics import MeterProvider  # type: ignore[import-not-found]
        from opentelemetry.sdk.metrics.export import (  # type: ignore[import-not-found]
            ConsoleMetricExporter,
            PeriodicExportingMetricReader,
        )
        from opentelemetry.sdk.resources import Resource  # type: ignore[import-not-found]

        resource = Resource.create(
            _runtime_metrics_resource_attributes(resolved.service_name)
        )
        if resolved.exporter == "console":
            exporter = ConsoleMetricExporter()
            reader = PeriodicExportingMetricReader(exporter)
        elif resolved.exporter == "prometheus":
            from opentelemetry.exporter.prometheus import (  # type: ignore[import-not-found]
                PrometheusMetricReader,
            )

            reader = PrometheusMetricReader()
        elif resolved.protocol == "grpc":
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (  # type: ignore[import-not-found]
                OTLPMetricExporter,
            )

            exporter = OTLPMetricExporter(
                endpoint=resolved.endpoint,
                insecure=resolved.insecure,
                headers=_resolve_otel_metrics_headers() or None,
                timeout=resolved.timeout_seconds,
            )
            reader = PeriodicExportingMetricReader(exporter)
        else:
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import (  # type: ignore[import-not-found]
                OTLPMetricExporter,
            )

            exporter = OTLPMetricExporter(
                endpoint=resolved.endpoint,
                headers=_resolve_otel_metrics_headers() or None,
                timeout=resolved.timeout_seconds,
            )
            reader = PeriodicExportingMetricReader(exporter)

        provider = MeterProvider(resource=resource, metric_readers=[reader])
        otel_metrics.set_meter_provider(provider)
    except Exception as exc:
        report = _runtime_metrics_report_from_config(
            resolved,
            status="degraded",
            initialized=False,
            reason=f"initialization_failed:{exc.__class__.__name__}",
        )
        _RUNTIME_METRICS_INITIALIZATION_REPORT = report
        return report

    report = _runtime_metrics_report_from_config(
        resolved,
        status="initialized",
        initialized=True,
        provider=provider.__class__.__name__,
        reader=reader.__class__.__name__,
    )
    _RUNTIME_METRICS_INITIALIZATION_REPORT = report
    return report


def current_runtime_metrics_initialization_report() -> RuntimeMetricsInitializationReport:
    if _RUNTIME_METRICS_INITIALIZATION_REPORT is not None:
        return _RUNTIME_METRICS_INITIALIZATION_REPORT
    config = resolve_runtime_metrics_exporter_config()
    return _runtime_metrics_report_from_config(
        config,
        status="disabled" if not config.env_gated else "degraded",
        initialized=False,
        reason=config.degradation_reason or "not_initialized",
    )


def reset_runtime_metrics_initialization_for_tests() -> None:
    global _RUNTIME_METRICS_INITIALIZATION_REPORT
    _RUNTIME_METRICS_INITIALIZATION_REPORT = None


def runtime_status_class(status_code: int) -> str:
    if 200 <= status_code < 300:
        return "2xx"
    if 300 <= status_code < 400:
        return "3xx"
    if 400 <= status_code < 500:
        return "4xx"
    if 500 <= status_code < 600:
        return "5xx"
    return "other"


def new_runtime_metrics_state() -> dict[str, Any]:
    return {
        "total_requests": 0,
        "total_errors": 0,
        "by_status_class": {
            "2xx": 0,
            "3xx": 0,
            "4xx": 0,
            "5xx": 0,
            "other": 0,
        },
        "last_request_at": None,
        "last_error_at": None,
        "recent_errors": [],
    }


def new_llm_metrics_state() -> dict[str, Any]:
    return {
        "total_calls": 0,
        "total_errors": 0,
        "total_timeouts": 0,
        "total_latency_seconds": 0.0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "by_model": {},
        "last_call_at": None,
        "last_error_at": None,
    }


_LLM_METRICS_LOCK = Lock()
_LLM_METRICS_STATE = new_llm_metrics_state()


def reset_runtime_llm_metrics() -> None:
    """Reset process-local LLM metrics, mainly for deterministic tests."""

    with _LLM_METRICS_LOCK:
        _LLM_METRICS_STATE.clear()
        _LLM_METRICS_STATE.update(new_llm_metrics_state())


def record_runtime_request(
    metrics: dict[str, Any],
    lock: Lock,
    *,
    status_code: int,
    timestamp: float | None = None,
) -> None:
    recorded_at = time.time() if timestamp is None else float(timestamp)
    status_class = runtime_status_class(int(status_code))
    with lock:
        metrics["total_requests"] += 1
        metrics["by_status_class"][status_class] = (
            int(metrics["by_status_class"].get(status_class, 0)) + 1
        )
        metrics["last_request_at"] = recorded_at


def record_runtime_error(
    metrics: dict[str, Any],
    lock: Lock,
    *,
    request: Any,
    status_code: int,
    error_code: str,
    message: str,
    sanitize_request_path: Callable[[str], str],
    sanitize_log_value: Callable[..., str],
    recent_error_limit: int,
    timestamp: float | None = None,
) -> None:
    recorded_at = time.time() if timestamp is None else float(timestamp)
    error_entry = {
        "timestamp": recorded_at,
        "request_id": str(getattr(request.state, "request_id", "") or "").strip(),
        "path": sanitize_request_path(request.url.path),
        "method": str(request.method or "").strip().upper(),
        "status_code": int(status_code),
        "error_code": sanitize_log_value(error_code, max_length=64),
        "message": sanitize_log_value(message, max_length=240),
    }
    with lock:
        metrics["total_errors"] += 1
        metrics["last_error_at"] = recorded_at
        recent_errors = list(metrics.get("recent_errors") or [])
        recent_errors.append(error_entry)
        metrics["recent_errors"] = recent_errors[-recent_error_limit:]


def _llm_metric_key(provider: str, model: str) -> str:
    normalized_provider = str(provider or "unknown").strip() or "unknown"
    normalized_model = str(model or "unknown").strip() or "unknown"
    return f"{normalized_provider}\0{normalized_model}"


def record_llm_call(
    *,
    provider: str = "unknown",
    model: str = "unknown",
    status: str = "success",
    latency_seconds: float = 0.0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    timestamp: float | None = None,
    metrics: dict[str, Any] | None = None,
    lock: Lock | None = None,
) -> None:
    """Record one LLM call without introducing a metrics dependency."""

    state = metrics if metrics is not None else _LLM_METRICS_STATE
    state_lock = lock if lock is not None else _LLM_METRICS_LOCK
    normalized_status = str(status or "success").strip().lower() or "success"
    provider_label = str(provider or "unknown").strip() or "unknown"
    model_label = str(model or "unknown").strip() or "unknown"
    recorded_at = time.time() if timestamp is None else float(timestamp)
    safe_latency = max(0.0, float(latency_seconds or 0.0))
    safe_prompt_tokens = max(0, int(prompt_tokens or 0))
    safe_completion_tokens = max(0, int(completion_tokens or 0))
    safe_total_tokens = max(
        0,
        int(total_tokens or 0) or safe_prompt_tokens + safe_completion_tokens,
    )

    with state_lock:
        state["total_calls"] = int(state.get("total_calls", 0)) + 1
        state["total_latency_seconds"] = float(state.get("total_latency_seconds", 0.0)) + safe_latency
        state["prompt_tokens"] = int(state.get("prompt_tokens", 0)) + safe_prompt_tokens
        state["completion_tokens"] = int(state.get("completion_tokens", 0)) + safe_completion_tokens
        state["total_tokens"] = int(state.get("total_tokens", 0)) + safe_total_tokens
        state["last_call_at"] = recorded_at
        if normalized_status != "success":
            state["total_errors"] = int(state.get("total_errors", 0)) + 1
            state["last_error_at"] = recorded_at
        if normalized_status == "timeout":
            state["total_timeouts"] = int(state.get("total_timeouts", 0)) + 1

        by_model = dict(state.get("by_model") or {})
        model_key = _llm_metric_key(provider_label, model_label)
        model_entry = dict(
            by_model.get(model_key)
            or {
                "provider": provider_label,
                "model": model_label,
                "total_calls": 0,
                "total_errors": 0,
                "total_timeouts": 0,
                "total_latency_seconds": 0.0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }
        )
        model_entry["total_calls"] = int(model_entry.get("total_calls", 0)) + 1
        model_entry["total_latency_seconds"] = (
            float(model_entry.get("total_latency_seconds", 0.0)) + safe_latency
        )
        model_entry["prompt_tokens"] = int(model_entry.get("prompt_tokens", 0)) + safe_prompt_tokens
        model_entry["completion_tokens"] = (
            int(model_entry.get("completion_tokens", 0)) + safe_completion_tokens
        )
        model_entry["total_tokens"] = int(model_entry.get("total_tokens", 0)) + safe_total_tokens
        if normalized_status != "success":
            model_entry["total_errors"] = int(model_entry.get("total_errors", 0)) + 1
        if normalized_status == "timeout":
            model_entry["total_timeouts"] = int(model_entry.get("total_timeouts", 0)) + 1
        by_model[model_key] = model_entry
        state["by_model"] = by_model


def runtime_llm_metrics_payload(
    metrics: dict[str, Any] | None = None,
    lock: Lock | None = None,
) -> dict[str, Any]:
    state = metrics if metrics is not None else _LLM_METRICS_STATE
    state_lock = lock if lock is not None else _LLM_METRICS_LOCK
    with state_lock:
        by_model = [
            dict(item)
            for item in dict(state.get("by_model") or {}).values()
        ]
        by_model.sort(
            key=lambda item: (
                str(item.get("provider") or ""),
                str(item.get("model") or ""),
            )
        )
        return {
            "total_calls": int(state.get("total_calls", 0)),
            "total_errors": int(state.get("total_errors", 0)),
            "total_timeouts": int(state.get("total_timeouts", 0)),
            "total_latency_seconds": round(float(state.get("total_latency_seconds", 0.0)), 6),
            "prompt_tokens": int(state.get("prompt_tokens", 0)),
            "completion_tokens": int(state.get("completion_tokens", 0)),
            "total_tokens": int(state.get("total_tokens", 0)),
            "last_call_at": state.get("last_call_at"),
            "last_error_at": state.get("last_error_at"),
            "by_model": by_model,
        }


def runtime_request_metrics_payload(
    metrics: dict[str, Any],
    lock: Lock,
) -> dict[str, Any]:
    with lock:
        by_status_class = {
            str(key): int(value or 0)
            for key, value in dict(metrics["by_status_class"]).items()
        }
        recent_errors = [dict(item) for item in list(metrics["recent_errors"])]
        return {
            "total_requests": int(metrics["total_requests"]),
            "total_errors": int(metrics["total_errors"]),
            "by_status_class": by_status_class,
            "last_request_at": metrics["last_request_at"],
            "last_error_at": metrics["last_error_at"],
            "recent_errors": recent_errors,
        }


def runtime_operations_summary_payload(
    *,
    request_metrics: dict[str, Any],
    task_summary: dict[str, Any],
    uptime_seconds: float,
    llm_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a compact operations health summary from existing snapshots."""

    total_requests = max(0, int(request_metrics.get("total_requests", 0) or 0))
    total_errors = max(0, int(request_metrics.get("total_errors", 0) or 0))
    safe_uptime = max(0.0, float(uptime_seconds or 0.0))
    running_tasks = max(0, int(task_summary.get("running", 0) or 0))
    pending_tasks = max(0, int(task_summary.get("pending", 0) or 0))
    active_tasks = running_tasks + pending_tasks
    llm_total_calls = 0
    llm_total_errors = 0
    if llm_metrics is not None:
        llm_total_calls = max(0, int(llm_metrics.get("total_calls", 0) or 0))
        llm_total_errors = max(0, int(llm_metrics.get("total_errors", 0) or 0))

    error_rate = (total_errors / total_requests) if total_requests else 0.0
    llm_error_rate = (llm_total_errors / llm_total_calls) if llm_total_calls else 0.0
    requests_per_minute = (total_requests / (safe_uptime / 60.0)) if safe_uptime > 0 else 0.0

    alerts: list[dict[str, Any]] = []
    if error_rate >= 0.05 and total_errors > 0:
        alerts.append(
            {
                "severity": "warning",
                "code": "runtime_http_error_rate",
                "message": "HTTP error rate is elevated.",
                "value": round(error_rate, 6),
            }
        )
    if llm_error_rate >= 0.05 and llm_total_errors > 0:
        alerts.append(
            {
                "severity": "warning",
                "code": "runtime_llm_error_rate",
                "message": "LLM error rate is elevated.",
                "value": round(llm_error_rate, 6),
            }
        )
    if running_tasks > 0:
        alerts.append(
            {
                "severity": "info",
                "code": "runtime_tasks_active",
                "message": "Tasks are currently running.",
                "value": running_tasks,
            }
        )
    task_health_summary = task_summary.get("health", {})
    if isinstance(task_health_summary, dict):
        task_health_summary = task_health_summary.get("summary", {})
    if isinstance(task_health_summary, dict):
        task_health_warning_count = int(task_health_summary.get("warning_count") or 0)
        if task_health_warning_count > 0:
            alerts.append(
                {
                    "severity": "warning",
                    "code": "runtime_task_queue_health",
                    "message": "Task queue health warnings are active.",
                    "value": task_health_warning_count,
                }
            )

    health_status = "warning" if any(item["severity"] == "warning" for item in alerts) else "ok"
    return {
        "health_status": health_status,
        "error_rate": round(error_rate, 6),
        "requests_per_minute": round(requests_per_minute, 6),
        "active_tasks": active_tasks,
        "llm_error_rate": round(llm_error_rate, 6),
        "alert_count": len(alerts),
        "alerts": alerts,
    }


def _snapshot_request_metrics(snapshot: dict[str, Any]) -> dict[str, Any]:
    request_metrics = snapshot.get("request_metrics")
    if isinstance(request_metrics, dict):
        return request_metrics
    return snapshot


def aggregate_runtime_metrics_snapshots(
    snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    """Merge process-local or external runtime metrics into node-aware totals."""

    nodes: list[dict[str, Any]] = []
    totals = {
        "total_requests": 0,
        "total_errors": 0,
        "by_status_class": {
            "2xx": 0,
            "3xx": 0,
            "4xx": 0,
            "5xx": 0,
            "other": 0,
        },
        "last_request_at": None,
        "last_error_at": None,
    }

    for index, raw_snapshot in enumerate(snapshots):
        if not isinstance(raw_snapshot, dict):
            continue
        metrics = _snapshot_request_metrics(raw_snapshot)
        source = str(raw_snapshot.get("source") or f"node-{index + 1}").strip() or f"node-{index + 1}"
        process_id = str(raw_snapshot.get("process_id") or source).strip() or source
        total_requests = max(0, int(metrics.get("total_requests", 0) or 0))
        total_errors = max(0, int(metrics.get("total_errors", 0) or 0))
        status_counts = {
            status_class: max(0, int(value or 0))
            for status_class, value in dict(metrics.get("by_status_class") or {}).items()
        }
        for status_class in totals["by_status_class"]:
            totals["by_status_class"][status_class] += int(status_counts.get(status_class, 0))
        for status_class, value in status_counts.items():
            if status_class not in totals["by_status_class"]:
                totals["by_status_class"][status_class] = int(value)

        last_request_at = metrics.get("last_request_at")
        if isinstance(last_request_at, (int, float)):
            totals["last_request_at"] = max(
                float(totals["last_request_at"] or 0.0),
                float(last_request_at),
            )
        last_error_at = metrics.get("last_error_at")
        if isinstance(last_error_at, (int, float)):
            totals["last_error_at"] = max(
                float(totals["last_error_at"] or 0.0),
                float(last_error_at),
            )

        totals["total_requests"] += total_requests
        totals["total_errors"] += total_errors
        nodes.append(
            {
                "source": source,
                "process_id": process_id,
                "total_requests": total_requests,
                "total_errors": total_errors,
                "by_status_class": status_counts,
                "last_request_at": last_request_at,
                "last_error_at": last_error_at,
            }
        )

    total_requests = int(totals["total_requests"])
    total_errors = int(totals["total_errors"])
    return {
        "nodes": nodes,
        "summary": {
            "node_count": len(nodes),
            "total_requests": total_requests,
            "total_errors": total_errors,
            "error_rate": round(total_errors / total_requests, 6) if total_requests else 0.0,
            "by_status_class": totals["by_status_class"],
            "last_request_at": totals["last_request_at"],
            "last_error_at": totals["last_error_at"],
        },
    }


def _prometheus_label_value(value: Any) -> str:
    normalized = str(value or "").strip()
    return (
        normalized.replace("\\", "\\\\")
        .replace("\n", " ")
        .replace("\r", " ")
        .replace('"', '\\"')
    )


def _prometheus_sample(
    name: str,
    value: Any,
    labels: dict[str, Any] | None = None,
) -> str:
    numeric_value = float(value or 0)
    if labels:
        label_pairs = ",".join(
            f'{key}="{_prometheus_label_value(label_value)}"'
            for key, label_value in sorted(labels.items())
        )
        return f"{name}{{{label_pairs}}} {numeric_value:g}"
    return f"{name} {numeric_value:g}"


def _task_queue_health_code_counts(task_summary: dict[str, Any]) -> dict[str, int]:
    health = task_summary.get("health")
    if not isinstance(health, dict):
        return {}

    codes: list[str] = []
    summary = health.get("summary")
    if isinstance(summary, dict):
        codes.extend(
            str(code).strip()
            for code in (summary.get("warning_codes") or [])
            if str(code).strip()
        )

    if not codes:
        for warning in list(health.get("warnings") or []):
            if isinstance(warning, dict):
                code = str(warning.get("code") or "").strip()
                if code:
                    codes.append(code)
        queue = health.get("queue")
        if isinstance(queue, dict):
            codes.extend(
                str(code).strip()
                for code in (queue.get("warnings") or [])
                if str(code).strip()
            )

    counts: dict[str, int] = {}
    for code in codes:
        counts[code] = counts.get(code, 0) + 1
    return counts


def runtime_prometheus_metrics_text(
    *,
    request_metrics: dict[str, Any],
    task_summary: dict[str, Any],
    uptime_seconds: float,
    task_backend: str = "unknown",
    llm_metrics: dict[str, Any] | None = None,
    operations_summary: dict[str, Any] | None = None,
) -> str:
    """Build a dependency-free Prometheus text exposition snapshot."""

    recent_errors_count = len(list(request_metrics.get("recent_errors") or []))
    status_counts = {
        str(key): int(value or 0)
        for key, value in dict(request_metrics.get("by_status_class") or {}).items()
    }
    task_status_counts = {
        str(key): int(value or 0)
        for key, value in dict(task_summary).items()
        if key not in {"in_memory_total", "latest_task_updated_at"}
        and isinstance(value, (int, float))
    }

    lines: list[str] = [
        "# HELP insightdesk_uptime_seconds Service uptime in seconds",
        "# TYPE insightdesk_uptime_seconds gauge",
        _prometheus_sample("insightdesk_uptime_seconds", uptime_seconds),
        "",
        "# HELP insightdesk_http_requests_total Total HTTP requests",
        "# TYPE insightdesk_http_requests_total counter",
        _prometheus_sample(
            "insightdesk_http_requests_total",
            request_metrics.get("total_requests", 0),
        ),
        "",
        "# HELP insightdesk_http_errors_total Total HTTP errors",
        "# TYPE insightdesk_http_errors_total counter",
        _prometheus_sample(
            "insightdesk_http_errors_total",
            request_metrics.get("total_errors", 0),
        ),
        "",
        "# HELP insightdesk_http_recent_errors Current retained recent error entries",
        "# TYPE insightdesk_http_recent_errors gauge",
        _prometheus_sample("insightdesk_http_recent_errors", recent_errors_count),
        "",
        "# HELP insightdesk_http_requests_by_status HTTP requests grouped by status class",
        "# TYPE insightdesk_http_requests_by_status counter",
    ]
    for status_class, count in sorted(status_counts.items()):
        lines.append(
            _prometheus_sample(
                "insightdesk_http_requests_by_status",
                count,
                {"status": status_class},
            )
        )

    last_request_at = request_metrics.get("last_request_at")
    last_error_at = request_metrics.get("last_error_at")
    if last_request_at is not None:
        lines.extend(
            [
                "",
                "# HELP insightdesk_http_last_request_timestamp_seconds Last request Unix timestamp",
                "# TYPE insightdesk_http_last_request_timestamp_seconds gauge",
                _prometheus_sample(
                    "insightdesk_http_last_request_timestamp_seconds",
                    last_request_at,
                ),
            ]
        )
    if last_error_at is not None:
        lines.extend(
            [
                "",
                "# HELP insightdesk_http_last_error_timestamp_seconds Last error Unix timestamp",
                "# TYPE insightdesk_http_last_error_timestamp_seconds gauge",
                _prometheus_sample(
                    "insightdesk_http_last_error_timestamp_seconds",
                    last_error_at,
                ),
            ]
        )

    lines.extend(
        [
            "",
            "# HELP insightdesk_task_queue_backend Configured task queue/store backend",
            "# TYPE insightdesk_task_queue_backend gauge",
            _prometheus_sample(
                "insightdesk_task_queue_backend",
                1,
                {"backend": task_backend or "unknown"},
            ),
            "",
            "# HELP insightdesk_tasks_total Total in-memory tasks",
            "# TYPE insightdesk_tasks_total gauge",
            _prometheus_sample(
                "insightdesk_tasks_total",
                task_summary.get("in_memory_total", 0),
            ),
            "",
            "# HELP insightdesk_tasks_by_status Tasks grouped by status",
            "# TYPE insightdesk_tasks_by_status gauge",
        ]
    )
    for status, count in sorted(task_status_counts.items()):
        lines.append(
            _prometheus_sample(
                "insightdesk_tasks_by_status",
                count,
                {"status": status},
            )
        )

    latest_task_updated_at = task_summary.get("latest_task_updated_at")
    if latest_task_updated_at is not None:
        lines.extend(
            [
                "",
                "# HELP insightdesk_tasks_latest_updated_timestamp_seconds Latest task update Unix timestamp",
                "# TYPE insightdesk_tasks_latest_updated_timestamp_seconds gauge",
                _prometheus_sample(
                    "insightdesk_tasks_latest_updated_timestamp_seconds",
                    latest_task_updated_at,
                ),
            ]
        )

    task_queue_health_counts = _task_queue_health_code_counts(task_summary)
    lines.extend(
        [
            "",
            "# HELP insightdesk_task_queue_health Current task queue health warnings grouped by code",
            "# TYPE insightdesk_task_queue_health gauge",
        ]
    )
    for code, count in sorted(task_queue_health_counts.items()):
        lines.append(
            _prometheus_sample(
                "insightdesk_task_queue_health",
                count,
                {"code": code},
            )
        )

    if llm_metrics is not None:
        lines.extend(
            [
                "",
                "# HELP insightdesk_llm_calls_total Total LLM calls",
                "# TYPE insightdesk_llm_calls_total counter",
                _prometheus_sample(
                    "insightdesk_llm_calls_total",
                    llm_metrics.get("total_calls", 0),
                ),
                "",
                "# HELP insightdesk_llm_errors_total Total failed LLM calls",
                "# TYPE insightdesk_llm_errors_total counter",
                _prometheus_sample(
                    "insightdesk_llm_errors_total",
                    llm_metrics.get("total_errors", 0),
                ),
                "",
                "# HELP insightdesk_llm_timeouts_total Total timed-out LLM calls",
                "# TYPE insightdesk_llm_timeouts_total counter",
                _prometheus_sample(
                    "insightdesk_llm_timeouts_total",
                    llm_metrics.get("total_timeouts", 0),
                ),
                "",
                "# HELP insightdesk_llm_latency_seconds_sum Total LLM latency seconds",
                "# TYPE insightdesk_llm_latency_seconds_sum counter",
                _prometheus_sample(
                    "insightdesk_llm_latency_seconds_sum",
                    llm_metrics.get("total_latency_seconds", 0.0),
                ),
                "",
                "# HELP insightdesk_llm_tokens_total Total LLM tokens reported by providers",
                "# TYPE insightdesk_llm_tokens_total counter",
                _prometheus_sample(
                    "insightdesk_llm_tokens_total",
                    llm_metrics.get("total_tokens", 0),
                ),
            ]
        )
        for item in list(llm_metrics.get("by_model") or []):
            labels = {
                "provider": item.get("provider") or "unknown",
                "model": item.get("model") or "unknown",
            }
            lines.append(
                _prometheus_sample(
                    "insightdesk_llm_calls_by_model_total",
                    item.get("total_calls", 0),
                    labels,
                )
            )
            lines.append(
                _prometheus_sample(
                    "insightdesk_llm_errors_by_model_total",
                    item.get("total_errors", 0),
                    labels,
                )
            )
            lines.append(
                _prometheus_sample(
                    "insightdesk_llm_latency_seconds_by_model_sum",
                    item.get("total_latency_seconds", 0.0),
                    labels,
                )
            )
            lines.append(
                _prometheus_sample(
                    "insightdesk_llm_tokens_by_model_total",
                    item.get("total_tokens", 0),
                    labels,
                )
            )

    if operations_summary is not None:
        lines.extend(
            [
                "",
                "# HELP insightdesk_operations_health_status Runtime health status encoded as 1=ok, 0=warning",
                "# TYPE insightdesk_operations_health_status gauge",
                _prometheus_sample(
                    "insightdesk_operations_health_status",
                    1 if operations_summary.get("health_status") == "ok" else 0,
                    {"status": operations_summary.get("health_status") or "unknown"},
                ),
                "",
                "# HELP insightdesk_operations_error_rate HTTP error ratio in the current process",
                "# TYPE insightdesk_operations_error_rate gauge",
                _prometheus_sample(
                    "insightdesk_operations_error_rate",
                    operations_summary.get("error_rate", 0.0),
                ),
                "",
                "# HELP insightdesk_operations_requests_per_minute Average HTTP requests per minute since startup",
                "# TYPE insightdesk_operations_requests_per_minute gauge",
                _prometheus_sample(
                    "insightdesk_operations_requests_per_minute",
                    operations_summary.get("requests_per_minute", 0.0),
                ),
                "",
                "# HELP insightdesk_operations_active_tasks Pending plus running task count",
                "# TYPE insightdesk_operations_active_tasks gauge",
                _prometheus_sample(
                    "insightdesk_operations_active_tasks",
                    operations_summary.get("active_tasks", 0),
                ),
                "",
                "# HELP insightdesk_operations_llm_error_rate LLM error ratio in the current process",
                "# TYPE insightdesk_operations_llm_error_rate gauge",
                _prometheus_sample(
                    "insightdesk_operations_llm_error_rate",
                    operations_summary.get("llm_error_rate", 0.0),
                ),
                "",
                "# HELP insightdesk_operations_alerts Current operations alert count",
                "# TYPE insightdesk_operations_alerts gauge",
                _prometheus_sample(
                    "insightdesk_operations_alerts",
                    operations_summary.get("alert_count", 0),
                ),
            ]
        )

    return "\n".join(lines) + "\n"
