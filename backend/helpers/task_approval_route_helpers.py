"""Route-level helpers for task approval decisions."""

from typing import Any

from fastapi import HTTPException


TASK_NOT_FOUND_DETAIL = "Task was not found."
TASK_APPROVAL_UNSUPPORTED_DETAIL = "Task does not support approval decisions."
TASK_APPROVAL_NOT_WAITING_DETAIL = "Task is not waiting for approval."
TASK_APPROVAL_ID_REQUIRED_DETAIL = "Task id is required."


def approval_decision_value(request: Any) -> str:
    return str(getattr(request, "decision", "") or "").strip().lower()


def ensure_task_accepts_approval_decision(record: Any) -> None:
    if record.task_type != "multi_agent_workflow":
        raise HTTPException(status_code=400, detail=TASK_APPROVAL_UNSUPPORTED_DETAIL)
    if _task_status_value(record.status) != "waiting_approval":
        raise HTTPException(status_code=400, detail=TASK_APPROVAL_NOT_WAITING_DETAIL)


def apply_approval_decision_to_record(
    record: Any,
    request: Any,
    *,
    updated_at: float,
) -> None:
    params = dict(record.params or {})
    params["approval_decision"] = approval_decision_value(request)
    params["approval_reviewer"] = str(getattr(request, "reviewer", "") or "").strip()
    params["approval_comment"] = str(getattr(request, "comment", "") or "").strip()

    record.params = params
    record.status = getattr(type(record.status), "PENDING", record.status)
    record.progress = min(100, max(10, int(getattr(record, "progress", 0) or 0)))
    record.error = None
    record.result = ""
    record.updated_at = updated_at


def normalize_task_approval_id(task_id: Any) -> str:
    return str(task_id or "").strip()


def task_approval_batch_id_required_result(task_id: str = "") -> dict[str, Any]:
    return {"task_id": task_id, "ok": False, "error": TASK_APPROVAL_ID_REQUIRED_DETAIL}


def task_approval_batch_error_result(task_id: str, error: Any) -> dict[str, Any]:
    return {"task_id": task_id, "ok": False, "error": str(error)}


def task_approval_batch_success_result(
    task_id: str,
    task_payload: dict[str, Any],
) -> dict[str, Any]:
    return {"task_id": task_id, "ok": True, "task": task_payload}


def build_task_approval_batch_payload(
    results: list[dict[str, Any]],
    *,
    succeeded: int,
) -> dict[str, Any]:
    failed = len(results) - succeeded
    return {
        "total": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }


def _task_status_value(status: Any) -> str:
    return str(getattr(status, "value", status) or "").strip()
