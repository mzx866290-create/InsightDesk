"""Compatibility import path for backend.core.logging_config."""

from __future__ import annotations

from backend.core.logging_config import (
    BoundLogger,
    JsonFormatter,
    configure_logging,
    configure_structlog,
    get_logger,
)

__all__ = [
    "BoundLogger",
    "JsonFormatter",
    "configure_logging",
    "configure_structlog",
    "get_logger",
]
