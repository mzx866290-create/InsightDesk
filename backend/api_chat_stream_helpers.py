import asyncio
import json
import logging
from collections.abc import AsyncGenerator, AsyncIterable, Awaitable, Callable
from typing import Any


def encode_sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def panel_event(panel_id: str, event_type: str, **payload: Any) -> str:
    return encode_sse({"panel_id": panel_id, "type": event_type, **payload})


def all_done_event() -> str:
    return encode_sse({"type": "all_done"})


def heartbeat_event() -> str:
    return encode_sse({"type": "heartbeat"})


def done_event(panel_id: str) -> str:
    return panel_event(panel_id, "done")


def build_agent_config_payload(
    *,
    session_id: str,
    persist_history: bool,
    persist_user_history: bool,
    persist_ai_history: bool,
    replace_ai_history: bool,
    exclude_ai_answer_group_id: str,
    panel_id: str,
    model_id: str,
    answer_group_id: str,
    raw_user_message: str,
    raw_images: list[dict[str, Any]],
    raw_files: list[dict[str, Any]],
    task_id: str = "",
    task_type: str = "",
) -> dict[str, dict[str, Any]]:
    configurable: dict[str, Any] = {
        "session_id": session_id,
        "persist_history": persist_history,
        "persist_user_history": persist_user_history,
        "persist_ai_history": persist_ai_history,
        "replace_ai_history": replace_ai_history,
        "exclude_ai_answer_group_id": exclude_ai_answer_group_id,
        "panel_id": panel_id,
        "model_id": model_id,
        "answer_group_id": answer_group_id,
        "raw_user_message": raw_user_message,
        "raw_images": raw_images,
        "raw_files": raw_files,
    }
    if task_id:
        configurable["task_id"] = task_id
    if task_type:
        configurable["task_type"] = task_type
    return {"configurable": configurable}


def answer_chunks(answer: str, chunk_size: int = 20) -> list[str]:
    if chunk_size <= 0:
        return [answer]
    return [answer[index : index + chunk_size] for index in range(0, len(answer), chunk_size)]


async def stream_single_sse(
    source: AsyncIterable[str],
    *,
    is_disconnected: Callable[[], Awaitable[bool]],
    heartbeat_interval_seconds: float = 5.0,
) -> AsyncGenerator[str, None]:
    queue: asyncio.Queue[Any] = asyncio.Queue()
    producer_done = object()
    disconnected = False
    poll_timeout = min(0.5, max(0.01, heartbeat_interval_seconds))
    last_emit_at = asyncio.get_running_loop().time()

    async def feed() -> None:
        try:
            async for item in source:
                await queue.put(item)
        finally:
            await queue.put(producer_done)

    task = asyncio.create_task(feed())

    try:
        while True:
            if await is_disconnected():
                disconnected = True
                break
            try:
                item = await asyncio.wait_for(queue.get(), timeout=poll_timeout)
            except asyncio.TimeoutError:
                now = asyncio.get_running_loop().time()
                if now - last_emit_at >= heartbeat_interval_seconds:
                    yield heartbeat_event()
                    last_emit_at = now
                continue
            if item is producer_done:
                break
            yield item
            last_emit_at = asyncio.get_running_loop().time()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    if not disconnected:
        yield all_done_event()


async def stream_parallel_sse(
    sources: list[AsyncIterable[str]],
    *,
    is_disconnected: Callable[[], Awaitable[bool]],
    logger: logging.Logger | None = None,
    heartbeat_interval_seconds: float = 5.0,
) -> AsyncGenerator[str, None]:
    queue: asyncio.Queue[Any] = asyncio.Queue()
    producer_done = object()
    all_producers_done = asyncio.Event()
    pending_producers = len(sources)
    disconnected = False
    active_logger = logger or logging.getLogger(__name__)
    poll_timeout = min(0.5, max(0.01, heartbeat_interval_seconds))
    last_emit_at = asyncio.get_running_loop().time()

    async def feed(source: AsyncIterable[str]) -> None:
        try:
            async for item in source:
                await queue.put(item)
        except asyncio.CancelledError:
            raise
        except Exception:
            active_logger.exception("Parallel SSE producer failed")
        finally:
            await queue.put(producer_done)

    tasks = [asyncio.create_task(feed(source)) for source in sources]

    try:
        while True:
            if all_producers_done.is_set() and queue.empty():
                break
            if await is_disconnected():
                disconnected = True
                break
            try:
                item = await asyncio.wait_for(queue.get(), timeout=poll_timeout)
            except asyncio.TimeoutError:
                now = asyncio.get_running_loop().time()
                if now - last_emit_at >= heartbeat_interval_seconds:
                    yield heartbeat_event()
                    last_emit_at = now
                continue
            if item is producer_done:
                pending_producers -= 1
                if pending_producers <= 0:
                    all_producers_done.set()
                continue
            yield item
            last_emit_at = asyncio.get_running_loop().time()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    if not disconnected:
        yield all_done_event()
