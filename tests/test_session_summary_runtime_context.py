from types import SimpleNamespace

import pytest

import backend.api_server as api_server
from backend.core.session_summary_runtime import (
    SessionSummaryRuntimeContext,
    build_session_summary_runtime_context,
)


def test_session_summary_runtime_context_tracks_source_changes(monkeypatch):
    ctx = build_session_summary_runtime_context(api_server)
    original_logger = ctx.logger

    sentinel_logger = SimpleNamespace(name="sentinel-summary-logger")
    monkeypatch.setattr(api_server, "logger", sentinel_logger)

    assert ctx.logger is sentinel_logger
    assert ctx.logger is not original_logger


def test_session_summary_runtime_context_rejects_unknown_dependency():
    ctx = SessionSummaryRuntimeContext(SimpleNamespace())

    with pytest.raises(AttributeError, match="not_a_real_dependency"):
        _ = ctx.not_a_real_dependency
