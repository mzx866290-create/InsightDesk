from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.helpers.task_approval_route_helpers import (
    TASK_APPROVAL_NOT_WAITING_DETAIL,
    TASK_APPROVAL_UNSUPPORTED_DETAIL,
    TASK_APPROVAL_ID_REQUIRED_DETAIL,
    apply_approval_decision_to_record,
    approval_decision_value,
    build_task_approval_batch_payload,
    ensure_task_accepts_approval_decision,
    normalize_task_approval_id,
    task_approval_batch_error_result,
    task_approval_batch_id_required_result,
    task_approval_batch_success_result,
)
from backend.stores.task_store import TaskStatus


def test_ensure_task_accepts_approval_decision_rejects_non_workflow_task():
    record = SimpleNamespace(
        task_type="generate_report",
        status=TaskStatus.WAITING_APPROVAL,
    )

    with pytest.raises(HTTPException) as exc_info:
        ensure_task_accepts_approval_decision(record)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == TASK_APPROVAL_UNSUPPORTED_DETAIL


def test_ensure_task_accepts_approval_decision_rejects_non_waiting_task():
    record = SimpleNamespace(
        task_type="multi_agent_workflow",
        status=TaskStatus.COMPLETED,
    )

    with pytest.raises(HTTPException) as exc_info:
        ensure_task_accepts_approval_decision(record)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == TASK_APPROVAL_NOT_WAITING_DETAIL


def test_ensure_task_accepts_approval_decision_accepts_waiting_status_values():
    ensure_task_accepts_approval_decision(
        SimpleNamespace(
            task_type="multi_agent_workflow",
            status=TaskStatus.WAITING_APPROVAL,
        )
    )
    ensure_task_accepts_approval_decision(
        SimpleNamespace(
            task_type="multi_agent_workflow",
            status="waiting_approval",
        )
    )


def test_apply_approval_decision_to_record_resets_record_for_resume():
    record = SimpleNamespace(
        params={"workflow_status": "waiting_approval"},
        status=TaskStatus.WAITING_APPROVAL,
        progress=5,
        error="previous failure",
        result="waiting for approval",
        updated_at=1.0,
    )
    request = SimpleNamespace(
        decision="APPROVED",
        reviewer=" owner-1 ",
        comment=" go ahead ",
    )

    apply_approval_decision_to_record(record, request, updated_at=123.0)

    assert record.status == TaskStatus.PENDING
    assert record.progress == 10
    assert record.error is None
    assert record.result == ""
    assert record.updated_at == 123.0
    assert record.params == {
        "workflow_status": "waiting_approval",
        "approval_decision": "approved",
        "approval_reviewer": "owner-1",
        "approval_comment": "go ahead",
    }


def test_task_approval_batch_helpers_build_stable_result_payloads():
    assert normalize_task_approval_id(" task-1 ") == "task-1"
    assert approval_decision_value(SimpleNamespace(decision=" Rejected ")) == "rejected"
    assert task_approval_batch_id_required_result() == {
        "task_id": "",
        "ok": False,
        "error": TASK_APPROVAL_ID_REQUIRED_DETAIL,
    }
    assert task_approval_batch_error_result("task-2", "blocked") == {
        "task_id": "task-2",
        "ok": False,
        "error": "blocked",
    }
    assert task_approval_batch_success_result("task-1", {"status": "pending"}) == {
        "task_id": "task-1",
        "ok": True,
        "task": {"status": "pending"},
    }

    payload = build_task_approval_batch_payload(
        [
            task_approval_batch_success_result("task-1", {"status": "pending"}),
            task_approval_batch_error_result("task-2", "blocked"),
        ],
        succeeded=1,
    )

    assert payload["total"] == 2
    assert payload["succeeded"] == 1
    assert payload["failed"] == 1
    assert payload["results"][0]["ok"] is True
    assert payload["results"][1]["ok"] is False
