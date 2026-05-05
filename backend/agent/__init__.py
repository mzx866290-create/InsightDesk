"""Public exports for the split agent runtime package.

Exports are resolved lazily so orchestrator-only imports do not eagerly load the
document pipeline, transformers, or torch stack.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_SUBMODULES = {
    "builder",
    "builder_context",
    "builder_history",
    "builder_streaming",
    "builder_wrappers",
    "dashboard",
    "dashboard_attachments",
    "dashboard_payload",
    "fallbacks",
    "langgraph",
    "langgraph_helpers",
    "runtime_intent",
    "runtime_plain_chat",
    "runtime_support",
    "runtime_tools",
    "tools",
}

_EXPORTS: dict[str, tuple[str, str]] = {
    "apply_approval_decision": ("backend.agent.approval", "apply_approval_decision"),
    "AgentProtocol": ("backend.agent.protocols", "AgentProtocol"),
    "AgentResult": ("backend.agent.protocols", "AgentResult"),
    "AgentTask": ("backend.agent.protocols", "AgentTask"),
    "AgentRegistry": ("backend.agent.registry", "AgentRegistry"),
    "StaticAgent": ("backend.agent.registry", "StaticAgent"),
    "create_default_agent_registry": (
        "backend.agent.registry",
        "create_default_agent_registry",
    ),
    "create_runtime_agent_registry": (
        "backend.agent.registry",
        "create_runtime_agent_registry",
    ),
    "OrchestratorAgentMetric": ("backend.agent.state", "OrchestratorAgentMetric"),
    "OrchestratorPlanStep": ("backend.agent.state", "OrchestratorPlanStep"),
    "OrchestratorState": ("backend.agent.state", "OrchestratorState"),
    "DeepResearchAgent": ("backend.agent.agents.researcher", "DeepResearchAgent"),
    "ResearchAgentConfig": ("backend.agent.agents.researcher", "ResearchAgentConfig"),
    "ReviewAgent": ("backend.agent.agents.reviewer", "ReviewAgent"),
    "ReviewAgentConfig": ("backend.agent.agents.reviewer", "ReviewAgentConfig"),
    "DataAnalysisAgent": ("backend.agent.agents.data_analysis", "DataAnalysisAgent"),
    "DataAnalysisAgentConfig": (
        "backend.agent.agents.data_analysis",
        "DataAnalysisAgentConfig",
    ),
    "ModelCompareAgent": ("backend.agent.agents.model_compare", "ModelCompareAgent"),
    "ModelCompareAgentConfig": (
        "backend.agent.agents.model_compare",
        "ModelCompareAgentConfig",
    ),
    "WritingAgent": ("backend.agent.agents.writer", "WritingAgent"),
    "WritingAgentConfig": ("backend.agent.agents.writer", "WritingAgentConfig"),
    "build_orchestrator_graph": (
        "backend.agent.orchestrator",
        "build_orchestrator_graph",
    ),
    "create_plan": ("backend.agent.orchestrator", "create_plan"),
    "infer_task_types": ("backend.agent.orchestrator", "infer_task_types"),
    "resume_orchestrator": ("backend.agent.orchestrator", "resume_orchestrator"),
    "resume_orchestrator_sync": (
        "backend.agent.orchestrator",
        "resume_orchestrator_sync",
    ),
    "run_orchestrator": ("backend.agent.orchestrator", "run_orchestrator"),
    "run_orchestrator_sync": ("backend.agent.orchestrator", "run_orchestrator_sync"),
    "build_runtime_tools": ("backend.agent.runtime_tools", "build_runtime_tools"),
    "create_tools": ("backend.agent.tools", "create_tools"),
    "AgentState": ("backend.agent.langgraph_helpers", "AgentState"),
    "_rewrite_search_query": ("backend.agent.langgraph_helpers", "_rewrite_search_query"),
    "build_langgraph_agent": ("backend.agent.langgraph", "build_langgraph_agent"),
    "build_agent": ("backend.agent.builder", "build_agent"),
    "test_agent": ("backend.agent.builder", "test_agent"),
    "_build_session_memory_message": (
        "backend.agent.history",
        "_build_session_memory_message",
    ),
    "CHAT_FILE_CONTEXT_END_MARKER": (
        "backend.agent.history",
        "CHAT_FILE_CONTEXT_END_MARKER",
    ),
    "CHAT_FILE_CONTEXT_START_MARKER": (
        "backend.agent.history",
        "CHAT_FILE_CONTEXT_START_MARKER",
    ),
    "clear_session_history": ("backend.agent.history", "clear_session_history"),
    "_looks_like_reasoning_only_output": (
        "backend.agent.runtime_intent",
        "_looks_like_reasoning_only_output",
    ),
    "_ainvoke_llm_with_timeout": (
        "backend.agent.llm",
        "_ainvoke_llm_with_timeout",
    ),
    "_strip_think_tags": ("backend.agent.llm", "_strip_think_tags"),
    "get_llm": ("backend.agent.connection", "get_llm"),
    "normalize_connection_type": (
        "backend.agent.connection",
        "normalize_connection_type",
    ),
    "list_enabled_builtin_tool_specs": (
        "backend.agent.tool_registry",
        "list_enabled_builtin_tool_specs",
    ),
    "load_mcp_tool_overrides": (
        "backend.agent_mcp_helpers",
        "load_mcp_tool_overrides",
    ),
}

for _name in (
    "aggregate_contradictions",
    "build_archive_reuse_context",
    "build_claim_evidence_chains",
    "build_claim_verification_summary",
    "build_fallback_research_plan",
    "build_query_matrix",
    "build_research_artifact",
    "build_research_brief_sections",
    "classify_research_intent",
    "evaluate_research_sources",
    "extract_atomic_claims",
    "flatten_query_matrix",
    "select_priority_sources",
    "summarize_reusable_archives",
    "verify_atomic_claims",
):
    _EXPORTS[_name] = ("backend.agent.agents.researcher", _name)

for _name in (
    "_build_plain_text_chat_messages",
    "_direct_plain_text_answer",
    "_astream_plain_text_answer",
    "_heuristic_langgraph_tool_choice",
    "_should_bypass_tools_for_plain_text_chat",
):
    _EXPORTS[_name] = ("backend.agent.runtime_plain_chat", _name)

for _name in (
    "_attach_configured_task_meta",
    "_build_invocation_config",
    "_build_workflow_snapshot",
    "_configurable_list",
    "_configurable_value",
):
    _EXPORTS[_name] = ("backend.agent.builder_context", _name)

for _name in (
    "_load_chat_history",
    "_persist_agent_result_history",
    "_persist_output_history",
    "_persist_panel_history",
):
    _EXPORTS[_name] = ("backend.agent.builder_history", _name)

for _name in (
    "_ainvoke_agent_wrapper",
    "_astream_langgraph_wrapper",
):
    _EXPORTS[_name] = ("backend.agent.builder_streaming", _name)

for _name in (
    "_extract_attachment_evidence",
    "_build_attachment_dashboard_fallback",
    "_coerce_dashboard_cell_value",
):
    _EXPORTS[_name] = ("backend.agent.dashboard_attachments", _name)

for _name in (
    "DASHBOARD_TRIGGER_KEYWORDS",
    "DEFAULT_DASHBOARD_TEMPLATE",
    "_build_dashboard_sources",
    "_extract_json_payload",
    "_normalize_dashboard_template",
    "_parse_numeric_dashboard_value",
    "_render_attachment_dashboard_card",
    "_render_dashboard_card",
    "_sanitize_dashboard_payload",
    "_should_generate_dashboard",
):
    _EXPORTS[_name] = ("backend.agent.dashboard_payload", _name)

for _name in (
    "_generate_dashboard_from_attachment",
    "_generate_dashboard_from_knowledge",
):
    _EXPORTS[_name] = ("backend.agent.dashboard", _name)

__all__ = sorted([*_SUBMODULES, *_EXPORTS])


def __getattr__(name: str) -> Any:
    if name in _SUBMODULES:
        value = import_module(f"backend.agent.{name}")
        globals()[name] = value
        return value
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value
