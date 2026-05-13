import asyncio
import json
import re

import pytest

from backend.agent import (
    AgentRegistry,
    DataAnalysisAgent,
    ModelCompareAgent,
    ReviewAgent,
    StaticAgent,
    WritingAgent,
    apply_approval_decision,
    build_orchestrator_graph,
    create_default_agent_registry,
    create_plan,
    create_runtime_agent_registry,
    infer_task_types,
    ResearchAgentConfig,
    resume_orchestrator,
    run_orchestrator,
)
from backend.agent.agents.integrator import IntegratorAgent, IntegratorAgentConfig
from backend.core.tracing import get_recent_trace_events, reset_trace_events


class UsageTrackingAgent:
    name = "research"
    description = "Research agent that reports deterministic usage."
    capabilities = ["research"]

    def can_handle(self, task_type: str) -> bool:
        return str(task_type or "").strip().lower() == "research"

    async def execute(self, task, context):
        return {
            "agent": self.name,
            "task_id": str(task.get("id") or ""),
            "task_type": str(task.get("type") or ""),
            "status": "completed",
            "output": "Usage-aware research completed.",
            "artifacts": [{"type": "research_report", "title": "Report"}],
            "sources": [{"title": "Source", "url": "https://example.test/source"}],
            "metadata": {
                "used_llm": True,
                "usage": {
                    "prompt_tokens": 11,
                    "completion_tokens": 7,
                    "estimated_cost_usd": 0.0123,
                },
            },
        }


class FailingResearchAgent:
    name = "research"
    description = "Research agent that fails for recovery tests."
    capabilities = ["research"]

    def can_handle(self, task_type: str) -> bool:
        return str(task_type or "").strip().lower() == "research"

    async def execute(self, task, context):
        raise RuntimeError("simulated research failure")


class WorkflowProbeAgent:
    def __init__(self, name: str, capability: str, *, delay: float = 0.0, fail: bool = False) -> None:
        self.name = name
        self.description = f"{name} probe"
        self.capabilities = [capability]
        self.delay = delay
        self.fail = fail

    def can_handle(self, task_type: str) -> bool:
        return str(task_type or "").strip().lower() in self.capabilities

    async def execute(self, task, context):
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError(f"{self.name} failed")
        upstream_step_ids = sorted((context.get("_agent_results") or {}).keys())
        return {
            "agent": self.name,
            "task_id": str(task.get("id") or ""),
            "task_type": str(task.get("type") or ""),
            "status": "completed",
            "output": f"{self.name} upstream={','.join(upstream_step_ids) or 'none'}",
            "artifacts": [],
            "sources": [],
            "metadata": {"upstream_step_ids": upstream_step_ids},
        }


def test_infer_task_types_keeps_expected_business_order():
    assert infer_task_types("research market info, analyze CSV data, write a report, and review it") == [
        "research",
        "data_analysis",
        "writing",
        "review",
    ]


def test_infer_task_types_routes_external_integration_after_delivery_steps():
    assert infer_task_types("write a report, review it, then send it to webhook") == [
        "writing",
        "review",
        "integration",
    ]


def test_default_registry_finds_specialist_agent():
    registry = create_default_agent_registry()

    agent = registry.find_for_task("data_analysis")

    assert agent is not None
    assert agent.name == "data_analysis"


def test_default_registry_uses_runtime_writing_and_review_agents():
    registry = create_default_agent_registry()

    assert isinstance(registry.get("data_analysis"), DataAnalysisAgent)
    assert isinstance(registry.get("writing"), WritingAgent)
    assert isinstance(registry.get("review"), ReviewAgent)
    assert isinstance(registry.get("model_compare"), ModelCompareAgent)


def test_registry_describes_agents_in_registration_order_with_metadata():
    registry = AgentRegistry()
    agent = StaticAgent(
        name="research",
        description="Research",
        capabilities=["research"],
        output_prefix="done",
        metadata={"tier": "core"},
    )
    registry.register(agent)

    catalog = registry.describe_agents()
    catalog[0]["metadata"]["tier"] = "changed"

    assert catalog == [
        {
            "name": "research",
            "description": "Research",
            "capabilities": ["research"],
            "metadata": {"tier": "changed"},
        }
    ]
    assert agent.metadata == {"tier": "core"}


def test_default_registry_describes_stable_agent_catalog():
    registry = create_default_agent_registry()

    catalog = registry.describe_agents()

    assert [item["name"] for item in catalog] == [
        "research",
        "data_analysis",
        "writing",
        "review",
        "integrator",
        "model_compare",
        "general",
    ]
    assert all(set(item) == {"name", "description", "capabilities", "metadata"} for item in catalog)
    assert catalog[0]["description"] == "Research Agent for search, evidence collection, and deep research tasks."
    assert catalog[0]["capabilities"] == ["research", "deep_research", "web_search"]
    assert catalog[-1]["metadata"] == {}


def test_runtime_registry_describes_stable_agent_catalog_with_config_metadata():
    registry = create_runtime_agent_registry(
        research_config=ResearchAgentConfig(metadata={"catalog": "runtime"})
    )

    catalog = registry.describe_agents()
    research = catalog[0]

    assert [item["name"] for item in catalog] == [
        "research",
        "data_analysis",
        "writing",
        "review",
        "integrator",
        "model_compare",
        "general",
    ]
    assert research["metadata"] == {"catalog": "runtime"}
    assert "topic_research" in research["capabilities"]


def test_registry_rejects_duplicate_agent_name():
    registry = AgentRegistry()
    agent = StaticAgent(
        name="research",
        description="Research",
        capabilities=["research"],
        output_prefix="done",
    )
    registry.register(agent)

    with pytest.raises(ValueError):
        registry.register(agent)


def test_create_plan_routes_each_step_to_registered_agent():
    registry = create_default_agent_registry()

    plan = create_plan("research the market and write a summary", registry)

    assert [step["task_type"] for step in plan] == ["research", "writing"]
    assert [step["agent"] for step in plan] == ["research", "writing"]
    assert all(step["status"] == "pending" for step in plan)
    assert all(step["approval_status"] == "not_required" for step in plan)


def test_create_plan_prefers_requested_tasks_over_inference():
    registry = create_default_agent_registry()

    plan = create_plan(
        "research the market and write a summary",
        registry,
        requested_tasks=["writing", "review"],
    )

    assert [step["task_type"] for step in plan] == ["writing", "review"]
    assert [step["agent"] for step in plan] == ["writing", "review"]
    assert plan[0]["metadata"]["planner"] == "context"
    assert plan[0]["metadata"]["requested_tasks"] == ["writing", "review"]


def test_create_plan_applies_requested_agents_by_position():
    registry = create_default_agent_registry()

    plan = create_plan(
        "research then write",
        registry,
        requested_agents=["review", "writing"],
    )

    assert [step["agent"] for step in plan] == ["review", "writing"]
    assert [step["task_type"] for step in plan] == ["review", "writing"]


def test_orchestrator_runs_registered_agents_and_synthesizes_output():
    reset_trace_events()

    state = asyncio.run(
        run_orchestrator(
            "research market info, analyze Excel data, write a report, and review risks",
            context={"session_id": "test-session"},
        )
    )

    assert state["status"] == "completed"
    assert [step["status"] for step in state["plan"]] == [
        "completed",
        "completed",
        "completed",
        "completed",
    ]
    assert set(state["agent_results"]) == {"step-1", "step-2", "step-3", "step-4"}
    assert "Research Agent" in state["final_output"]
    assert "Data Agent" in state["final_output"]
    assert "Writing Agent" in state["final_output"]
    assert "QA Agent" in state["final_output"]

    events = get_recent_trace_events()
    completed_run = [
        event
        for event in events
        if event["name"] == "agent.orchestrator.run" and event["event"] == "end"
    ]
    completed_steps = [
        event
        for event in events
        if event["name"] == "agent.orchestrator.step" and event["event"] == "end"
    ]

    assert completed_run[-1]["attributes"]["status"] == "completed"
    assert completed_run[-1]["attributes"]["step_count"] == 4
    assert completed_run[-1]["duration_ms"] >= 0
    assert [event["attributes"]["agent"] for event in completed_steps] == [
        "research",
        "data_analysis",
        "writing",
        "review",
    ]
    assert all(event["attributes"]["step_status"] == "completed" for event in completed_steps)


def test_run_orchestrator_prefers_explicit_requested_tasks_over_context():
    registry = AgentRegistry()
    registry.register(WorkflowProbeAgent("writing", "writing"))
    registry.register(WorkflowProbeAgent("review", "review"))
    registry.register(WorkflowProbeAgent("general", "general"))

    state = asyncio.run(
        run_orchestrator(
            "research then write",
            context={"requested_tasks": ["writing"]},
            requested_tasks=["review"],
            registry=registry,
        )
    )

    assert state["status"] == "completed"
    assert [step["task_type"] for step in state["plan"]] == ["review"]
    assert [step["agent"] for step in state["plan"]] == ["review"]
    assert state["agent_results"]["step-1"]["agent"] == "review"


def test_orchestrator_records_agent_metrics_and_cost_summary():
    reset_trace_events()
    registry = AgentRegistry()
    registry.register(UsageTrackingAgent())

    state = asyncio.run(
        run_orchestrator(
            "research token costs",
            registry=registry,
        )
    )

    metric = state["agent_metrics"]["step-1"]
    summary = state["agent_cost_summary"]
    research_summary = summary["agents"]["research"]

    assert state["status"] == "completed"
    assert metric["agent"] == "research"
    assert metric["status"] == "completed"
    assert metric["trace_id"]
    assert metric["span_id"]
    assert metric["used_llm"] is True
    assert metric["prompt_tokens"] == 11
    assert metric["completion_tokens"] == 7
    assert metric["total_tokens"] == 18
    assert metric["estimated_cost_usd"] == 0.0123
    assert metric["artifact_count"] == 1
    assert metric["source_count"] == 1
    assert summary["step_count"] == 1
    assert summary["completed_count"] == 1
    assert summary["failed_count"] == 0
    assert summary["total_tokens"] == 18
    assert summary["estimated_cost_usd"] == 0.0123
    assert research_summary["total_tokens"] == 18
    assert research_summary["artifact_count"] == 1
    assert research_summary["source_count"] == 1

    step_events = [
        event
        for event in get_recent_trace_events()
        if event["name"] == "agent.orchestrator.step" and event["event"] == "end"
    ]
    assert step_events[-1]["attributes"]["total_tokens"] == 18
    assert step_events[-1]["attributes"]["estimated_cost_usd"] == 0.0123


def test_orchestrator_records_failed_agent_metric():
    registry = AgentRegistry()
    registry.register(FailingResearchAgent())

    state = asyncio.run(
        run_orchestrator(
            "research failure handling",
            registry=registry,
        )
    )

    metric = state["agent_metrics"]["step-1"]

    assert state["status"] == "failed"
    assert state["plan"][0]["status"] == "failed"
    assert metric["agent"] == "research"
    assert metric["status"] == "failed"
    assert metric["error"] == "simulated research failure"
    assert metric["trace_id"]
    assert metric["span_id"]
    assert state["agent_cost_summary"]["failed_count"] == 1
    assert state["agent_cost_summary"]["agents"]["research"]["failed_count"] == 1


def test_orchestrator_runs_parallel_group_before_downstream_step():
    registry = AgentRegistry()
    registry.register(WorkflowProbeAgent("research", "research", delay=0.02))
    registry.register(WorkflowProbeAgent("data_analysis", "data_analysis", delay=0.01))
    registry.register(WorkflowProbeAgent("writing", "writing"))

    state = asyncio.run(
        run_orchestrator(
            "parallel research and data, then write",
            registry=registry,
            plan=[
                {
                    "id": "step-1",
                    "agent": "research",
                    "task_type": "research",
                    "description": "Research",
                    "input": "Research",
                    "status": "pending",
                    "requires_approval": False,
                    "parallel_group": "evidence",
                },
                {
                    "id": "step-2",
                    "agent": "data_analysis",
                    "task_type": "data_analysis",
                    "description": "Analyze data",
                    "input": "Analyze data",
                    "status": "pending",
                    "requires_approval": False,
                    "parallel_group": "evidence",
                },
                {
                    "id": "step-3",
                    "agent": "writing",
                    "task_type": "writing",
                    "description": "Write summary",
                    "input": "Write summary",
                    "status": "pending",
                    "requires_approval": False,
                },
            ],
        )
    )

    assert state["status"] == "completed"
    assert [step["status"] for step in state["plan"]] == ["completed", "completed", "completed"]
    assert state["agent_results"]["step-1"]["metadata"]["upstream_step_ids"] == []
    assert state["agent_results"]["step-2"]["metadata"]["upstream_step_ids"] == []
    assert state["agent_results"]["step-3"]["metadata"]["upstream_step_ids"] == ["step-1", "step-2"]
    assert state["final_output"].index("### research") < state["final_output"].index("### data_analysis")
    assert state["agent_cost_summary"]["step_count"] == 3


def test_model_compare_agent_builds_repository_preference_and_real_synthesis():
    state = asyncio.run(
        run_orchestrator(
            "compare models and synthesize the best implementation",
            requested_tasks=["model_compare"],
            context={
                "preference_contract": {
                    "required_terms": ["typed contracts", "regression tests"],
                    "preferred_terms": ["evidence"],
                },
                "model_candidates": [
                    {
                        "panel_id": "panel-a",
                        "model_id": "model-a",
                        "content": "Short answer.",
                    },
                    {
                        "panel_id": "panel-b",
                        "model_id": "model-b",
                        "content": "Recommended implementation keeps evidence, typed contracts, and regression tests visible.",
                        "sources": [{"title": "Design note", "url": "https://example.test/design"}],
                        "artifacts": [{"type": "plan", "content": {"steps": 3}}],
                        "metadata": {"completed_workflow_count": 2},
                    },
                ]
            },
        )
    )

    result = state["agent_results"]["step-1"]
    artifacts_by_type = {item["type"]: item for item in result["artifacts"]}
    repository = artifacts_by_type["model_evaluation_repository"]["content"]
    preference = artifacts_by_type["model_preference"]["content"]
    synthesis = artifacts_by_type["model_compare_synthesis"]["content"]

    assert state["status"] == "completed"
    assert state["plan"][0]["agent"] == "model_compare"
    assert repository["candidate_count"] == 2
    assert repository["ranking"][0]["panel_id"] == "panel-b"
    assert preference["selected_model_id"] == "model-b"
    assert preference["selected_contract_satisfied"] is True
    assert preference["preference_contract"]["required_terms"] == ["typed contracts", "regression tests"]
    assert synthesis["source_panel_id"] == "panel-b"
    assert synthesis["strategy"] == "deterministic_weighted_preference_synthesis"
    assert synthesis["synthesis_inputs"][0]["contract_satisfied"] is True
    assert synthesis["selection_reasons"][0] == "satisfied required terms: typed contracts, regression tests"
    assert state["final_output"] == synthesis["answer"]
    assert "Recommended implementation" in state["final_output"]
    assert state["agent_metrics"]["step-1"]["metadata"]["candidate_count"] == 2


def test_model_compare_synthesizes_from_parallel_upstream_results():
    registry = AgentRegistry()
    registry.register(WorkflowProbeAgent("research", "research"))
    registry.register(WorkflowProbeAgent("data_analysis", "data_analysis"))
    registry.register(ModelCompareAgent())

    state = asyncio.run(
        run_orchestrator(
            "run parallel candidates then model_compare synthesis",
            registry=registry,
            plan=[
                {
                    "id": "candidate-a",
                    "agent": "research",
                    "task_type": "research",
                    "description": "Evidence candidate",
                    "status": "pending",
                    "depends_on": [],
                },
                {
                    "id": "candidate-b",
                    "agent": "data_analysis",
                    "task_type": "data_analysis",
                    "description": "Data candidate",
                    "status": "pending",
                    "depends_on": [],
                },
                {
                    "id": "compare",
                    "agent": "model_compare",
                    "task_type": "model_compare",
                    "description": "Compare upstream model outputs",
                    "status": "pending",
                    "depends_on": ["candidate-a", "candidate-b"],
                },
            ],
        )
    )

    repository = state["agent_results"]["compare"]["artifacts"][0]["content"]

    assert state["status"] == "completed"
    assert repository["candidate_count"] == 2
    assert {item["panel_id"] for item in repository["ranking"]} == {"candidate-a", "candidate-b"}
    assert state["final_output"].startswith("# Synthesized Answer")
    assert "upstream=none" in state["final_output"]


def test_parallel_group_failure_skips_downstream_steps():
    registry = AgentRegistry()
    registry.register(WorkflowProbeAgent("research", "research"))
    registry.register(WorkflowProbeAgent("data_analysis", "data_analysis", fail=True))
    registry.register(WorkflowProbeAgent("writing", "writing"))

    state = asyncio.run(
        run_orchestrator(
            "parallel failure should stop downstream",
            registry=registry,
            plan=[
                {
                    "id": "step-1",
                    "agent": "research",
                    "task_type": "research",
                    "description": "Research",
                    "status": "pending",
                    "parallel_group": "evidence",
                },
                {
                    "id": "step-2",
                    "agent": "data_analysis",
                    "task_type": "data_analysis",
                    "description": "Analyze data",
                    "status": "pending",
                    "parallel_group": "evidence",
                },
                {
                    "id": "step-3",
                    "agent": "writing",
                    "task_type": "writing",
                    "description": "Write summary",
                    "status": "pending",
                },
            ],
        )
    )

    assert state["status"] == "failed"
    assert [step["status"] for step in state["plan"]] == ["completed", "failed", "blocked"]
    assert set(state["agent_results"]) == {"step-1"}
    assert state["agent_metrics"]["step-2"]["status"] == "failed"
    assert state["agent_metrics"]["step-2"]["error"] == "data_analysis failed"
    assert "step-3" not in state["agent_results"]
    assert state["blocked_steps"]["step-3"]["blocked_by"] == [
        {"step_id": "step-2", "status": "failed"}
    ]
    assert state["agent_cost_summary"]["failed_count"] == 1


def test_orchestrator_schedules_explicit_dag_ready_steps_without_adjacent_groups():
    registry = AgentRegistry()
    registry.register(WorkflowProbeAgent("research", "research", delay=0.02))
    registry.register(WorkflowProbeAgent("data_analysis", "data_analysis"))
    registry.register(WorkflowProbeAgent("writing", "writing"))
    registry.register(WorkflowProbeAgent("review", "review"))

    state = asyncio.run(
        run_orchestrator(
            "run a non-adjacent dag",
            registry=registry,
            plan=[
                {
                    "id": "collect-evidence",
                    "agent": "research",
                    "task_type": "research",
                    "description": "Collect evidence",
                    "status": "pending",
                    "depends_on": [],
                },
                {
                    "id": "draft-evidence",
                    "agent": "writing",
                    "task_type": "writing",
                    "description": "Draft evidence",
                    "status": "pending",
                    "depends_on": ["collect-evidence"],
                },
                {
                    "id": "analyze-data",
                    "agent": "data_analysis",
                    "task_type": "data_analysis",
                    "description": "Analyze data",
                    "status": "pending",
                    "depends_on": [],
                },
                {
                    "id": "review-data",
                    "agent": "review",
                    "task_type": "review",
                    "description": "Review data",
                    "status": "pending",
                    "depends_on": ["analyze-data"],
                },
            ],
        )
    )

    assert state["status"] == "completed"
    assert [step["status"] for step in state["plan"]] == [
        "completed",
        "completed",
        "completed",
        "completed",
    ]
    assert state["agent_results"]["collect-evidence"]["metadata"]["upstream_step_ids"] == []
    assert state["agent_results"]["analyze-data"]["metadata"]["upstream_step_ids"] == []
    assert state["agent_results"]["draft-evidence"]["metadata"]["upstream_step_ids"] == [
        "analyze-data",
        "collect-evidence",
    ]
    assert state["agent_results"]["review-data"]["metadata"]["upstream_step_ids"] == [
        "analyze-data",
        "collect-evidence",
    ]


def test_orchestrator_exposes_batched_approval_metadata_for_ready_steps():
    registry = create_default_agent_registry()
    graph = build_orchestrator_graph(registry)

    state = asyncio.run(
        graph.ainvoke(
            {
                "user_request": "publish and notify",
                "context": {},
                "plan": [
                    {
                        "id": "publish-report",
                        "agent": "writing",
                        "task_type": "writing",
                        "description": "Publish report",
                        "status": "pending",
                        "requires_approval": True,
                        "depends_on": [],
                        "metadata": {"action": "publish"},
                    },
                    {
                        "id": "send-webhook",
                        "agent": "integrator",
                        "task_type": "integration",
                        "description": "Send webhook",
                        "status": "pending",
                        "requires_approval": True,
                        "depends_on": [],
                        "metadata": {"action": "webhook"},
                    },
                ],
                "current_step": 0,
                "agent_results": {},
                "final_output": "",
                "needs_human_approval": False,
                "errors": [],
                "status": "pending",
            }
        )
    )

    assert state["status"] == "waiting_approval"
    assert state["needs_human_approval"] is True
    assert state["approval_step_id"] == "publish-report"
    assert state["approval_batch"]["mode"] == "batch"
    assert state["approval_batch"]["step_ids"] == ["publish-report", "send-webhook"]
    assert [step["status"] for step in state["plan"]] == [
        "waiting_approval",
        "waiting_approval",
    ]


def test_task_approval_policy_marks_matching_workflow_steps_for_approval():
    state = asyncio.run(
        run_orchestrator(
            "write a launch report",
            requested_tasks=["writing"],
            context={
                "task_approval_policy": {
                    "enabled": True,
                    "required_task_types": ["writing"],
                    "high_risk_requires_approval": True,
                    "default_reviewer_role": "owner",
                }
            },
        )
    )

    step = state["plan"][0]

    assert state["status"] == "waiting_approval"
    assert state["needs_human_approval"] is True
    assert state["approval_step_id"] == "step-1"
    assert step["requires_approval"] is True
    assert step["approval_status"] == "pending"
    assert step["metadata"]["approval_policy_match"] == {
        "reason": "required_task_type",
        "matched_task_type": "writing",
        "reviewer_role": "owner",
    }


def test_plugin_manifest_requires_approval_in_requested_plan(tmp_path):
    plugin_dir = tmp_path / "agent_plugins"
    plugin_dir.mkdir()
    (plugin_dir / "external-publisher.json").write_text(
        json.dumps(
            {
                "name": "external_publisher",
                "description": "Publishes workflow output to an external system.",
                "capabilities": ["external_publish"],
                "output_prefix": "External publisher completed",
                "risk_level": "critical",
                "requires_approval": True,
                "approval_reason": "External side effect.",
            }
        ),
        encoding="utf-8",
    )
    registry = create_default_agent_registry(plugin_dirs=[plugin_dir])

    state = asyncio.run(
        run_orchestrator(
            "publish final report",
            registry=registry,
            requested_tasks=["external_publish"],
        )
    )

    step = state["plan"][0]

    assert state["status"] == "waiting_approval"
    assert state["needs_human_approval"] is True
    assert step["agent"] == "external_publisher"
    assert step["requires_approval"] is True
    assert step["approval_status"] == "pending"
    assert step["metadata"]["agent_plugin"] is True
    assert step["metadata"]["agent_source"] == "plugin_manifest"
    assert step["metadata"]["risk_level"] == "critical"
    assert step["metadata"]["approval_reason"] == "External side effect."


def test_plugin_manifest_risk_level_participates_in_approval_policy(tmp_path):
    plugin_dir = tmp_path / "agent_plugins"
    plugin_dir.mkdir()
    (plugin_dir / "auditor.json").write_text(
        json.dumps(
            {
                "name": "external_auditor",
                "description": "Reviews sensitive external audit data.",
                "capabilities": ["external_audit"],
                "risk_level": "high",
            }
        ),
        encoding="utf-8",
    )
    registry = create_default_agent_registry(plugin_dirs=[plugin_dir])

    state = asyncio.run(
        run_orchestrator(
            "audit external records",
            registry=registry,
            requested_tasks=["external_audit"],
            context={"task_approval_policy": {"enabled": True}},
        )
    )

    step = state["plan"][0]

    assert state["status"] == "waiting_approval"
    assert step["metadata"]["risk_level"] == "high"
    assert step["metadata"]["approval_policy_match"] == {
        "reason": "high_risk",
        "risk_level": "high",
        "reviewer_role": "admin",
    }


def test_plugin_manifest_metadata_enriches_supplied_plan(tmp_path):
    plugin_dir = tmp_path / "agent_plugins"
    plugin_dir.mkdir()
    (plugin_dir / "legal-review.json").write_text(
        json.dumps(
            {
                "name": "legal_review",
                "description": "Reviews legal-risk output.",
                "capabilities": ["legal_review"],
                "risk_level": "high",
            }
        ),
        encoding="utf-8",
    )
    registry = create_default_agent_registry(plugin_dirs=[plugin_dir])

    state = asyncio.run(
        run_orchestrator(
            "review external contract summary",
            registry=registry,
            context={"task_approval_policy": {"enabled": True}},
            plan=[
                {
                    "id": "legal-step",
                    "agent": "legal_review",
                    "task_type": "legal_review",
                    "description": "Review summary",
                    "status": "pending",
                }
            ],
        )
    )

    step = state["plan"][0]

    assert state["status"] == "waiting_approval"
    assert step["metadata"]["agent_plugin"] is True
    assert step["metadata"]["risk_level"] == "high"
    assert step["metadata"]["approval_policy_match"]["reason"] == "high_risk"


def test_dag_failure_blocks_only_downstream_and_completes_independent_branch():
    registry = AgentRegistry()
    registry.register(WorkflowProbeAgent("research", "research", fail=True))
    registry.register(WorkflowProbeAgent("data_analysis", "data_analysis"))
    registry.register(WorkflowProbeAgent("writing", "writing"))
    registry.register(WorkflowProbeAgent("review", "review"))

    state = asyncio.run(
        run_orchestrator(
            "one dag branch fails",
            registry=registry,
            plan=[
                {
                    "id": "source-a",
                    "agent": "research",
                    "task_type": "research",
                    "description": "Source A",
                    "status": "pending",
                    "depends_on": [],
                },
                {
                    "id": "source-b",
                    "agent": "data_analysis",
                    "task_type": "data_analysis",
                    "description": "Source B",
                    "status": "pending",
                    "depends_on": [],
                },
                {
                    "id": "draft-a",
                    "agent": "writing",
                    "task_type": "writing",
                    "description": "Draft A",
                    "status": "pending",
                    "depends_on": ["source-a"],
                },
                {
                    "id": "review-b",
                    "agent": "review",
                    "task_type": "review",
                    "description": "Review B",
                    "status": "pending",
                    "depends_on": ["source-b"],
                },
            ],
        )
    )

    assert state["status"] == "failed"
    assert [step["status"] for step in state["plan"]] == [
        "failed",
        "completed",
        "blocked",
        "completed",
    ]
    assert set(state["agent_results"]) == {"source-b", "review-b"}
    assert state["blocked_steps"]["draft-a"]["blocked_by"] == [
        {"step_id": "source-a", "status": "failed"}
    ]
    assert state["trace_spans"]["source-a"]["trace_id"]
    assert state["trace_spans"]["review-b"]["span_id"]


def test_orchestrator_routes_integration_to_integrator_agent():
    registry = create_default_agent_registry(
        integrator_agent=IntegratorAgent(
            config=IntegratorAgentConfig(
                connectors=[
                    {
                        "id": "ops-webhook",
                        "type": "webhook",
                        "name": "Ops Webhook",
                        "settings": {"webhook_url": "https://example.test/hook"},
                    }
                ]
            )
        )
    )

    state = asyncio.run(
        run_orchestrator(
            "send the final summary to webhook",
            registry=registry,
            context={"payload": {"summary": "Ready to ship"}},
        )
    )

    result = state["agent_results"]["step-1"]
    artifact = result["artifacts"][0]
    assert state["status"] == "completed"
    assert state["plan"][0]["agent"] == "integrator"
    assert result["status"] == "completed"
    assert "Integrator Agent Dry-run" in result["output"]
    assert artifact["type"] == "integration_dry_run"
    assert artifact["content"]["connector"]["id"] == "ops-webhook"
    assert artifact["content"]["connector"]["settings"]["webhook_url"] == "***redacted***"


def test_writing_agent_receives_upstream_agent_results():
    state = asyncio.run(
        run_orchestrator(
            "research market info and write a report",
            plan=[
                {
                    "id": "step-1",
                    "agent": "research",
                    "task_type": "research",
                    "description": "Collect market info",
                    "input": "market info",
                    "status": "pending",
                    "requires_approval": False,
                },
                {
                    "id": "step-2",
                    "agent": "writing",
                    "task_type": "writing",
                    "description": "Draft the report",
                    "input": "market info",
                    "status": "pending",
                    "requires_approval": False,
                },
            ],
        )
    )

    writing_output = state["agent_results"]["step-2"]["output"]
    assert state["status"] == "completed"
    assert "Writing Agent Draft" in writing_output
    assert "Research Agent" in writing_output


def test_writing_agent_builds_structured_markdown_from_research_and_data_artifacts():
    agent = WritingAgent()

    result = asyncio.run(
        agent.execute(
            {
                "id": "write-1",
                "type": "writing",
                "description": "Write an investor-ready summary",
                "input": "Create a delivery brief",
            },
            {
                "_agent_results": {
                    "step-1": {
                        "agent": "research",
                        "status": "completed",
                        "output": "Research Agent findings",
                        "artifacts": [
                            {
                                "type": "research_report",
                                "summary": "Market is growing.",
                                "highlights": ["Demand increased in enterprise accounts."],
                                "caveats": ["Validate regional estimates."],
                            }
                        ],
                        "sources": [{"title": "Market source", "url": "https://example.test"}],
                    },
                    "step-2": {
                        "agent": "data_analysis",
                        "status": "completed",
                        "output": "Data Agent Analysis",
                        "artifacts": [
                            {
                                "type": "json",
                                "content": {
                                    "row_count": 2,
                                    "column_count": 2,
                                    "numeric_columns": {
                                        "revenue": {
                                            "sum": 300,
                                            "mean": 150,
                                            "min": 120,
                                            "max": 180,
                                        }
                                    },
                                },
                            },
                            {
                                "type": "query_result",
                                "content": {
                                    "metric": "revenue",
                                    "dimension": "region",
                                    "rows": [{"dimension": "North", "value": 180}],
                                },
                            },
                        ],
                        "sources": [{"type": "dataset", "title": "task.input"}],
                    },
                }
            },
        )
    )

    output = result["output"]
    assert "# Writing Agent Draft" in output
    assert "## Executive Summary" in output
    assert "Demand increased in enterprise accounts." in output
    assert "Dataset profile: 2 rows across 2 columns." in output
    assert "region North: 180." in output
    assert result["metadata"]["upstream_agents"] == ["research", "data_analysis"]


def test_review_agent_outputs_quality_gate_and_issue_list():
    agent = ReviewAgent()

    result = asyncio.run(
        agent.execute(
            {
                "id": "review-1",
                "type": "review",
                "description": "Review final brief",
                "input": "Check whether the brief can ship",
            },
            {
                "_agent_results": {
                    "step-1": {
                        "agent": "writing",
                        "status": "completed",
                        "output": "# Writing Agent Delivery Draft\n\nA sourced brief.",
                        "artifacts": [{"type": "markdown", "content": "# Draft"}],
                        "sources": [{"title": "Market source"}],
                    }
                }
            },
        )
    )

    output = result["output"]
    gate_artifact = next(item for item in result["artifacts"] if item["type"] == "quality_gate")

    assert "## Quality Gate" in output
    assert "- Passed: yes" in output
    assert result["metadata"]["quality_gate"] == "pass"
    assert result["metadata"]["passed"] is True
    assert gate_artifact["content"]["issues"] == []


def test_review_agent_blocks_when_no_upstream_content_exists():
    agent = ReviewAgent()

    result = asyncio.run(
        agent.execute(
            {
                "id": "review-2",
                "type": "review",
                "description": "Review missing deliverable",
                "input": "Can this ship?",
            },
            {"_agent_results": {}},
        )
    )

    gate_artifact = next(item for item in result["artifacts"] if item["type"] == "quality_gate")

    assert result["metadata"]["quality_gate"] == "fail"
    assert result["metadata"]["passed"] is False
    assert gate_artifact["content"]["issues"][0]["severity"] == "blocker"


def test_data_analysis_agent_profiles_structured_rows():
    state = asyncio.run(
        run_orchestrator(
            "analyze revenue data",
            plan=[
                {
                    "id": "step-1",
                    "agent": "data_analysis",
                    "task_type": "data_analysis",
                    "description": "Analyze revenue by region",
                    "input": {
                        "rows": [
                            {"region": "North", "revenue": 120, "orders": 4},
                            {"region": "South", "revenue": 180, "orders": 6},
                        ]
                    },
                    "status": "pending",
                    "requires_approval": False,
                }
            ],
        )
    )

    result = state["agent_results"]["step-1"]
    profile = result["artifacts"][0]["content"]

    assert state["status"] == "completed"
    assert "Data Agent Analysis" in result["output"]
    assert profile["row_count"] == 2
    assert profile["numeric_columns"]["revenue"]["sum"] == 300
    assert profile["categorical_columns"]["region"]["unique"] == 2
    assert result["sources"][0]["type"] == "dataset"


def test_data_analysis_agent_loads_csv_file_path(tmp_path):
    csv_path = tmp_path / "revenue.csv"
    csv_path.write_text("region,revenue,orders\nNorth,120,4\nSouth,180,6\n", encoding="utf-8")

    state = asyncio.run(
        run_orchestrator(
            "analyze uploaded CSV revenue data",
            plan=[
                {
                    "id": "step-1",
                    "agent": "data_analysis",
                    "task_type": "data_analysis",
                    "description": "Analyze CSV file",
                    "input": "Analyze uploaded CSV",
                    "status": "pending",
                    "requires_approval": False,
                    "metadata": {"file_path": str(csv_path)},
                }
            ],
        )
    )

    result = state["agent_results"]["step-1"]
    profile = result["artifacts"][0]["content"]

    assert state["status"] == "completed"
    assert result["metadata"]["source"] == "task.metadata.file_path"
    assert profile["row_count"] == 2
    assert profile["numeric_columns"]["revenue"]["mean"] == 150
    assert profile["categorical_columns"]["region"]["top_values"][0]["value"] == "North"


def test_data_analysis_agent_loads_json_file_path_from_task_input(tmp_path):
    json_path = tmp_path / "revenue.json"
    json_path.write_text(
        '[{"region":"North","revenue":120},{"region":"South","revenue":180}]',
        encoding="utf-8",
    )

    state = asyncio.run(
        run_orchestrator(
            "analyze JSON revenue data",
            plan=[
                {
                    "id": "step-1",
                    "agent": "data_analysis",
                    "task_type": "data_analysis",
                    "description": "Analyze JSON file",
                    "input": {"file_path": str(json_path)},
                    "status": "pending",
                    "requires_approval": False,
                }
            ],
        )
    )

    profile = state["agent_results"]["step-1"]["artifacts"][0]["content"]

    assert state["status"] == "completed"
    assert profile["row_count"] == 2
    assert profile["numeric_columns"]["revenue"]["sum"] == 300


def test_data_analysis_agent_answers_top_n_grouped_query():
    state = asyncio.run(
        run_orchestrator(
            "Show top 2 regions by revenue",
            plan=[
                {
                    "id": "step-1",
                    "agent": "data_analysis",
                    "task_type": "data_analysis",
                    "description": "Rank regions by revenue",
                    "input": "Show top 2 regions by revenue",
                    "status": "pending",
                    "requires_approval": False,
                    "metadata": {
                        "rows": [
                            {"region": "North", "revenue": 120},
                            {"region": "South", "revenue": 180},
                            {"region": "North", "revenue": 80},
                            {"region": "East", "revenue": 90},
                        ]
                    },
                }
            ],
        )
    )

    artifacts = state["agent_results"]["step-1"]["artifacts"]
    query_result = next(item["content"] for item in artifacts if item["type"] == "query_result")

    assert query_result["operation"] == "grouped_rank"
    assert query_result["metric"] == "revenue"
    assert query_result["dimension"] == "region"
    assert [row["dimension"] for row in query_result["rows"]] == ["North", "South"]
    assert [row["value"] for row in query_result["rows"]] == [200.0, 180.0]


def test_data_analysis_agent_filters_before_grouped_rank():
    state = asyncio.run(
        run_orchestrator(
            "Show top 1 regions by revenue where channel = online",
            plan=[
                {
                    "id": "step-1",
                    "agent": "data_analysis",
                    "task_type": "data_analysis",
                    "description": "Rank filtered regions by revenue",
                    "input": "Show top 1 regions by revenue where channel = online",
                    "status": "pending",
                    "requires_approval": False,
                    "metadata": {
                        "rows": [
                            {"region": "North", "channel": "online", "revenue": 120},
                            {"region": "South", "channel": "retail", "revenue": 240},
                            {"region": "North", "channel": "online", "revenue": 80},
                            {"region": "East", "channel": "online", "revenue": 90},
                        ]
                    },
                }
            ],
        )
    )

    artifacts = state["agent_results"]["step-1"]["artifacts"]
    query_result = next(item["content"] for item in artifacts if item["type"] == "query_result")

    assert query_result["operation"] == "grouped_rank"
    assert query_result["filters"] == [{"column": "channel", "operator": "=", "value": "online"}]
    assert query_result["rows"] == [{"dimension": "North", "value": 200.0, "count": 2, "sum": 200.0}]


def test_data_analysis_agent_supports_or_filter_groups():
    state = asyncio.run(
        run_orchestrator(
            "Show top 2 regions by revenue where channel = online or retail",
            plan=[
                {
                    "id": "step-1",
                    "agent": "data_analysis",
                    "task_type": "data_analysis",
                    "description": "Rank OR-filtered regions by revenue",
                    "input": "Show top 2 regions by revenue where channel = online or retail",
                    "status": "pending",
                    "requires_approval": False,
                    "metadata": {
                        "rows": [
                            {"region": "North", "channel": "online", "revenue": 120},
                            {"region": "South", "channel": "retail", "revenue": 240},
                            {"region": "North", "channel": "online", "revenue": 80},
                            {"region": "East", "channel": "partner", "revenue": 300},
                        ]
                    },
                }
            ],
        )
    )

    artifacts = state["agent_results"]["step-1"]["artifacts"]
    query_result = next(item["content"] for item in artifacts if item["type"] == "query_result")

    assert query_result["filter_groups"] == [
        [{"column": "channel", "operator": "=", "value": "online"}],
        [{"column": "channel", "operator": "=", "value": "retail"}],
    ]
    assert [row["dimension"] for row in query_result["rows"]] == ["South", "North"]
    assert [row["value"] for row in query_result["rows"]] == [240.0, 200.0]


def test_data_analysis_agent_supports_between_filter():
    state = asyncio.run(
        run_orchestrator(
            "Show top 2 regions by revenue where revenue between 100 and 200",
            plan=[
                {
                    "id": "step-1",
                    "agent": "data_analysis",
                    "task_type": "data_analysis",
                    "description": "Rank rows inside a revenue range",
                    "input": "Show top 2 regions by revenue where revenue between 100 and 200",
                    "status": "pending",
                    "requires_approval": False,
                    "metadata": {
                        "rows": [
                            {"region": "North", "revenue": 80},
                            {"region": "South", "revenue": 180},
                            {"region": "East", "revenue": 240},
                            {"region": "West", "revenue": 120},
                        ]
                    },
                }
            ],
        )
    )

    artifacts = state["agent_results"]["step-1"]["artifacts"]
    query_result = next(item["content"] for item in artifacts if item["type"] == "query_result")

    assert query_result["filters"] == [{"column": "revenue", "operator": "between", "value": [100.0, 200.0]}]
    assert [row["dimension"] for row in query_result["rows"]] == ["South", "West"]
    assert [row["value"] for row in query_result["rows"]] == [180.0, 120.0]


def test_data_analysis_agent_builds_average_line_chart_for_time_dimension():
    state = asyncio.run(
        run_orchestrator(
            "average revenue by month",
            plan=[
                {
                    "id": "step-1",
                    "agent": "data_analysis",
                    "task_type": "data_analysis",
                    "description": "Average revenue by month",
                    "input": "average revenue by month",
                    "status": "pending",
                    "requires_approval": False,
                    "metadata": {
                        "rows": [
                            {"month": "2024-01", "revenue": 100},
                            {"month": "2024-01", "revenue": 200},
                            {"month": "2024-02", "revenue": 300},
                            {"month": "2024-03", "revenue": 150},
                        ]
                    },
                }
            ],
        )
    )

    artifacts = state["agent_results"]["step-1"]["artifacts"]
    query_result = next(item["content"] for item in artifacts if item["type"] == "query_result")
    chart_spec = next(item["content"] for item in artifacts if item["type"] == "chart_spec")

    assert query_result["operation"] == "grouped_summary"
    assert query_result["aggregation"] == "avg"
    assert [row["value"] for row in query_result["rows"]] == [150.0, 300.0, 150.0]
    assert chart_spec["type"] == "line"
    assert chart_spec["labels"] == ["2024-01", "2024-02", "2024-03"]


def test_data_analysis_agent_reports_sampling_metadata():
    state = asyncio.run(
        run_orchestrator(
            "analyze sampled revenue data",
            context={
                "rows": [{"region": "North", "revenue": 120}, {"region": "South", "revenue": 180}],
                "data_sampling": {
                    "name": "large.csv",
                    "row_count": 600,
                    "sampled": True,
                    "sampled_row_count": 500,
                    "sample_limit": 500,
                },
            },
            plan=[
                {
                    "id": "step-1",
                    "agent": "data_analysis",
                    "task_type": "data_analysis",
                    "description": "Analyze sampled rows",
                    "input": "analyze sampled revenue data",
                    "status": "pending",
                    "requires_approval": False,
                }
            ],
        )
    )

    result = state["agent_results"]["step-1"]
    profile = result["artifacts"][0]["content"]

    assert "Sampling: showing 500 of 600 parsed rows" in result["output"]
    assert profile["sampling"]["sampled"] is True
    assert result["metadata"]["sampling"]["sample_limit"] == 500


def test_data_analysis_agent_outputs_dashboard_card_for_structured_data():
    state = asyncio.run(
        run_orchestrator(
            "Show top 2 regions by revenue",
            plan=[
                {
                    "id": "step-1",
                    "agent": "data_analysis",
                    "task_type": "data_analysis",
                    "description": "Rank regions by revenue",
                    "input": "Show top 2 regions by revenue",
                    "status": "pending",
                    "requires_approval": False,
                    "metadata": {
                        "rows": [
                            {"region": "North", "revenue": 120},
                            {"region": "South", "revenue": 180},
                            {"region": "North", "revenue": 80},
                            {"region": "East", "revenue": 90},
                        ]
                    },
                }
            ],
        )
    )

    result = state["agent_results"]["step-1"]
    match = re.search(r":::dashboard-card\s*\n([\s\S]*?)\n:::", result["output"])
    assert match is not None
    payload = json.loads(match.group(1))

    assert payload["title"] == "Data Agent Dashboard"
    assert payload["metrics"][0]["label"] == "Rows"
    assert payload["charts"][0]["chart_data"]["labels"] == ["North", "South"]
    assert payload["table"]["columns"][:2] == ["region", "revenue"]
    assert payload["evidence"][0]["source_type"] == "dataset"
    assert any(item["type"] == "dashboard_card" for item in result["artifacts"])


def test_data_analysis_agent_answers_bottom_row_query_without_dimension():
    state = asyncio.run(
        run_orchestrator(
            "bottom 1 by latency",
            plan=[
                {
                    "id": "step-1",
                    "agent": "data_analysis",
                    "task_type": "data_analysis",
                    "description": "Rank latency",
                    "input": "bottom 1 by latency",
                    "status": "pending",
                    "requires_approval": False,
                    "metadata": {
                        "rows": [
                            {"latency": 320, "errors": 2},
                            {"latency": 180, "errors": 4},
                            {"latency": 260, "errors": 1},
                        ]
                    },
                }
            ],
        )
    )

    artifacts = state["agent_results"]["step-1"]["artifacts"]
    query_result = next(item["content"] for item in artifacts if item["type"] == "query_result")

    assert query_result["operation"] == "row_rank"
    assert query_result["intent"] == "bottom"
    assert query_result["metric"] == "latency"
    assert query_result["rows"][0]["latency"] == 180.0


def test_orchestrator_waits_for_human_approval_before_running_step():
    registry = create_default_agent_registry()
    graph = build_orchestrator_graph(registry)

    state = asyncio.run(
        graph.ainvoke(
            {
                "user_request": "publish report",
                "context": {},
                "plan": [
                    {
                        "id": "step-1",
                        "agent": "writing",
                        "task_type": "writing",
                        "description": "Publish the report to external users",
                        "input": "publish report",
                        "status": "pending",
                        "requires_approval": True,
                        "metadata": {"action": "report_publish"},
                    }
                ],
                "current_step": 0,
                "agent_results": {},
                "final_output": "",
                "needs_human_approval": False,
                "errors": [],
                "status": "pending",
            }
        )
    )

    assert state["status"] == "waiting_approval"
    assert state["needs_human_approval"] is True
    assert state["approval_step_id"] == "step-1"
    assert state["plan"][0]["status"] == "waiting_approval"
    assert state["plan"][0]["approval_status"] == "pending"
    assert state["agent_results"] == {}


def test_resume_orchestrator_runs_approved_step():
    registry = create_default_agent_registry()
    graph = build_orchestrator_graph(registry)
    waiting_state = asyncio.run(
        graph.ainvoke(
            {
                "user_request": "publish report",
                "context": {"request_id": "approval-1"},
                "plan": [
                    {
                        "id": "step-1",
                        "agent": "writing",
                        "task_type": "writing",
                        "description": "Publish the report to external users",
                        "input": "publish report",
                        "status": "pending",
                        "requires_approval": True,
                        "metadata": {"action": "report_publish"},
                    }
                ],
                "current_step": 0,
                "agent_results": {},
                "final_output": "",
                "needs_human_approval": False,
                "errors": [],
                "status": "pending",
            }
        )
    )

    resumed_state = asyncio.run(
        resume_orchestrator(
            waiting_state,
            approval_decision="approved",
            approval_reviewer="owner-1",
            approval_comment="Approved for publication",
            registry=registry,
        )
    )

    assert resumed_state["status"] == "completed"
    assert resumed_state["plan"][0]["status"] == "completed"
    assert resumed_state["plan"][0]["approval_status"] == "approved"
    assert resumed_state["agent_results"]["step-1"]["status"] == "completed"
    assert resumed_state["plan"][0]["metadata"]["approval"]["reviewer"] == "owner-1"
    assert "Writing Agent" in resumed_state["final_output"]


def test_resume_orchestrator_skips_rejected_step_and_continues():
    registry = create_default_agent_registry()
    graph = build_orchestrator_graph(registry)
    waiting_state = asyncio.run(
        graph.ainvoke(
            {
                "user_request": "publish and review report",
                "context": {},
                "plan": [
                    {
                        "id": "step-1",
                        "agent": "writing",
                        "task_type": "writing",
                        "description": "Publish the report to external users",
                        "input": "publish report",
                        "status": "pending",
                        "requires_approval": True,
                        "metadata": {"action": "report_publish"},
                    },
                    {
                        "id": "step-2",
                        "agent": "review",
                        "task_type": "review",
                        "description": "Review the report internally",
                        "input": "review report",
                        "status": "pending",
                        "requires_approval": False,
                        "metadata": {},
                    },
                ],
                "current_step": 0,
                "agent_results": {},
                "final_output": "",
                "needs_human_approval": False,
                "errors": [],
                "status": "pending",
            }
        )
    )

    resumed_state = asyncio.run(
        resume_orchestrator(
            waiting_state,
            approval_decision="rejected",
            approval_reviewer="owner-2",
            approval_comment="External publishing is not approved",
            registry=registry,
        )
    )

    assert resumed_state["status"] == "completed"
    assert resumed_state["plan"][0]["status"] == "skipped"
    assert resumed_state["plan"][0]["approval_status"] == "rejected"
    assert resumed_state["agent_results"]["step-1"]["status"] == "rejected"
    assert resumed_state["plan"][1]["status"] == "completed"
    assert resumed_state["agent_results"]["step-2"]["status"] == "completed"
    assert "Writing Agent" not in resumed_state["final_output"]
    assert "QA Agent" in resumed_state["final_output"]


def test_apply_approval_decision_requires_approval_step():
    with pytest.raises(ValueError):
        apply_approval_decision(
            {
                "plan": [
                    {
                        "id": "step-1",
                        "agent": "general",
                        "task_type": "general",
                        "description": "No approval needed",
                        "status": "pending",
                        "requires_approval": False,
                        "metadata": {},
                    }
                ],
                "current_step": 0,
            },
            decision="approved",
        )
