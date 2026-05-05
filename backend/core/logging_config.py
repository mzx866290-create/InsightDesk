"""Structured logging entrypoint with a small structlog-compatible facade."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

_RESERVED_RECORD_KEYS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
    "asctime",
    "taskName",
}

_COMMON_CONTEXT_KEYS: tuple[str, ...] = (
    "request_id",
    "trace_id",
    "span_id",
    "path",
    "method",
    "status",
    "status_code",
    "latency_ms",
    "user_id",
    "user_role",
    "auth_mode",
    "auth_source",
    "action",
    "result",
    "error_code",
)


class JsonFormatter(logging.Formatter):
    """Serialize LogRecord objects as one-line JSON."""

    def __init__(
        self,
        *,
        service_name: str = "insightdesk-backend",
        extra_keys: Iterable[str] = _COMMON_CONTEXT_KEYS,
    ) -> None:
        super().__init__()
        self._service_name = str(service_name or "").strip() or "service"
        self._extra_keys = tuple(extra_keys or ())

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        base: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "service": self._service_name,
            "message": record.getMessage(),
        }

        for key in self._extra_keys:
            if hasattr(record, key):
                value = getattr(record, key)
                if value is not None and value != "":
                    base[key] = value

        for key, value in record.__dict__.items():
            if key in _RESERVED_RECORD_KEYS or key in base or key.startswith("_"):
                continue
            try:
                json.dumps(value, default=str)
            except (TypeError, ValueError):
                continue
            base[key] = value

        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            base["stack_info"] = self.formatStack(record.stack_info)

        try:
            return json.dumps(base, ensure_ascii=False, default=str)
        except Exception:
            return json.dumps(
                {
                    "timestamp": base.get("timestamp"),
                    "level": base.get("level"),
                    "logger": base.get("logger"),
                    "message": str(base.get("message", "")),
                    "service": self._service_name,
                },
                ensure_ascii=False,
            )


class BoundLogger:
    """Minimal structlog-like logger for gradual migration.

    It supports the common ``bind()``, ``unbind()``, ``new()`` and level methods,
    while emitting through standard logging so existing handlers keep working.
    """

    def __init__(
        self,
        logger: logging.Logger,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        self._logger = logger
        self._context = dict(context or {})

    @property
    def context(self) -> dict[str, Any]:
        return dict(self._context)

    def bind(self, **context: Any) -> "BoundLogger":
        next_context = dict(self._context)
        next_context.update(context)
        return BoundLogger(self._logger, next_context)

    def unbind(self, *keys: str) -> "BoundLogger":
        next_context = dict(self._context)
        for key in keys:
            next_context.pop(key, None)
        return BoundLogger(self._logger, next_context)

    def new(self, **context: Any) -> "BoundLogger":
        return BoundLogger(self._logger, context)

    def isEnabledFor(self, level: int) -> bool:  # noqa: N802 - logging compatibility
        return self._logger.isEnabledFor(level)

    def log(self, level: int, event: str, *args: Any, **kwargs: Any) -> None:
        exc_info = kwargs.pop("exc_info", None)
        stack_info = kwargs.pop("stack_info", False)
        stacklevel = int(kwargs.pop("stacklevel", 1))
        extra = dict(self._context)
        extra.update(dict(kwargs.pop("extra", {}) or {}))
        extra.update(kwargs)
        try:
            from backend.core.tracing import get_current_trace_context

            for key, value in get_current_trace_context().items():
                extra.setdefault(key, value)
        except Exception:
            pass
        self._logger.log(
            level,
            event,
            *args,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel + 1,
            extra=extra,
        )

    def debug(self, event: str, *args: Any, **kwargs: Any) -> None:
        self.log(logging.DEBUG, event, *args, **kwargs)

    def info(self, event: str, *args: Any, **kwargs: Any) -> None:
        self.log(logging.INFO, event, *args, **kwargs)

    def warning(self, event: str, *args: Any, **kwargs: Any) -> None:
        self.log(logging.WARNING, event, *args, **kwargs)

    warn = warning

    def error(self, event: str, *args: Any, **kwargs: Any) -> None:
        self.log(logging.ERROR, event, *args, **kwargs)

    def exception(self, event: str, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("exc_info", True)
        self.error(event, *args, **kwargs)

    def critical(self, event: str, *args: Any, **kwargs: Any) -> None:
        self.log(logging.CRITICAL, event, *args, **kwargs)


def _resolve_log_level(raw: str | None, default: int = logging.INFO) -> int:
    if not raw:
        return default
    normalized = str(raw).strip().upper()
    if not normalized:
        return default
    level = logging.getLevelName(normalized)
    if isinstance(level, int):
        return level
    try:
        return int(normalized)
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _otel_tracing_env_gated() -> bool:
    exporter = str(os.getenv("OTEL_TRACES_EXPORTER") or "none").strip().lower()
    return exporter not in {"", "none"} and not _env_bool("OTEL_SDK_DISABLED")


def _otel_metrics_env_gated() -> bool:
    exporter = str(os.getenv("OTEL_METRICS_EXPORTER") or "none").strip().lower()
    return exporter not in {"", "none"} and not _env_bool("OTEL_SDK_DISABLED")


def _configure_otel_tracing_if_enabled(service_name: str) -> dict[str, Any] | None:
    if not _otel_tracing_env_gated():
        return None
    try:
        from backend.core.tracing import initialize_otel_tracing

        report = initialize_otel_tracing()
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "OpenTelemetry tracing initialization failed: %s",
            exc.__class__.__name__,
        )
        return {
            "status": "degraded",
            "initialized": False,
            "reason": f"initialization_failed:{exc.__class__.__name__}",
        }

    payload = report.to_dict()
    log = logging.getLogger(__name__)
    if report.initialized:
        log.info(
            "OpenTelemetry tracing initialized: exporter=%s service=%s protocol=%s",
            report.exporter,
            service_name,
            report.protocol,
        )
    else:
        log.warning(
            "OpenTelemetry tracing degraded: exporter=%s reason=%s",
            report.exporter,
            report.reason,
        )
    return payload


def _configure_otel_metrics_if_enabled(service_name: str) -> dict[str, Any] | None:
    if not _otel_metrics_env_gated():
        return None
    try:
        from backend.core.runtime_metrics import initialize_runtime_metrics_exporter

        report = initialize_runtime_metrics_exporter()
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "OpenTelemetry metrics initialization failed: %s",
            exc.__class__.__name__,
        )
        return {
            "status": "degraded",
            "initialized": False,
            "reason": f"initialization_failed:{exc.__class__.__name__}",
        }

    payload = report.to_dict()
    log = logging.getLogger(__name__)
    if report.initialized:
        log.info(
            "OpenTelemetry metrics initialized: exporter=%s service=%s protocol=%s",
            report.exporter,
            service_name,
            report.protocol,
        )
    else:
        log.warning(
            "OpenTelemetry metrics degraded: exporter=%s reason=%s",
            report.exporter,
            report.reason,
        )
    return payload


def _merge_trace_context(_logger: Any, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    try:
        from backend.core.tracing import get_current_trace_context

        for key, value in get_current_trace_context().items():
            event_dict.setdefault(key, value)
    except Exception:
        pass
    return event_dict


def configure_logging(
    *,
    log_format: str | None = None,
    log_level: str | None = None,
    service_name: str = "insightdesk-backend",
    use_structlog: bool | None = None,
) -> str:
    """Configure root logging and optional structlog processors.

    Returns the effective log format: ``"json"`` or ``"text"``.
    """

    resolved_format = (
        str(log_format if log_format is not None else os.getenv("LOG_FORMAT", "text"))
        .strip()
        .lower()
        or "text"
    )
    if resolved_format not in {"json", "text"}:
        resolved_format = "text"
    resolved_level = _resolve_log_level(log_level or os.getenv("LOG_LEVEL"), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(resolved_level)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(stream=sys.stderr)
    if resolved_format == "json":
        handler.setFormatter(JsonFormatter(service_name=service_name))
    else:
        handler.setFormatter(
            logging.Formatter(fmt="%(asctime)s [%(name)s] %(levelname)s %(message)s")
        )
    handler.setLevel(resolved_level)
    root_logger.addHandler(handler)

    logging.getLogger("httpx").setLevel(max(resolved_level, logging.WARNING))
    logging.getLogger("httpcore").setLevel(max(resolved_level, logging.WARNING))

    if use_structlog if use_structlog is not None else _env_bool("LOG_USE_STRUCTLOG"):
        configure_structlog(service_name=service_name, log_format=resolved_format)

    _configure_otel_tracing_if_enabled(service_name)
    _configure_otel_metrics_if_enabled(service_name)

    return resolved_format


def configure_structlog(
    *,
    service_name: str = "insightdesk-backend",
    log_format: str | None = None,
) -> bool:
    """Configure structlog when the optional dependency is installed."""

    try:
        import structlog  # type: ignore[import-not-found]
    except Exception:
        return False

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        _merge_trace_context,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.EventRenamer("message"),
    ]
    if (log_format or os.getenv("LOG_FORMAT", "text")).strip().lower() == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.NOTSET),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    structlog.contextvars.bind_contextvars(service=service_name)
    return True


def get_logger(name: str | None = None, **context: Any) -> Any:
    """Return a structlog logger when enabled, otherwise a compatible facade."""

    if _env_bool("LOG_USE_STRUCTLOG"):
        try:
            import structlog  # type: ignore[import-not-found]

            logger = structlog.get_logger(name or "insightdesk")
            return logger.bind(**context) if context else logger
        except Exception:
            pass
    return BoundLogger(logging.getLogger(name or "insightdesk"), context)


__all__ = [
    "BoundLogger",
    "JsonFormatter",
    "configure_logging",
    "configure_structlog",
    "get_logger",
]
