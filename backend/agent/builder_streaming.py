"""Invocation and streaming helpers shared by agent builder wrappers."""

import asyncio
from typing import Any

from backend.agent.builder_context import (
    _attach_configured_task_meta,
    _build_invocation_config,
    _build_workflow_snapshot,
    _configurable_value,
)
from backend.agent.builder_history import (
    _persist_agent_result_history,
    _persist_output_history,
)
from backend.agent.prompts import _finalize_agent_result


async def _ainvoke_agent_wrapper(
    wrapper: Any,
    inputs: dict,
    config: dict | None = None,
    *,
    supports_workflow_event_sink: bool = False,
) -> dict[str, Any]:
    invocation = _build_invocation_config(config)
    user_input = inputs.get("input", "")
    run_kwargs: dict[str, Any] = {
        "panel_id": invocation.panel_id,
        "exclude_ai_answer_group_id": invocation.exclude_ai_answer_group_id,
    }
    if supports_workflow_event_sink:
        run_kwargs["workflow_event_sink"] = _configurable_value(
            config,
            "workflow_event_sink",
            None,
        )

    result = await wrapper._run_once(invocation.session_id, user_input, **run_kwargs)
    result = _attach_configured_task_meta(result, config)
    result = _finalize_agent_result(
        result,
        user_input=user_input,
        raw_files=invocation.raw_files,
        raw_images=invocation.raw_images,
        answer_group_id=invocation.answer_group_id,
    )
    _persist_agent_result_history(invocation, user_input, result)
    return result


async def _astream_langgraph_wrapper(
    wrapper: Any,
    user_input: Any,
    config: dict | None = None,
):
    invocation = _build_invocation_config(config)
    event_queue: asyncio.Queue[Any] = asyncio.Queue()
    workflow_events: list[dict[str, Any]] = []
    native_stream_items: list[str] = []
    event_loop = asyncio.get_running_loop()
    streamed_sources = False

    def workflow_event_sink(payload: dict[str, Any]) -> None:
        event_loop.call_soon_threadsafe(event_queue.put_nowait, payload)

    def stream_item_sink(payload: Any) -> None:
        event_loop.call_soon_threadsafe(event_queue.put_nowait, payload)

    run_task = asyncio.create_task(
        wrapper._run_once(
            invocation.session_id,
            user_input,
            panel_id=invocation.panel_id,
            exclude_ai_answer_group_id=invocation.exclude_ai_answer_group_id,
            workflow_event_sink=workflow_event_sink,
            stream_item_sink=stream_item_sink,
        )
    )

    try:
        while True:
            if run_task.done():
                break
            try:
                queued_item = await asyncio.wait_for(event_queue.get(), timeout=0.05)
            except asyncio.TimeoutError:
                continue
            if isinstance(queued_item, dict) and queued_item.get("type") == "workflow_state":
                workflow_events.append(queued_item)
                yield queued_item
                continue
            if isinstance(queued_item, str) and queued_item:
                native_stream_items.append(queued_item)
                continue
            yield queued_item

        while not event_queue.empty():
            queued_item = event_queue.get_nowait()
            if isinstance(queued_item, dict) and queued_item.get("type") == "workflow_state":
                workflow_events.append(queued_item)
                yield queued_item
                continue
            if isinstance(queued_item, str) and queued_item:
                native_stream_items.append(queued_item)
                continue
            yield queued_item

        result = await run_task
    except Exception:
        if not run_task.done():
            run_task.cancel()
            await asyncio.gather(run_task, return_exceptions=True)
        raise

    result = _attach_configured_task_meta(result, config)
    result = _finalize_agent_result(
        result,
        user_input=user_input,
        raw_files=invocation.raw_files,
        raw_images=invocation.raw_images,
        answer_group_id=invocation.answer_group_id,
    )
    output = result.get("output", "")
    sources = result.get("sources", [])
    workflow_nodes = _build_workflow_snapshot(workflow_events)
    result["workflow_nodes"] = workflow_nodes

    if sources and not streamed_sources:
        yield {"type": "sources", "sources": sources}

    native_stream_chunks = native_stream_items or [
        str(item)
        for item in list(result.get("_native_stream_chunks") or [])
        if str(item or "").strip()
    ]
    if native_stream_chunks:
        has_classifier_events = any(
            str(event.get("node_name") or "") == "classify_intent"
            for event in workflow_events
        )
        if has_classifier_events:
            for chunk in native_stream_chunks:
                yield chunk
                await asyncio.sleep(0)
        else:
            yield "".join(native_stream_chunks)
    else:
        chunk_size = 20
        for i in range(0, len(output), chunk_size):
            yield output[i : i + chunk_size]
            await asyncio.sleep(0.01)

    _persist_output_history(
        invocation,
        user_input,
        output,
        sources=sources,
        workflow_nodes=workflow_nodes,
        task_id=str(result.get("task_id", "") or ""),
        task_type=str(result.get("task_type", "") or ""),
    )
