from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


class SearchRuntimeError(Exception):
    """Base error for search runtime failures."""


class SearchConfigError(SearchRuntimeError):
    """Raised when a provider is missing required configuration."""


class SearchTimeoutError(SearchRuntimeError):
    """Raised when a provider request times out."""


class UnsupportedSearchProviderError(SearchRuntimeError):
    """Raised when a configured search provider is unknown."""


class SearchProviderHTTPError(SearchRuntimeError):
    """Raised when a provider returns an HTTP error."""

    def __init__(self, status_code: int, response_text: str = "", message: str = "搜索 API 请求失败"):
        super().__init__(message)
        self.status_code = int(status_code)
        self.response_text = str(response_text or "")


@dataclass(frozen=True)
class SearchProviderCapabilities:
    name: str
    supports_time_range: bool = False
    supports_news_topic: bool = False
    supports_answer: bool = False
    supports_raw_content: bool = False
    supports_domain_filter_native: bool = False


@dataclass
class ResearchIntent:
    intent: str
    time_sensitive: bool
    region: str | None = None
    time_window: str | None = None
    requires_exact_dates: bool = False


@dataclass
class ResearchQuery:
    query: str
    facet: str
    bucket: str
    expected_source_tier: str
    provider_caveat: str = ""


@dataclass
class ResearchBudget:
    max_llm_calls: int = 5
    max_round_one_queries: int = 4
    max_follow_up_queries: int = 2
    max_total_queries: int = 6
    max_fetch_pages: int = 6
    max_repair_loops: int = 1


@dataclass
class ResearchPlan:
    topic: str
    facets: list[str] = field(default_factory=list)
    queries: list[ResearchQuery] = field(default_factory=list)
    template_id: str | None = None
    resolution_strategy: str = "generic_fallback"
    source_policy: dict[str, object] = field(default_factory=dict)
    evidence_policy: dict[str, object] = field(default_factory=dict)
    caveats: list[str] = field(default_factory=list)


@dataclass
class SearchDocument:
    doc_id: str
    provider: str
    source_type: Literal["web", "social", "news", "code", "forum", "trend"] = "web"
    title: str = ""
    url: str = ""
    snippet: str = ""
    raw_text: str = ""
    published_at: str | None = None
    fetched_at: str | None = None
    domain: str | None = None
    author: str | None = None
    score: float | None = None
    provider_score: float | None = None
    confidence: float | None = None
    trust_score: float | None = None
    freshness_score: float | None = None
    source_quality: str | None = None
    retrieval_query: str | None = None
    matched_terms: list[str] = field(default_factory=list)
    evidence_tags: list[str] = field(default_factory=list)

    def to_source_item(self, index: int) -> dict[str, object]:
        source: dict[str, object] = {
            "type": "web",
            "title": self.title or "无标题",
            "url": self.url,
            "snippet": (self.raw_text or self.snippet)[:200],
            "index": index,
            "provider": self.provider,
        }
        if self.score is not None:
            source["score"] = round(self.score, 4)
        if self.provider_score is not None:
            source["provider_score"] = round(self.provider_score, 4)
        if self.confidence is not None:
            source["confidence"] = round(self.confidence, 4)
        if self.published_at:
            source["published_at"] = self.published_at
        if self.domain:
            source["domain"] = self.domain
        if self.trust_score is not None:
            source["trust_score"] = round(self.trust_score, 4)
        if self.freshness_score is not None:
            source["freshness_score"] = round(self.freshness_score, 4)
        if self.source_quality:
            source["source_quality"] = self.source_quality
        if self.retrieval_query:
            source["retrieval_query"] = self.retrieval_query
        if self.matched_terms:
            source["matched_terms"] = list(self.matched_terms)
        if self.evidence_tags:
            source["evidence_tags"] = list(self.evidence_tags)
        return source


@dataclass
class SearchResponse:
    query: str
    provider: str
    results: list[SearchDocument] = field(default_factory=list)
    answer: str = ""
    search_depth: str = "basic"
    rewritten_query: str = ""
    topic: str | None = None
    time_range: str | None = None
    include_domains: list[str] = field(default_factory=list)
    exclude_domains: list[str] = field(default_factory=list)
    provider_capabilities: list[SearchProviderCapabilities] = field(default_factory=list)
    provider_caveats: list[str] = field(default_factory=list)


@dataclass
class ResearchFinding:
    claim: str
    status: Literal["verified", "partial", "unverified"] = "verified"
    evidence: list[str] = field(default_factory=list)
    note: str = ""


@dataclass
class ResearchContradiction:
    topic: str
    details: str
    resolution_action: Literal["no_action", "clarify_in_output", "repair_search"] = "clarify_in_output"
    sources: list[str] = field(default_factory=list)


@dataclass
class ResearchSource:
    doc: SearchDocument
    facet: str = ""
    bucket: str = ""
    source_tier: Literal["primary", "secondary", "tertiary"] = "tertiary"
    source_family: str = ""
    freshness_band: str = "unknown"
    selection_reason: str = ""
    provider_caveat: str = ""

    def to_payload(self, index: int) -> dict[str, object]:
        payload = self.doc.to_source_item(index)
        payload.update(
            {
                "facet": self.facet,
                "source_bucket": self.bucket,
                "source_tier": self.source_tier,
                "source_family": self.source_family,
                "freshness_band": self.freshness_band,
                "selection_reason": self.selection_reason,
                "provider_caveat": self.provider_caveat,
            }
        )
        return payload


@dataclass
class AtomicClaim:
    claim_id: str
    facet: str
    text: str
    claim_type: Literal["event", "data_point", "policy_signal", "market_trend", "forecast"] = "event"
    date: str | None = None
    candidate_sources: list[str] = field(default_factory=list)

    def to_payload(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "facet": self.facet,
            "text": self.text,
            "claim_type": self.claim_type,
            "date": self.date,
            "candidate_sources": list(self.candidate_sources),
        }


@dataclass
class ClaimVerification:
    claim_id: str
    status: Literal["verified", "partial", "unverified"]
    evidence_strength: Literal["high", "medium", "low"]
    supporting_sources: list[str] = field(default_factory=list)
    verification_note: str = ""

    def to_payload(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "status": self.status,
            "evidence_strength": self.evidence_strength,
            "supporting_sources": list(self.supporting_sources),
            "verification_note": self.verification_note,
        }


@dataclass
class ResearchRound:
    name: str
    queries: list[str] = field(default_factory=list)
    source_count: int = 0
    highlights: list[str] = field(default_factory=list)


@dataclass
class WebResearchResult:
    query: str
    provider: str
    answer: str = ""
    summary: str = ""
    rewritten_query: str = ""
    sources: list[SearchDocument] = field(default_factory=list)
    highlights: list[str] = field(default_factory=list)
    findings: list[ResearchFinding] = field(default_factory=list)
    contradictions: list[ResearchContradiction] = field(default_factory=list)
    rounds: list[ResearchRound] = field(default_factory=list)
    workflow_nodes: list[dict[str, object]] = field(default_factory=list)
    provider_summary: str = ""
    provider_capabilities: list[SearchProviderCapabilities] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    research_intent: ResearchIntent | None = None
    research_plan: ResearchPlan | None = None

    def to_text(self, *, max_sources: int = 5) -> str:
        lines = [
            f"研究主题：{self.query}",
            f"搜索提供方：{self.provider_summary or self.provider}",
        ]

        summary = (self.summary or self.answer).strip()
        if summary:
            lines.extend(["", "核心结论：", summary])

        if self.highlights:
            lines.append("")
            lines.append("关键线索：")
            for index, item in enumerate(self.highlights, 1):
                lines.append(f"{index}. {item.strip()}")

        if self.findings:
            lines.append("")
            lines.append("研究发现：")
            for index, finding in enumerate(self.findings, 1):
                suffix = f"（{finding.status}）" if finding.status else ""
                lines.append(f"{index}. {finding.claim.strip()}{suffix}")
                if finding.note.strip():
                    lines.append(f"   说明：{finding.note.strip()}")
                if finding.evidence:
                    evidence_text = "；".join(item.strip() for item in finding.evidence if item.strip())
                    if evidence_text:
                        lines.append(f"   证据来源：{evidence_text}")

        if self.contradictions:
            lines.append("")
            lines.append("待核对事项：")
            for index, contradiction in enumerate(self.contradictions, 1):
                lines.append(f"{index}. {contradiction.topic.strip()} | {contradiction.details.strip()}")
                if contradiction.sources:
                    source_text = "；".join(item.strip() for item in contradiction.sources if item.strip())
                    if source_text:
                        lines.append(f"   相关来源：{source_text}")
                if contradiction.resolution_action:
                    lines.append(f"   处理建议：{contradiction.resolution_action}")

        if self.caveats:
            lines.append("")
            lines.append("研究说明：")
            for index, caveat in enumerate(self.caveats, 1):
                cleaned = str(caveat or "").strip()
                if cleaned:
                    lines.append(f"{index}. {cleaned}")

        if self.sources:
            lines.append("")
            lines.append("主要来源：")
            for index, source in enumerate(self.sources[:max_sources], 1):
                snippet = source.snippet.strip()
                if len(snippet) > 120:
                    snippet = f"{snippet[:117]}..."
                source_line = f"{index}. {source.title or '无标题'}"
                if source.url:
                    source_line += f" | {source.url}"
                if snippet:
                    source_line += f" | {snippet}"
                lines.append(source_line)

        return "\n".join(lines).strip()
