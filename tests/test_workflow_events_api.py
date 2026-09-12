"""Step-level workflow event bus + SSE endpoint tests."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core import workflow_events
from backend.routes.workflow_event_routes import router


def setup_function():
    workflow_events.reset_workflow_events()


def test_publish_buffers_and_marks_terminal():
    workflow_events.publish_workflow_event("t1", {"type": "workflow_started"})
    workflow_events.publish_workflow_event("t1", {"type": "step_started", "agent": "research"})
    workflow_events.publish_workflow_event("t1", {"type": "workflow_completed"})

    snapshot = workflow_events.snapshot_workflow_events("t1")
    assert [event["type"] for event in snapshot] == [
        "workflow_started",
        "step_started",
        "workflow_completed",
    ]
    assert all(event["task_id"] == "t1" for event in snapshot)
    assert workflow_events.is_terminal_workflow_event(snapshot[-1])
    assert not workflow_events.is_terminal_workflow_event(snapshot[0])


def test_subscribe_receives_live_events_and_unsubscribe_cleans_up():
    queue = workflow_events.subscribe_workflow_events("t2")
    workflow_events.publish_workflow_event("t2", {"type": "step_completed"})

    event = queue.get_nowait()
    assert event["type"] == "step_completed"

    workflow_events.unsubscribe_workflow_events("t2", queue)
    assert workflow_events._subscribers.get("t2") in (None, [])


def test_events_endpoint_replays_snapshot_and_closes_on_terminal():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    workflow_events.publish_workflow_event("wf-1", {"type": "workflow_started"})
    workflow_events.publish_workflow_event("wf-1", {"type": "step_started", "agent": "research"})
    workflow_events.publish_workflow_event("wf-1", {"type": "workflow_completed"})

    with client.stream("POST", "/api/tasks/wf-1/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(chunk for chunk in response.iter_text())

    assert '"workflow_started"' in body
    assert '"step_started"' in body
    assert '"workflow_completed"' in body
    # the stream closed on the terminal event instead of hanging
    assert body.endswith("\n\n")


def test_bus_isolates_tasks():
    workflow_events.publish_workflow_event("a", {"type": "workflow_started"})
    workflow_events.publish_workflow_event("b", {"type": "step_started"})

    assert [event["type"] for event in workflow_events.snapshot_workflow_events("a")] == [
        "workflow_started"
    ]
    assert [event["type"] for event in workflow_events.snapshot_workflow_events("b")] == [
        "step_started"
    ]


def test_async_subscriber_delivery():
    async def scenario():
        queue = workflow_events.subscribe_workflow_events("t3")
        loop = asyncio.get_running_loop()
        loop.call_soon(
            workflow_events.publish_workflow_event, "t3", {"type": "step_started"}
        )
        event = await asyncio.wait_for(queue.get(), timeout=2)
        return event

    event = asyncio.run(scenario())
    assert event == {"type": "step_started", "task_id": "t3"}
