"""Stage 6-7: source normalization, bucketing, and priority selection."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from urllib.parse import urlparse

from search_runtime.types import ResearchPlan, ResearchSource, SearchDocument

PRIMARY_DOMAIN_HINTS = (
    ".gov",
    "gov.cn",
    "pbc.gov.cn",
    "csrc.gov.cn",
    "nfra.gov.cn",
    "stats.gov.cn",
    "sec.gov",
    "federalreserve.gov",
    "europa.eu",
    "who.int",
    "worldbank.org",
    "imf.org",
)
SECONDARY_DOMAIN_HINTS = (
    "reuters.com",
    "bloomberg.com",
    "ft.com",
    "wsj.com",
    "economist.com",
    "caixin.com",
    "yicai.com",
)
LOW_TRUST_DOMAIN_HINTS = (
    "reddit.com",
    "quora.com",
    "zhihu.com",
    "weibo.com",
)
QUALITY_FLAG_LOW_TRUST = "low_trust_domain"
QUALITY_FLAG_LOW_CONFIDENCE = "low_confidence"
QUALITY_FLAG_LOW_SOURCE_QUALITY = "low_source_quality"
QUALITY_FLAG_STALE = "stale_source"
QUALITY_FLAG_UNKNOWN_FRESHNESS = "unknown_freshness"
QUALITY_FLAG_TERTIARY = "tertiary_source"
QUALITY_FLAG_SNIPPET_ONLY = "snippet_only"
QUALITY_FLAG_DETAILED_LOW_TRUST = "detailed_low_trust"
QUALITY_FLAG_RATIO_EXCEEDED = "low_trust_ratio_exceeded"

TIER_HEAT = {"primary": 1.0, "secondary": 0.7, "tertiary": 0.3}
FRESHNESS_HEAT = {"7d": 1.0, "30d": 0.85, "90d": 0.62, "stale": 0.25, "unknown": 0.35}


def _normalize_domain(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    if "://" in raw:
        raw = urlparse(raw).netloc
    return raw.removeprefix("www.")


def _source_family(document: SearchDocument) -> str:
    domain = _normalize_domain(document.domain or document.url)
    if not domain:
        return str(document.provider or "unknown").strip().lower() or "unknown"
    parts = [part for part in domain.split(".") if part]
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return domain


def _source_tier(document: SearchDocument) -> str:
    domain = _normalize_domain(document.domain or document.url)
    if any(hint in domain for hint in PRIMARY_DOMAIN_HINTS):
        return "primary"
    if any(hint in domain for hint in SECONDARY_DOMAIN_HINTS):
        return "secondary"
    if any(hint in domain for hint in LOW_TRUST_DOMAIN_HINTS):
        return "tertiary"
    if document.trust_score is not None and document.trust_score >= 0.72:
        return "secondary"
    return "tertiary"


def _clamp(value: float, *, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _normalized_score(value: float | None, default: float) -> float:
    if value is None:
        return default
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if 0.0 <= numeric <= 1.0:
        return numeric
    return _clamp(numeric / 100.0 if numeric > 10 else numeric / 10.0)


def _freshness_band(document: SearchDocument) -> str:
    raw_date = str(document.published_at or document.fetched_at or "").strip()
    if not raw_date:
        return "unknown"
    match = re.search(r"\d{4}-\d{2}-\d{2}", raw_date)
    if not match:
        return "unknown"
    try:
        published = datetime.fromisoformat(match.group(0)).replace(tzinfo=UTC)
    except ValueError:
        return "unknown"
    age_days = max(0, (datetime.now(UTC) - published).days)
    if age_days <= 7:
        return "7d"
    if age_days <= 30:
        return "30d"
    if age_days <= 90:
        return "90d"
    return "stale"


def _quality_flags(
    document: SearchDocument,
    *,
    source_tier: str,
    freshness_band: str,
) -> list[str]:
    domain = _normalize_domain(document.domain or document.url)
    flags: list[str] = []
    if any(hint in domain for hint in LOW_TRUST_DOMAIN_HINTS):
        flags.append(QUALITY_FLAG_LOW_TRUST)
    if source_tier == "tertiary":
        flags.append(QUALITY_FLAG_TERTIARY)
    if freshness_band == "stale":
        flags.append(QUALITY_FLAG_STALE)
    elif freshness_band == "unknown":
        flags.append(QUALITY_FLAG_UNKNOWN_FRESHNESS)
    if document.source_quality == "low":
        flags.append(QUALITY_FLAG_LOW_SOURCE_QUALITY)
    if document.confidence is not None and document.confidence < 0.45:
        flags.append(QUALITY_FLAG_LOW_CONFIDENCE)
    if not document.raw_text:
        flags.append(QUALITY_FLAG_SNIPPET_ONLY)
    if document.raw_text and (
        QUALITY_FLAG_LOW_TRUST in flags
        or QUALITY_FLAG_LOW_SOURCE_QUALITY in flags
        or source_tier == "tertiary"
    ):
        # Long page text is not enough to make a weak source eligible as evidence.
        flags.append(QUALITY_FLAG_DETAILED_LOW_TRUST)
    return list(dict.fromkeys(flags))


def _requires_fresh_evidence(plan: ResearchPlan | None) -> bool:
    if not plan:
        return False
    return bool(plan.evidence_policy.get("require_date_for_time_sensitive_claims", False))


def _source_heat_score(
    document: SearchDocument,
    *,
    source_tier: str,
    freshness_band: str,
    quality_flags: list[str],
    plan: ResearchPlan | None,
) -> float:
    tier_score = TIER_HEAT.get(source_tier, 0.3)
    freshness_score = _normalized_score(
        document.freshness_score,
        FRESHNESS_HEAT.get(freshness_band, 0.35),
    )
    confidence = _normalized_score(document.confidence or document.score, 0.55)
    trust_score = _normalized_score(
        document.trust_score,
        {"primary": 0.95, "secondary": 0.72, "tertiary": 0.4}.get(source_tier, 0.45),
    )
    provider_score = _normalized_score(document.provider_score, 0.55)

    score = (
        0.28 * trust_score
        + 0.24 * freshness_score
        + 0.22 * confidence
        + 0.16 * tier_score
        + 0.10 * provider_score
    )
    if document.raw_text:
        score += 0.03
    if QUALITY_FLAG_LOW_TRUST in quality_flags:
        score -= 0.12
    if QUALITY_FLAG_LOW_SOURCE_QUALITY in quality_flags:
        score -= 0.18
    if QUALITY_FLAG_LOW_CONFIDENCE in quality_flags:
        score -= 0.16
    if QUALITY_FLAG_TERTIARY in quality_flags:
        score -= 0.08
    if QUALITY_FLAG_DETAILED_LOW_TRUST in quality_flags:
        score -= 0.10
    if _requires_fresh_evidence(plan) and freshness_band in {"stale", "unknown"}:
        score -= 0.12
    return round(_clamp(score), 4)


def _heat_level(heat_score: float) -> str:
    if heat_score >= 0.75:
        return "hot"
    if heat_score >= 0.55:
        return "warm"
    return "cold"


def _adoption_role(
    *,
    source_tier: str,
    freshness_band: str,
    heat_score: float,
    quality_flags: list[str],
    plan: ResearchPlan | None,
) -> str:
    blocking_flags = {
        QUALITY_FLAG_LOW_CONFIDENCE,
        QUALITY_FLAG_LOW_SOURCE_QUALITY,
        QUALITY_FLAG_DETAILED_LOW_TRUST,
    }
    if blocking_flags.intersection(quality_flags):
        return "rejected" if heat_score < 0.52 else "context"
    if QUALITY_FLAG_LOW_TRUST in quality_flags and heat_score < 0.65:
        return "rejected"
    if _requires_fresh_evidence(plan) and freshness_band in {"stale", "unknown"} and source_tier != "primary":
        return "context"
    if source_tier == "primary" and heat_score >= 0.55 and freshness_band != "stale":
        return "evidence"
    if source_tier == "secondary" and heat_score >= 0.62 and freshness_band not in {"stale", "unknown"}:
        return "evidence"
    if source_tier == "tertiary" and heat_score >= 0.78 and freshness_band in {"7d", "30d"}:
        return "context"
    if heat_score >= 0.75 and QUALITY_FLAG_LOW_TRUST not in quality_flags:
        return "evidence"
    return "context"


def _selection_reason(
    document: SearchDocument,
    source_tier: str,
    freshness_band: str,
    *,
    heat_level: str,
    adoption_role: str,
    quality_flags: list[str],
) -> str:
    reasons = [f"{source_tier}_source"]
    if freshness_band in {"7d", "30d"}:
        reasons.append(f"fresh_{freshness_band}")
    if document.raw_text:
        reasons.append("body_fetched")
    if document.score is not None:
        reasons.append("ranked")
    reasons.append(f"{heat_level}_heat")
    reasons.append(f"{adoption_role}_role")
    reasons.extend(quality_flags[:3])
    return " + ".join(reasons)


def _low_trust_ratio_limit(plan: ResearchPlan | None) -> float:
    if not plan:
        return 0.2
    try:
        raw_value = float(plan.source_policy.get("max_low_trust_ratio", 0.2) or 0.2)
    except (TypeError, ValueError):
        return 0.2
    return _clamp(raw_value)


def _enforce_low_trust_ratio(
    sources: list[ResearchSource],
    *,
    plan: ResearchPlan | None,
) -> None:
    evidence_sources = [source for source in sources if source.adoption_role == "evidence"]
    if not evidence_sources:
        return

    max_ratio = _low_trust_ratio_limit(plan)
    max_low_trust = int(len(evidence_sources) * max_ratio)
    low_trust_evidence = [
        source
        for source in evidence_sources
        if source.source_tier == "tertiary" or QUALITY_FLAG_LOW_TRUST in source.quality_flags
    ]
    overflow_count = max(0, len(low_trust_evidence) - max_low_trust)
    if overflow_count <= 0:
        return

    for source in sorted(low_trust_evidence, key=lambda item: item.heat_score)[:overflow_count]:
        source.adoption_role = "context"
        if QUALITY_FLAG_RATIO_EXCEEDED not in source.quality_flags:
            source.quality_flags.append(QUALITY_FLAG_RATIO_EXCEEDED)
        source.selection_reason = f"{source.selection_reason} + {QUALITY_FLAG_RATIO_EXCEEDED}"


def evaluate_research_sources(
    documents: list[SearchDocument],
    *,
    plan: ResearchPlan | None = None,
    provider_caveats: list[str] | None = None,
) -> list[ResearchSource]:
    """Normalize raw search documents into source-level V2 metadata."""
    default_facet = (plan.facets[0] if plan and plan.facets else "overview")
    caveat = " | ".join(provider_caveats or [])
    evaluated: list[ResearchSource] = []
    for document in documents:
        tier = _source_tier(document)
        freshness = _freshness_band(document)
        flags = _quality_flags(document, source_tier=tier, freshness_band=freshness)
        heat_score = _source_heat_score(
            document,
            source_tier=tier,
            freshness_band=freshness,
            quality_flags=flags,
            plan=plan,
        )
        level = _heat_level(heat_score)
        role = _adoption_role(
            source_tier=tier,
            freshness_band=freshness,
            heat_score=heat_score,
            quality_flags=flags,
            plan=plan,
        )
        evaluated.append(
            ResearchSource(
                doc=document,
                facet=str(default_facet or "overview"),
                bucket=str(document.source_type or "web"),
                source_tier=tier,  # type: ignore[arg-type]
                source_family=_source_family(document),
                freshness_band=freshness,
                selection_reason=_selection_reason(
                    document,
                    tier,
                    freshness,
                    heat_level=level,
                    adoption_role=role,
                    quality_flags=flags,
                ),
                provider_caveat=caveat,
                heat_score=heat_score,
                heat_level=level,  # type: ignore[arg-type]
                adoption_role=role,  # type: ignore[arg-type]
                quality_flags=flags,
            )
        )
    _enforce_low_trust_ratio(evaluated, plan=plan)
    return evaluated


def select_priority_sources(
    sources: list[ResearchSource],
    *,
    limit: int,
) -> list[ResearchSource]:
    """Select sources for fetch/verification with primary and fresh sources first."""
    eligible_sources = [source for source in sources if source.adoption_role != "rejected"] or list(sources)
    role_rank = {"evidence": 0, "context": 1, "rejected": 2}
    tier_rank = {"primary": 0, "secondary": 1, "tertiary": 2}
    freshness_rank = {"7d": 0, "30d": 1, "90d": 2, "stale": 3, "unknown": 4}
    return sorted(
        eligible_sources,
        key=lambda item: (
            role_rank.get(item.adoption_role, 2),
            tier_rank.get(item.source_tier, 3),
            freshness_rank.get(item.freshness_band, 4),
            -float(item.heat_score or 0.0),
            -(item.doc.score or 0.0),
            item.source_family,
        ),
    )[: max(1, int(limit or 1))]


__all__ = ["evaluate_research_sources", "select_priority_sources"]
