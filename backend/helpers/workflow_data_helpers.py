"""Helpers for extracting workflow data-file context."""

import base64
import io
from typing import Any
from urllib.parse import unquote_to_bytes

DEFAULT_WORKFLOW_DATA_ROW_SAMPLE_LIMIT = 500


def decode_workflow_data_url(data_url: str) -> bytes:
    if not data_url.startswith("data:") or "," not in data_url:
        return b""
    header, encoded = data_url.split(",", 1)
    try:
        if ";base64" in header:
            return base64.b64decode(encoded, validate=True)
        return unquote_to_bytes(encoded)
    except Exception:
        return b""


def rows_from_workflow_excel_payload(payload: bytes) -> list[dict[str, Any]]:
    if not payload:
        return []
    try:
        import pandas as pd
    except ImportError:
        return []
    try:
        frame = pd.read_excel(io.BytesIO(payload), nrows=DEFAULT_WORKFLOW_DATA_ROW_SAMPLE_LIMIT)
    except Exception:
        return []
    frame = frame.where(pd.notnull(frame), None)
    rows = frame.to_dict(orient="records")
    return [{str(key): value for key, value in row.items()} for row in rows]


def workflow_file_payload(raw_file: Any) -> dict[str, Any]:
    if hasattr(raw_file, "model_dump"):
        payload = raw_file.model_dump(mode="json")
        return dict(payload) if isinstance(payload, dict) else {}
    if hasattr(raw_file, "dict"):
        payload = raw_file.dict()
        return dict(payload) if isinstance(payload, dict) else {}
    if isinstance(raw_file, dict):
        return dict(raw_file)
    return {}


def rows_from_workflow_data_file(raw_file: Any) -> list[dict[str, Any]]:
    file_payload = workflow_file_payload(raw_file)
    if not file_payload:
        return []

    from backend.agent.agents.data_analysis import DataAnalysisAgent

    analyzer = DataAnalysisAgent()
    extracted_text = str(file_payload.get("extracted_text") or "").strip()
    if extracted_text:
        rows = analyzer._coerce_rows(extracted_text)
        if rows:
            return rows

    data_url = str(file_payload.get("data_url") or "").strip()
    payload = decode_workflow_data_url(data_url)
    if not payload:
        return []
    file_name = str(file_payload.get("name") or "").strip().lower()
    media_type = str(file_payload.get("media_type") or "").strip().lower()
    if (
        file_name.endswith((".xlsx", ".xls"))
        or media_type
        in {
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
        }
    ):
        return rows_from_workflow_excel_payload(payload)
    text = payload.decode("utf-8-sig", errors="replace")
    return analyzer._coerce_rows(text)


def enrich_workflow_data_context(
    context: dict[str, Any],
    data_files: list[Any],
    *,
    row_sample_limit: int = DEFAULT_WORKFLOW_DATA_ROW_SAMPLE_LIMIT,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not data_files:
        return context, []

    next_context = dict(context)
    summaries: list[dict[str, Any]] = []
    for raw_file in data_files:
        file_payload = workflow_file_payload(raw_file)
        if not file_payload:
            continue
        rows = rows_from_workflow_data_file(file_payload)
        if not rows:
            continue
        name = str(file_payload.get("name") or "workflow-data-file").strip()
        sampled_rows = rows[:row_sample_limit]
        summary = {"name": name, "row_count": len(rows)}
        if len(rows) > len(sampled_rows):
            summary.update(
                {
                    "sampled": True,
                    "sampled_row_count": len(sampled_rows),
                    "sample_limit": row_sample_limit,
                }
            )
        summaries.append(summary)
        if "rows" not in next_context and "data" not in next_context:
            next_context["rows"] = sampled_rows
            next_context["data_source"] = name
            if summary.get("sampled"):
                next_context["data_sampling"] = summary
    if summaries:
        next_context["data_files"] = summaries
    return next_context, summaries


def ensure_data_analysis_plan_step(
    plan: list[dict[str, Any]],
    *,
    user_request: str,
    has_data_rows: bool,
) -> list[dict[str, Any]]:
    if not has_data_rows:
        return plan
    if any(
        str(step.get("agent") or step.get("task_type") or "") == "data_analysis"
        for step in plan
    ):
        return plan

    step = {
        "id": "step-data-analysis",
        "agent": "data_analysis",
        "task_type": "data_analysis",
        "description": user_request,
        "input": user_request,
        "status": "pending",
        "requires_approval": False,
        "metadata": {"planner": "workflow_data_files"},
    }
    next_plan = [dict(item) for item in plan]
    insert_at = len(next_plan)
    for index, current in enumerate(next_plan):
        if str(current.get("agent") or "") in {"writing", "review"}:
            insert_at = index
            break
    next_plan.insert(insert_at, step)
    for index, current in enumerate(next_plan, start=1):
        current["id"] = str(current.get("id") or f"step-{index}")
    return next_plan
