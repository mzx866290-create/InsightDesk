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
    trust_score: float | None = None
    freshness_score: float | None = None
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
        if self.published_at:
            source["published_at"] = self.published_at
        if self.domain:
            source["domain"] = self.domain
        return source


@dataclass
class SearchResponse:
    query: str
    provider: str
    results: list[SearchDocument] = field(default_factory=list)
    answer: str = ""
    search_depth: str = "basic"


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
    sources: list[str] = field(default_factory=list)


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
    sources: list[SearchDocument] = field(default_factory=list)
    highlights: list[str] = field(default_factory=list)
    findings: list[ResearchFinding] = field(default_factory=list)
    contradictions: list[ResearchContradiction] = field(default_factory=list)
    rounds: list[ResearchRound] = field(default_factory=list)
    workflow_nodes: list[dict[str, object]] = field(default_factory=list)
    provider_summary: str = ""

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

        if self.contradictions:
            lines.append("")
            lines.append("待核对事项：")
            for index, contradiction in enumerate(self.contradictions, 1):
                lines.append(
                    f"{index}. {contradiction.topic.strip()} | {contradiction.details.strip()}"
                )

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
