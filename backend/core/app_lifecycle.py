"""FastAPI/Starlette lifecycle registration helpers."""

from __future__ import annotations

from typing import Any


def register_app_lifecycle_handler(app: Any, event: str, handler: Any) -> None:
    """Register lifecycle hooks across FastAPI/Starlette versions."""
    add_event_handler = getattr(app, "add_event_handler", None)
    if callable(add_event_handler):
        add_event_handler(event, handler)
        return

    router = getattr(app, "router", None)
    hook_list = getattr(router, f"on_{event}", None)
    if isinstance(hook_list, list):
        hook_list.append(handler)
        return

    on_event = getattr(app, "on_event", None)
    if callable(on_event):
        on_event(event)(handler)
        return

    raise RuntimeError(f"FastAPI app does not support {event!r} lifecycle hooks")
