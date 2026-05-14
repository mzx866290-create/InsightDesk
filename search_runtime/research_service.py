from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable, Sequence
from typing import Any
from urllib.parse import urlparse

from .service import build_related_questions, dedupe_search_documents, fetch_webpage_document, search_web
from .types import (
    ResearchBudget,
    ResearchContradiction,
    ResearchFinding,
    ResearchIntent,
    ResearchPlan,
    ResearchQuery,
    ResearchRound,
    ResearchSourceStrategy,
    SearchDocument,
    SearchProviderCapabilities,
    SearchResponse,
    WebResearchResult,
)

logger = logging.getLogger(__name__)

TIME_SENSITIVE_TERMS = (
    "latest",
    "recent",
    "newest",
    "today",
    "this week",
    "breaking",
    "最新",
    "近期",
    "近况",
    "最近",
    "动态",
)
INDUSTRY_RESEARCH_TERMS = (
    "industry",
    "sector",
    "market",
    "outlook",
    "trend",
    "动态",
    "行业",
    "市场",
    "政策",
    "监管",
    "投融资",
)
FINANCE_TEMPLATE_TERMS = (
    "finance",
    "financial",
    "banking",
    "insurance",
    "capital market",
    "fintech",
    "金融",
    "银行",
    "保险",
    "资本市场",
    "证券",
    "外汇",
)
FINANCE_TEMPLATE_FACETS = [
    "macro_policy",
    "banking_insurance",
    "capital_markets",
    "cross_border_fx",
    "fintech_funding",
    "regulation_risk",
]
GENERIC_FACETS = [
    "market_structure",
    "policy_regulation",
    "data_metrics",
    "corporate_activity",
    "risks_controversies",
]
COMMUNITY_FACETS = [
    "social_signals",
    "community_discussion",
    "key_accounts",
    "verification_sources",
    "risks_controversies",
]
VALID_SOURCE_STRATEGIES = {
    "web_only",
    "web_and_community",
    "community_first",
    "evidence_strict",
}
COMMUNITY_FIRST_CAVEAT = (
    "Community-first research uses search-engine-indexed social/community pages and "
    "user-provided social links; it does not use the X API or promise complete real-time X coverage."
)
SOCIAL_DOMAINS = (
    "x.com",
    "twitter.com",
    "bsky.app",
    "mastodon.social",
    "threads.net",
    "weibo.com",
)
FORUM_DOMAINS = (
    "reddit.com",
    "news.ycombinator.com",
    "lobste.rs",
    "v2ex.com",
    "zhihu.com",
    "quora.com",
    "stackoverflow.com",
)
CODE_DOMAINS = (
    "github.com",
    "gitlab.com",
    "bitbucket.org",
)
DEFAULT_SOURCE_POLICY: dict[str, object] = {
    "primary_required": True,
    "max_low_trust_ratio": 0.2,
    "prefer_official": True,
}
DEFAULT_EVIDENCE_POLICY: dict[str, object] = {
    "min_independent_families_per_claim": 2,
    "require_date_for_time_sensitive_claims": True,
    "require_primary_for_policy_claims": True,
}
DOMAIN_TEMPLATE_REGISTRY: dict[str, dict[str, object]] = {
    "finance": {
        "match_terms": (
            "finance",
            "financial",
            "banking",
            "insurance",
            "capital market",
            "fintech",
            "閲戣瀺",
            "閾惰",
            "淇濋櫓",
            "璧勬湰甯傚満",
            "璇佸埜",
            "澶栨眹",
        ),
        "facets": [
            "macro_policy",
            "banking_insurance",
            "capital_markets",
            "cross_border_fx",
            "fintech_funding",
            "regulation_risk",
        ],
        "prompt_hint": "Finance template matched. Use finance-specific facets only when they fit the query.",
    }
}


def _strip_think_tags(text: str) -> str:
    cleaned = str(text or "")
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if re.search(r"<think>", cleaned, flags=re.IGNORECASE):
        cleaned = re.split(r"<think>", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
    return cleaned.strip()


def _response_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return _strip_think_tags(content)
    if isinstance(content, list):
        return _strip_think_tags("\n".join(str(item) for item in content if item))
    return _strip_think_tags(str(content or ""))


def _extract_json_payload(text: str) -> Any | None:
    stripped = str(text or "").strip()
    if not stripped:
        return None

    fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    if fenced_match:
        stripped = fenced_match.group(1).strip()

    candidates = [stripped]
    if "{" in stripped and "}" in stripped:
        candidates.append(stripped[stripped.find("{") : stripped.rfind("}") + 1])
    if "[" in stripped and "]" in stripped:
        candidates.append(stripped[stripped.find("[") : stripped.rfind("]") + 1])

    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _contains_any(text: str, keywords: Sequence[str]) -> bool:
    lowered = str(text or "").lower()
    return any(keyword in lowered for keyword in keywords)


def _contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", str(text or "")))


def _normalize_source_strategy(value: str | None) -> ResearchSourceStrategy:
    normalized = str(value or "web_only").strip().lower().replace("-", "_")
    if normalized in {"community", "social", "social_intel", "social_intelligence"}:
        return "community_first"
    if normalized in VALID_SOURCE_STRATEGIES:
        return normalized  # type: ignore[return-value]
    return "web_only"


def _is_community_strategy(source_strategy: ResearchSourceStrategy) -> bool:
    return source_strategy in {"web_and_community", "community_first"}


def _domain_from_document(document: SearchDocument) -> str:
    raw_domain = str(document.domain or "").strip().lower()
    if not raw_domain and document.url:
        raw_domain = urlparse(document.url).netloc.lower()
    return raw_domain.removeprefix("www.")


def _domain_matches_any(domain: str, patterns: Sequence[str]) -> bool:
    normalized = domain.removeprefix("www.")
    return any(normalized == pattern or normalized.endswith(f".{pattern}") for pattern in patterns)


def _community_source_type(document: SearchDocument) -> str:
    domain = _domain_from_document(document)
    if _domain_matches_any(domain, SOCIAL_DOMAINS):
        return "social"
    if _domain_matches_any(domain, FORUM_DOMAINS):
        return "forum"
    if _domain_matches_any(domain, CODE_DOMAINS):
        return "code"
    return document.source_type


def _tag_documents_for_source_strategy(
    documents: Sequence[SearchDocument],
    *,
    source_strategy: ResearchSourceStrategy,
) -> list[SearchDocument]:
    if source_strategy == "web_only":
        return list(documents)

    tagged: list[SearchDocument] = []
    for document in documents:
        source_type = _community_source_type(document)
        tags = list(document.evidence_tags or [])
        if source_type in {"social", "forum", "code"}:
            tags.append("community_signal")
        if source_type == "social":
            tags.append("social_lead")
        if source_strategy == "evidence_strict":
            tags.append("evidence_strict")

        tagged.append(
            SearchDocument(
                doc_id=document.doc_id,
                provider=document.provider,
                source_type=source_type,  # type: ignore[arg-type]
                title=document.title,
                url=document.url,
                snippet=document.snippet,
                raw_text=document.raw_text,
                published_at=document.published_at,
                fetched_at=document.fetched_at,
                domain=document.domain,
                author=document.author,
                score=document.score,
                provider_score=document.provider_score,
                confidence=document.confidence,
                trust_score=document.trust_score,
                freshness_score=document.freshness_score,
                source_quality=document.source_quality,
                retrieval_query=document.retrieval_query,
                matched_terms=list(document.matched_terms or []),
                evidence_tags=list(dict.fromkeys(tags)),
            )
        )
    return tagged


def _tag_response_for_source_strategy(
    response: SearchResponse,
    *,
    source_strategy: ResearchSourceStrategy,
) -> SearchResponse:
    response.results = _tag_documents_for_source_strategy(
        response.results,
        source_strategy=source_strategy,
    )
    return response


def _should_fetch_source(
    source: SearchDocument,
    *,
    source_strategy: ResearchSourceStrategy,
) -> bool:
    if source_strategy == "web_only":
        return True
    if source.source_type == "social":
        return False
    return True


def _source_strategy_source_policy(source_strategy: ResearchSourceStrategy) -> dict[str, object]:
    policy = dict(DEFAULT_SOURCE_POLICY)
    policy["strategy"] = source_strategy
    if source_strategy == "community_first":
        policy.update(
            {
                "primary_required": False,
                "prefer_official": False,
                "max_low_trust_ratio": 0.0,
                "treat_social_as_leads": True,
                "allow_search_engine_indexed_social": True,
                "direct_x_api_required": False,
            }
        )
    elif source_strategy == "web_and_community":
        policy.update(
            {
                "treat_social_as_leads": True,
                "allow_search_engine_indexed_social": True,
                "direct_x_api_required": False,
            }
        )
    elif source_strategy == "evidence_strict":
        policy.update(
            {
                "primary_required": True,
                "max_low_trust_ratio": 0.0,
                "treat_social_as_leads": True,
            }
        )
    return policy


def _source_strategy_evidence_policy(source_strategy: ResearchSourceStrategy) -> dict[str, object]:
    policy = dict(DEFAULT_EVIDENCE_POLICY)
    if _is_community_strategy(source_strategy):
        policy.update(
            {
                "community_claims_require_independent_verification": True,
                "social_links_are_context_by_default": True,
            }
        )
    if source_strategy == "evidence_strict":
        policy["min_independent_families_per_claim"] = 2
        policy["social_links_are_context_by_default"] = True
    return policy


def _dedupe_strings(items: Sequence[str]) -> list[str]:
    deduped: list[str] = []
    for item in items:
        cleaned = str(item or "").strip()
        if cleaned and cleaned not in deduped:
            deduped.append(cleaned)
    return deduped


def _normalize_text_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return _dedupe_strings([value])
    if isinstance(value, Sequence):
        return _dedupe_strings(str(item) for item in value if str(item).strip())
    return []


def _infer_time_window(query: str, explicit_time_range: str | None) -> str:
    normalized = str(explicit_time_range or "").strip().lower()
    if normalized == "day":
        return "1d"
    if normalized == "week":
        return "7d"
    if normalized == "month":
        return "30d"
    if _contains_any(query, ("today", "breaking", "今天", "刚刚")):
        return "1d"
    if _contains_any(query, TIME_SENSITIVE_TERMS):
        return "30d"
    return "90d"


def _infer_research_intent(query: str, explicit_time_range: str | None) -> ResearchIntent:
    lowered = str(query or "").lower()
    time_sensitive = _contains_any(lowered, TIME_SENSITIVE_TERMS) or bool(explicit_time_range)
    intent = "industry_research" if _contains_any(lowered, INDUSTRY_RESEARCH_TERMS) else "topic_research"

    region: str | None = None
    if any(term in lowered for term in ("china", "chinese", "中国", "国内")):
        region = "china"

    return ResearchIntent(
        intent=intent,
        time_sensitive=time_sensitive,
        region=region,
        time_window=_infer_time_window(query, explicit_time_range),
        requires_exact_dates=time_sensitive,
    )


def _resolve_domain_template(query: str) -> dict[str, object] | None:
    lowered = str(query or "").lower()
    best_match: dict[str, object] | None = None
    best_score = 0

    for template_id, template in DOMAIN_TEMPLATE_REGISTRY.items():
        match_terms = tuple(str(item).lower() for item in template.get("match_terms", ()) if str(item).strip())
        score = sum(1 for term in match_terms if term and term in lowered)
        if score <= 0 or score < best_score:
            continue
        best_score = score
        best_match = {
            "template_id": template_id,
            "facets": list(template.get("facets", [])),
            "prompt_hint": str(template.get("prompt_hint") or "").strip(),
            "match_score": score,
        }

    return best_match


def _generic_facets_for_intent(
    intent: ResearchIntent,
    source_strategy: ResearchSourceStrategy = "web_only",
) -> list[str]:
    if _is_community_strategy(source_strategy):
        return list(COMMUNITY_FACETS)
    if intent.intent == "industry_research":
        return list(GENERIC_FACETS)
    return ["overview", "facts", "updates", "metrics", "risks"]


def _default_budget(*, max_rounds: int, max_fetch_pages: int) -> ResearchBudget:
    normalized_rounds = max(1, min(2, int(max_rounds or 1)))
    follow_up_queries = 0 if normalized_rounds <= 1 else 2
    return ResearchBudget(
        max_llm_calls=5,
        max_round_one_queries=4,
        max_follow_up_queries=follow_up_queries,
        max_total_queries=4 + follow_up_queries,
        max_fetch_pages=max(0, min(6, int(max_fetch_pages or 0))),
        max_repair_loops=1 if normalized_rounds > 1 else 0,
    )


def _format_facet_label(facet: str) -> str:
    cleaned = str(facet or "").strip()
    if not cleaned:
        return ""
    return cleaned.replace("_", " ")


def _parse_findings(payload: Any) -> list[ResearchFinding]:
    findings: list[ResearchFinding] = []
    if not isinstance(payload, list):
        return findings

    for item in payload:
        if not isinstance(item, dict):
            continue
        claim = str(item.get("claim") or "").strip()
        if not claim:
            continue
        findings.append(
            ResearchFinding(
                claim=claim,
                status=str(item.get("status") or "verified").strip() or "verified",
                evidence=[str(value).strip() for value in item.get("evidence", []) if str(value).strip()],
                note=str(item.get("note") or "").strip(),
            )
        )
    return findings


def _parse_contradictions(payload: Any) -> list[ResearchContradiction]:
    contradictions: list[ResearchContradiction] = []
    if not isinstance(payload, list):
        return contradictions

    for item in payload:
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic") or "").strip()
        details = str(item.get("details") or "").strip()
        if not topic or not details:
            continue
        contradictions.append(
            ResearchContradiction(
                topic=topic,
                details=details,
                sources=[str(value).strip() for value in item.get("sources", []) if str(value).strip()],
            )
        )
    return contradictions


def _source_reference_map(sources: Sequence[SearchDocument]) -> dict[str, str]:
    refs: dict[str, str] = {}
    for index, source in enumerate(sources, 1):
        label = f"[{index}] {source.title or source.url or 'Untitled source'}"
        for candidate in (
            str(index),
            f"source-{index}",
            f"source_{index}",
            f"source {index}",
            source.doc_id,
            source.url,
            source.title,
        ):
            key = str(candidate or "").strip().lower()
            if key and key not in refs:
                refs[key] = label
    return refs


def _resolve_reference_labels(items: Sequence[str], sources: Sequence[SearchDocument]) -> list[str]:
    if not items:
        return []

    refs = _source_reference_map(sources)
    resolved: list[str] = []
    for item in items:
        raw = str(item or "").strip()
        if not raw:
            continue
        key = raw.lower()
        label = refs.get(key)
        if label is None and key.startswith("source") and re.search(r"\d+", key):
            match = re.search(r"\d+", key)
            if match:
                label = refs.get(match.group(0))
        resolved.append(label or raw)

    return _dedupe_strings(resolved)


def _attach_source_references(
    findings: Sequence[ResearchFinding],
    contradictions: Sequence[ResearchContradiction],
    sources: Sequence[SearchDocument],
) -> tuple[list[ResearchFinding], list[ResearchContradiction]]:
    normalized_findings = [
        ResearchFinding(
            claim=item.claim,
            status=item.status,
            evidence=_resolve_reference_labels(item.evidence, sources),
            note=item.note,
        )
        for item in findings
    ]
    normalized_contradictions = [
        ResearchContradiction(
            topic=item.topic,
            details=item.details,
            sources=_resolve_reference_labels(item.sources, sources),
        )
        for item in contradictions
    ]
    return normalized_findings, normalized_contradictions


def _search_response_excerpt(response: SearchResponse) -> str:
    lines = [f"Provider: {response.provider}", f"Query: {response.query}"]
    if response.provider_caveats:
        lines.append("Caveats: " + " | ".join(response.provider_caveats))
    for index, result in enumerate(response.results[:4], 1):
        lines.append(
            f"{index}. {result.title or 'Untitled'} | {result.url} | {result.snippet[:220]}"
        )
    return "\n".join(lines)


def _workflow_node(
    node_id: str,
    display_name: str,
    *,
    started_at_ms: int,
    ended_at_ms: int,
    tool_name: str = "",
    tool_params: dict[str, Any] | None = None,
    tool_result: str = "",
    status: str = "completed",
    error: str = "",
) -> dict[str, object]:
    node: dict[str, object] = {
        "id": node_id,
        "name": node_id,
        "displayName": display_name,
        "status": status,
        "startTime": started_at_ms,
        "endTime": ended_at_ms,
        "duration": max(0, ended_at_ms - started_at_ms),
    }
    if tool_name:
        node["toolName"] = tool_name
    if tool_params:
        node["toolParams"] = tool_params
    if tool_result:
        node["toolResult"] = tool_result
    if error:
        node["error"] = error
    return node


def _knowledge_context_text(
    query: str,
    knowledge_search: Callable[[str], Sequence[SearchDocument]] | None,
) -> str:
    if not callable(knowledge_search):
        return ""
    try:
        docs = list(knowledge_search(query))
    except Exception:
        logger.exception("knowledge_search failed query=%s", query)
        return ""
    if not docs:
        return ""
    parts: list[str] = []
    for index, doc in enumerate(docs[:3], 1):
        parts.append(
            f"[KB {index}] {doc.title or doc.url or 'Local material'}\n{(doc.raw_text or doc.snippet or '')[:600]}"
        )
    return "\n\n".join(parts)


def _dedupe_capabilities(capabilities: Sequence[SearchProviderCapabilities]) -> list[SearchProviderCapabilities]:
    deduped: list[SearchProviderCapabilities] = []
    seen: set[str] = set()
    for capability in capabilities:
        key = str(getattr(capability, "name", "") or "").strip().lower()
        if not key or key in seen:
            continue
        deduped.append(capability)
        seen.add(key)
    return deduped


def _response_capabilities(responses: Sequence[SearchResponse]) -> list[SearchProviderCapabilities]:
    capabilities: list[SearchProviderCapabilities] = []
    for response in responses:
        capabilities.extend(response.provider_capabilities or [])
    return _dedupe_capabilities(capabilities)


def _response_caveats(responses: Sequence[SearchResponse]) -> list[str]:
    caveats: list[str] = []
    for response in responses:
        caveats.extend(str(item).strip() for item in (response.provider_caveats or []) if str(item).strip())
    return _dedupe_strings(caveats)


def _parse_research_queries(raw_payload: Any, *, fallback_facet: str, limit: int) -> list[ResearchQuery]:
    queries: list[ResearchQuery] = []
    if isinstance(raw_payload, list):
        for item in raw_payload:
            if isinstance(item, dict):
                query = str(item.get("query") or "").strip()
                if not query:
                    continue
                queries.append(
                    ResearchQuery(
                        query=query,
                        facet=str(item.get("facet") or fallback_facet).strip() or fallback_facet,
                        bucket=str(item.get("bucket") or "news").strip() or "news",
                        expected_source_tier=str(item.get("expected_source_tier") or "secondary").strip() or "secondary",
                        provider_caveat=str(item.get("provider_caveat") or "").strip(),
                    )
                )
            else:
                cleaned = str(item or "").strip()
                if cleaned:
                    queries.append(
                        ResearchQuery(
                            query=cleaned,
                            facet=fallback_facet,
                            bucket="news",
                            expected_source_tier="secondary",
                        )
                    )
    elif isinstance(raw_payload, dict):
        for bucket, items in raw_payload.items():
            if not isinstance(items, list):
                continue
            for item in items:
                cleaned = str(item or "").strip()
                if not cleaned:
                    continue
                queries.append(
                    ResearchQuery(
                        query=cleaned,
                        facet=fallback_facet,
                        bucket=str(bucket or "news").strip() or "news",
                        expected_source_tier="secondary",
                    )
                )

    deduped: list[ResearchQuery] = []
    seen_queries: set[str] = set()
    for item in queries:
        key = item.query.strip().lower()
        if not key or key in seen_queries:
            continue
        deduped.append(item)
        seen_queries.add(key)
        if len(deduped) >= limit:
            break
    return deduped


def _fallback_query_matrix(
    query: str,
    *,
    facets: Sequence[str],
    intent: ResearchIntent,
    budget: ResearchBudget,
    source_strategy: ResearchSourceStrategy = "web_only",
) -> list[ResearchQuery]:
    is_cjk = _contains_cjk(query)
    queries: list[ResearchQuery] = []

    def add_query(text: str, facet: str, bucket: str, tier: str) -> None:
        if len(queries) >= budget.max_round_one_queries:
            return
        cleaned = text.strip()
        if not cleaned:
            return
        if any(item.query == cleaned for item in queries):
            return
        queries.append(
            ResearchQuery(
                query=cleaned,
                facet=facet,
                bucket=bucket,
                expected_source_tier=tier,
            )
        )

    first_facet = _format_facet_label(facets[0]) if facets else ""
    second_facet = _format_facet_label(facets[1]) if len(facets) > 1 else first_facet

    if source_strategy == "community_first":
        add_query(
            f"{query} site:x.com OR site:twitter.com",
            first_facet or "social_signals",
            "social",
            "tertiary",
        )
        add_query(
            f"{query} Reddit Hacker News GitHub discussion",
            second_facet or "community_discussion",
            "forum",
            "tertiary",
        )
        add_query(
            f"{query} community feedback user discussion",
            second_facet or "community_discussion",
            "forum",
            "tertiary",
        )
        add_query(
            f"{query} official announcement latest news",
            "verification_sources",
            "news",
            "secondary",
        )
    elif source_strategy == "web_and_community":
        add_query(
            f"{query} latest discussion Reddit Hacker News",
            second_facet or "community_discussion",
            "forum",
            "tertiary",
        )
        add_query(
            f"{query} official announcement latest news",
            first_facet or "verification_sources",
            "news",
            "secondary",
        )
        add_query(
            f"{query} {first_facet} overview".strip(),
            first_facet or "overview",
            "reports",
            "secondary",
        )
        add_query(
            f"{query} {second_facet} data".strip(),
            second_facet or "data_metrics",
            "data",
            "secondary",
        )
    elif intent.time_sensitive:
        add_query(
            f"{query} 官方 政策" if is_cjk else f"{query} official policy",
            first_facet or "overview",
            "official",
            "primary",
        )
        add_query(
            f"{query} 最新 动态" if is_cjk else f"{query} latest updates",
            first_facet or "overview",
            "news",
            "secondary",
        )
        add_query(
            f"{query} {first_facet} 数据" if is_cjk and first_facet else f"{query} {first_facet} data".strip(),
            first_facet or "data_metrics",
            "data",
            "primary",
        )
        add_query(
            f"{query} {second_facet} 报告" if is_cjk and second_facet else f"{query} {second_facet} report".strip(),
            second_facet or "market_structure",
            "reports",
            "secondary",
        )
    else:
        add_query(
            f"{query} {first_facet} overview".strip(),
            first_facet or "overview",
            "reports",
            "secondary",
        )
        add_query(
            f"{query} {second_facet} data".strip(),
            second_facet or "data_metrics",
            "data",
            "secondary",
        )

    return queries[: budget.max_round_one_queries]


def _parse_plan_payload(
    payload: Any,
    *,
    query: str,
    template_id: str | None,
    template_facets: Sequence[str],
    generic_facets: Sequence[str],
    intent: ResearchIntent,
    budget: ResearchBudget,
    source_strategy: ResearchSourceStrategy = "web_only",
) -> ResearchPlan:
    topic = str(query or "").strip()
    facets: list[str] = []
    resolution_strategy = ""
    caveats: list[str] = []
    queries: list[ResearchQuery] = []
    llm_facets: list[str] = []

    if isinstance(payload, dict):
        topic = str(payload.get("topic") or topic).strip() or topic
        raw_facets = payload.get("facets")
        if isinstance(raw_facets, list):
            llm_facets = _dedupe_strings(str(item) for item in raw_facets)

        caveats = _normalize_text_list(payload.get("caveats"))

    if llm_facets:
        facets = llm_facets
        resolution_strategy = "llm_with_template_hint" if template_id else "llm_generated"
    elif template_facets:
        facets = _dedupe_strings(template_facets)
        resolution_strategy = "template_fallback"
        if template_id:
            caveats.append(f"Facet generation fell back to '{template_id}' domain template.")
        else:
            caveats.append("Facet generation fell back to a matched domain template.")
    else:
        facets = _dedupe_strings(generic_facets)
        resolution_strategy = "generic_fallback"
        caveats.append("Facet generation fell back to generic facets.")

    if isinstance(payload, dict):
        raw_query_groups = payload.get("query_groups")
        queries = _parse_research_queries(
            raw_query_groups,
            fallback_facet=_format_facet_label(facets[0]) if facets else "overview",
            limit=budget.max_round_one_queries,
        )

        if not queries:
            raw_queries = payload.get("queries") or payload.get("queries_by_bucket")
            queries = _parse_research_queries(
                raw_queries,
                fallback_facet=_format_facet_label(facets[0]) if facets else "overview",
                limit=budget.max_round_one_queries,
            )

    if not queries:
        queries = _fallback_query_matrix(
            query,
            facets=facets,
            intent=intent,
            budget=budget,
            source_strategy=source_strategy,
        )
        caveats.append("Query planning fell back to deterministic query templates.")

    if source_strategy == "community_first":
        caveats.append(COMMUNITY_FIRST_CAVEAT)
    elif source_strategy == "web_and_community":
        caveats.append(
            "Community sources are used as additional leads and should be verified against independent sources."
        )
    elif source_strategy == "evidence_strict":
        caveats.append("Evidence-strict research treats social/community sources as context unless independently verified.")

    return ResearchPlan(
        topic=topic,
        facets=facets,
        queries=queries[: budget.max_round_one_queries],
        template_id=template_id,
        resolution_strategy=resolution_strategy,
        source_strategy=source_strategy,
        source_policy=_source_strategy_source_policy(source_strategy),
        evidence_policy=_source_strategy_evidence_policy(source_strategy),
        caveats=_dedupe_strings(caveats),
    )


def _format_budget_summary(budget: ResearchBudget) -> str:
    return (
        f"llm_calls<={budget.max_llm_calls}, "
        f"round1_queries<={budget.max_round_one_queries}, "
        f"follow_up_queries<={budget.max_follow_up_queries}, "
        f"fetch_pages<={budget.max_fetch_pages}"
    )


async def run_deep_research(
    query: str,
    *,
    llm: Any,
    providers: Sequence[str] | None = None,
    max_rounds: int = 2,
    max_results_per_query: int = 4,
    time_range: str | None = None,
    source_strategy: str | None = "web_only",
    knowledge_search: Callable[[str], Sequence[SearchDocument]] | None = None,
    max_fetch_pages: int = 3,
) -> WebResearchResult:
    if llm is None:
        raise ValueError("run_deep_research requires an llm instance.")

    workflow_nodes: list[dict[str, object]] = []
    round_results: list[SearchResponse] = []
    caveats: list[str] = []
    budget = _default_budget(max_rounds=max_rounds, max_fetch_pages=max_fetch_pages)
    intent = _infer_research_intent(query, time_range)
    resolved_source_strategy = _normalize_source_strategy(source_strategy)
    template_match = _resolve_domain_template(query)
    template_id = None
    template_facets: list[str] = []
    template_prompt_hint = ""
    if template_match:
        template_id = str(template_match.get("template_id") or "").strip() or None
        template_facets = _dedupe_strings(str(item) for item in template_match.get("facets", []))
        template_prompt_hint = str(template_match.get("prompt_hint") or "").strip()
    generic_facets = _generic_facets_for_intent(intent, resolved_source_strategy)

    async def invoke_json_prompt(prompt: str) -> tuple[str, Any | None]:
        response = await llm.ainvoke(prompt)
        text = _response_text(response)
        return text, _extract_json_payload(text)

    started_at = int(time.time() * 1000)
    plan_prompt = f"""
You are a research planner.
Return JSON only:
{{
  "topic": "short topic",
  "facets": ["facet_1", "facet_2"],
  "query_groups": [
    {{"query": "search query", "facet": "facet_1", "bucket": "official", "expected_source_tier": "primary"}}
  ],
  "source_strategy": "{resolved_source_strategy}",
  "caveats": ["optional caveat"],
  "related_questions": ["concise user-facing follow-up question"]
}}

Rules:
- Use at most {budget.max_round_one_queries} first-round queries.
- Prefer official, policy, or data buckets first when the topic is time-sensitive.
- Keep facets short and stable.
- Treat any matched template as an optional hint, not a required structure.
- Generate facets from the user query first. Only borrow template facets when they clearly fit.
- Source strategy is {resolved_source_strategy}.
- If source strategy is community_first, discover community/forum/social leads through search-engine indexed pages and user-provided links only. Do not assume direct X API access, scraping, or complete real-time X coverage.
- If using social/community sources, plan at least one independent verification query from news, official pages, docs, GitHub, or other durable web sources.

User query: {query}
Research intent: {json.dumps(intent.__dict__, ensure_ascii=False)}
Source strategy: {resolved_source_strategy}
Suggested template id: {template_id or "none"}
Suggested template hint: {template_prompt_hint or "none"}
Suggested template facets: {json.dumps(template_facets, ensure_ascii=False)}
Generic fallback facets: {json.dumps(generic_facets, ensure_ascii=False)}
"""
    plan_text, plan_payload = await invoke_json_prompt(plan_prompt)
    research_plan = _parse_plan_payload(
        plan_payload,
        query=query,
        template_id=template_id,
        template_facets=template_facets,
        generic_facets=generic_facets,
        intent=intent,
        budget=budget,
        source_strategy=resolved_source_strategy,
    )
    caveats.extend(research_plan.caveats)
    round_one_queries = [item.query for item in research_plan.queries[: budget.max_round_one_queries]] or [query]
    workflow_nodes.append(
        _workflow_node(
            "plan_research",
            "Research Plan",
            started_at_ms=started_at,
            ended_at_ms=int(time.time() * 1000),
            tool_name="llm_plan",
            tool_params={
                "query": query,
                "intent": intent.intent,
                "time_sensitive": intent.time_sensitive,
                "time_window": intent.time_window,
                "template_id": research_plan.template_id or "",
                "resolution_strategy": research_plan.resolution_strategy,
                "source_strategy": research_plan.source_strategy,
                "facets": research_plan.facets,
                "budget": _format_budget_summary(budget),
            },
            tool_result=" | ".join(round_one_queries),
        )
    )

    round_one_started = int(time.time() * 1000)
    round_one_responses: list[SearchResponse] = []
    for item in research_plan.queries[: budget.max_round_one_queries]:
        response = await search_web(
            item.query,
            max_results=max_results_per_query,
            providers=providers,
            search_depth="advanced",
            topic=item.bucket if item.bucket == "news" else None,
            time_range=time_range,
            include_answer=True,
        )
        round_one_responses.append(
            _tag_response_for_source_strategy(
                response,
                source_strategy=resolved_source_strategy,
            )
        )
    if not round_one_responses:
        response = await search_web(
            query,
            max_results=max_results_per_query,
            providers=providers,
            search_depth="advanced",
            time_range=time_range,
            include_answer=True,
        )
        round_one_responses.append(
            _tag_response_for_source_strategy(
                response,
                source_strategy=resolved_source_strategy,
            )
        )
    round_results.extend(round_one_responses)
    caveats.extend(_response_caveats(round_one_responses))
    deduped_round_one_sources = dedupe_search_documents(
        [doc for response in round_one_responses for doc in response.results],
        limit=8,
        max_per_domain=2,
    )
    workflow_nodes.append(
        _workflow_node(
            "search_round_1",
            "Search Round 1",
            started_at_ms=round_one_started,
            ended_at_ms=int(time.time() * 1000),
            tool_name="search_web",
            tool_params={
                "queries": [item.query for item in research_plan.queries[: budget.max_round_one_queries]],
                "providers": list(providers or []),
                "source_strategy": research_plan.source_strategy,
            },
            tool_result=f"sources={len(deduped_round_one_sources)}",
        )
    )

    round_one = ResearchRound(
        name="search_round_1",
        queries=[response.query for response in round_one_responses],
        source_count=len(deduped_round_one_sources),
        highlights=[doc.snippet for doc in deduped_round_one_sources[:3] if doc.snippet],
    )

    knowledge_context = _knowledge_context_text(query, knowledge_search)
    analysis_started = int(time.time() * 1000)
    analysis_prompt = f"""
You are a research analyst.
Return JSON only:
{{
  "sufficient": true,
  "follow_up_queries": [
    {{"query": "repair query", "facet": "facet", "bucket": "news", "expected_source_tier": "secondary"}}
  ],
  "findings": [{{"claim": "finding", "status": "verified", "note": "why", "evidence": ["source-1"]}}],
  "contradictions": [{{"topic": "topic", "details": "details", "sources": ["source-1"]}}],
  "caveats": ["optional caveat"]
}}

Rules:
- Propose at most {budget.max_follow_up_queries} follow-up queries.
- Only propose follow-up queries that repair coverage gaps or contradictions.
- If evidence is sufficient, return an empty follow-up list.
- For community-first research, treat social/forum posts as leads. Mark claims as partial or unverified unless an independent durable source supports them.

User query: {query}
Research intent: {json.dumps(intent.__dict__, ensure_ascii=False)}
Source strategy: {research_plan.source_strategy}
Research plan facets: {json.dumps(research_plan.facets, ensure_ascii=False)}
First-round results:
{chr(10).join(_search_response_excerpt(response) for response in round_one_responses)}

Knowledge context:
{knowledge_context or "none"}
"""
    analysis_text, analysis_payload = await invoke_json_prompt(analysis_prompt)
    analysis_data = analysis_payload if isinstance(analysis_payload, dict) else {}
    preliminary_findings = _parse_findings(analysis_data.get("findings"))
    preliminary_contradictions = _parse_contradictions(analysis_data.get("contradictions"))
    caveats.extend(_normalize_text_list(analysis_data.get("caveats")))
    follow_up_queries = _parse_research_queries(
        analysis_data.get("follow_up_queries"),
        fallback_facet=_format_facet_label(research_plan.facets[0]) if research_plan.facets else "overview",
        limit=budget.max_follow_up_queries,
    )
    if not follow_up_queries and max_rounds > 1 and preliminary_contradictions and budget.max_follow_up_queries > 0:
        contradiction_hint = preliminary_contradictions[0].topic
        fallback_query = (
            f"{query} {contradiction_hint}"
            if contradiction_hint and contradiction_hint.lower() not in query.lower()
            else query
        )
        follow_up_queries = [
            ResearchQuery(
                query=fallback_query,
                facet=_format_facet_label(research_plan.facets[0]) if research_plan.facets else "overview",
                bucket="news",
                expected_source_tier="secondary",
            )
        ]
        caveats.append("Follow-up planning fell back to a contradiction repair query.")
    workflow_nodes.append(
        _workflow_node(
            "analyze_gaps",
            "Gap Analysis",
            started_at_ms=analysis_started,
            ended_at_ms=int(time.time() * 1000),
            tool_name="llm_analysis",
            tool_params={"round": 1, "follow_up_budget": budget.max_follow_up_queries},
            tool_result=analysis_text[:240],
        )
    )

    round_two_responses: list[SearchResponse] = []
    round_two_sources: list[SearchDocument] = []
    round_two_started = int(time.time() * 1000)
    if max_rounds > 1 and follow_up_queries and budget.max_follow_up_queries > 0:
        for item in follow_up_queries[: budget.max_follow_up_queries]:
            response = await search_web(
                item.query,
                max_results=max_results_per_query,
                providers=providers,
                search_depth="advanced",
                topic=item.bucket if item.bucket == "news" else None,
                time_range=time_range,
                include_answer=True,
            )
            round_two_responses.append(
                _tag_response_for_source_strategy(
                    response,
                    source_strategy=resolved_source_strategy,
                )
            )
        round_results.extend(round_two_responses)
        caveats.extend(_response_caveats(round_two_responses))
        round_two_sources = dedupe_search_documents(
            [doc for response in round_two_responses for doc in response.results],
            limit=8,
            max_per_domain=2,
        )
        round_two_result = f"sources={len(round_two_sources)}"
    else:
        round_two_result = "skipped"
    workflow_nodes.append(
        _workflow_node(
            "search_round_2",
            "Search Round 2",
            started_at_ms=round_two_started,
            ended_at_ms=int(time.time() * 1000),
            tool_name="search_web",
            tool_params={
                "queries": [item.query for item in follow_up_queries[: budget.max_follow_up_queries]],
                "source_strategy": research_plan.source_strategy,
            },
            tool_result=round_two_result,
        )
    )

    rounds: list[ResearchRound] = [round_one]
    if follow_up_queries:
        rounds.append(
            ResearchRound(
                name="search_round_2",
                queries=[item.query for item in follow_up_queries[: budget.max_follow_up_queries]],
                source_count=len(round_two_sources),
                highlights=[doc.snippet for doc in round_two_sources[:3] if doc.snippet],
            )
        )

    all_sources = dedupe_search_documents(
        [doc for response in round_results for doc in response.results],
        limit=8,
        max_per_domain=2,
    )

    fetch_started = int(time.time() * 1000)
    fetched_docs: list[SearchDocument] = []
    fetch_limit = min(len(all_sources), budget.max_fetch_pages)
    if budget.max_fetch_pages < max_fetch_pages:
        caveats.append(f"Fetch pages capped at {budget.max_fetch_pages} by research budget.")
    for source in all_sources[:fetch_limit]:
        if not source.url:
            continue
        if not _should_fetch_source(source, source_strategy=resolved_source_strategy):
            continue
        try:
            fetched_docs.append(await fetch_webpage_document(source.url))
        except Exception:
            logger.warning("fetch_primary_pages failed url=%s", source.url, exc_info=True)
    tagged_fetched_docs = _tag_documents_for_source_strategy(
        fetched_docs,
        source_strategy=resolved_source_strategy,
    )
    enriched_sources = dedupe_search_documents([*tagged_fetched_docs, *all_sources], limit=8, max_per_domain=2)
    fetch_result = f"fetched={len(fetched_docs)}"
    if not fetched_docs:
        fetch_result = "fetched=0"
    workflow_nodes.append(
        _workflow_node(
            "fetch_primary_pages",
            "Fetch Primary Pages",
            started_at_ms=fetch_started,
            ended_at_ms=int(time.time() * 1000),
            tool_name="fetch_webpage",
            tool_params={"max_pages": fetch_limit},
            tool_result=fetch_result,
        )
    )

    synthesize_started = int(time.time() * 1000)
    synthesis_prompt = f"""
You are a research synthesis assistant.
Return JSON only:
{{
  "summary": "short summary",
  "highlights": ["highlight 1", "highlight 2"],
  "findings": [{{"claim": "finding", "status": "verified", "note": "why", "evidence": ["source-1"]}}],
  "contradictions": [{{"topic": "topic", "details": "details", "sources": ["source-1"]}}],
  "caveats": ["optional caveat"]
}}

User query: {query}
Research intent: {json.dumps(intent.__dict__, ensure_ascii=False)}
Research plan: {json.dumps({
    "topic": research_plan.topic,
    "facets": research_plan.facets,
    "template_id": research_plan.template_id,
    "resolution_strategy": research_plan.resolution_strategy,
    "source_strategy": research_plan.source_strategy,
    "source_policy": research_plan.source_policy,
    "evidence_policy": research_plan.evidence_policy,
}, ensure_ascii=False)}
Research caveats so far: {json.dumps(_dedupe_strings(caveats), ensure_ascii=False)}
Rules:
- If source_strategy is community_first, separate "community signals" from verified facts.
- Do not present social/forum posts as confirmed evidence unless durable independent sources support the same claim.
- Mention coverage limits when X/social results come through search-engine indexes rather than direct platform APIs.
Knowledge context:
{knowledge_context or "none"}

Sources:
{chr(10).join(f"{index}. {source.title} | {source.url} | {(source.raw_text or source.snippet)[:400]}" for index, source in enumerate(enriched_sources, 1))}
"""
    synthesis_text, synthesis_payload = await invoke_json_prompt(synthesis_prompt)
    synthesis_data = synthesis_payload if isinstance(synthesis_payload, dict) else {}
    summary = str(synthesis_data.get("summary") or "").strip()
    if not summary:
        summary = synthesis_text[:400].strip() or f"Completed web research for '{query}'."

    highlights = [
        str(item).strip()
        for item in synthesis_data.get("highlights", [])
        if str(item).strip()
    ]
    if not highlights:
        highlights = [doc.snippet for doc in enriched_sources[:3] if doc.snippet]

    findings = _parse_findings(synthesis_data.get("findings")) or preliminary_findings
    contradictions = (
        _parse_contradictions(synthesis_data.get("contradictions"))
        or preliminary_contradictions
    )
    findings, contradictions = _attach_source_references(findings, contradictions, enriched_sources)
    caveats.extend(_normalize_text_list(synthesis_data.get("caveats")))
    related_questions = _normalize_text_list(synthesis_data.get("related_questions"))
    if not related_questions:
        related_questions = build_related_questions(query, enriched_sources, search_strategy=None)
    workflow_nodes.append(
        _workflow_node(
            "synthesize_report",
            "Synthesize Report",
            started_at_ms=synthesize_started,
            ended_at_ms=int(time.time() * 1000),
            tool_name="llm_synthesis",
            tool_params={"sources": len(enriched_sources), "facets": research_plan.facets},
            tool_result=summary[:240],
        )
    )

    provider_labels: list[str] = []
    for response in round_results:
        if response.provider and response.provider not in provider_labels:
            provider_labels.append(response.provider)

    provider_capabilities = _response_capabilities(round_results)
    caveats = _dedupe_strings([*caveats, *_response_caveats(round_results)])

    return WebResearchResult(
        query=query,
        provider=provider_labels[0] if provider_labels else "research",
        provider_summary=" + ".join(provider_labels) if provider_labels else "research",
        answer=summary,
        summary=summary,
        rewritten_query=research_plan.queries[0].query if research_plan.queries else query,
        sources=enriched_sources,
        highlights=highlights[:5],
        findings=findings,
        contradictions=contradictions,
        rounds=rounds,
        workflow_nodes=workflow_nodes,
        provider_capabilities=provider_capabilities,
        caveats=caveats,
        research_intent=intent,
        research_plan=research_plan,
        related_questions=related_questions,
    )
