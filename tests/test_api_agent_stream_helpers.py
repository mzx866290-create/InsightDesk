import asyncio
import json
from types import SimpleNamespace

from backend.api_agent_stream_helpers import (
    MAX_ITERATIONS_DASHBOARD_ERROR,
    dashboard_prompt_excerpt,
    fail_dashboard_task,
    finalize_dashboard_task,
    resolve_non_stream_agent_result,
    stream_agent_item,
    task_created_event,
)
from backend.api_task_store import TaskStatus


def test_dashboard_prompt_excerpt_compacts_whitespace_and_limits_length():
    excerpt = dashboard_prompt_excerpt("  alpha \n\n beta\tgamma  ", limit=10)

    assert excerpt == "alpha beta"


def test_task_created_event_serializes_panel_and_task_ids():
    payload = json.loads(
        task_created_event(
            "panel-1",
            SimpleNamespace(task_id="task-1", task_type="generate_dashboard"),
        ).removeprefix("data: ").strip()
    )

    assert payload == {
        "panel_id": "panel-1",
        "type": "task_created",
        "task_id": "task-1",
        "task_type": "generate_dashboard",
    }


def test_stream_agent_item_handles_sources_workflow_and_chunks():
    sources_event, sources_chunk = stream_agent_item(
        "panel-1",
        {"type": "sources", "sources": [{"title": "brief"}]},
    )
    workflow_event, workflow_chunk = stream_agent_item(
        "panel-1",
        {"type": "workflow_state", "node_name": "classify", "status": "running"},
    )
    chunk_event, chunk_value = stream_agent_item("panel-1", "hello")

    assert sources_chunk is None
    assert workflow_chunk is None
    assert chunk_value == "hello"
    assert json.loads(sources_event.removeprefix("data: ").strip())["type"] == "sources"
    assert json.loads(workflow_event.removeprefix("data: ").strip())["status"] == "running"
    assert json.loads(chunk_event.removeprefix("data: ").strip())["content"] == "hello"


def test_resolve_non_stream_agent_result_returns_plain_answer_when_no_fallback_needed():
    async def collect():
        return await resolve_non_stream_agent_result(
            "panel-1",
            {"output": "final answer", "sources": [{"title": "brief"}]},
            mc=object(),
            message="hello",
            is_max_iterations_output=lambda _: False,
            stringify_user_input=lambda value: str(value),
            fallback_generate=_unused_fallback,
        )

    outcome = asyncio.run(collect())

    assert outcome.answer == "final answer"
    assert outcome.sources == [{"title": "brief"}]
    assert outcome.events == []
    assert outcome.should_stop is False


def test_resolve_non_stream_agent_result_uses_fallback_with_intermediate_steps():
    calls = []

    async def fallback_generate(mc, user_input, tool_outputs):
        calls.append((mc, user_input, tool_outputs))
        return "fallback answer"

    async def collect():
        return await resolve_non_stream_agent_result(
            "panel-1",
            {
                "output": "Agent stopped due to max iterations.",
                "sources": [{"title": "brief"}],
                "intermediate_steps": [("tool", "alpha"), ("tool", "beta")],
            },
            mc="model-config",
            message=[{"type": "text", "text": "hello"}],
            is_max_iterations_output=lambda _: True,
            stringify_user_input=lambda value: f"stringified:{value[0]['text']}",
            fallback_generate=fallback_generate,
        )

    outcome = asyncio.run(collect())

    assert outcome.answer == "fallback answer"
    assert outcome.should_stop is False
    assert outcome.events == []
    assert calls == [("model-config", "stringified:hello", "alpha\n\nbeta")]


def test_resolve_non_stream_agent_result_returns_terminal_error_without_intermediate_steps():
    async def collect():
        return await resolve_non_stream_agent_result(
            "panel-1",
            {"output": "Agent stopped due to max iterations.", "sources": []},
            mc=object(),
            message="hello",
            is_max_iterations_output=lambda _: True,
            stringify_user_input=lambda value: str(value),
            fallback_generate=_unused_fallback,
        )

    outcome = asyncio.run(collect())
    payloads = [json.loads(event.removeprefix("data: ").strip()) for event in outcome.events]

    assert outcome.answer == ""
    assert outcome.should_stop is True
    assert outcome.dashboard_error == MAX_ITERATIONS_DASHBOARD_ERROR
    assert payloads[0]["type"] == "error"
    assert payloads[0]["error_code"] == "MAX_ITERATIONS"
    assert payloads[1]["type"] == "done"


def test_finalize_dashboard_task_marks_completion_when_card_is_present():
    calls = []

    async def set_inline_task_state(record, **kwargs):
        calls.append((record, kwargs))
        return {"record": record, "kwargs": kwargs}

    async def collect():
        return await finalize_dashboard_task(
            "task-record",
            "intro\n:::dashboard-card\n{}\n:::",
            contains_dashboard_card=lambda content: "dashboard-card" in content,
            summarize_dashboard_task_result=lambda _: "知识看板已生成。",
            summarize_dashboard_task_error=lambda _: "failed",
            set_inline_task_state=set_inline_task_state,
        )

    result = asyncio.run(collect())

    assert calls[0][1]["status"] == TaskStatus.COMPLETED
    assert calls[0][1]["result"] == "知识看板已生成。"
    assert result["kwargs"]["progress"] == 100


def test_finalize_dashboard_task_marks_failure_when_card_is_missing():
    calls = []

    async def set_inline_task_state(record, **kwargs):
        calls.append((record, kwargs))
        return kwargs

    outcome = asyncio.run(
        finalize_dashboard_task(
            "task-record",
            "plain answer",
            contains_dashboard_card=lambda content: False,
            summarize_dashboard_task_result=lambda _: "unused",
            summarize_dashboard_task_error=lambda content: f"failed:{content}",
            set_inline_task_state=set_inline_task_state,
        )
    )

    assert calls[0][1]["status"] == TaskStatus.FAILED
    assert calls[0][1]["error"] == "failed:plain answer"
    assert outcome["result"] is None


def test_fail_dashboard_task_sets_failed_status():
    calls = []

    async def set_inline_task_state(record, **kwargs):
        calls.append((record, kwargs))
        return kwargs

    outcome = asyncio.run(
        fail_dashboard_task(
            "task-record",
            error="boom",
            set_inline_task_state=set_inline_task_state,
        )
    )

    assert calls[0][1]["status"] == TaskStatus.FAILED
    assert calls[0][1]["error"] == "boom"
    assert outcome["progress"] == 100


async def _unused_fallback(mc, user_input, tool_outputs):
    raise AssertionError(f"fallback should not run: {mc}, {user_input}, {tool_outputs}")
