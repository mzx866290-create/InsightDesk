"""Stage 10: contradiction aggregation and escalation."""

from __future__ import annotations

from typing import Literal

from search_runtime.types import ClaimVerification, ResearchContradiction, WebResearchResult


def aggregate_contradictions(
    result: WebResearchResult,
    verifications: list[ClaimVerification],
) -> list[ResearchContradiction]:
    """Attach V2 resolution actions to discovered contradictions."""
    aggregated: list[ResearchContradiction] = []
    weak_claims = [item for item in verifications if item.status != "verified"]
    for item in result.contradictions:
        action: Literal["no_action", "clarify_in_output", "repair_search"] = (
            item.resolution_action or "clarify_in_output"
        )
        if weak_claims and item.sources:
            action = "repair_search"
        aggregated.append(
            ResearchContradiction(
                topic=item.topic,
                details=item.details,
                resolution_action=action,
                sources=list(item.sources),
            )
        )
    return aggregated


__all__ = ["aggregate_contradictions"]
