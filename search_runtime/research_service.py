from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable, Sequence
from typing import Any

from .service import dedupe_search_documents, fetch_webpage_document, search_web
from .types import (
    ResearchContradiction,
    ResearchFinding,
    ResearchRound,
    SearchDocument,
    SearchResponse,
    WebResearchResult,
)

logger = logging.getLogger(__name__)


def _response_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(str(item) for item in content if item).strip()
    return str(content or "").strip()


def _extract_json_payload(text: str) -> Any | None:
    stripped = str(text or "").strip()
    if not stripped:
        return None

    fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    if fenced_match:
        stripped = fenced_match.group(1).strip()

    for candidate in (stripped, stripped[stripped.find("{") : stripped.rfind("}") + 1] if "{" in stripped and "}" in stripped else ""):
        candidate = candidate.strip()
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _parse_query_list(text: str, *, limit: int) -> list[str]:
    payload = _extract_json_payload(text)
    candidates: list[str] = []
    if isinstance(payload, dict):
        raw_queries = payload.get("queries") or payload.get("follow_up_queries") or []
        if isinstance(raw_queries, list):
            candidates = [str(item).strip() for item in raw_queries if str(item).strip()]

    if not candidates:
        for line in str(text or "").splitlines():
            cleaned = re.sub(r"^\s*[-*\d.]+\s*", "", line).strip()
            if cleaned:
                candidates.append(cleaned)

    deduped: list[str] = []
    for candidate in candidates:
        if candidate not in deduped:
            deduped.append(candidate)
        if len(deduped) >= limit:
            break
    return deduped


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


def _search_response_excerpt(response: SearchResponse) -> str:
    lines = [f"Provider: {response.provider}", f"Query: {response.query}"]
    for index, result in enumerate(response.results[:4], 1):
        lines.append(
            f"{index}. {result.title or '无标题'} | {result.url} | {result.snippet[:220]}"
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
            f"[知识库 {index}] {doc.title or doc.url or '本地资料'}\n{(doc.raw_text or doc.snippet or '')[:600]}"
        )
    return "\n\n".join(parts)


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

    async def invoke_json_prompt(prompt: str) -> tuple[str, Any | None]:
        response = await llm.ainvoke(prompt)
        text = _response_text(response)
        return text, _extract_json_payload(text)

    started_at = int(time.time() * 1000)
    plan_text, _ = await invoke_json_prompt(
        f"""你是研究规划助手。请围绕下面的问题生成 3 个搜索查询词，用于第一轮研究。
输出 JSON：{{"queries":["查询1","查询2","查询3"]}}

用户问题：{query}
"""
    )
    round_one_queries = _parse_query_list(plan_text, limit=3) or [query]
    workflow_nodes.append(
        _workflow_node(
            "plan_research",
            "研究规划",
            started_at_ms=started_at,
            ended_at_ms=int(time.time() * 1000),
            tool_name="llm_plan",
            tool_params={"query": query},
            tool_result="；".join(round_one_queries),
        )
    )

    round_one_started = int(time.time() * 1000)
    round_one_responses: list[SearchResponse] = []
    for item in round_one_queries:
        round_one_responses.append(
            await search_web(
                item,
                max_results=max_results_per_query,
                providers=providers,
                search_depth="advanced",
                time_range=time_range,
                include_answer=True,
            )
        )
    round_results.extend(round_one_responses)
    deduped_round_one_sources = dedupe_search_documents(
        [doc for response in round_one_responses for doc in response.results],
        limit=8,
    )
    workflow_nodes.append(
        _workflow_node(
            "search_round_1",
            "第一轮搜索",
            started_at_ms=round_one_started,
            ended_at_ms=int(time.time() * 1000),
            tool_name="search_web",
            tool_params={"queries": round_one_queries, "providers": list(providers or [])},
            tool_result=f"获得 {len(deduped_round_one_sources)} 条去重来源",
        )
    )

    round_one = ResearchRound(
        name="search_round_1",
        queries=round_one_queries,
        source_count=len(deduped_round_one_sources),
        highlights=[doc.snippet for doc in deduped_round_one_sources[:3] if doc.snippet],
    )

    knowledge_context = _knowledge_context_text(query, knowledge_search)
    analysis_started = int(time.time() * 1000)
    analysis_text, analysis_payload = await invoke_json_prompt(
        f"""你是研究分析助手。请基于第一轮搜索结果判断是否需要第二轮搜索。
输出 JSON：
{{
  "sufficient": true,
  "follow_up_queries": ["补充查询1", "补充查询2"],
  "findings": [{{"claim":"结论","status":"verified","note":"说明","evidence":["来源1"]}}],
  "contradictions": [{{"topic":"争议点","details":"冲突说明","sources":["来源1"]}}]
}}

用户问题：{query}

第一轮结果：
{chr(10).join(_search_response_excerpt(response) for response in round_one_responses)}

知识库补充：
{knowledge_context or "无"}
"""
    )
    analysis_data = analysis_payload if isinstance(analysis_payload, dict) else {}
    preliminary_findings = _parse_findings(analysis_data.get("findings"))
    preliminary_contradictions = _parse_contradictions(analysis_data.get("contradictions"))
    follow_up_queries = _parse_query_list(
        json.dumps({"follow_up_queries": analysis_data.get("follow_up_queries", [])}, ensure_ascii=False)
        if analysis_data
        else analysis_text,
        limit=2,
    )
    if not follow_up_queries and max_rounds > 1 and preliminary_contradictions:
        follow_up_queries = [query]
    workflow_nodes.append(
        _workflow_node(
            "analyze_gaps",
            "缺口分析",
            started_at_ms=analysis_started,
            ended_at_ms=int(time.time() * 1000),
            tool_name="llm_analysis",
            tool_params={"round": 1},
            tool_result=analysis_text[:240],
        )
    )

    round_two_responses: list[SearchResponse] = []
    round_two_sources: list[SearchDocument] = []
    round_two_started = int(time.time() * 1000)
    if max_rounds > 1 and follow_up_queries:
        for item in follow_up_queries[:2]:
            round_two_responses.append(
                await search_web(
                    item,
                    max_results=max_results_per_query,
                    providers=providers,
                    search_depth="advanced",
                    time_range=time_range,
                    include_answer=True,
                )
            )
        round_results.extend(round_two_responses)
        round_two_sources = dedupe_search_documents(
            [doc for response in round_two_responses for doc in response.results],
            limit=8,
        )
        round_two_result = f"获得 {len(round_two_sources)} 条补充来源"
    else:
        round_two_result = "无需进行第二轮搜索"
    workflow_nodes.append(
        _workflow_node(
            "search_round_2",
            "第二轮搜索",
            started_at_ms=round_two_started,
            ended_at_ms=int(time.time() * 1000),
            tool_name="search_web",
            tool_params={"queries": follow_up_queries[:2]},
            tool_result=round_two_result,
        )
    )

    rounds: list[ResearchRound] = [round_one]
    if follow_up_queries:
        rounds.append(
            ResearchRound(
                name="search_round_2",
                queries=follow_up_queries[:2],
                source_count=len(round_two_sources),
                highlights=[doc.snippet for doc in round_two_sources[:3] if doc.snippet],
            )
        )

    all_sources = dedupe_search_documents(
        [doc for response in round_results for doc in response.results],
        limit=8,
    )

    fetch_started = int(time.time() * 1000)
    fetched_docs: list[SearchDocument] = []
    for source in all_sources[: max(0, max_fetch_pages)]:
        if not source.url:
            continue
        try:
            fetched_docs.append(await fetch_webpage_document(source.url))
        except Exception:
            logger.warning("fetch_primary_pages failed url=%s", source.url, exc_info=True)
    enriched_sources = dedupe_search_documents([*fetched_docs, *all_sources], limit=8)
    fetch_result = f"抓取 {len(fetched_docs)} 个网页正文"
    if not fetched_docs:
        fetch_result = "未抓取额外网页正文"
    workflow_nodes.append(
        _workflow_node(
            "fetch_primary_pages",
            "网页正文抓取",
            started_at_ms=fetch_started,
            ended_at_ms=int(time.time() * 1000),
            tool_name="fetch_webpage",
            tool_params={"max_pages": max_fetch_pages},
            tool_result=fetch_result,
        )
    )

    synthesize_started = int(time.time() * 1000)
    synthesis_text, synthesis_payload = await invoke_json_prompt(
        f"""你是研究综合助手。请把多轮搜索结果综合为结构化研究结论。
输出 JSON：
{{
  "summary": "简洁结论",
  "highlights": ["线索1", "线索2"],
  "findings": [{{"claim":"结论","status":"verified","note":"说明","evidence":["来源1"]}}],
  "contradictions": [{{"topic":"争议点","details":"冲突说明","sources":["来源1"]}}]
}}

用户问题：{query}

知识库补充：
{knowledge_context or "无"}

综合来源：
{chr(10).join(f"{index}. {source.title} | {source.url} | {(source.raw_text or source.snippet)[:400]}" for index, source in enumerate(enriched_sources, 1))}
"""
    )
    synthesis_data = synthesis_payload if isinstance(synthesis_payload, dict) else {}
    summary = str(synthesis_data.get("summary") or "").strip()
    if not summary:
        summary = synthesis_text[:400].strip() or f"已完成关于“{query}”的联网研究。"

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
    workflow_nodes.append(
        _workflow_node(
            "synthesize_report",
            "综合结论",
            started_at_ms=synthesize_started,
            ended_at_ms=int(time.time() * 1000),
            tool_name="llm_synthesis",
            tool_params={"sources": len(enriched_sources)},
            tool_result=summary[:240],
        )
    )

    provider_labels: list[str] = []
    for response in round_results:
        if response.provider and response.provider not in provider_labels:
            provider_labels.append(response.provider)

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
    )
