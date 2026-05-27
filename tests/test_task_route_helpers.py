from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.helpers.task_route_helpers import filter_visible_task_records


def test_filter_visible_task_records_skips_forbidden_session_tasks():
    records = [
        SimpleNamespace(task_id="visible", session_id="session-visible"),
        SimpleNamespace(task_id="hidden", session_id="session-hidden"),
        SimpleNamespace(task_id="global", session_id=""),
    ]

    def require_session_access(_request, session_id, role):
        assert role == "viewer"
        if session_id == "session-hidden":
            raise HTTPException(status_code=403, detail="hidden")
        return {"session_id": session_id}

    visible = filter_visible_task_records(
        records,
        SimpleNamespace(),
        require_session_access=require_session_access,
        require_remote_viewer=lambda request: {"role": "viewer"},
    )

    assert [record.task_id for record in visible] == ["visible", "global"]


def test_filter_visible_task_records_reraises_non_forbidden_session_errors():
    with pytest.raises(HTTPException) as exc_info:
        filter_visible_task_records(
            [SimpleNamespace(task_id="missing", session_id="session-missing")],
            SimpleNamespace(),
            require_session_access=lambda *args: (_ for _ in ()).throw(
                HTTPException(status_code=404, detail="missing")
            ),
            require_remote_viewer=lambda request: {"role": "viewer"},
        )

    assert exc_info.value.status_code == 404
