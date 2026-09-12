"""Optional LLM planner for workflow plan creation.

The deterministic keyword heuristics in ``orchestrator.infer_task_types``
remain the default. When enabled (env ``WORKFLOW_LLM_PLANNER`` or the
per-request ``use_llm_planner`` context flag) and an LLM is available, the
planner classifies the request into known task types and returns fully-formed
plan steps tagged with ``planner: "llm"``. Any failure -- missing LLM,
malformed JSON, unknown task types only, timeout -- returns ``None`` so the
caller falls back to the heuristic path.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

PLANNER_ENV_FLAG = "WORKFLOW_LLM_PLANNER"
_TRUTHY = {"1", "true", "yes", "on"}
_PLANNER_TIMEOUT_SECONDS = 25.0
_MAX_STEPS = 6
_KNOWN_TASK_TYPES = (
    "research",
    "data_analysis",
    "writing",
    "review",
    "model_compare",
    "integration",
    "general",
)

_PLANNER_PROMPT = (
    "你是多智能体工作流的规划器。请把用户请求分类为一个或多个任务类型。\n"
    "可选任务类型（只能使用这些值）：research, data_analysis, writing, review, "
    "model_compare, integration, general。\n"
    "硬性要求：\n"
    "1. 只输出 JSON，不要输出解释。\n"
    "2. 最多 6 个步骤，按执行顺序排列，不要重复。\n"
    '3. 输出形如 {{"task_types": ["research", "writing"]}}\n\n'
    "用户请求：\n{user_request}"
)


def llm_planner_enabled(context: dict[str, Any] | None = None) -> bool:
    """Env flag is the default; the per-request context flag wins when set."""
    import os

    if isinstance(context, dict):
        raw = context.get("use_llm_planner")
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            value = raw.strip().lower()
            if value in _TRUTHY:
                return True
            if value in {"0", "false", "no", "off"}:
                return False
    return os.getenv(PLANNER_ENV_FLAG, "").strip().lower() in _TRUTHY


def _extract_json_object(text: str) -> dict[str, Any] | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def normalize_planned_task_types(value: Any) -> list[str] | None:
    """Validate an LLM task-type list; unknown or duplicate types are dropped."""
    if not isinstance(value, list):
        return None
    seen: list[str] = []
    for item in value:
        task_type = str(item or "").strip().lower()
        if task_type in _KNOWN_TASK_TYPES and task_type not in seen:
            seen.append(task_type)
    if not seen:
        return None
    return seen[:_MAX_STEPS]


async def plan_task_types_with_llm(
    user_request: str,
    llm: Any,
    *,
    timeout_seconds: float = _PLANNER_TIMEOUT_SECONDS,
) -> list[str] | None:
    """Ask the LLM to classify the request; None means fall back to heuristics."""
    if llm is None:
        return None
    prompt = _PLANNER_PROMPT.format(user_request=str(user_request or "").strip())
    try:
        response = await asyncio.wait_for(llm.ainvoke(prompt), timeout=timeout_seconds)
    except Exception:
        return None
    content = getattr(response, "content", response)
    if not isinstance(content, str):
        content = str(content or "")
    parsed = _extract_json_object(content)
    if parsed is None:
        return None
    return normalize_planned_task_types(parsed.get("task_types"))


async def build_llm_plan(
    user_request: str,
    llm: Any,
    registry: Any,
) -> list[dict[str, Any]] | None:
    """Return fully-formed plan steps from an LLM classification, or None."""
    task_types = await plan_task_types_with_llm(user_request, llm)
    if not task_types:
        return None

    plan: list[dict[str, Any]] = []
    for index, task_type in enumerate(task_types, start=1):
        agent = registry.find_for_task(task_type)
        agent_name = agent.name if agent is not None else "general"
        plan.append(
            {
                "id": f"step-{index}",
                "agent": agent_name,
                "task_type": task_type,
                "description": str(user_request or "").strip(),
                "input": user_request,
                "status": "pending",
                "requires_approval": False,
                "approval_status": "not_required",
                "metadata": {"planner": "llm", "planner_run_id": uuid.uuid4().hex[:8]},
            }
        )
    return plan
