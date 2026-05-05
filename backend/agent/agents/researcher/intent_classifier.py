"""Stage 1: research intent and scope classification."""

from __future__ import annotations

from search_runtime.research_service import _infer_research_intent
from search_runtime.types import ResearchIntent


def classify_research_intent(
    query: str,
    *,
    time_range: str | None = None,
) -> ResearchIntent:
    """Classify a research request using the shared search runtime rules."""
    return _infer_research_intent(query, time_range)


__all__ = ["classify_research_intent"]
