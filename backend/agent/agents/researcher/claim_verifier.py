"""Stage 9: claim verification."""

from __future__ import annotations

from search_runtime.types import AtomicClaim, ClaimVerification, ResearchPlan, ResearchSource


def _source_lookup(sources: list[ResearchSource]) -> dict[str, ResearchSource]:
    lookup: dict[str, ResearchSource] = {}
    for index, source in enumerate(sources, 1):
        labels = {
            str(index),
            f"source-{index}",
            f"source_{index}",
            source.doc.doc_id,
            source.doc.url,
            source.doc.title,
        }
        for label in labels:
            key = str(label or "").strip().lower()
            if key:
                lookup[key] = source
    return lookup


def verify_atomic_claims(
    claims: list[AtomicClaim],
    sources: list[ResearchSource],
    *,
    plan: ResearchPlan | None = None,
) -> list[ClaimVerification]:
    """Verify claims using source independence and plan evidence policies."""
    lookup = _source_lookup(sources)
    min_families = 2
    require_date = False
    if plan:
        min_families = int(plan.evidence_policy.get("min_independent_families_per_claim", 2) or 2)
        require_date = bool(plan.evidence_policy.get("require_date_for_time_sensitive_claims", False))

    verifications: list[ClaimVerification] = []
    for claim in claims:
        matched_sources: list[ResearchSource] = []
        for raw_label in claim.candidate_sources:
            key = str(raw_label or "").strip().lower()
            source = lookup.get(key)
            if source is not None and source not in matched_sources:
                matched_sources.append(source)
        if not matched_sources and sources:
            evidence_fallback = [source for source in sources if source.adoption_role == "evidence"]
            matched_sources = evidence_fallback[:1] or sources[:1]

        evidence_sources = [
            source for source in matched_sources if source.adoption_role == "evidence"
        ]
        ineligible_sources = [
            source for source in matched_sources if source.adoption_role != "evidence"
        ]
        families = {source.source_family for source in evidence_sources if source.source_family}
        has_primary = any(source.source_tier == "primary" for source in evidence_sources)
        has_date = bool(claim.date)
        supporting = [
            source.doc.title or source.doc.url or source.doc.doc_id
            for source in evidence_sources
        ]

        if claim.claim_type == "policy_signal" and has_primary:
            status = "verified"
            strength = "high"
            note = "policy claim has primary-source support"
        elif len(families) >= min_families:
            status = "verified"
            strength = "high" if has_primary else "medium"
            note = f"supported by {len(families)} independent source families"
        elif evidence_sources:
            status = "partial"
            strength = "medium" if has_primary else "low"
            note = "supported by limited or single-family evidence"
        else:
            status = "unverified"
            strength = "low"
            note = "no eligible evidence source matched"

        if ineligible_sources:
            blocked_roles = sorted({source.adoption_role for source in ineligible_sources})
            note = f"{note}; ignored non-evidence source roles: {', '.join(blocked_roles)}"

        if require_date and claim.claim_type in {"event", "data_point", "policy_signal"} and not has_date:
            if status == "verified":
                status = "partial"
            strength = "low" if strength == "medium" else strength
            note = f"{note}; exact date is missing"

        verifications.append(
            ClaimVerification(
                claim_id=claim.claim_id,
                status=status,  # type: ignore[arg-type]
                evidence_strength=strength,  # type: ignore[arg-type]
                supporting_sources=supporting,
                verification_note=note,
            )
        )
    return verifications


__all__ = ["verify_atomic_claims"]
