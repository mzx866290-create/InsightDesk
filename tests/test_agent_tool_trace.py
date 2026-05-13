import asyncio
from types import SimpleNamespace

from langchain_core.tools import StructuredTool

from backend.agent import langgraph as agent_langgraph
from backend.agent import runtime_tools as agent_runtime_tools
from backend.core.tracing import get_recent_trace_events, reset_trace_events


class _FakePipeline:
    vectorstore = None
    vector_store_path = "unused"


def _fake_tool() -> StructuredTool:
    async def _run(question: str) -> str:
        return f"answer:{question}"

    return StructuredTool.from_function(
        coroutine=_run,
        name="fake_tool",
        description="fake tool for tracing tests",
    )


async def _empty_mcp_tools(**kwargs) -> dict:
    return {}


def test_build_runtime_tools_wraps_tool_execution_with_trace(monkeypatch) -> None:
    reset_trace_events()

    fake_tool = _fake_tool()
    monkeypatch.setattr(agent_runtime_tools, "create_tools", lambda *args, **kwargs: [fake_tool])
    monkeypatch.setattr(
        agent_runtime_tools,
        "list_enabled_builtin_tool_specs",
        lambda **kwargs: [SimpleNamespace(name="fake_tool")],
    )

    async def _run() -> str:
        tools = await agent_runtime_tools.build_runtime_tools(
            _FakePipeline(),
            mcp_tool_loader=_empty_mcp_tools,
            trace_tool_execution=True,
        )
        return await tools[0].ainvoke({"question": "hello"})

    result = asyncio.run(_run())
    events = (
        event
        for event in get_recent_trace_events()
        if event["name"] == "tool.execute"
    )
    events = list(events)

    assert result == "answer:hello"
    assert [event["event"] for event in events] == ["start", "end"]
    assert events[-1]["attributes"]["tool.name"] == "fake_tool"
    assert events[-1]["attributes"]["tool.status"] == "success"
    assert events[-1]["attributes"]["tool.result_size"] == len("answer:hello")
    assert events[-1]["attributes"]["tool.duration_ms"] >= 0


def test_build_runtime_tools_can_skip_trace_wrapping(monkeypatch) -> None:
    reset_trace_events()

    fake_tool = _fake_tool()
    monkeypatch.setattr(agent_runtime_tools, "create_tools", lambda *args, **kwargs: [fake_tool])
    monkeypatch.setattr(
        agent_runtime_tools,
        "list_enabled_builtin_tool_specs",
        lambda **kwargs: [SimpleNamespace(name="fake_tool")],
    )

    async def _run() -> str:
        tools = await agent_runtime_tools.build_runtime_tools(
            _FakePipeline(),
            mcp_tool_loader=_empty_mcp_tools,
            trace_tool_execution=False,
        )
        return await tools[0].ainvoke({"question": "hello"})

    result = asyncio.run(_run())
    events = (
        event
        for event in get_recent_trace_events()
        if event["name"] == "tool.execute"
    )
    events = list(events)

    assert result == "answer:hello"
    assert events == []


def test_langgraph_build_runtime_tools_disables_duplicate_tool_traces(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def _fake_build_runtime_tools(*args, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(agent_langgraph, "build_runtime_tools", _fake_build_runtime_tools)

    asyncio.run(
        agent_langgraph.build_langgraph_agent(
            llm=SimpleNamespace(),
            pipeline=_FakePipeline(),
            verbose=False,
        )
    )

    assert captured["trace_tool_execution"] is False
