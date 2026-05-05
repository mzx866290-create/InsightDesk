"""Stage 12: claim-level evidence chain assembly."""

from __future__ import annotations

from collections import Counter
from typing import Any

from search_runtime.types import (
    AtomicClaim,
    ClaimVerification,
    ResearchContradiction,
    ResearchSource,
)


def _normalize_label(value: object) -> str:
    return str(value or "").strip().lower()


def _source_labels(index: int, source: ResearchSource) -> set[str]:
    return {
        label
        for label in {
            str(index),
            f"source-{index}",
            f"source_{index}",
            source.doc.doc_id,
            source.doc.url,
            source.doc.title,
        }
        if _normalize_label(label)
    }


def _indexed_sources(sources: list[ResearchSource]) -> list[tuple[int, ResearchSource, set[str]]]:
    return [
        (index, source, {_normalize_label(label) for label in _source_labels(index, source)})
        for index, source in enumerate(sources, start=1)
    ]


def _verification_by_claim(
    verifications: list[ClaimVerification],
) -> dict[str, ClaimVerification]:
    return {item.claim_id: item for item in verifications}


def _match_sources(
    claim: AtomicClaim,
    verification: ClaimVerification | None,
    sources: list[tuple[int, ResearchSource, set[str]]],
) -> list[tuple[int, ResearchSource]]:
    labels = {_normalize_label(label) for label in claim.candidate_sources}
    if verification:
        labels.update(_normalize_label(label) for label in verification.supporting_sources)
    labels.discard("")

    matched: list[tuple[int, ResearchSource]] = []
    for index, source, source_labels in sources:
        if labels.intersection(source_labels):
            matched.append((index, source))
    return matched


def _source_payload(index: int, source: ResearchSource) -> dict[str, object]:
    source_id = source.doc.doc_id or source.doc.url or f"source-{index}"
    payload: dict[str, object] = {
        "source_id": source_id,
        "doc_id": source.doc.doc_id,
        "source_index": index,
        "title": source.doc.title or source.doc.url or source.doc.doc_id,
        "url": source.doc.url,
        "domain": source.doc.domain,
        "provider": source.doc.provider,
        "source_tier": source.source_tier,
        "source_family": source.source_family,
        "freshness_band": source.freshness_band,
        "published_at": source.doc.published_at,
        "snippet": (source.doc.raw_text or source.doc.snippet)[:500],
        "selection_reason": source.selection_reason,
        "citation_label": f"[{index}]",
    }
    if source.provider_caveat:
        payload["provider_caveat"] = source.provider_caveat
    return payload


def build_claim_evidence_chains(
    claims: list[AtomicClaim],
    sources: list[ResearchSource],
    verifications: list[ClaimVerification],
) -> list[dict[str, object]]:
    """Build deterministic, claim-level evidence chains for Research V2 artifacts."""
    source_index = _indexed_sources(sources)
    verification_index = _verification_by_claim(verifications)

    chains: list[dict[str, object]] = []
    for claim in claims:
        verification = verification_index.get(claim.claim_id)
        matched_sources = _match_sources(claim, verification, source_index)
        families = sorted(
            {
                source.source_family
                for _, source in matched_sources
                if source.source_family
            }
        )
        source_items = [_source_payload(index, source) for index, source in matched_sources]
        supporting_source_ids = [
            str(item.get("source_id") or item.get("url") or "")
            for item in source_items
            if str(item.get("source_id") or item.get("url") or "").strip()
        ]

        status = verification.status if verification else "unverified"
        strength = verification.evidence_strength if verification else "low"
        chains.append(
            {
                "claim_id": claim.claim_id,
                "claim_text": claim.text,
                "facet": claim.facet,
                "claim_type": claim.claim_type,
                "date": claim.date,
                "status": status,
                "evidence_strength": strength,
                "verification_note": verification.verification_note if verification else "no verification found",
                "candidate_sources": list(claim.candidate_sources),
                "supporting_source_count": len(source_items),
                "supporting_source_ids": supporting_source_ids,
                "independent_source_families": families,
                "has_primary_source": any(source.source_tier == "primary" for _, source in matched_sources),
                "needs_attention": status != "verified",
                "sources": source_items,
            }
        )
    return chains


def build_claim_verification_summary(
    evidence_chains: list[dict[str, object]],
    contradictions: list[ResearchContradiction],
) -> dict[str, object]:
    """Summarize claim verification coverage for quick UI and audit checks."""
    status_counts = Counter(str(item.get("status") or "unverified") for item in evidence_chains)
    strength_counts = Counter(str(item.get("evidence_strength") or "low") for item in evidence_chains)
    resolution_counts = Counter(item.resolution_action for item in contradictions)
    attention_claims = [
        str(item.get("claim_id"))
        for item in evidence_chains
        if item.get("needs_attention")
    ]

    return {
        "total_claims": len(evidence_chains),
        "verified_claims": status_counts.get("verified", 0),
        "partial_claims": status_counts.get("partial", 0),
        "unverified_claims": status_counts.get("unverified", 0),
        "high_strength_claims": strength_counts.get("high", 0),
        "medium_strength_claims": strength_counts.get("medium", 0),
        "low_strength_claims": strength_counts.get("low", 0),
        "claims_needing_attention": attention_claims,
        "contradiction_count": len(contradictions),
        "resolution_actions": dict(resolution_counts),
    }


__all__ = ["build_claim_evidence_chains", "build_claim_verification_summary"]
