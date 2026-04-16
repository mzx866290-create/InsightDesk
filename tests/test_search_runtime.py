import asyncio

from api_task_execution_helpers import (
    persist_web_research_task_placeholder,
    persist_web_research_task_result,
    run_web_research_task,
)
from api_task_store import TaskRecord, TaskStatus
from chat_store import connect_sqlite
from search_runtime.research_service import run_deep_research
from search_runtime import service as search_service
from search_runtime.types import SearchDocument, SearchResponse, WebResearchResult


def test_search_web_text_formats_results_and_sources(monkeypatch):
    class FakeProvider:
        async def search(
            self,
            query,
            *,
            max_results=5,
            search_depth="basic",
            include_answer=True,
            topic=None,
            time_range=None,
            include_raw_content=False,
        ):
            assert query == "AI agent"
            assert max_results == 4
            return SearchResponse(
                query=query,
                provider="fake",
                answer="这是一段总结",
                results=[
                    SearchDocument(
                        doc_id="fake-1",
                        provider="fake",
                        title="Example Result",
                        url="https://example.com/article",
                        snippet="Snippet text",
                    )
                ],
            )

    monkeypatch.setattr(search_service, "get_search_provider", lambda provider=None: FakeProvider())

    result = asyncio.run(search_service.search_web_text("AI agent", max_results=4))

    assert "【AI 总结】" in result
    assert "Example Result" in result
    assert "__SOURCES__:" in result
    assert "\"provider\": \"fake\"" in result


def test_search_web_falls_back_to_searxng(monkeypatch):
    monkeypatch.setenv("SEARXNG_URL", "http://localhost:8888")

    class FailingProvider:
        async def search(self, *args, **kwargs):
            raise search_service.SearchConfigError("missing tavily")

    class FallbackProvider:
        async def search(
            self,
            query,
            *,
            max_results=5,
            search_depth="basic",
            include_answer=True,
            topic=None,
            time_range=None,
            include_raw_content=False,
        ):
            assert query == "fallback topic"
            return SearchResponse(
                query=query,
                provider="searxng",
                results=[
                    SearchDocument(
                        doc_id="fallback-1",
                        provider="searxng",
                        title="Fallback Result",
                        url="https://fallback.example.com/post",
                        snippet="Fallback snippet",
                    )
                ],
            )

    def fake_get_provider(name=None):
        if name == "tavily":
            return FailingProvider()
        if name == "searxng":
            return FallbackProvider()
        raise AssertionError(f"unexpected provider: {name}")

    monkeypatch.setattr(search_service, "get_search_provider", fake_get_provider)

    response = asyncio.run(
        search_service.search_web(
            "fallback topic",
            provider="tavily",
            max_results=5,
        )
    )

    assert response.provider == "searxng"
    assert len(response.results) == 1
    assert response.results[0].title == "Fallback Result"


def test_run_deep_research_builds_rounds_findings_and_workflow(monkeypatch):
    responses = iter(
        [
            '{"queries":["OpenAI agents latest", "OpenAI agents benchmarks", "OpenAI agents enterprise"]}',
            '{"sufficient": false, "follow_up_queries": ["OpenAI agents pricing", "OpenAI agents adoption"], "findings": [{"claim":"Agents are getting productized","status":"verified","note":"Seen across launch posts","evidence":["source-1"]}], "contradictions": [{"topic":"Pricing","details":"Different pages mention different plans","sources":["source-2"]}]}',
            '{"summary":"本周 OpenAI agents 相关动态集中在产品化、价格和企业采用。","highlights":["产品化推进明显","企业采用增加"],"findings":[{"claim":"OpenAI agents 正在从能力展示走向产品化","status":"verified","note":"多来源一致","evidence":["source-1","source-3"]}],"contradictions":[{"topic":"Pricing","details":"不同来源对计费方案描述不一致","sources":["source-2"]}]}',
        ]
    )

    class FakeLLM:
        async def ainvoke(self, prompt: str):
            return type("Resp", (), {"content": next(responses)})()

    async def fake_search_web(query, **kwargs):
        return SearchResponse(
            query=query,
            provider="tavily",
            answer="stub summary",
            results=[
                SearchDocument(
                    doc_id=f"{query}-1",
                    provider="tavily",
                    title=f"{query} result",
                    url=f"https://example.com/{query.replace(' ', '-')}",
                    snippet=f"{query} snippet",
                )
            ],
        )

    async def fake_fetch_webpage_document(url, *, max_chars=8000):
        return SearchDocument(
            doc_id=f"fetch:{url}",
            provider="fetch",
            title=url,
            url=url,
            snippet="Fetched snippet",
            raw_text="Fetched body",
        )

    monkeypatch.setattr("search_runtime.research_service.search_web", fake_search_web)
    monkeypatch.setattr("search_runtime.research_service.fetch_webpage_document", fake_fetch_webpage_document)

    result = asyncio.run(
        run_deep_research(
            "OpenAI agents",
            llm=FakeLLM(),
            providers=["tavily"],
            max_rounds=2,
            max_results_per_query=2,
        )
    )

    assert result.summary.startswith("本周 OpenAI agents")
    assert len(result.rounds) == 2
    assert result.rounds[0].queries[0] == "OpenAI agents latest"
    assert result.findings[0].claim.startswith("OpenAI agents")
    assert result.contradictions[0].topic == "Pricing"
    assert len(result.workflow_nodes) == 6
    assert result.workflow_nodes[-1]["id"] == "synthesize_report"
    assert len(result.sources) >= 2


def test_run_web_research_task_builds_summary(monkeypatch):
    async def fake_run_web_research(
        query,
        *,
        max_results=8,
        provider=None,
        providers=None,
        search_depth="advanced",
        topic=None,
        time_range=None,
    ):
        assert query == "OpenAI agents"
        assert provider == "tavily"
        assert max_results == 6
        return WebResearchResult(
            query=query,
            provider="tavily",
            answer="核心结论已经生成。",
            sources=[
                SearchDocument(
                    doc_id="src-1",
                    provider="tavily",
                    title="OpenAI News",
                    url="https://example.com/openai-news",
                    snippet="A useful snippet",
                )
            ],
            highlights=["一个关键线索"],
        )

    monkeypatch.setattr("api_task_execution_helpers.run_web_research", fake_run_web_research)

    record = TaskRecord(
        task_id="task-research",
        task_type="web_research",
        status=TaskStatus.RUNNING,
        params={"query": "OpenAI agents", "provider": "tavily", "max_results": 6},
        session_id="session-1",
        created_at=1.0,
        updated_at=1.0,
        progress=0,
    )
    progress_updates: list[int] = []

    async def set_progress(value: int) -> None:
        progress_updates.append(value)

    asyncio.run(run_web_research_task(record, set_progress=set_progress))

    assert progress_updates == [25, 85]
    assert record.result is not None
    assert "研究主题：OpenAI agents" in record.result
    assert "核心结论：" in record.result
    assert "OpenAI News" in record.result
    assert isinstance(record.params.get("research_sources"), list)
    assert record.params["research_sources"][0]["title"] == "OpenAI News"


def test_run_web_research_task_supports_deep_mode(monkeypatch):
    async def fake_run_deep_research(
        query,
        *,
        llm,
        providers=None,
        max_rounds=2,
        max_results_per_query=4,
        time_range=None,
        knowledge_search=None,
    ):
        assert query == "OpenAI agents"
        assert providers == ["tavily"]
        assert max_rounds == 2
        assert max_results_per_query == 4
        return WebResearchResult(
            query=query,
            provider="tavily",
            provider_summary="tavily",
            summary="深度研究完成",
            sources=[
                SearchDocument(
                    doc_id="src-deep-1",
                    provider="tavily",
                    title="Deep Source",
                    url="https://example.com/deep",
                    snippet="Deep snippet",
                )
            ],
            workflow_nodes=[
                {
                    "id": "plan_research",
                    "name": "plan_research",
                    "displayName": "研究规划",
                    "status": "completed",
                }
            ],
        )

    monkeypatch.setattr("api_task_execution_helpers.run_deep_research", fake_run_deep_research)

    llm_calls: list[tuple[str, str]] = []

    def fake_create_llm(provider, model_name, base_url, api_key, temperature):
        llm_calls.append((provider, model_name))
        return object()

    record = TaskRecord(
        task_id="task-research-deep",
        task_type="web_research",
        status=TaskStatus.RUNNING,
        params={
            "query": "OpenAI agents",
            "providers": ["tavily"],
            "research_mode": "deep",
            "panel_config": {
                "panel_id": "panel-main",
                "provider": "ollama",
                "connection_type": "ollama",
                "model": "qwen3.5-2B:latest",
                "base_url": "http://localhost:11434",
                "api_key": "",
                "temperature": 0.3,
                "agent_mode": "auto",
            },
        },
        session_id="session-1",
        created_at=1.0,
        updated_at=1.0,
        progress=0,
    )
    progress_updates: list[int] = []

    async def set_progress(value: int) -> None:
        progress_updates.append(value)

    asyncio.run(
        run_web_research_task(
            record,
            set_progress=set_progress,
            normalize_model_config=lambda value: type("Cfg", (), value)(),
            create_llm=fake_create_llm,
        )
    )

    assert progress_updates == [15, 55, 85]
    assert llm_calls == [("ollama", "qwen3.5-2B:latest")]
    assert record.params["research_mode"] == "deep"
    assert record.params["research_summary"] == "深度研究完成"
    assert record.params["research_workflow_nodes"][0]["id"] == "plan_research"
    assert "深度研究完成" in (record.result or "")


def test_web_research_persistence_helpers_write_placeholder_and_result(tmp_path):
    db_path = tmp_path / "chat_history.db"
    record = TaskRecord(
        task_id="task-research-persist",
        task_type="web_research",
        status=TaskStatus.RUNNING,
        params={
            "query": "AI assistants",
            "panel_id": "panel-main",
            "answer_group_id": "grp-research",
            "model_id": "web_research",
        },
        session_id="session-research",
        created_at=1.0,
        updated_at=1.0,
        progress=20,
    )

    persist_web_research_task_placeholder(record, db_path=str(db_path))
    persist_web_research_task_result(
        record,
        content="研究完成摘要",
        sources=[
            {
                "type": "web",
                "title": "Example Source",
                "url": "https://example.com",
                "snippet": "Example snippet",
                "index": 1,
            }
        ],
        workflow_nodes=[
            {
                "id": "plan_research",
                "name": "plan_research",
                "displayName": "研究规划",
                "status": "completed",
            }
        ],
        db_path=str(db_path),
    )

    with connect_sqlite(str(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT type, content, panel_id, answer_group_id, task_id, task_type, sources_json, workflow_json
            FROM messages
            WHERE session_id = ?
            ORDER BY id
            """,
            ("session-research",),
        ).fetchall()

    assert len(rows) == 2
    assert rows[0][0] == "human"
    assert rows[0][1] == "AI assistants"
    assert rows[1][0] == "ai"
    assert rows[1][1] == "研究完成摘要"
    assert rows[1][2] == "panel-main"
    assert rows[1][3] == "grp-research"
    assert rows[1][4] == "task-research-persist"
    assert rows[1][5] == "web_research"
    assert "Example Source" in rows[1][6]
    assert "plan_research" in rows[1][7]
