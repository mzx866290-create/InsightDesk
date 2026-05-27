"""Route-level helpers for task listing."""

from typing import Any, Callable

from fastapi import HTTPException, Request


def filter_visible_task_records(
    records: list[Any],
    request: Request,
    *,
    require_session_access: Callable[[Request, str, str], dict[str, Any]],
    require_remote_viewer: Callable[[Request], dict[str, Any]],
) -> list[Any]:
    visible_records: list[Any] = []
    for record in records:
        session_id = str(getattr(record, "session_id", "") or "").strip()
        if session_id:
            try:
                require_session_access(request, session_id, "viewer")
            except HTTPException as exc:
                if exc.status_code == 403:
                    continue
                raise
        else:
            require_remote_viewer(request)
        visible_records.append(record)
    return visible_records
