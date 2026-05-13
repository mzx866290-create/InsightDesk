from types import SimpleNamespace

import backend.api_server as api_server
from backend.core.router_registration import (
    RouterContext,
    build_core_router_context,
    build_deferred_router_context,
    build_router_context,
)


def test_router_context_tracks_source_changes(monkeypatch):
    ctx = build_router_context(api_server)
    original_logger = ctx.logger

    sentinel_logger = SimpleNamespace(name="sentinel-router-logger")
    monkeypatch.setattr(api_server, "logger", sentinel_logger)

    assert ctx.logger is sentinel_logger
    assert ctx.logger is not original_logger


def test_router_context_rejects_unknown_dependency():
    ctx = RouterContext(SimpleNamespace())

    try:
        _ = ctx.not_a_real_dependency
    except AttributeError as exc:
        assert "not_a_real_dependency" in str(exc)
    else:
        raise AssertionError("expected AttributeError")


def test_api_server_context_source_tracks_allowed_globals(monkeypatch):
    source = api_server._api_server_context_source(("logger",))
    original_logger = source.logger

    sentinel_logger = SimpleNamespace(name="sentinel-api-server-source")
    monkeypatch.setattr(api_server, "logger", sentinel_logger)

    assert source.logger is sentinel_logger
    assert source.logger is not original_logger

    try:
        _ = source.not_a_real_dependency
    except AttributeError as exc:
        assert "not_a_real_dependency" in str(exc)
    else:
        raise AssertionError("source should reject unknown dependencies")


def test_core_and_deferred_contexts_have_separate_dependency_surfaces():
    core_ctx = build_core_router_context(api_server)
    deferred_ctx = build_deferred_router_context(api_server)

    assert core_ctx.SecurityStatusResponse is api_server.SecurityStatusResponse
    assert deferred_ctx.ChatRequest is api_server.ChatRequest

    try:
        _ = core_ctx._list_assistant_presets
    except AttributeError as exc:
        assert "_list_assistant_presets" in str(exc)
    else:
        raise AssertionError("core context should not expose prompt CRUD wrappers")

    try:
        _ = core_ctx._build_doc_pipeline
    except AttributeError as exc:
        assert "_build_doc_pipeline" in str(exc)
    else:
        raise AssertionError("core context should not expose document factories")

    try:
        _ = core_ctx.ChatRequest
    except AttributeError as exc:
        assert "ChatRequest" in str(exc)
    else:
        raise AssertionError("core context should not expose deferred dependencies")

    try:
        _ = deferred_ctx.SecurityStatusResponse
    except AttributeError as exc:
        assert "SecurityStatusResponse" in str(exc)
    else:
        raise AssertionError("deferred context should not expose core dependencies")
