"""Payload builders for workflow task routes."""

from typing import Any, Callable

from backend.helpers.workflow_data_helpers import (
    enrich_workflow_data_context,
    ensure_data_analysis_plan_step,
)


def json_compatible_model_payload(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    return value


def build_multi_agent_workflow_task_params(
    request: Any,
    *,
    task_approval_policy_loader: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    user_request = str(getattr(request, "user_request", "") or "").strip()
    if not user_request:
        raise ValueError("Workflow user_request cannot be empty.")

    context = dict(getattr(request, "context", {}) or {})
    context, data_file_summaries = enrich_workflow_data_context(
        context,
        list(getattr(request, "data_files", []) or []),
    )

    session_id = str(getattr(request, "session_id", "") or "").strip()
    if session_id and not str(context.get("session_id") or "").strip():
        context["session_id"] = session_id

    task_approval_policy = (
        task_approval_policy_loader() if task_approval_policy_loader is not None else {}
    )
    if task_approval_policy.get("enabled"):
        context["task_approval_policy"] = task_approval_policy

    plan = ensure_data_analysis_plan_step(
        [
            dict(step)
            for step in list(getattr(request, "plan", []) or [])
            if isinstance(step, dict)
        ],
        user_request=user_request,
        has_data_rows=bool(context.get("rows")),
    )

    params: dict[str, Any] = {
        "user_request": user_request,
        "panel_id": str(getattr(request, "panel_id", "") or "").strip(),
        "answer_group_id": str(getattr(request, "answer_group_id", "") or "").strip(),
        "model_id": str(
            getattr(request, "model_id", "multi_agent_workflow")
            or "multi_agent_workflow"
        ).strip()
        or "multi_agent_workflow",
        "context": context,
        "plan": plan,
        "research_mode": str(getattr(request, "research_mode", "deep") or "deep")
        .strip()
        .lower()
        or "deep",
        "research_source_strategy": str(
            getattr(request, "research_source_strategy", "web_only") or "web_only"
        )
        .strip()
        .lower()
        or "web_only",
        "providers": [
            str(item).strip()
            for item in list(getattr(request, "providers", []) or [])
            if str(item).strip()
        ],
        "max_rounds": max(1, int(getattr(request, "max_rounds", 2) or 2)),
        "max_results_per_query": max(
            1,
            int(getattr(request, "max_results_per_query", 4) or 4),
        ),
        "max_fetch_pages": max(1, int(getattr(request, "max_fetch_pages", 3) or 3)),
        "time_range": str(getattr(request, "time_range", "") or "").strip(),
        "use_kb_context": bool(getattr(request, "use_kb_context", False)),
        "vector_store_path": str(getattr(request, "vector_store_path", "") or "").strip(),
        "allow_quick_fallback": bool(getattr(request, "allow_quick_fallback", False)),
    }

    if data_file_summaries:
        params["data_files"] = data_file_summaries

    panel_config = getattr(request, "panel_config", None)
    if panel_config is not None:
        params["panel_config"] = json_compatible_model_payload(panel_config)

    return params
