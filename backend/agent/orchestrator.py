"""LangGraph-based multi-agent orchestration runtime."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Literal

from langgraph.graph import END, StateGraph

from backend.agent.approval import apply_approval_decision
from backend.agent.protocols import AgentTask
from backend.agent.agents.model_compare import ModelCompareAgentConfig
from backend.agent.agents.researcher import ResearchAgentConfig
from backend.agent.orchestrator_metrics import build_agent_metric, summarize_agent_metrics
from backend.agent.registry import (
    AgentRegistry,
    create_default_agent_registry,
    create_runtime_agent_registry,
)
from backend.agent.state import (
    ApprovalDecision,
    OrchestratorPlanStep,
    OrchestratorState,
)
from backend.core.tracing import trace_span

DEFAULT_STEP_ORDER = ("research", "data_analysis", "writing", "review", "integrator", "model_compare")


def infer_task_types(user_request: str) -> list[str]:
    """Use deterministic routing until an LLM planner is introduced."""
    text = str(user_request or "").lower()
    task_types: list[str] = []

    if any(keyword in text for keyword in ("研究", "调研", "搜索", "检索", "资料", "research", "search")):
        task_types.append("research")
    if any(keyword in text for keyword in ("数据", "表格", "excel", "csv", "图表", "统计", "dashboard")):
        task_types.append("data_analysis")
    if any(keyword in text for keyword in ("写", "撰写", "润色", "报告", "文案", "总结", "draft", "write")):
        task_types.append("writing")
    if any(keyword in text for keyword in ("审核", "检查", "质量", "风险", "review", "qa")):
        task_types.append("review")
    if any(
        keyword in text
        for keyword in (
            "model compare",
            "model_compare",
            "compare models",
            "multi-model",
            "parallel compare",
            "synthesis",
            "preference",
            "evaluation repository",
        )
    ):
        task_types.append("model_compare")
    if any(
        keyword in text
        for keyword in (
            "推送",
            "发送",
            "同步",
            "通知",
            "邮件",
            "邮箱",
            "飞书",
            "钉钉",
            "webhook",
            "email",
            "feishu",
            "dingtalk",
            "integration",
            "integrate",
            "push",
            "send",
            "sync",
        )
    ):
        task_types.append("integration")

    return task_types or ["general"]


def _normalize_requested_items(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = [value]
    normalized: list[Any] = []
    for item in items:
        if isinstance(item, str):
            text = item.strip()
            if text:
                normalized.append(text)
        elif isinstance(item, dict):
            normalized.append(dict(item))
        else:
            text = str(item or "").strip()
            if text:
                normalized.append(text)
    return normalized


def _agent_task_type(agent_name: str, registry: AgentRegistry) -> str:
    normalized = str(agent_name or "").strip()
    if not normalized:
        return "general"
    try:
        agent = registry.get(normalized)
    except KeyError:
        return "general"
    capabilities = [
        str(capability or "").strip().lower()
        for capability in getattr(agent, "capabilities", [])
        if str(capability or "").strip()
    ]
    return capabilities[0] if capabilities else normalized.lower() or "general"


def _build_requested_plan(
    user_request: str,
    registry: AgentRegistry,
    context: dict[str, Any] | None,
    *,
    requested_tasks: Any = None,
    requested_agents: Any = None,
) -> list[OrchestratorPlanStep]:
    context_map = dict(context or {})

    explicit_steps = _normalize_requested_items(context_map.get("requested_steps"))
    if explicit_steps:
        plan: list[OrchestratorPlanStep] = []
        for index, raw_step in enumerate(explicit_steps, start=1):
            if isinstance(raw_step, dict):
                task_type = str(
                    raw_step.get("task_type")
                    or raw_step.get("type")
                    or raw_step.get("task")
                    or raw_step.get("agent")
                    or "general"
                ).strip()
                agent_name = str(raw_step.get("agent") or "").strip()
                if not agent_name:
                    agent = registry.find_for_task(task_type)
                    agent_name = agent.name if agent is not None else "general"
                plan.append(
                    {
                        "id": str(raw_step.get("id") or f"step-{index}").strip(),
                        "agent": agent_name,
                        "task_type": task_type or _agent_task_type(agent_name, registry),
                        "description": str(
                            raw_step.get("description")
                            or raw_step.get("input")
                            or user_request
                            or ""
                        ).strip(),
                        "input": raw_step.get("input", user_request),
                        "status": str(raw_step.get("status") or "pending"),
                        "requires_approval": bool(raw_step.get("requires_approval", False)),
                        "approval_status": str(
                            raw_step.get("approval_status")
                            or (
                                "pending"
                                if bool(raw_step.get("requires_approval", False))
                                else "not_required"
                            )
                        ),
                        "parallel_group": str(raw_step.get("parallel_group") or "").strip(),
                        "depends_on": _normalize_depends_on(raw_step.get("depends_on")),
                        "metadata": dict(raw_step.get("metadata") or {}),
                    }
                )
            else:
                task_type = str(raw_step or "").strip().lower() or "general"
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
                        "metadata": {"planner": "context", "requested_steps": True},
                    }
                )
        return plan

    task_requests = _normalize_requested_items(
        requested_tasks if requested_tasks is not None else context_map.get("requested_tasks")
    )
    agent_requests = _normalize_requested_items(
        requested_agents if requested_agents is not None else context_map.get("requested_agents")
    )
    if task_requests or agent_requests:
        step_count = max(len(task_requests), len(agent_requests))
        plan: list[OrchestratorPlanStep] = []
        for index in range(step_count):
            requested_task = str(task_requests[index] or "").strip() if index < len(task_requests) else ""
            requested_agent = str(agent_requests[index] or "").strip() if index < len(agent_requests) else ""

            if requested_agent:
                try:
                    registry.get(requested_agent)
                except KeyError:
                    requested_agent = ""
            if not requested_task and requested_agent:
                requested_task = _agent_task_type(requested_agent, registry)
            if not requested_agent and requested_task:
                agent = registry.find_for_task(requested_task)
                requested_agent = agent.name if agent is not None else "general"

            task_type = requested_task or _agent_task_type(requested_agent, registry)
            agent = registry.find_for_task(task_type)
            agent_name = requested_agent or (agent.name if agent is not None else "general")
            plan.append(
                {
                    "id": f"step-{index + 1}",
                    "agent": agent_name,
                    "task_type": task_type,
                    "description": str(user_request or "").strip(),
                    "input": user_request,
                    "status": "pending",
                    "requires_approval": False,
                    "approval_status": "not_required",
                    "metadata": {
                        "planner": "context",
                        "requested_tasks": task_requests,
                        "requested_agents": agent_requests,
                    },
                }
            )
        return plan

    return []


def create_plan(
    user_request: str,
    registry: AgentRegistry,
    context: dict[str, Any] | None = None,
    *,
    requested_tasks: Any = None,
    requested_agents: Any = None,
) -> list[OrchestratorPlanStep]:
    requested_plan = _build_requested_plan(
        user_request,
        registry,
        context,
        requested_tasks=requested_tasks,
        requested_agents=requested_agents,
    )
    if requested_plan:
        return _apply_task_approval_policy(requested_plan, context)
    plan: list[OrchestratorPlanStep] = []
    for index, task_type in enumerate(infer_task_types(user_request), start=1):
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
                "metadata": {"planner": "heuristic"},
            }
        )
    return _apply_task_approval_policy(plan, context)


def _normalize_task_approval_policy(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    required_task_types: list[str] = []
    seen: set[str] = set()
    raw_task_types = raw.get("required_task_types")
    if isinstance(raw_task_types, str):
        raw_task_types = [raw_task_types]
    if isinstance(raw_task_types, (list, tuple, set)):
        for item in raw_task_types:
            task_type = str(item or "").strip().lower()
            if task_type and task_type not in seen:
                required_task_types.append(task_type)
                seen.add(task_type)

    return {
        "enabled": bool(raw.get("enabled", False)),
        "required_task_types": required_task_types,
        "high_risk_requires_approval": bool(raw.get("high_risk_requires_approval", True)),
        "default_reviewer_role": str(raw.get("default_reviewer_role") or "admin").strip()
        or "admin",
    }


def _task_approval_policy_match(
    step: OrchestratorPlanStep,
    policy: dict[str, Any],
) -> dict[str, Any] | None:
    if not policy.get("enabled"):
        return None

    task_type = str(step.get("task_type") or "").strip().lower()
    required_task_types = set(policy.get("required_task_types") or [])
    if task_type and task_type in required_task_types:
        return {
            "reason": "required_task_type",
            "matched_task_type": task_type,
            "reviewer_role": policy["default_reviewer_role"],
        }

    metadata = step.get("metadata") if isinstance(step.get("metadata"), dict) else {}
    risk_level = str(
        metadata.get("risk_level")
        or metadata.get("risk")
        or step.get("risk_level")
        or ""
    ).strip().lower()
    high_risk = bool(metadata.get("high_risk") or step.get("high_risk"))
    if policy.get("high_risk_requires_approval") and (
        high_risk or risk_level in {"high", "critical", "severe"}
    ):
        return {
            "reason": "high_risk",
            "risk_level": risk_level or "high",
            "reviewer_role": policy["default_reviewer_role"],
        }

    return None


def _apply_task_approval_policy(
    plan: list[OrchestratorPlanStep],
    context: dict[str, Any] | None,
) -> list[OrchestratorPlanStep]:
    context_map = dict(context or {})
    policy = _normalize_task_approval_policy(
        context_map.get("task_approval_policy") or context_map.get("approval_policy")
    )
    if not policy.get("enabled"):
        return [dict(step) for step in plan]

    updated_plan: list[OrchestratorPlanStep] = []
    for raw_step in plan:
        step = dict(raw_step)
        match = _task_approval_policy_match(step, policy)
        if match:
            metadata = dict(step.get("metadata") or {})
            metadata["task_approval_policy"] = {
                "enabled": True,
                "required_task_types": list(policy["required_task_types"]),
                "high_risk_requires_approval": bool(policy["high_risk_requires_approval"]),
                "default_reviewer_role": policy["default_reviewer_role"],
            }
            metadata["approval_policy_match"] = match
            step["metadata"] = metadata
            step["requires_approval"] = True
            if str(step.get("approval_status") or "not_required") == "not_required":
                step["approval_status"] = "pending"
        updated_plan.append(step)
    return updated_plan


def _copy_state(state: OrchestratorState) -> OrchestratorState:
    return dict(state)


def _mark_step(
    plan: list[OrchestratorPlanStep],
    index: int,
    status: Literal["waiting_approval", "running", "completed", "failed", "blocked", "skipped"],
    *,
    error: str = "",
) -> list[OrchestratorPlanStep]:
    updated = [dict(step) for step in plan]
    if 0 <= index < len(updated):
        updated[index]["status"] = status
        if error:
            updated[index]["error"] = error
    return updated


def _step_id(step: OrchestratorPlanStep, index: int) -> str:
    return str(step.get("id") or f"step-{index + 1}").strip()


def _normalize_depends_on(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        raw_items = [item.strip() for item in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        raw_items = [str(item or "").strip() for item in value]
    else:
        raw_items = [str(value or "").strip()]

    normalized: list[str] = []
    for item in raw_items:
        if item and item not in normalized:
            normalized.append(item)
    return normalized


def _normalize_plan(plan: list[OrchestratorPlanStep]) -> list[OrchestratorPlanStep]:
    normalized: list[OrchestratorPlanStep] = []
    previous_barrier_step_ids: list[str] = []
    active_group_id = ""
    active_group_step_ids: list[str] = []
    active_group_depends_on: list[str] = []

    for index, raw_step in enumerate(plan):
        step = dict(raw_step)
        step["id"] = _step_id(step, index)
        requires_approval = bool(step.get("requires_approval", False))
        explicit_depends_on = "depends_on" in step
        step.setdefault("status", "pending")
        step.setdefault("metadata", {})
        step.setdefault("approval_status", "pending" if requires_approval else "not_required")

        group_id = _parallel_group_id(step)
        if explicit_depends_on:
            depends_on = _normalize_depends_on(step.get("depends_on"))
        elif group_id and group_id == active_group_id:
            depends_on = list(active_group_depends_on)
        else:
            depends_on = list(previous_barrier_step_ids)
        step["depends_on"] = depends_on

        normalized.append(step)

        if group_id:
            if group_id != active_group_id:
                active_group_id = group_id
                active_group_step_ids = []
                active_group_depends_on = list(depends_on)
            active_group_step_ids.append(str(step["id"]))
            previous_barrier_step_ids = list(active_group_step_ids)
        else:
            active_group_id = ""
            active_group_step_ids = []
            active_group_depends_on = []
            previous_barrier_step_ids = [str(step["id"])]
    return normalized


def _format_final_output(state: OrchestratorState) -> str:
    synthesized = _extract_synthesized_output(state)
    if synthesized:
        return synthesized

    results = state.get("agent_results", {})
    lines: list[str] = []
    for step in state.get("plan", []):
        step_id = str(step.get("id") or "")
        result = results.get(step_id)
        if not result:
            continue
        agent = str(result.get("agent") or step.get("agent") or "agent")
        output = str(result.get("output") or "").strip()
        if output:
            lines.append(f"### {agent}\n{output}")
    return "\n\n".join(lines).strip()


def _extract_synthesized_output(state: OrchestratorState) -> str:
    """Prefer structured synthesis artifacts over legacy concatenated output."""
    results = state.get("agent_results", {})
    plan = list(state.get("plan", []))
    ordered_step_ids = [
        str(step.get("id") or f"step-{index + 1}").strip()
        for index, step in enumerate(plan)
    ]
    for step_id in reversed(ordered_step_ids):
        result = results.get(step_id)
        if not isinstance(result, dict):
            continue
        artifacts = result.get("artifacts")
        if not isinstance(artifacts, list):
            continue
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            if str(artifact.get("type") or "") != "model_compare_synthesis":
                continue
            content = artifact.get("content")
            if isinstance(content, dict):
                answer = str(content.get("answer") or "").strip()
                if answer:
                    return answer
            text = str(content or "").strip()
            if text:
                return text
    return ""


def _parallel_group_id(step: OrchestratorPlanStep) -> str:
    return str(step.get("parallel_group") or "").strip()


def _parallel_group_indexes(plan: list[OrchestratorPlanStep], start_index: int) -> list[int]:
    if not 0 <= start_index < len(plan):
        return []
    group_id = _parallel_group_id(plan[start_index])
    if not group_id:
        return [start_index]

    indexes: list[int] = []
    for index in range(start_index, len(plan)):
        step = plan[index]
        if _parallel_group_id(step) != group_id:
            break
        if str(step.get("status") or "pending") not in {"pending", "waiting_approval"}:
            break
        indexes.append(index)
    return indexes or [start_index]


def _has_unapproved_step(plan: list[OrchestratorPlanStep], indexes: list[int]) -> bool:
    return any(
        bool(plan[index].get("requires_approval"))
        and str(plan[index].get("approval_status") or "") != "approved"
        for index in indexes
        if 0 <= index < len(plan)
    )


def _terminal_dependency_statuses() -> set[str]:
    return {"completed", "skipped"}


def _plan_status_by_id(plan: list[OrchestratorPlanStep]) -> dict[str, str]:
    return {
        _step_id(step, index): str(step.get("status") or "pending")
        for index, step in enumerate(plan)
    }


def _dependency_blockers(
    step: OrchestratorPlanStep,
    status_by_id: dict[str, str],
) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    for dependency_id in _normalize_depends_on(step.get("depends_on")):
        dependency_status = status_by_id.get(dependency_id)
        if dependency_status in {"failed", "blocked"}:
            blockers.append({"step_id": dependency_id, "status": dependency_status})
        elif dependency_status is None:
            blockers.append({"step_id": dependency_id, "status": "missing"})
    return blockers


def _dependencies_satisfied(
    step: OrchestratorPlanStep,
    status_by_id: dict[str, str],
) -> bool:
    return all(
        status_by_id.get(dependency_id) in _terminal_dependency_statuses()
        for dependency_id in _normalize_depends_on(step.get("depends_on"))
    )


def _refresh_blocked_steps(
    plan: list[OrchestratorPlanStep],
) -> tuple[list[OrchestratorPlanStep], dict[str, Any]]:
    updated = [dict(step) for step in plan]
    changed = True
    while changed:
        changed = False
        status_by_id = _plan_status_by_id(updated)
        for index, step in enumerate(updated):
            if str(step.get("status") or "pending") != "pending":
                continue
            blockers = _dependency_blockers(step, status_by_id)
            if not blockers:
                continue
            step_id = _step_id(step, index)
            updated[index]["status"] = "blocked"
            updated[index]["error"] = "Blocked by failed dependency"
            metadata = dict(updated[index].get("metadata") or {})
            metadata["blocked_by"] = blockers
            updated[index]["metadata"] = metadata
            changed = True

    blocked_steps: dict[str, Any] = {}
    for index, step in enumerate(updated):
        if str(step.get("status") or "") == "blocked":
            step_id = _step_id(step, index)
            metadata = dict(step.get("metadata") or {})
            blocked_steps[step_id] = {
                "step_id": step_id,
                "depends_on": _normalize_depends_on(step.get("depends_on")),
                "blocked_by": list(metadata.get("blocked_by") or []),
                "agent": str(step.get("agent") or ""),
                "task_type": str(step.get("task_type") or ""),
            }
    return updated, blocked_steps


def _ready_step_indexes(plan: list[OrchestratorPlanStep]) -> list[int]:
    status_by_id = _plan_status_by_id(plan)
    ready: list[int] = []
    for index, step in enumerate(plan):
        if str(step.get("status") or "pending") != "pending":
            continue
        if _dependencies_satisfied(step, status_by_id):
            ready.append(index)
    return ready


def _build_approval_batch(
    plan: list[OrchestratorPlanStep],
    indexes: list[int],
) -> dict[str, Any]:
    approvals: list[dict[str, Any]] = []
    for index in indexes:
        step = plan[index]
        step_id = _step_id(step, index)
        approvals.append(
            {
                "step_id": step_id,
                "agent": str(step.get("agent") or "general"),
                "task_type": str(step.get("task_type") or "general"),
                "description": str(step.get("description") or "Task requires approval"),
                "depends_on": _normalize_depends_on(step.get("depends_on")),
                "parallel_group": _parallel_group_id(step),
                "metadata": dict(step.get("metadata") or {}),
            }
        )
    step_ids = [item["step_id"] for item in approvals]
    return {
        "id": "approval-" + "-".join(step_ids),
        "step_ids": step_ids,
        "count": len(step_ids),
        "approvals": approvals,
        "mode": "batch" if len(step_ids) > 1 else "single",
    }


def _next_pending_index(plan: list[OrchestratorPlanStep]) -> int:
    for index, step in enumerate(plan):
        if str(step.get("status") or "pending") in {"pending", "waiting_approval", "running"}:
            return index
    return len(plan)


def build_orchestrator_graph(
    registry: AgentRegistry | None = None,
    *,
    llm: Any | None = None,
    research_config: ResearchAgentConfig | None = None,
    model_compare_config: ModelCompareAgentConfig | None = None,
    integrator_connectors: tuple[Any, ...] | list[Any] | None = None,
):
    """Build the multi-agent orchestration graph."""
    agent_registry = registry or (
        create_runtime_agent_registry(
            llm=llm,
            research_config=research_config,
            model_compare_config=model_compare_config,
            integrator_connectors=integrator_connectors,
        )
        if (
            llm is not None
            or research_config is not None
            or model_compare_config is not None
            or integrator_connectors is not None
        )
        else create_default_agent_registry()
    )

    async def plan_node(state: OrchestratorState) -> OrchestratorState:
        next_state = _copy_state(state)
        if not next_state.get("plan"):
            next_state["plan"] = create_plan(
                next_state.get("user_request", ""),
                agent_registry,
                context=next_state.get("context") or {},
                requested_tasks=next_state.get("requested_tasks"),
                requested_agents=next_state.get("requested_agents"),
            )
        else:
            next_state["plan"] = _normalize_plan(next_state.get("plan", []))
            next_state["plan"] = _apply_task_approval_policy(
                next_state.get("plan", []),
                next_state.get("context") or {},
            )
        next_state.setdefault("agent_results", {})
        next_state.setdefault("agent_metrics", {})
        next_state.setdefault("agent_cost_summary", {})
        next_state.setdefault("trace_spans", {})
        next_state.setdefault("blocked_steps", {})
        next_state.setdefault("approval_batch", {})
        next_state.setdefault("errors", [])
        next_state["current_step"] = _next_pending_index(next_state.get("plan", []))
        next_state["parallel_step_indexes"] = [
            int(item) for item in next_state.get("parallel_step_indexes", []) if str(item).strip()
        ]
        next_state["status"] = "running"
        return next_state

    async def route_to_agent_node(state: OrchestratorState) -> OrchestratorState:
        next_state = _copy_state(state)
        plan, blocked_steps = _refresh_blocked_steps(next_state.get("plan", []))
        next_state["plan"] = plan
        next_state["blocked_steps"] = blocked_steps
        ready_indexes = _ready_step_indexes(plan)
        current_step = ready_indexes[0] if ready_indexes else _next_pending_index(plan)
        next_state["current_step"] = current_step

        if not ready_indexes:
            next_state["next_agent"] = ""
            next_state["parallel_step_indexes"] = []
            next_state["needs_human_approval"] = False
            next_state["approval_reason"] = ""
            next_state["approval_step_id"] = ""
            next_state["approval_batch"] = {}
            return next_state

        approval_indexes = [
            index
            for index in ready_indexes
            if bool(plan[index].get("requires_approval"))
            and str(plan[index].get("approval_status") or "") != "approved"
        ]
        if approval_indexes:
            first_index = approval_indexes[0]
            first_step = plan[first_index]
            approval_batch = _build_approval_batch(plan, approval_indexes)
            next_state["needs_human_approval"] = True
            next_state["approval_reason"] = str(
                first_step.get("description") or "Task requires approval"
            )
            next_state["approval_step_id"] = _step_id(first_step, first_index)
            next_state["approval_batch"] = approval_batch
            next_state["status"] = "waiting_approval"
            next_state["next_agent"] = "human_gate"
            updated_plan = [dict(item) for item in plan]
            for index in approval_indexes:
                updated_plan[index]["status"] = "waiting_approval"
            next_state["plan"] = updated_plan
            next_state["current_step"] = first_index
            return next_state

        executable_indexes = [
            index
            for index in ready_indexes
            if not bool(plan[index].get("requires_approval"))
            or str(plan[index].get("approval_status") or "") == "approved"
        ]
        next_state["needs_human_approval"] = False
        next_state["approval_reason"] = ""
        next_state["approval_step_id"] = ""
        next_state["approval_batch"] = {}

        if len(executable_indexes) > 1:
            next_state["next_agent"] = "parallel_group"
            next_state["parallel_step_indexes"] = executable_indexes
            updated_plan = [dict(item) for item in plan]
            for index in executable_indexes:
                updated_plan[index]["status"] = "running"
            next_state["plan"] = updated_plan
            next_state["current_step"] = executable_indexes[0]
            return next_state

        current_step = executable_indexes[0]
        step = plan[current_step]
        next_state["next_agent"] = str(step.get("agent") or "general")
        next_state["parallel_step_indexes"] = []
        next_state["plan"] = _mark_step(plan, current_step, "running")
        next_state["current_step"] = current_step
        return next_state

    async def run_agent_step(
        state: OrchestratorState,
        step_index: int,
        expected_agent: str,
    ) -> dict[str, Any]:
        plan = state.get("plan", [])
        step = plan[step_index]
        task: AgentTask = {
            "id": str(step.get("id") or f"step-{step_index + 1}"),
            "type": str(step.get("task_type") or "general"),
            "description": str(step.get("description") or ""),
            "input": step.get("input"),
            "requires_approval": bool(step.get("requires_approval", False)),
            "metadata": dict(step.get("metadata") or {}),
        }
        span_attributes = {
            "component": "agent_orchestrator",
            "agent": expected_agent,
            "step_id": task["id"],
            "task_type": task["type"],
            "current_step": step_index,
        }
        started_at = time.perf_counter()
        async with trace_span("agent.orchestrator.step", span_attributes) as span:
            try:
                agent = agent_registry.get(expected_agent)
                agent_context = dict(state.get("context") or {})
                agent_context["_agent_results"] = dict(state.get("agent_results") or {})
                agent_context["_plan"] = [dict(item) for item in state.get("plan", [])]
                agent_context["_current_step"] = step_index
                result = await agent.execute(task, agent_context)
                metric = build_agent_metric(
                    task,
                    expected_agent,
                    result,
                    duration_ms=int((time.perf_counter() - started_at) * 1000),
                    status=str(result.get("status") or "completed"),
                    trace_id=str(span.trace_id or ""),
                    span_id=str(span.span_id or ""),
                )
                span.set_attributes(
                    {
                        "step_status": "completed",
                        "result_status": str(result.get("status") or ""),
                        "duration_ms": metric["duration_ms"],
                        "total_tokens": metric["total_tokens"],
                        "estimated_cost_usd": metric["estimated_cost_usd"],
                    }
                )
                return {"index": step_index, "task_id": task["id"], "result": result, "metric": metric}
            except Exception as exc:
                error = str(exc)
                metric = build_agent_metric(
                    task,
                    expected_agent,
                    None,
                    duration_ms=int((time.perf_counter() - started_at) * 1000),
                    status="failed",
                    error=error,
                    trace_id=str(span.trace_id or ""),
                    span_id=str(span.span_id or ""),
                )
                span.set_attributes({"step_status": "failed", "duration_ms": metric["duration_ms"]})
                span.error(exc)
                return {"index": step_index, "task_id": task["id"], "error": error, "metric": metric}

    def apply_step_outcome(
        state: OrchestratorState,
        outcome: dict[str, Any],
        plan: list[OrchestratorPlanStep],
    ) -> list[OrchestratorPlanStep]:
        step_index = int(outcome.get("index") or 0)
        task_id = str(outcome.get("task_id") or f"step-{step_index + 1}")
        metric = outcome["metric"]
        state.setdefault("agent_metrics", {})[task_id] = metric
        state.setdefault("trace_spans", {})[task_id] = {
            "trace_id": str(metric.get("trace_id") or ""),
            "span_id": str(metric.get("span_id") or ""),
            "agent": str(metric.get("agent") or ""),
            "task_type": str(metric.get("task_type") or ""),
        }
        if "error" in outcome:
            error = str(outcome.get("error") or "")
            state.setdefault("errors", []).append(error)
            return _mark_step(plan, step_index, "failed", error=error)
        state.setdefault("agent_results", {})[task_id] = outcome["result"]
        return _mark_step(plan, step_index, "completed")

    async def execute_named_agent(
        state: OrchestratorState,
        expected_agent: str,
    ) -> OrchestratorState:
        next_state = _copy_state(state)
        plan = next_state.get("plan", [])
        current_step = int(next_state.get("current_step") or 0)
        if current_step >= len(plan):
            return next_state
        outcome = await run_agent_step(next_state, current_step, expected_agent)
        next_state["plan"] = apply_step_outcome(next_state, outcome, [dict(item) for item in plan])
        next_state["current_step"] = _next_pending_index(next_state["plan"])
        return next_state

    async def execute_parallel_group_node(state: OrchestratorState) -> OrchestratorState:
        next_state = _copy_state(state)
        plan = [dict(item) for item in next_state.get("plan", [])]
        indexes = [
            int(index)
            for index in next_state.get("parallel_step_indexes", [])
            if 0 <= int(index) < len(plan)
        ]
        if not indexes:
            return next_state
        outcomes = await asyncio.gather(
            *[
                run_agent_step(next_state, index, str(plan[index].get("agent") or "general"))
                for index in indexes
            ]
        )
        for outcome in outcomes:
            plan = apply_step_outcome(next_state, outcome, plan)
        next_state["plan"] = plan
        next_state["current_step"] = _next_pending_index(plan)
        next_state["parallel_step_indexes"] = []
        return next_state

    async def research_agent_node(state: OrchestratorState) -> OrchestratorState:
        return await execute_named_agent(state, "research")

    async def data_agent_node(state: OrchestratorState) -> OrchestratorState:
        return await execute_named_agent(state, "data_analysis")

    async def writing_agent_node(state: OrchestratorState) -> OrchestratorState:
        return await execute_named_agent(state, "writing")

    async def qa_agent_node(state: OrchestratorState) -> OrchestratorState:
        return await execute_named_agent(state, "review")

    async def integrator_agent_node(state: OrchestratorState) -> OrchestratorState:
        return await execute_named_agent(state, "integrator")

    async def model_compare_agent_node(state: OrchestratorState) -> OrchestratorState:
        return await execute_named_agent(state, "model_compare")

    async def general_agent_node(state: OrchestratorState) -> OrchestratorState:
        return await execute_named_agent(state, "general")

    async def synthesize_node(state: OrchestratorState) -> OrchestratorState:
        next_state = _copy_state(state)
        plan, blocked_steps = _refresh_blocked_steps(next_state.get("plan", []))
        next_state["plan"] = plan
        next_state["blocked_steps"] = blocked_steps
        next_state["agent_cost_summary"] = summarize_agent_metrics(
            dict(next_state.get("agent_metrics") or {})
        )
        next_state["final_output"] = _format_final_output(next_state)
        next_state["status"] = (
            "completed"
            if not next_state.get("errors") and not blocked_steps
            else "failed"
        )
        return next_state

    async def human_approval_node(state: OrchestratorState) -> OrchestratorState:
        next_state = _copy_state(state)
        next_state["status"] = "waiting_approval"
        next_state["needs_human_approval"] = True
        return next_state

    def after_route(state: OrchestratorState) -> str:
        if state.get("needs_human_approval"):
            return "human_gate"
        next_agent = str(state.get("next_agent") or "")
        if next_agent == "parallel_group":
            return "parallel_group"
        if next_agent in {"research", "data_analysis", "writing", "review", "integrator", "model_compare"}:
            return next_agent
        if next_agent:
            return "general"
        return "synthesize"

    def after_agent(state: OrchestratorState) -> str:
        plan, _blocked_steps = _refresh_blocked_steps(state.get("plan", []))
        if not _ready_step_indexes(plan):
            return "synthesize"
        return "route"

    graph = StateGraph(OrchestratorState)
    graph.add_node("plan", plan_node)
    graph.add_node("route", route_to_agent_node)
    graph.add_node("research", research_agent_node)
    graph.add_node("data_analysis", data_agent_node)
    graph.add_node("writing", writing_agent_node)
    graph.add_node("review", qa_agent_node)
    graph.add_node("integrator", integrator_agent_node)
    graph.add_node("model_compare", model_compare_agent_node)
    graph.add_node("general", general_agent_node)
    graph.add_node("parallel_group", execute_parallel_group_node)
    graph.add_node("synthesize", synthesize_node)
    graph.add_node("human_gate", human_approval_node)

    graph.set_entry_point("plan")
    graph.add_edge("plan", "route")
    graph.add_conditional_edges(
        "route",
        after_route,
        {
            "research": "research",
            "data_analysis": "data_analysis",
            "writing": "writing",
            "review": "review",
            "integrator": "integrator",
            "model_compare": "model_compare",
            "general": "general",
            "parallel_group": "parallel_group",
            "synthesize": "synthesize",
            "human_gate": "human_gate",
        },
    )
    for node_name in DEFAULT_STEP_ORDER + ("general",):
        graph.add_conditional_edges(
            node_name,
            after_agent,
            {"route": "route", "synthesize": "synthesize"},
        )
    graph.add_conditional_edges(
        "parallel_group",
        after_agent,
        {"route": "route", "synthesize": "synthesize"},
    )
    graph.add_edge("synthesize", END)
    graph.add_edge("human_gate", END)
    return graph.compile()


async def run_orchestrator(
    user_request: str,
    *,
    context: dict[str, Any] | None = None,
    requested_tasks: list[str] | None = None,
    requested_agents: list[str] | None = None,
    plan: list[OrchestratorPlanStep] | None = None,
    registry: AgentRegistry | None = None,
    llm: Any | None = None,
    research_config: ResearchAgentConfig | None = None,
    model_compare_config: ModelCompareAgentConfig | None = None,
    integrator_connectors: tuple[Any, ...] | list[Any] | None = None,
) -> OrchestratorState:
    """Convenience helper for one-shot orchestrator execution."""
    normalized_requested_tasks = [
        str(item)
        for item in _normalize_requested_items(requested_tasks)
        if not isinstance(item, dict)
    ]
    normalized_requested_agents = [
        str(item)
        for item in _normalize_requested_items(requested_agents)
        if not isinstance(item, dict)
    ]
    context_map = dict(context or {})
    requested_task_count = len(
        normalized_requested_tasks
        if requested_tasks is not None
        else _normalize_requested_items(context_map.get("requested_tasks"))
    )
    requested_agent_count = len(
        normalized_requested_agents
        if requested_agents is not None
        else _normalize_requested_items(context_map.get("requested_agents"))
    )
    async with trace_span(
        "agent.orchestrator.run",
        {
            "component": "agent_orchestrator",
            "plan_supplied": bool(plan),
            "context_keys": sorted(str(key) for key in context_map.keys()),
            "requested_tasks": requested_task_count,
            "requested_agents": requested_agent_count,
            "requested_steps": len(_normalize_requested_items(context_map.get("requested_steps"))),
        },
    ) as span:
        graph = build_orchestrator_graph(
            registry,
            llm=llm,
            research_config=research_config,
            model_compare_config=model_compare_config,
            integrator_connectors=integrator_connectors,
        )
        initial_state: OrchestratorState = {
            "user_request": user_request,
            "context": context_map,
            "plan": list(plan or []),
            "current_step": 0,
            "agent_results": {},
            "agent_metrics": {},
            "agent_cost_summary": {},
            "trace_spans": {},
            "blocked_steps": {},
            "approval_batch": {},
            "final_output": "",
            "needs_human_approval": False,
            "errors": [],
            "status": "pending",
        }
        if requested_tasks is not None:
            initial_state["requested_tasks"] = normalized_requested_tasks
        if requested_agents is not None:
            initial_state["requested_agents"] = normalized_requested_agents
        result = await graph.ainvoke(initial_state)
        span.set_attributes(
            {
                "status": str(result.get("status") or ""),
                "step_count": len(result.get("plan", [])),
                "error_count": len(result.get("errors", [])),
            }
        )
        return result


async def resume_orchestrator(
    state: OrchestratorState,
    *,
    approval_decision: ApprovalDecision | None = None,
    approval_reviewer: str = "",
    approval_comment: str = "",
    registry: AgentRegistry | None = None,
    llm: Any | None = None,
    research_config: ResearchAgentConfig | None = None,
    model_compare_config: ModelCompareAgentConfig | None = None,
    integrator_connectors: tuple[Any, ...] | list[Any] | None = None,
) -> OrchestratorState:
    """Resume an existing orchestrator state, optionally after a human decision."""
    async with trace_span(
        "agent.orchestrator.resume",
        {
            "component": "agent_orchestrator",
            "approval_decision": str(approval_decision or ""),
            "incoming_status": str(state.get("status") or ""),
        },
    ) as span:
        resume_state = _copy_state(state)
        if resume_state.get("needs_human_approval") and approval_decision is None:
            raise ValueError("Approval decision is required before resuming this orchestrator run")
        if approval_decision is not None:
            resume_state = apply_approval_decision(
                resume_state,
                decision=approval_decision,
                reviewer=approval_reviewer,
                comment=approval_comment,
            )

        graph = build_orchestrator_graph(
            registry,
            llm=llm,
            research_config=research_config,
            model_compare_config=model_compare_config,
            integrator_connectors=integrator_connectors,
        )
        result = await graph.ainvoke(resume_state)
        span.set_attributes(
            {
                "status": str(result.get("status") or ""),
                "step_count": len(result.get("plan", [])),
                "error_count": len(result.get("errors", [])),
            }
        )
        return result


def run_orchestrator_sync(
    user_request: str,
    *,
    context: dict[str, Any] | None = None,
    requested_tasks: list[str] | None = None,
    requested_agents: list[str] | None = None,
    plan: list[OrchestratorPlanStep] | None = None,
    registry: AgentRegistry | None = None,
    llm: Any | None = None,
    research_config: ResearchAgentConfig | None = None,
    model_compare_config: ModelCompareAgentConfig | None = None,
    integrator_connectors: tuple[Any, ...] | list[Any] | None = None,
) -> OrchestratorState:
    """Synchronous wrapper for scripts and tests."""
    return asyncio.run(
        run_orchestrator(
            user_request,
            context=context,
            requested_tasks=requested_tasks,
            requested_agents=requested_agents,
            plan=plan,
            registry=registry,
            llm=llm,
            research_config=research_config,
            model_compare_config=model_compare_config,
            integrator_connectors=integrator_connectors,
        )
    )


def resume_orchestrator_sync(
    state: OrchestratorState,
    *,
    approval_decision: ApprovalDecision | None = None,
    approval_reviewer: str = "",
    approval_comment: str = "",
    registry: AgentRegistry | None = None,
    llm: Any | None = None,
    research_config: ResearchAgentConfig | None = None,
    model_compare_config: ModelCompareAgentConfig | None = None,
    integrator_connectors: tuple[Any, ...] | list[Any] | None = None,
) -> OrchestratorState:
    """Synchronous wrapper for resuming an orchestrator run."""
    return asyncio.run(
        resume_orchestrator(
            state,
            approval_decision=approval_decision,
            approval_reviewer=approval_reviewer,
            approval_comment=approval_comment,
            registry=registry,
            llm=llm,
            research_config=research_config,
            model_compare_config=model_compare_config,
            integrator_connectors=integrator_connectors,
        )
    )


__all__ = [
    "DEFAULT_STEP_ORDER", "build_orchestrator_graph", "create_plan", "infer_task_types",
    "resume_orchestrator", "resume_orchestrator_sync", "run_orchestrator", "run_orchestrator_sync",
]
