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


def _selection_reason(document: SearchDocument, source_tier: str, freshness_band: str) -> str:
    reasons = [f"{source_tier}_source"]
    if freshness_band in {"7d", "30d"}:
        reasons.append(f"fresh_{freshness_band}")
    if document.raw_text:
        reasons.append("body_fetched")
    if document.score is not None:
        reasons.append("ranked")
    return " + ".join(reasons)


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
        evaluated.append(
            ResearchSource(
                doc=document,
                facet=str(default_facet or "overview"),
                bucket=str(document.source_type or "web"),
                source_tier=tier,  # type: ignore[arg-type]
                source_family=_source_family(document),
                freshness_band=freshness,
                selection_reason=_selection_reason(document, tier, freshness),
                provider_caveat=caveat,
            )
        )
    return evaluated


def select_priority_sources(
    sources: list[ResearchSource],
    *,
    limit: int,
) -> list[ResearchSource]:
    """Select sources for fetch/verification with primary and fresh sources first."""
    tier_rank = {"primary": 0, "secondary": 1, "tertiary": 2}
    freshness_rank = {"7d": 0, "30d": 1, "90d": 2, "stale": 3, "unknown": 4}
    return sorted(
        sources,
        key=lambda item: (
            tier_rank.get(item.source_tier, 3),
            freshness_rank.get(item.freshness_band, 4),
            -(item.doc.score or 0.0),
            item.source_family,
        ),
    )[: max(1, int(limit or 1))]


__all__ = ["evaluate_research_sources", "select_priority_sources"]
