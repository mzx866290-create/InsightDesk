from types import SimpleNamespace

import pytest

import backend.api_server as api_server
from backend.core.task_runtime import TaskRuntimeContext, build_task_runtime_context


def test_task_runtime_context_tracks_source_changes(monkeypatch):
    ctx = build_task_runtime_context(api_server)
    original_logger = ctx.logger

    sentinel_logger = SimpleNamespace(name="sentinel-task-logger")
    monkeypatch.setattr(api_server, "logger", sentinel_logger)

    assert ctx.logger is sentinel_logger
    assert ctx.logger is not original_logger


def test_task_runtime_context_forwards_allowed_writes():
    source = SimpleNamespace(_task_store=None)
    ctx = TaskRuntimeContext(source, allowed_attributes=("_task_store",))

    ctx._task_store = "store-sentinel"

    assert source._task_store == "store-sentinel"


def test_task_runtime_context_rejects_unknown_dependency():
    ctx = TaskRuntimeContext(SimpleNamespace())

    with pytest.raises(AttributeError, match="not_a_real_dependency"):
        _ = ctx.not_a_real_dependency

    with pytest.raises(AttributeError, match="not_a_real_dependency"):
        ctx.not_a_real_dependency = object()
