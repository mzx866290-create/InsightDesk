"""
结构化日志配置模块。

提供 JSON 日志格式化器与统一的 `configure_logging()` 入口，
通过环境变量 `LOG_FORMAT=json|text` 切换（默认 text，避免改变默认行为）。

设计目标：
- 每条日志自带 timestamp / level / logger / message 基础字段
- 允许通过 LogRecord.extra 透传 request_id / path / method / status 等上下文
- 错误日志附带 exc_info 的结构化堆栈
- 与现有 logging 调用完全兼容（不需要改动每一处 logger.info 调用）
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Iterable

# 这些字段属于 LogRecord 原生字段，序列化时需要跳过
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

# 常见的上下文字段（logger.info(..., extra={...}) 中传入）会被显式提取
_COMMON_CONTEXT_KEYS: tuple[str, ...] = (
    "request_id",
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
    """将 LogRecord 序列化为单行 JSON 字符串。"""

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

        # 显式提取常见上下文字段（如果通过 extra= 传入）
        for key in self._extra_keys:
            if hasattr(record, key):
                value = getattr(record, key)
                if value is None or value == "":
                    continue
                base[key] = value

        # 附加其他自定义 extra（排除 reserved 字段与已提取的 context 字段）
        for key, value in record.__dict__.items():
            if key in _RESERVED_RECORD_KEYS:
                continue
            if key in base:
                continue
            if key.startswith("_"):
                continue
            try:
                json.dumps(value)  # 仅保留 JSON 可序列化字段
            except (TypeError, ValueError):
                continue
            base[key] = value

        # 异常堆栈
        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            base["stack_info"] = self.formatStack(record.stack_info)

        try:
            return json.dumps(base, ensure_ascii=False, default=str)
        except Exception:
            # 兜底：即使序列化失败也不要让日志链路抛出异常
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


def configure_logging(
    *,
    log_format: str | None = None,
    log_level: str | None = None,
    service_name: str = "insightdesk-backend",
) -> str:
    """配置根 logger。

    返回实际生效的日志格式 ("json" | "text")，便于在启动日志里打印确认。
    """
    resolved_format = (
        str(log_format if log_format is not None else os.getenv("LOG_FORMAT", "text"))
        .strip()
        .lower()
        or "text"
    )
    resolved_level = _resolve_log_level(log_level or os.getenv("LOG_LEVEL"), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(resolved_level)

    # 清理可能存在的旧 handler（重复调用 configure_logging 时保持幂等）
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(stream=sys.stderr)
    if resolved_format == "json":
        handler.setFormatter(JsonFormatter(service_name=service_name))
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(name)s] %(levelname)s %(message)s",
            )
        )
    handler.setLevel(resolved_level)
    root_logger.addHandler(handler)

    # Keep third-party request logs from leaking sensitive path segments
    # such as share tokens into the default INFO log stream.
    logging.getLogger("httpx").setLevel(max(resolved_level, logging.WARNING))
    logging.getLogger("httpcore").setLevel(max(resolved_level, logging.WARNING))

    return resolved_format
