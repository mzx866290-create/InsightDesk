import asyncio

from backend.agent import (
    DeepResearchAgent,
    ResearchAgentConfig,
    summarize_reusable_archives,
    build_fallback_research_plan,
    build_query_matrix,
    classify_research_intent,
    create_runtime_agent_registry,
    evaluate_research_sources,
    select_priority_sources,
)
from search_runtime.types import (
    ResearchFinding,
    ResearchPlan,
    ResearchQuery,
    ResearchRound,
    SearchDocument,
    WebResearchResult,
)


def _research_result(query: str) -> WebResearchResult:
    return WebResearchResult(
        query=query,
        provider="fake",
        provider_summary="fake",
        summary="Research summary",
        answer="Research summary",
        rewritten_query=f"{query} rewritten",
        sources=[
            SearchDocument(
                doc_id="source-1",
                provider="fake",
                title="Source One",
                url="https://example.com/one",
                snippet="Source snippet",
                domain="pbc.gov.cn",
                published_at="2026-04-20",
            )
        ],
        highlights=["Important highlight"],
        findings=[
            ResearchFinding(
                claim="Important claim",
                evidence=["[1] Source One"],
                note="Supported by source",
            )
        ],
        rounds=[
            ResearchRound(
                name="search_round_1",
                queries=[query],
                source_count=1,
                highlights=["Source snippet"],
            )
        ],
        workflow_nodes=[{"id": "plan_research", "status": "completed"}],
        caveats=["Provider is fake"],
    )


def _unsourced_research_result(query: str) -> WebResearchResult:
    return WebResearchResult(
        query=query,
        provider="fake",
        provider_summary="fake",
        summary="Unsourced summary",
        answer="Unsourced summary",
        sources=[],
        findings=[
            ResearchFinding(
                claim="Unsourced market claim",
                evidence=[],
                note="Needs supporting evidence",
            )
        ],
        caveats=["No sources returned"],
    )


def test_research_intent_classifier_detects_time_sensitive_request():
    intent = classify_research_intent("最新 AI Agent 行业动态")

    assert intent.time_sensitive is True
    assert intent.time_window == "30d"
    assert intent.intent == "industry_research"


def test_fallback_plan_uses_finance_template_facets():
    plan = build_fallback_research_plan("latest China finance industry updates")

    assert plan.template_id == "finance"
    assert "macro_policy" in plan.facets
    assert plan.queries


def test_query_matrix_groups_by_source_bucket_order():
    plan = ResearchPlan(
        topic="topic",
        queries=[
            ResearchQuery("news query", "overview", "news", "secondary"),
            ResearchQuery("official query", "overview", "official", "primary"),
            ResearchQuery("report query", "overview", "reports", "secondary"),
        ],
    )

    matrix = build_query_matrix(plan)

    assert list(matrix) == ["official", "reports", "news"]
    assert matrix["official"][0].query == "official query"


def test_source_evaluator_adds_v2_metadata_and_prioritizes_primary_sources():
    docs = [
        SearchDocument(
            doc_id="tertiary",
            provider="fake",
            title="Forum",
            url="https://reddit.com/r/topic",
            snippet="forum",
            domain="reddit.com",
        ),
        SearchDocument(
            doc_id="primary",
            provider="fake",
            title="Regulator",
            url="https://pbc.gov.cn/update",
            snippet="official",
            domain="pbc.gov.cn",
            published_at="2026-04-20",
        ),
    ]

    evaluated = evaluate_research_sources(docs, provider_caveats=["no strict time filter"])
    priority = select_priority_sources(evaluated, limit=1)

    assert evaluated[0].source_tier == "tertiary"
    assert evaluated[1].source_tier == "primary"
    assert evaluated[1].provider_caveat == "no strict time filter"
    assert priority[0].doc.doc_id == "primary"


def test_deep_research_agent_calls_deep_runner_with_task_metadata():
    calls = []

    class FakeLLM:
        pass

    async def fake_deep_runner(query, **kwargs):
        calls.append((query, kwargs))
        return _research_result(query)

    agent = DeepResearchAgent(
        llm=FakeLLM(),
        config=ResearchAgentConfig(mode="deep"),
        deep_runner=fake_deep_runner,
    )

    result = asyncio.run(
        agent.execute(
            {
                "id": "step-1",
                "type": "research",
                "description": "fallback description",
                "input": "OpenAI agents latest",
                "metadata": {
                    "providers": ["tavily"],
                    "max_rounds": 2,
                    "max_results_per_query": 3,
                    "max_fetch_pages": 1,
                    "time_range": "30d",
                },
            },
            {"session_id": "test-session"},
        )
    )

    assert result["status"] == "completed"
    assert result["metadata"]["research_mode"] == "deep"
    assert result["metadata"]["source_count"] == 1
    assert result["metadata"]["atomic_claim_count"] == 2
    assert result["sources"][0]["title"] == "Source One"
    assert result["sources"][0]["source_tier"] == "primary"
    assert "研究发现：" in result["output"]
    artifact = result["artifacts"][0]
    assert artifact["version"] == "v2"
    assert artifact["atomic_claims"][0]["claim_id"] == "claim-001"
    assert artifact["claim_verifications"][0]["supporting_sources"]
    assert artifact["claim_evidence_chains"][0]["claim_id"] == "claim-001"
    assert artifact["claim_evidence_chains"][0]["supporting_source_count"] == 1
    assert artifact["claim_evidence_chains"][0]["supporting_source_ids"] == ["source-1"]
    assert artifact["claim_evidence_chains"][0]["sources"][0]["source_id"] == "source-1"
    assert artifact["claim_evidence_chains"][0]["sources"][0]["provider"] == "fake"
    assert artifact["claim_evidence_chains"][0]["sources"][0]["source_tier"] == "primary"
    assert artifact["citation_panel"]["version"] == "v2"
    assert artifact["citation_panel"]["source_index"]["source-1"]["provider"] == "fake"
    assert artifact["citation_panel"]["claim_source_links"] == [
        {"claim_id": "claim-001", "source_id": "source-1", "link_type": "supports"},
        {"claim_id": "claim-002", "source_id": "source-1", "link_type": "supports"},
    ]
    assert artifact["claim_verification_summary"]["partial_claims"] == 2
    assert artifact["brief_sections"]["verification_summary"]["total_claims"] == 2
    assert artifact["brief_sections"]["executive_summary"] == "Research summary"
    delivery_quality = artifact["delivery_quality"]
    assert delivery_quality["coverage"]["claim_count"] == 2
    assert delivery_quality["coverage"]["supported_claim_count"] == 2
    assert delivery_quality["coverage"]["source_coverage_ratio"] == 1.0
    assert delivery_quality["coverage"]["verification_ratio"] == 0.0
    assert delivery_quality["source_quality"]["source_tier_counts"]["primary"] == 1
    assert delivery_quality["source_quality"]["primary_source_count"] == 1
    assert delivery_quality["source_quality"]["unique_source_family_count"] == 1
    assert [item["id"] for item in delivery_quality["action_items"]] == [
        "strengthen_partial_claims",
        "diversify_sources",
        "review_research_caveats",
    ]
    assert result["metadata"]["partial_claim_count"] == 2
    assert result["metadata"]["unverified_claim_count"] == 0
    assert result["metadata"]["contradiction_count"] == 0
    assert result["metadata"]["claim_source_coverage_ratio"] == 1.0
    assert result["metadata"]["claim_verification_ratio"] == 0.0
    assert result["metadata"]["primary_source_count"] == 1
    assert result["metadata"]["delivery_action_count"] == 3
    assert calls[0][0] == "OpenAI agents latest"
    assert calls[0][1]["providers"] == ["tavily"]
    assert calls[0][1]["max_results_per_query"] == 3
    assert calls[0][1]["max_fetch_pages"] == 1


def test_research_agent_attaches_reusable_archive_context():
    async def fake_quick_runner(query, **kwargs):
        return _research_result(query)

    agent = DeepResearchAgent(
        config=ResearchAgentConfig(mode="quick"),
        quick_runner=fake_quick_runner,
    )

    result = asyncio.run(
        agent.execute(
            {
                "id": "step-archive-reuse",
                "type": "research",
                "input": "AI slide market enterprise adoption",
            },
            {
                "research_archives": [
                    {
                        "artifact_id": "archive-1",
                        "title": "AI slide market",
                        "research_report": {
                            "query": "AI slide market",
                            "summary": "Enterprise buyers pilot AI slide tools.",
                        },
                        "claim_evidence_chains": [
                            {
                                "claim_id": "claim-old",
                                "claim_text": "Enterprise buyers pilot AI slide tools.",
                                "status": "verified",
                                "supporting_source_ids": ["source-old"],
                            }
                        ],
                        "sources": [
                            {
                                "source_id": "source-old",
                                "title": "AI Slides Report",
                                "provider": "bing",
                            }
                        ],
                    }
                ]
            },
        )
    )

    reused = result["artifacts"][0]["reused_archives"]
    assert reused["enabled"] is True
    assert reused["candidate_count"] == 1
    assert reused["candidates"][0]["archive_id"] == "archive-1"
    assert reused["candidates"][0]["matched_claims"][0]["claim_id"] == "claim-old"
    assert result["artifacts"][0]["citation_panel"]["reused_archives"] == reused
    assert result["artifacts"][0]["citation_panel"]["archive_claim_source_links"] == [
        {
            "archive_id": "archive-1",
            "claim_id": "claim-old",
            "source_id": "source-old",
            "link_type": "archive_supports",
        }
    ]


def test_research_agent_flags_cross_archive_conflict_review():
    async def fake_quick_runner(query, **kwargs):
        result = _research_result(query)
        result.findings[0].claim = "Enterprise buyers are not adopting AI slide tools."
        result.summary = "Enterprise buyers are not adopting AI slide tools."
        return result

    agent = DeepResearchAgent(
        config=ResearchAgentConfig(mode="quick"),
        quick_runner=fake_quick_runner,
    )

    result = asyncio.run(
        agent.execute(
            {
                "id": "step-archive-conflict",
                "type": "research",
                "input": "AI slide market enterprise adoption",
            },
            {
                "research_archives": [
                    {
                        "artifact_id": "archive-1",
                        "title": "AI slide market",
                        "research_report": {
                            "query": "AI slide market",
                            "summary": "Enterprise buyers pilot AI slide tools.",
                        },
                        "claim_evidence_chains": [
                            {
                                "claim_id": "claim-old",
                                "claim_text": "Enterprise buyers pilot AI slide tools.",
                                "status": "verified",
                                "supporting_source_ids": ["source-old"],
                            }
                        ],
                        "sources": [{"source_id": "source-old", "title": "AI Slides Report"}],
                    }
                ]
            },
        )
    )

    review = result["artifacts"][0]["archive_conflict_review"]
    citation_panel = result["artifacts"][0]["citation_panel"]

    assert review["status"] == "conflicts_found"
    assert review["conflict_count"] == 1
    assert review["conflicts"][0]["archive_id"] == "archive-1"
    assert review["conflicts"][0]["archive_claim_id"] == "claim-old"
    assert review["review_action"] == "resolve_archive_conflicts"
    assert citation_panel["archive_conflict_review"] == review
    assert citation_panel["archive_conflict_links"] == [
        {
            "claim_id": "claim-001",
            "archive_id": "archive-1",
            "archive_claim_id": "claim-old",
            "link_type": "archive_conflicts",
            "severity": "needs_review",
            "resolution_action": "compare_current_and_archive_sources",
        }
    ]


def test_summarize_reusable_archives_filters_by_query_tokens():
    candidates = summarize_reusable_archives(
        [
            {
                "artifact_id": "archive-match",
                "title": "AI slide adoption",
                "claim_evidence_chains": [
                    {"claim_id": "c1", "claim_text": "Enterprise adoption is rising."}
                ],
                "sources": [{"source_id": "s1", "title": "Enterprise report"}],
            },
            {
                "artifact_id": "archive-miss",
                "title": "Battery prices",
            },
        ],
        query="enterprise slide adoption",
    )

    assert [item["archive_id"] for item in candidates] == ["archive-match"]


def test_deep_research_agent_falls_back_to_quick_without_llm():
    calls = []

    async def fake_quick_runner(query, **kwargs):
        calls.append((query, kwargs))
        return _research_result(query)

    agent = DeepResearchAgent(
        config=ResearchAgentConfig(mode="deep", allow_quick_fallback=True),
        quick_runner=fake_quick_runner,
    )

    result = asyncio.run(
        agent.execute(
            {
                "id": "step-1",
                "type": "research",
                "input": "政策追踪",
                "metadata": {"providers": "bing,duckduckgo"},
            },
            {},
        )
    )

    assert result["status"] == "completed"
    assert result["metadata"]["research_mode"] == "quick"
    assert calls[0][1]["providers"] == ["bing", "duckduckgo"]


def test_research_artifact_delivery_quality_flags_missing_sources():
    async def fake_quick_runner(query, **kwargs):
        return _unsourced_research_result(query)

    agent = DeepResearchAgent(
        config=ResearchAgentConfig(mode="quick"),
        quick_runner=fake_quick_runner,
    )

    result = asyncio.run(
        agent.execute(
            {
                "id": "step-2",
                "type": "research",
                "input": "market claim without sources",
            },
            {},
        )
    )

    artifact = result["artifacts"][0]
    delivery_quality = artifact["delivery_quality"]
    action_ids = [item["id"] for item in delivery_quality["action_items"]]

    assert result["status"] == "completed"
    assert delivery_quality["coverage"]["claim_count"] == 1
    assert delivery_quality["coverage"]["supported_claim_count"] == 0
    assert delivery_quality["coverage"]["unsupported_claim_count"] == 1
    assert delivery_quality["coverage"]["source_coverage_ratio"] == 0.0
    assert delivery_quality["coverage"]["unverified_claim_count"] == 1
    assert delivery_quality["source_quality"]["source_count"] == 0
    assert delivery_quality["source_quality"]["primary_source_count"] == 0
    assert action_ids == [
        "collect_sources",
        "verify_unverified_claims",
        "review_research_caveats",
    ]
    assert result["metadata"]["delivery_action_count"] == 3
    assert result["metadata"]["claim_source_coverage_ratio"] == 0.0


def test_runtime_registry_installs_deep_research_agent():
    class FakeLLM:
        pass

    registry = create_runtime_agent_registry(llm=FakeLLM())

    agent = registry.find_for_task("deep_research")

    assert isinstance(agent, DeepResearchAgent)
