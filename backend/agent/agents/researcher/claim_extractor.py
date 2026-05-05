"""Stage 8: atomic claim extraction."""

from __future__ import annotations

import re

from search_runtime.types import AtomicClaim, WebResearchResult


_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:%|亿美元|亿元|million|billion|trillion)?", re.IGNORECASE)


def _claim_type(text: str) -> str:
    lowered = text.lower()
    if _NUMBER_RE.search(text):
        return "data_point"
    if any(term in lowered for term in ("policy", "regulation", "监管", "政策", "合规")):
        return "policy_signal"
    if any(term in lowered for term in ("forecast", "outlook", "预计", "预测", "展望")):
        return "forecast"
    if any(term in lowered for term in ("trend", "增长", "下降", "回升", "趋势")):
        return "market_trend"
    return "event"


def extract_atomic_claims(
    result: WebResearchResult,
    *,
    max_claims: int = 24,
) -> list[AtomicClaim]:
    """Extract bounded atomic claims from findings and highlights."""
    candidates: list[tuple[str, list[str]]] = []
    for finding in result.findings:
        candidates.append((finding.claim, list(finding.evidence)))
    for highlight in result.highlights:
        candidates.append((highlight, []))

    claims: list[AtomicClaim] = []
    seen: set[str] = set()
    for raw_text, evidence in candidates:
        text = re.sub(r"\s+", " ", str(raw_text or "")).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        date_match = _DATE_RE.search(text)
        fallback_sources = [f"source-{index}" for index in range(1, min(3, len(result.sources)) + 1)]
        claims.append(
            AtomicClaim(
                claim_id=f"claim-{len(claims) + 1:03d}",
                facet=(result.research_plan.facets[0] if result.research_plan and result.research_plan.facets else "overview"),
                text=text,
                claim_type=_claim_type(text),  # type: ignore[arg-type]
                date=date_match.group(1) if date_match else None,
                candidate_sources=evidence or fallback_sources,
            )
        )
        if len(claims) >= max(1, int(max_claims or 1)):
            break
    return claims


__all__ = ["extract_atomic_claims"]
