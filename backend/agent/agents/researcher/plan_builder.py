"""Stage 2-4: research plan, facets, and query matrix fallback building."""

from __future__ import annotations

from search_runtime.research_service import (
    _default_budget,
    _generic_facets_for_intent,
    _parse_plan_payload,
    _resolve_domain_template,
)
from search_runtime.types import ResearchPlan

from backend.agent.agents.researcher.intent_classifier import classify_research_intent


def build_fallback_research_plan(
    query: str,
    *,
    time_range: str | None = None,
    max_rounds: int = 2,
    max_fetch_pages: int = 3,
) -> ResearchPlan:
    """Build the deterministic plan used when an LLM planner cannot provide JSON."""
    intent = classify_research_intent(query, time_range=time_range)
    template_match = _resolve_domain_template(query)
    template_id = None
    template_facets: list[str] = []
    if template_match:
        template_id = str(template_match.get("template_id") or "").strip() or None
        template_facets = [
            str(item).strip()
            for item in template_match.get("facets", [])
            if str(item).strip()
        ]

    return _parse_plan_payload(
        None,
        query=query,
        template_id=template_id,
        template_facets=template_facets,
        generic_facets=_generic_facets_for_intent(intent),
        intent=intent,
        budget=_default_budget(max_rounds=max_rounds, max_fetch_pages=max_fetch_pages),
    )


__all__ = ["build_fallback_research_plan"]
