"""Stage 11: structured research artifact synthesis."""

from __future__ import annotations

import re

from search_runtime.types import (
    AtomicClaim,
    ClaimVerification,
    ResearchContradiction,
    ResearchSource,
    WebResearchResult,
)


def _source_id(source: ResearchSource, index: int) -> str:
    return source.doc.doc_id or source.doc.url or f"source-{index}"


def _build_citation_panel_payload(
    *,
    evaluated_sources: list[ResearchSource],
    evidence_chains: list[dict[str, object]],
    verification_summary: dict[str, object] | None,
    reused_archives: dict[str, object] | None,
    archive_conflict_review: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build a backend-shaped payload that CitationPanel can consume directly."""
    source_index = {
        _source_id(source, index): {
            "source_id": _source_id(source, index),
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
        }
        for index, source in enumerate(evaluated_sources, start=1)
    }
    claim_source_links: list[dict[str, object]] = []
    for chain in evidence_chains:
        claim_id = str(chain.get("claim_id") or "").strip()
        for source_id in chain.get("supporting_source_ids", []):
            source_id_text = str(source_id or "").strip()
            if claim_id and source_id_text:
                claim_source_links.append(
                    {
                        "claim_id": claim_id,
                        "source_id": source_id_text,
                        "link_type": "supports",
                    }
                )
    archive_claim_source_links = _build_archive_claim_source_links(reused_archives)
    archive_conflict_links = _build_archive_conflict_links(archive_conflict_review)

    return {
        "version": "v2",
        "claim_evidence_chains": list(evidence_chains),
        "claim_verification_summary": verification_summary or {},
        "source_index": source_index,
        "claim_source_links": claim_source_links,
        "archive_claim_source_links": archive_claim_source_links,
        "archive_conflict_links": archive_conflict_links,
        "archive_conflict_review": archive_conflict_review
        or {"status": "not_applicable", "conflict_count": 0, "conflicts": [], "review_action": "none"},
        "reused_archives": reused_archives or {"enabled": False, "candidate_count": 0, "candidates": []},
    }


def _build_archive_conflict_links(
    archive_conflict_review: dict[str, object] | None,
) -> list[dict[str, object]]:
    """Expose current-vs-archive conflict edges for CitationPanel consumers."""
    if not isinstance(archive_conflict_review, dict):
        return []
    conflicts = archive_conflict_review.get("conflicts")
    if not isinstance(conflicts, list):
        return []

    links: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for conflict in conflicts:
        if not isinstance(conflict, dict):
            continue
        claim_id = str(conflict.get("claim_id") or "").strip()
        archive_id = str(conflict.get("archive_id") or "").strip()
        archive_claim_id = str(conflict.get("archive_claim_id") or "").strip()
        if not claim_id or not archive_id or not archive_claim_id:
            continue
        key = (claim_id, archive_id, archive_claim_id)
        if key in seen:
            continue
        seen.add(key)
        links.append(
            {
                "claim_id": claim_id,
                "archive_id": archive_id,
                "archive_claim_id": archive_claim_id,
                "link_type": "archive_conflicts",
                "severity": str(conflict.get("severity") or "needs_review"),
                "resolution_action": str(
                    conflict.get("resolution_action") or "compare_current_and_archive_sources"
                ),
            }
        )
    return links


def _build_archive_claim_source_links(
    reused_archives: dict[str, object] | None,
) -> list[dict[str, object]]:
    """Expose reused archive claim-source edges for CitationPanel consumers."""
    if not isinstance(reused_archives, dict):
        return []
    candidates = reused_archives.get("candidates")
    if not isinstance(candidates, list):
        return []

    links: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        archive_id = str(candidate.get("archive_id") or candidate.get("artifact_id") or "").strip()
        matched_claims = candidate.get("matched_claims")
        if not archive_id or not isinstance(matched_claims, list):
            continue
        for claim in matched_claims:
            if not isinstance(claim, dict):
                continue
            claim_id = str(claim.get("claim_id") or "").strip()
            source_ids = claim.get("source_ids")
            if not claim_id or not isinstance(source_ids, list):
                continue
            for source_id in source_ids:
                source_id_text = str(source_id or "").strip()
                key = (archive_id, claim_id, source_id_text)
                if not source_id_text or key in seen:
                    continue
                seen.add(key)
                links.append(
                    {
                        "archive_id": archive_id,
                        "claim_id": claim_id,
                        "source_id": source_id_text,
                        "link_type": "archive_supports",
                    }
                )
    return links


def _build_archive_conflict_review(
    atomic_claims: list[AtomicClaim],
    reused_archives: dict[str, object] | None,
) -> dict[str, object]:
    """Flag likely current-vs-archive claim conflicts without making a hard fact judgment."""
    if not atomic_claims or not isinstance(reused_archives, dict):
        return {"status": "not_applicable", "conflict_count": 0, "conflicts": [], "review_action": "none"}

    candidates = reused_archives.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return {"status": "not_applicable", "conflict_count": 0, "conflicts": [], "review_action": "none"}

    conflicts: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for claim in atomic_claims:
        current_text = claim.text.strip()
        if not current_text:
            continue
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            archive_id = str(candidate.get("archive_id") or candidate.get("artifact_id") or "").strip()
            matched_claims = candidate.get("matched_claims")
            if not archive_id or not isinstance(matched_claims, list):
                continue
            for archive_claim in matched_claims:
                if not isinstance(archive_claim, dict):
                    continue
                archive_claim_id = str(archive_claim.get("claim_id") or "").strip()
                archive_text = str(archive_claim.get("claim_text") or "").strip()
                if not archive_claim_id or not archive_text:
                    continue
                if not _claims_likely_conflict(current_text, archive_text):
                    continue
                key = (claim.claim_id, archive_id, archive_claim_id)
                if key in seen:
                    continue
                seen.add(key)
                conflicts.append(
                    {
                        "claim_id": claim.claim_id,
                        "claim_text": current_text,
                        "archive_id": archive_id,
                        "archive_claim_id": archive_claim_id,
                        "archive_claim_text": archive_text,
                        "severity": "needs_review",
                        "resolution_action": "compare_current_and_archive_sources",
                    }
                )

    return {
        "status": "conflicts_found" if conflicts else "clear",
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "review_action": "resolve_archive_conflicts" if conflicts else "none",
    }


def _claims_likely_conflict(current_text: str, archive_text: str) -> bool:
    shared_tokens = _content_tokens(current_text) & _content_tokens(archive_text)
    if len(shared_tokens) < 3:
        return False

    current_polarity = _directional_polarity(current_text)
    archive_polarity = _directional_polarity(archive_text)
    if current_polarity and archive_polarity and current_polarity != archive_polarity:
        return True

    return _has_negation(current_text) != _has_negation(archive_text)


def _directional_polarity(text: str) -> str:
    normalized = text.lower()
    positive_markers = {
        "adopt",
        "adopting",
        "adoption",
        "increase",
        "increased",
        "growth",
        "grew",
        "rise",
        "rising",
        "pilot",
        "piloting",
        "support",
        "supported",
    }
    negative_markers = {
        "decline",
        "declined",
        "decrease",
        "decreased",
        "fall",
        "falling",
        "reject",
        "rejected",
        "stalled",
        "slowdown",
        "unsupported",
    }
    if any(marker in normalized for marker in negative_markers):
        return "negative"
    if any(marker in normalized for marker in positive_markers):
        return "positive"
    return ""


def _has_negation(text: str) -> bool:
    return bool(
        re.search(
            r"\b(no|not|never|without|neither|nor|cannot|can't|isn't|aren't|wasn't|weren't)\b",
            text.lower(),
        )
    )


def _content_tokens(text: str) -> set[str]:
    stop_words = {
        "and",
        "are",
        "for",
        "from",
        "has",
        "have",
        "that",
        "the",
        "this",
        "with",
    }
    return {
        token
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
        if token not in stop_words
    }


def build_research_brief_sections(
    result: WebResearchResult,
    verifications: list[ClaimVerification],
    contradictions: list[ResearchContradiction],
    verification_summary: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build product-facing V2 brief sections."""
    verified_ids = {item.claim_id for item in verifications if item.status == "verified"}
    partial_ids = {item.claim_id for item in verifications if item.status == "partial"}
    return {
        "executive_summary": result.summary or result.answer,
        "key_trends": list(result.highlights),
        "verified_findings": [item.claim_id for item in verifications if item.claim_id in verified_ids],
        "partial_findings": [item.claim_id for item in verifications if item.claim_id in partial_ids],
        "contradictions": [
            {
                "topic": item.topic,
                "details": item.details,
                "resolution_action": item.resolution_action,
                "sources": list(item.sources),
            }
            for item in contradictions
        ],
        "source_notes": result.provider_summary,
        "research_caveats": list(result.caveats),
        "verification_summary": verification_summary or {},
    }


def build_research_artifact(
    result: WebResearchResult,
    *,
    evaluated_sources: list[ResearchSource],
    atomic_claims: list[AtomicClaim],
    verifications: list[ClaimVerification],
    contradictions: list[ResearchContradiction],
    evidence_chains: list[dict[str, object]] | None = None,
    verification_summary: dict[str, object] | None = None,
    reused_archives: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build the persisted V2 artifact stored in Agent result payloads."""
    chains = list(evidence_chains or [])
    archive_conflict_review = _build_archive_conflict_review(atomic_claims, reused_archives)
    return {
        "type": "research_report",
        "version": "v2",
        "query": result.query,
        "summary": result.summary,
        "highlights": list(result.highlights),
        "research_intent": result.research_intent.__dict__ if result.research_intent else None,
        "research_plan": {
            "topic": result.research_plan.topic,
            "facets": list(result.research_plan.facets),
            "template_id": result.research_plan.template_id,
            "resolution_strategy": result.research_plan.resolution_strategy,
            "source_policy": dict(result.research_plan.source_policy),
            "evidence_policy": dict(result.research_plan.evidence_policy),
            "caveats": list(result.research_plan.caveats),
        }
        if result.research_plan
        else None,
        "sources": [
            source.to_payload(index)
            for index, source in enumerate(evaluated_sources, start=1)
        ],
        "atomic_claims": [claim.to_payload() for claim in atomic_claims],
        "claim_verifications": [verification.to_payload() for verification in verifications],
        "claim_evidence_chains": chains,
        "claim_verification_summary": verification_summary or {},
        "reused_archives": reused_archives or {"enabled": False, "candidate_count": 0, "candidates": []},
        "archive_conflict_review": archive_conflict_review,
        "citation_panel": _build_citation_panel_payload(
            evaluated_sources=evaluated_sources,
            evidence_chains=chains,
            verification_summary=verification_summary,
            reused_archives=reused_archives,
            archive_conflict_review=archive_conflict_review,
        ),
        "contradictions": [
            {
                "topic": item.topic,
                "details": item.details,
                "resolution_action": item.resolution_action,
                "sources": list(item.sources),
            }
            for item in contradictions
        ],
        "rounds": [
            {
                "name": round_item.name,
                "queries": list(round_item.queries),
                "source_count": round_item.source_count,
                "highlights": list(round_item.highlights),
            }
            for round_item in result.rounds
        ],
        "workflow_nodes": list(result.workflow_nodes),
        "caveats": list(result.caveats),
        "brief_sections": build_research_brief_sections(
            result,
            verifications,
            contradictions,
            verification_summary,
        ),
    }


__all__ = ["build_research_artifact", "build_research_brief_sections"]
