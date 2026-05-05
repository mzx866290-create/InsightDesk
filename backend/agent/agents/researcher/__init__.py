"""Research Agent package."""

from backend.agent.agents.researcher.agent import DeepResearchAgent, ResearchAgentConfig
from backend.agent.agents.researcher.claim_extractor import extract_atomic_claims
from backend.agent.agents.researcher.claim_verifier import verify_atomic_claims
from backend.agent.agents.researcher.archive_reuse import (
    build_archive_reuse_context,
    summarize_reusable_archives,
)
from backend.agent.agents.researcher.contradiction import aggregate_contradictions
from backend.agent.agents.researcher.evidence_chain import (
    build_claim_evidence_chains,
    build_claim_verification_summary,
)
from backend.agent.agents.researcher.intent_classifier import classify_research_intent
from backend.agent.agents.researcher.plan_builder import build_fallback_research_plan
from backend.agent.agents.researcher.query_matrix import build_query_matrix, flatten_query_matrix
from backend.agent.agents.researcher.source_evaluator import (
    evaluate_research_sources,
    select_priority_sources,
)
from backend.agent.agents.researcher.synthesizer import (
    build_research_artifact,
    build_research_brief_sections,
)

__all__ = [
    "DeepResearchAgent",
    "ResearchAgentConfig",
    "aggregate_contradictions",
    "build_fallback_research_plan",
    "build_claim_evidence_chains",
    "build_archive_reuse_context",
    "build_claim_verification_summary",
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
]
