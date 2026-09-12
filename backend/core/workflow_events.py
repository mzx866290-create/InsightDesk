"""Process-local step-event bus for multi-agent workflow tasks.

Events are buffered per task id (bounded ring) and fanned out to live SSE
subscribers. This serves the memory task backend (the default for local and
desktop deployments) where the workflow runs inside the API server process.
arq-dispatched workflows run in a separate process and keep the existing
task-polling channel; bridging them would require Redis pub/sub.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

_BUFFER_LIMIT = 500
_TERMINAL_EVENT_TYPES = {"workflow_completed", "workflow_failed"}

_buffers: dict[str, list[dict[str, Any]]] = defaultdict(list)
_subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)


def publish_workflow_event(task_id: str, event: dict[str, Any]) -> None:
    """Append an event to the task buffer and fan it out to subscribers."""
    task_key = str(task_id or "").strip()
    if not task_key or not isinstance(event, dict):
        return
    payload = dict(event)
    payload.setdefault("task_id", task_key)
    buffer = _buffers[task_key]
    buffer.append(payload)
    del _buffers[task_key][: max(0, len(buffer) - _BUFFER_LIMIT)]

    for queue in list(_subscribers.get(task_key, [])):
        try:
            queue.put_nowait(payload)
        except RuntimeError:
            continue


def snapshot_workflow_events(task_id: str) -> list[dict[str, Any]]:
    """Replay buffer for subscribers that attach after a workflow started."""
    return [dict(event) for event in _buffers.get(str(task_id or "").strip(), [])]


def subscribe_workflow_events(task_id: str) -> asyncio.Queue:
    task_key = str(task_id or "").strip()
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers[task_key].append(queue)
    return queue


def unsubscribe_workflow_events(task_id: str, queue: asyncio.Queue) -> None:
    task_key = str(task_id or "").strip()
    try:
        _subscribers[task_key].remove(queue)
    except (KeyError, ValueError):
        pass
    if not _subscribers.get(task_key):
        _subscribers.pop(task_key, None)


def is_terminal_workflow_event(event: dict[str, Any]) -> bool:
    return str(event.get("type") or "") in _TERMINAL_EVENT_TYPES


def reset_workflow_events() -> None:
    """Test helper: drop all buffers and subscribers."""
    _buffers.clear()
    _subscribers.clear()
