from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable, Sequence
from typing import Any

from .service import dedupe_search_documents, fetch_webpage_document, search_web
from .types import (
    ResearchBudget,
    ResearchContradiction,
    ResearchFinding,
    ResearchIntent,
    ResearchPlan,
    ResearchQuery,
    ResearchRound,
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


def _dedupe_strings(items: Sequence[str]) -> list[str]:
    deduped: list[str] = []
    for item in items:
        cleaned = str(item or "").strip()
        if cleaned and cleaned not in deduped:
            deduped.append(cleaned)
    return deduped


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


def _generic_facets_for_intent(intent: ResearchIntent) -> list[str]:
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

    if intent.time_sensitive:
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

        caveats = _dedupe_strings(str(item) for item in payload.get("caveats", []) if str(item).strip())

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
        queries = _fallback_query_matrix(query, facets=facets, intent=intent, budget=budget)
        caveats.append("Query planning fell back to deterministic query templates.")

    return ResearchPlan(
        topic=topic,
        facets=facets,
        queries=queries[: budget.max_round_one_queries],
        template_id=template_id,
        resolution_strategy=resolution_strategy,
        source_policy=dict(DEFAULT_SOURCE_POLICY),
        evidence_policy=dict(DEFAULT_EVIDENCE_POLICY),
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
    template_match = _resolve_domain_template(query)
    template_id = None
    template_facets: list[str] = []
    template_prompt_hint = ""
    if template_match:
        template_id = str(template_match.get("template_id") or "").strip() or None
        template_facets = _dedupe_strings(str(item) for item in template_match.get("facets", []))
        template_prompt_hint = str(template_match.get("prompt_hint") or "").strip()
    generic_facets = _generic_facets_for_intent(intent)

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
  "caveats": ["optional caveat"]
}}

Rules:
- Use at most {budget.max_round_one_queries} first-round queries.
- Prefer official, policy, or data buckets first when the topic is time-sensitive.
- Keep facets short and stable.
- Treat any matched template as an optional hint, not a required structure.
- Generate facets from the user query first. Only borrow template facets when they clearly fit.

User query: {query}
Research intent: {json.dumps(intent.__dict__, ensure_ascii=False)}
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
                "facets": research_plan.facets,
                "budget": _format_budget_summary(budget),
            },
            tool_result=" | ".join(round_one_queries),
        )
    )

    round_one_started = int(time.time() * 1000)
    round_one_responses: list[SearchResponse] = []
    for item in research_plan.queries[: budget.max_round_one_queries]:
        round_one_responses.append(
            await search_web(
                item.query,
                max_results=max_results_per_query,
                providers=providers,
                search_depth="advanced",
                topic=item.bucket if item.bucket == "news" else None,
                time_range=time_range,
                include_answer=True,
            )
        )
    if not round_one_responses:
        round_one_responses.append(
            await search_web(
                query,
                max_results=max_results_per_query,
                providers=providers,
                search_depth="advanced",
                time_range=time_range,
                include_answer=True,
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

User query: {query}
Research intent: {json.dumps(intent.__dict__, ensure_ascii=False)}
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
    caveats.extend(
        _dedupe_strings(str(item) for item in analysis_data.get("caveats", []) if str(item).strip())
    )
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
            round_two_responses.append(
                await search_web(
                    item.query,
                    max_results=max_results_per_query,
                    providers=providers,
                    search_depth="advanced",
                    topic=item.bucket if item.bucket == "news" else None,
                    time_range=time_range,
                    include_answer=True,
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
            tool_params={"queries": [item.query for item in follow_up_queries[: budget.max_follow_up_queries]]},
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
        try:
            fetched_docs.append(await fetch_webpage_document(source.url))
        except Exception:
            logger.warning("fetch_primary_pages failed url=%s", source.url, exc_info=True)
    enriched_sources = dedupe_search_documents([*fetched_docs, *all_sources], limit=8, max_per_domain=2)
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
}, ensure_ascii=False)}
Research caveats so far: {json.dumps(_dedupe_strings(caveats), ensure_ascii=False)}
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
    caveats.extend(
        _dedupe_strings(str(item) for item in synthesis_data.get("caveats", []) if str(item).strip())
    )
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
    )
