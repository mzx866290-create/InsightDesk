"""Shared state types for the multi-agent orchestration graph."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from backend.agent.protocols import AgentResult

OrchestratorStatus = Literal["pending", "running", "waiting_approval", "completed", "failed"]
OrchestratorStepStatus = Literal[
    "pending",
    "waiting_approval",
    "running",
    "completed",
    "failed",
    "blocked",
    "skipped",
]
ApprovalStatus = Literal["not_required", "pending", "approved", "rejected"]
ApprovalDecision = Literal["approved", "rejected"]


class OrchestratorPlanStep(TypedDict, total=False):
    id: str
    agent: str
    task_type: str
    parallel_group: str
    depends_on: list[str]
    description: str
    input: Any
    status: OrchestratorStepStatus
    requires_approval: bool
    approval_status: ApprovalStatus
    error: str
    metadata: dict[str, Any]


class OrchestratorAgentMetric(TypedDict, total=False):
    step_id: str
    agent: str
    task_type: str
    status: str
    trace_id: str
    span_id: str
    duration_ms: int
    artifact_count: int
    source_count: int
    used_llm: bool
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    error: str
    metadata: dict[str, Any]


class OrchestratorState(TypedDict, total=False):
    user_request: str
    context: dict[str, Any]
    requested_tasks: list[str]
    requested_agents: list[str]
    plan: list[OrchestratorPlanStep]
    current_step: int
    next_agent: str
    parallel_step_indexes: list[int]
    approval_batch: dict[str, Any]
    blocked_steps: dict[str, Any]
    trace_spans: dict[str, dict[str, Any]]
    agent_results: dict[str, AgentResult]
    agent_metrics: dict[str, OrchestratorAgentMetric]
    agent_cost_summary: dict[str, Any]
    final_output: str
    needs_human_approval: bool
    approval_reason: str
    approval_step_id: str
    approval_decision: ApprovalDecision
    errors: list[str]
    status: OrchestratorStatus
