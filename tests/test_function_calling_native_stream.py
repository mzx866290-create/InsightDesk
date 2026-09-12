"""Native token streaming for the function-calling agent wrapper."""

from __future__ import annotations

import asyncio
import types

from backend.agent.builder_wrappers import FunctionCallingAgentWrapper


class FakeChunk:
    def __init__(self, content, tool_call_chunks=None):
        self.content = content
        self.tool_call_chunks = tool_call_chunks or []


class FakeExecutor:
    def __init__(self, events):
        self._events = events
        self.payloads = []

    async def astream_events(self, payload):
        self.payloads.append(payload)
        for event in self._events:
            yield event


def _make_agent(events):
    return FunctionCallingAgentWrapper(
        FakeExecutor(events),
        llm=types.SimpleNamespace(ainvoke=lambda payload: None),
        pipeline=object(),
        system_prompt="",
        dashboard_template=None,
        knowledge_base_enabled=False,
        web_search_enabled=True,
    )


def _collect(agent, user_input="what does plan mean?"):
    async def consume():
        items = []
        async for item in agent.astream_answer(
            user_input,
            config={"configurable": {"session_id": "fc-native-stream", "persist_history": False}},
        ):
            items.append(item)
        return items

    return asyncio.run(consume())


def test_native_stream_preserves_token_boundaries():
    events = [
        {"event": "on_chat_model_stream", "data": {"chunk": FakeChunk("Understood")}},
        {"event": "on_chat_model_stream", "data": {"chunk": FakeChunk(" completely.")}},
        {
            "event": "on_chain_end",
            "name": "AgentExecutor",
            "data": {
                "output": {
                    "output": "Understood completely.",
                    "sources": [],
                    "intermediate_steps": [],
                }
            },
        },
    ]
    items = _collect(_make_agent(events))

    text_chunks = [item for item in items if isinstance(item, str)]
    # token boundaries are preserved (the old fake path would re-chunk at 20 chars)
    assert text_chunks == ["Understood", " completely."]

    usage_frame = items[-1]
    assert usage_frame["type"] == "token_usage"


def test_native_stream_skips_tool_call_chunks_and_keeps_tool_sources():
    marker_sources = [
        {"type": "web", "title": "Example", "snippet": "https://example.com/page"}
    ]
    tool_output = "__SOURCES__:" + __import__("json").dumps(marker_sources)
    events = [
        {
            "event": "on_chat_model_stream",
            "data": {"chunk": FakeChunk("", tool_call_chunks=[{"name": "web_search"}])},
        },
        {"event": "on_tool_end", "data": {"output": tool_output}},
        {"event": "on_chat_model_stream", "data": {"chunk": FakeChunk("Answer")}},
        {"event": "on_chat_model_stream", "data": {"chunk": FakeChunk(" with sources.")}},
        {
            "event": "on_chain_end",
            "name": "AgentExecutor",
            "data": {
                "output": {
                    "output": "Answer with sources.",
                    "sources": [],
                    "intermediate_steps": [],
                }
            },
        },
    ]
    items = _collect(_make_agent(events))

    text_chunks = [item for item in items if isinstance(item, str)]
    assert text_chunks == ["Answer", " with sources."]

    source_frames = [item for item in items if isinstance(item, dict) and item.get("type") == "sources"]
    assert source_frames, "expected a sources frame from tool observations"
    assert source_frames[0]["sources"] == marker_sources


def test_native_stream_falls_back_to_paced_chunks_without_token_events():
    events = [
        {
            "event": "on_chain_end",
            "name": "AgentExecutor",
            "data": {
                "output": {
                    "output": "Final answer text without streamed token events.",
                    "sources": [],
                    "intermediate_steps": [],
                }
            },
        },
    ]
    items = _collect(_make_agent(events))

    text_chunks = [item for item in items if isinstance(item, str)]
    assert "".join(text_chunks) == "Final answer text without streamed token events."
