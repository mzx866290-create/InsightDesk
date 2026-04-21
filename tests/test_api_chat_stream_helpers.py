import asyncio
import json

from backend.api_chat_stream_helpers import (
    all_done_event,
    answer_chunks,
    build_agent_config_payload,
    done_event,
    encode_sse,
    heartbeat_event,
    panel_event,
    stream_parallel_sse,
    stream_single_sse,
)


def test_encode_helpers_build_expected_sse_payloads():
    assert encode_sse({"type": "hello"}) == 'data: {"type": "hello"}\n\n'
    assert panel_event("panel-1", "chunk", content="hi") == (
        'data: {"panel_id": "panel-1", "type": "chunk", "content": "hi"}\n\n'
    )
    assert done_event("panel-1") == 'data: {"panel_id": "panel-1", "type": "done"}\n\n'
    assert all_done_event() == 'data: {"type": "all_done"}\n\n'
    assert heartbeat_event() == 'data: {"type": "heartbeat"}\n\n'


def test_build_agent_config_payload_includes_optional_task_metadata():
    payload = build_agent_config_payload(
        session_id="session-1",
        persist_history=True,
        persist_user_history=False,
        persist_ai_history=True,
        replace_ai_history=False,
        exclude_ai_answer_group_id="grp-old",
        panel_id="panel-1",
        model_id="qwen-main",
        answer_group_id="grp-new",
        raw_user_message="hello",
        raw_images=[{"name": "chart.png"}],
        raw_files=[{"name": "brief.txt"}],
        task_id="task-1",
        task_type="generate_dashboard",
    )

    assert payload == {
        "configurable": {
            "session_id": "session-1",
            "persist_history": True,
            "persist_user_history": False,
            "persist_ai_history": True,
            "replace_ai_history": False,
            "exclude_ai_answer_group_id": "grp-old",
            "panel_id": "panel-1",
            "model_id": "qwen-main",
            "answer_group_id": "grp-new",
            "raw_user_message": "hello",
            "raw_images": [{"name": "chart.png"}],
            "raw_files": [{"name": "brief.txt"}],
            "task_id": "task-1",
            "task_type": "generate_dashboard",
        }
    }


def test_answer_chunks_splits_text_on_requested_boundary():
    assert answer_chunks("abcdefghij", chunk_size=4) == ["abcd", "efgh", "ij"]
    assert answer_chunks("hello", chunk_size=0) == ["hello"]


def test_stream_single_sse_appends_all_done_when_connected():
    async def source():
        yield panel_event("panel-1", "chunk", content="a")
        yield panel_event("panel-1", "done")

    async def collect():
        items = []
        async for item in stream_single_sse(source(), is_disconnected=lambda: _false()):
            items.append(item)
        return items

    items = asyncio.run(collect())

    assert items[-1] == all_done_event()
    assert json.loads(items[0].removeprefix("data: ").strip())["content"] == "a"


def test_stream_single_sse_stops_without_all_done_after_disconnect():
    state = {"calls": 0}

    async def source():
        yield panel_event("panel-1", "chunk", content="a")
        yield panel_event("panel-1", "chunk", content="b")

    async def is_disconnected():
        state["calls"] += 1
        return state["calls"] >= 2

    async def collect():
        items = []
        async for item in stream_single_sse(source(), is_disconnected=is_disconnected):
            items.append(item)
        return items

    items = asyncio.run(collect())

    assert len(items) == 1
    assert json.loads(items[0].removeprefix("data: ").strip())["content"] == "a"


def test_stream_single_sse_emits_heartbeat_while_waiting():
    async def source():
        await asyncio.sleep(0.03)
        yield panel_event("panel-1", "chunk", content="late")
        yield panel_event("panel-1", "done")

    async def collect():
        items = []
        async for item in stream_single_sse(
            source(),
            is_disconnected=lambda: _false(),
            heartbeat_interval_seconds=0.01,
        ):
            items.append(item)
        return items

    items = asyncio.run(collect())
    payloads = [json.loads(item.removeprefix("data: ").strip()) for item in items]

    assert any(payload["type"] == "heartbeat" for payload in payloads)
    assert payloads[-1] == {"type": "all_done"}


def test_stream_parallel_sse_merges_sources_and_appends_all_done():
    async def source(prefix: str):
        yield panel_event(prefix, "chunk", content=f"{prefix}-1")
        await asyncio.sleep(0)
        yield panel_event(prefix, "done")

    async def collect():
        items = []
        async for item in stream_parallel_sse(
            [source("panel-a"), source("panel-b")],
            is_disconnected=lambda: _false(),
        ):
            items.append(item)
        return items

    items = asyncio.run(collect())
    payloads = [json.loads(item.removeprefix("data: ").strip()) for item in items]

    assert payloads[-1] == {"type": "all_done"}
    assert {payload["panel_id"] for payload in payloads[:-1]} == {"panel-a", "panel-b"}


def test_stream_parallel_sse_omits_all_done_when_disconnected():
    state = {"calls": 0}

    async def source(prefix: str):
        yield panel_event(prefix, "chunk", content=f"{prefix}-1")
        await asyncio.sleep(0)
        yield panel_event(prefix, "done")

    async def is_disconnected():
        state["calls"] += 1
        return state["calls"] >= 2

    async def collect():
        items = []
        async for item in stream_parallel_sse(
            [source("panel-a"), source("panel-b")],
            is_disconnected=is_disconnected,
        ):
            items.append(item)
        return items

    items = asyncio.run(collect())

    assert all(json.loads(item.removeprefix("data: ").strip())["type"] != "all_done" for item in items)


async def _false():
    return False
