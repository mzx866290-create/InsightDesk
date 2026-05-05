"""Stage 10: contradiction aggregation and escalation."""

from __future__ import annotations

from search_runtime.types import ClaimVerification, ResearchContradiction, WebResearchResult


def aggregate_contradictions(
    result: WebResearchResult,
    verifications: list[ClaimVerification],
) -> list[ResearchContradiction]:
    """Attach V2 resolution actions to discovered contradictions."""
    aggregated: list[ResearchContradiction] = []
    weak_claims = [item for item in verifications if item.status != "verified"]
    for item in result.contradictions:
        action = item.resolution_action or "clarify_in_output"
        if weak_claims and item.sources:
            action = "repair_search"
        aggregated.append(
            ResearchContradiction(
                topic=item.topic,
                details=item.details,
                resolution_action=action,  # type: ignore[arg-type]
                sources=list(item.sources),
            )
        )
    return aggregated


__all__ = ["aggregate_contradictions"]
