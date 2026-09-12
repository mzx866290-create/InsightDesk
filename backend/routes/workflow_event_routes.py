"""Step-level SSE stream for multi-agent workflow tasks.

``POST /api/tasks/{task_id}/events`` replays the buffered workflow events and
then follows live ones until a terminal event arrives. POST matches the
project's fetch-based SSE convention (no Authorization header needed on
loopback, where the local-only middleware already guards access).
"""

from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.core.workflow_events import (
    is_terminal_workflow_event,
    snapshot_workflow_events,
    subscribe_workflow_events,
    unsubscribe_workflow_events,
)

router = APIRouter()

_STREAM_MAX_SECONDS = 600
_HEARTBEAT_SECONDS = 15


def _encode_event(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"


@router.post("/api/tasks/{task_id}/events")
async def stream_task_workflow_events(task_id: str):
    queue = subscribe_workflow_events(task_id)

    async def event_stream():
        try:
            for event in snapshot_workflow_events(task_id):
                yield _encode_event(event)
                if is_terminal_workflow_event(event):
                    return
            deadline = time.monotonic() + _STREAM_MAX_SECONDS
            while True:
                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=_HEARTBEAT_SECONDS
                    )
                except asyncio.TimeoutError:
                    if time.monotonic() > deadline:
                        return
                    yield ": keep-alive\n\n"
                    continue
                yield _encode_event(event)
                if is_terminal_workflow_event(event):
                    return
        finally:
            unsubscribe_workflow_events(task_id, queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
