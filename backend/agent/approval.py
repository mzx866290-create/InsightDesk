"""Helpers for human approval gates in the multi-agent orchestrator."""

from __future__ import annotations

from typing import Any

from backend.agent.protocols import AgentResult
from backend.agent.state import ApprovalDecision, OrchestratorPlanStep, OrchestratorState


def _copy_state(state: OrchestratorState) -> OrchestratorState:
    return dict(state)


def _normalize_approval_status(step: OrchestratorPlanStep) -> str:
    if step.get("approval_status"):
        return str(step["approval_status"])
    return "pending" if step.get("requires_approval") else "not_required"


def _build_approval_metadata(
    step: OrchestratorPlanStep,
    *,
    decision: ApprovalDecision,
    reviewer: str,
    comment: str,
    quality_gate: dict[str, Any] | None = None,
    review_evaluation: dict[str, Any] | None = None,
    approval_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = dict(step.get("metadata") or {})
    metadata["approval"] = {
        "decision": decision,
        "reviewer": reviewer,
        "comment": comment,
        "quality_gate": quality_gate,
        "review": review_evaluation,
        "policy": approval_policy or _normalize_approval_policy(metadata.get("approval_policy")),
    }
    return metadata


def _normalize_approval_policy(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    blocked_gates = raw.get("block_on_quality_gates", ["fail"])
    if isinstance(blocked_gates, str):
        blocked_gates = [blocked_gates]
    if not isinstance(blocked_gates, list):
        blocked_gates = ["fail"]
    return {
        "block_on_quality_gates": [
            str(item).strip().lower()
            for item in blocked_gates
            if str(item or "").strip()
        ],
        "allow_quality_gate_override": bool(raw.get("allow_quality_gate_override", False)),
    }


def _latest_review_evaluation(state: OrchestratorState) -> dict[str, Any] | None:
    results = state.get("agent_results")
    if not isinstance(results, dict):
        return None
    fallback_quality_gate: dict[str, Any] | None = None
    for result in reversed(list(results.values())):
        if not isinstance(result, dict):
            continue
        is_review_result = str(result.get("agent") or "").strip().lower() == "review"
        quality_gate: dict[str, Any] | None = None
        approval_recommendation: dict[str, Any] | None = None
        artifacts = result.get("artifacts")
        if isinstance(artifacts, list):
            for artifact in reversed(artifacts):
                if not isinstance(artifact, dict) or not isinstance(artifact.get("content"), dict):
                    continue
                if artifact.get("type") == "approval_recommendation" and approval_recommendation is None:
                    approval_recommendation = dict(artifact["content"])
                elif artifact.get("type") == "quality_gate" and quality_gate is None:
                    quality_gate = dict(artifact["content"])
        if quality_gate is not None and fallback_quality_gate is None:
            fallback_quality_gate = quality_gate
        if not is_review_result:
            continue
        metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
        if quality_gate is None and isinstance(metadata.get("quality_gate"), str):
            quality_gate = {
                "gate": metadata.get("quality_gate"),
                "passed": bool(metadata.get("passed", False)),
                "issues": [],
            }
        if approval_recommendation is None and isinstance(metadata.get("approval_recommendation"), dict):
            approval_recommendation = dict(metadata["approval_recommendation"])
        if quality_gate or approval_recommendation:
            return {
                "quality_gate": quality_gate,
                "approval_recommendation": approval_recommendation,
            }
    if fallback_quality_gate is not None:
        return {
            "quality_gate": fallback_quality_gate,
            "approval_recommendation": None,
        }
    return None


def _approval_policy_for_step(step: OrchestratorPlanStep, batch: dict[str, Any]) -> dict[str, Any]:
    metadata = step.get("metadata") if isinstance(step.get("metadata"), dict) else {}
    policy = _normalize_approval_policy(metadata.get("approval_policy"))
    batch_policy = batch.get("approval_policy")
    if isinstance(batch_policy, dict):
        merged = dict(policy)
        merged.update(_normalize_approval_policy(batch_policy))
        return merged
    return policy


def _assert_quality_gate_allows_approval(
    *,
    decision: ApprovalDecision,
    quality_gate: dict[str, Any] | None,
    approval_policy: dict[str, Any],
    comment: str,
) -> None:
    if decision != "approved" or not quality_gate:
        return
    gate = str(quality_gate.get("gate") or "").strip().lower()
    if gate not in set(approval_policy.get("block_on_quality_gates") or []):
        return
    if approval_policy.get("allow_quality_gate_override") and comment.strip():
        return
    raise ValueError(f"Quality gate '{gate}' blocks approval")


def _assert_review_recommendation_allows_approval(
    *,
    decision: ApprovalDecision,
    review_evaluation: dict[str, Any] | None,
    approval_policy: dict[str, Any],
    comment: str,
) -> None:
    if decision != "approved" or not review_evaluation:
        return
    recommendation = review_evaluation.get("approval_recommendation")
    if not isinstance(recommendation, dict):
        return
    recommended_decision = str(recommendation.get("decision") or "").strip().lower()
    if recommended_decision in {"", "approve", "approved", "pass"}:
        return
    if approval_policy.get("allow_quality_gate_override") and comment.strip():
        return
    raise ValueError(f"Review recommendation '{recommended_decision}' blocks approval")


def apply_approval_decision(
    state: OrchestratorState,
    *,
    decision: ApprovalDecision,
    reviewer: str = "",
    comment: str = "",
) -> OrchestratorState:
    """Apply a human approval decision to the current orchestrator step."""
    next_state = _copy_state(state)
    plan = [dict(step) for step in next_state.get("plan", [])]
    current_step = int(next_state.get("current_step") or 0)
    batch = next_state.get("approval_batch") if isinstance(next_state.get("approval_batch"), dict) else {}
    batch_step_ids = [
        str(step_id)
        for step_id in list(batch.get("step_ids") or [])
        if str(step_id or "").strip()
    ]

    if current_step >= len(plan) and not batch_step_ids:
        raise ValueError("No pending orchestrator step is available for approval")

    approval_indexes = [
        index
        for index, step in enumerate(plan)
        if str(step.get("id") or f"step-{index + 1}") in set(batch_step_ids)
    ]
    if not approval_indexes:
        approval_indexes = [current_step]

    if any(index >= len(plan) for index in approval_indexes):
        raise ValueError("No pending orchestrator step is available for approval")
    if any(not plan[index].get("requires_approval") for index in approval_indexes):
        raise ValueError("Current orchestrator step does not require approval")

    approval_statuses = [_normalize_approval_status(plan[index]) for index in approval_indexes]
    if all(status == "approved" for status in approval_statuses) and decision == "approved":
        raise ValueError("Current orchestrator step has already been approved")
    if all(status == "rejected" for status in approval_statuses) and decision == "rejected":
        raise ValueError("Current orchestrator step has already been rejected")

    reason = comment.strip()
    if not reason:
        reason = (
            "Rejected during manual approval."
            if decision == "rejected"
            else "Approved during manual approval."
        )
    review_evaluation = _latest_review_evaluation(next_state)
    quality_gate = review_evaluation.get("quality_gate") if isinstance(review_evaluation, dict) else None
    approval_policies = {
        index: _approval_policy_for_step(plan[index], batch)
        for index in approval_indexes
    }
    for index, policy in approval_policies.items():
        _assert_quality_gate_allows_approval(
            decision=decision,
            quality_gate=quality_gate,
            approval_policy=policy,
            comment=comment,
        )
        _assert_review_recommendation_allows_approval(
            decision=decision,
            review_evaluation=review_evaluation,
            approval_policy=policy,
            comment=comment,
        )

    next_state["approval_decision"] = decision
    next_state["needs_human_approval"] = False
    next_state["approval_reason"] = ""
    next_state["approval_step_id"] = ""
    next_state["approval_batch"] = {}
    next_state["next_agent"] = ""

    for index in approval_indexes:
        step = dict(plan[index])
        step["approval_status"] = decision
        step["metadata"] = _build_approval_metadata(
            step,
            decision=decision,
            reviewer=reviewer.strip(),
            comment=reason,
            quality_gate=quality_gate,
            review_evaluation=review_evaluation,
            approval_policy=approval_policies[index],
        )

        if decision == "approved":
            step["status"] = "pending"
        else:
            step["status"] = "skipped"
            step["error"] = reason
            step_id = str(step.get("id") or f"step-{index + 1}")
            next_state.setdefault("agent_results", {})
            rejected_result: AgentResult = {
                "agent": str(step.get("agent") or "human_gate"),
                "task_id": step_id,
                "task_type": str(step.get("task_type") or "approval"),
                "status": "rejected",
                "output": "",
                "artifacts": [],
                "sources": [],
                "error": reason,
                "metadata": dict(step["metadata"]),
            }
            next_state["agent_results"][step_id] = rejected_result
        plan[index] = step

    next_state["plan"] = plan
    if decision == "rejected":
        next_state["current_step"] = min(
            [index for index, step in enumerate(plan) if step.get("status") == "pending"]
            or [len(plan)]
        )
    if decision == "approved":
        next_state["status"] = "pending"
    else:
        next_state["status"] = "running"
    return next_state


__all__ = ["apply_approval_decision"]
