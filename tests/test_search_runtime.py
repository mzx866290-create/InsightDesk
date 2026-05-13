import asyncio
from types import SimpleNamespace

import backend.helpers.task_execution_helpers as task_execution_helpers_module
from backend.helpers.task_execution_helpers import (
    persist_web_research_task_placeholder,
    persist_web_research_task_result,
    run_web_research_task,
)
from backend.stores.task_store import TaskRecord, TaskStatus
from backend.chat_store import connect_sqlite
from search_runtime.providers.bing_provider import BingSearchProvider
from search_runtime.providers.duckduckgo_provider import DuckDuckGoSearchProvider
from search_runtime import registry as search_registry
from search_runtime import service as search_service
from search_runtime.research_service import run_deep_research
from search_runtime.types import (
    SearchDocument,
    SearchProviderCapabilities,
    SearchResponse,
    SearchRuntimeError,
    WebResearchResult,
)
import httpx


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
                answer="summary",
                results=[
                    SearchDocument(
                        doc_id="fake-1",
                        provider="fake",
                        title="Example Result",
                        url="https://example.com/article",
                        snippet="Snippet text",
                        published_at="2026-04-17",
                    )
                ],
            )

    monkeypatch.setattr(search_service, "get_search_provider", lambda provider=None: FakeProvider())

    result = asyncio.run(search_service.search_web_text("AI agent", max_results=4))

    assert "【AI 总结】" in result
    assert "Example Result" in result
    assert "置信度:" in result
    assert "发布时间: 2026-04-17" in result
    assert "__SOURCES__:" in result
    assert '"provider": "fake"' in result
    assert '"confidence"' in result


def test_quick_answer_text_preserves_structured_sources(monkeypatch):
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
            assert query.startswith("今天广东中山天气怎么样")
            assert max_results == 3
            assert include_answer is True
            return SearchResponse(
                query=query,
                provider="fake",
                answer="中山今天小雨，气温约 22-25°C。",
                results=[
                    SearchDocument(
                        doc_id="weather-1",
                        provider="fake",
                        title="中山天气预报",
                        url="https://weather.example.com/zhongshan",
                        snippet="中山小雨，22-25°C。",
                    )
                ],
            )

    monkeypatch.setattr(search_service, "get_search_provider", lambda provider=None: FakeProvider())

    result = asyncio.run(search_service.quick_answer_text("今天广东中山天气怎么样"))

    assert "中山今天小雨" in result
    assert "中山天气预报" in result
    assert "__SOURCES__:" in result
    assert '"type": "web"' in result
    assert '"url": "https://weather.example.com/zhongshan"' in result


def test_search_web_weather_continues_after_irrelevant_provider_results(monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER_SEQUENCE", "bing,duckduckgo")

    class BadWeatherProvider:
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
            return SearchResponse(
                query=query,
                provider="bing",
                results=[
                    SearchDocument(
                        doc_id="calendar-1",
                        provider="bing",
                        title="今日黄历查询",
                        url="https://calendar.example.com/today",
                        snippet="今天是什么日子。",
                    )
                ],
            )

    class WeatherProvider:
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
            return SearchResponse(
                query=query,
                provider="duckduckgo",
                results=[
                    SearchDocument(
                        doc_id="weather-1",
                        provider="duckduckgo",
                        title="中山天气预报",
                        url="https://weather.com.cn/weathern/101281701.shtml",
                        snippet="中山天气预报，及时准确发布中央气象台天气信息。",
                    )
                ],
            )

    def fake_provider(provider=None):
        if provider == "bing":
            return BadWeatherProvider()
        if provider == "duckduckgo":
            return WeatherProvider()
        raise AssertionError(f"unexpected provider: {provider}")

    monkeypatch.setattr(search_service, "get_search_provider", fake_provider)

    response = asyncio.run(search_service.search_web("今天广东中山天气怎么样", max_results=3))

    assert response.provider == "duckduckgo"
    assert [item.title for item in response.results] == ["中山天气预报"]
    assert response.results[0].domain == "weather.com.cn"


def test_quick_answer_text_uses_default_provider_sequence(monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER_SEQUENCE", "bing,duckduckgo")

    class EmptyProvider:
        async def search(self, query, **kwargs):
            return SearchResponse(query=query, provider="bing", results=[])

    class WeatherProvider:
        async def search(self, query, **kwargs):
            return SearchResponse(
                query=query,
                provider="duckduckgo",
                results=[
                    SearchDocument(
                        doc_id="weather-1",
                        provider="duckduckgo",
                        title="中山天气预报",
                        url="https://weather.com.cn/weathern/101281701.shtml",
                        snippet="中山天气预报，及时准确发布中央气象台天气信息。",
                    )
                ],
            )

    def fake_provider(provider=None):
        if provider == "bing":
            return EmptyProvider()
        if provider == "duckduckgo":
            return WeatherProvider()
        raise AssertionError(f"unexpected provider: {provider}")

    monkeypatch.setattr(search_service, "get_search_provider", fake_provider)

    result = asyncio.run(search_service.quick_answer_text("今天广东中山天气怎么样"))

    assert "中山天气预报" in result
    assert "__SOURCES__:" in result
    assert '"provider": "duckduckgo"' in result


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


def test_registry_prefers_available_runtime_providers(monkeypatch):
    monkeypatch.delenv("SEARCH_PROVIDER", raising=False)
    monkeypatch.delenv("DEFAULT_SEARCH_PROVIDER", raising=False)
    monkeypatch.delenv("SEARCH_PROVIDER_SEQUENCE", raising=False)
    monkeypatch.delenv("DEFAULT_SEARCH_PROVIDER_SEQUENCE", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("SEARXNG_URL", raising=False)

    assert search_registry.get_default_provider_sequence() == ["bing", "duckduckgo"]
    assert search_registry.normalize_provider_name(None) == "bing"


def test_registry_respects_explicit_provider_selection(monkeypatch):
    monkeypatch.setenv("SEARXNG_URL", "http://localhost:8888")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-key")

    assert search_registry.normalize_provider_list(["tavily"]) == ["tavily"]
    assert search_registry.normalize_provider_list("tavily") == ["tavily", "searxng", "bing", "duckduckgo"]
    assert search_registry.normalize_provider_list("searxng") == ["searxng"]


def test_query_plan_strips_conversational_prefix_and_generates_candidates():
    plan = search_service._build_query_plan(  # noqa: SLF001
        "please help me find the latest OpenAI agents updates for enterprise users"
    )

    assert plan.effective_query.startswith("the latest OpenAI agents updates")
    assert plan.original_query in plan.query_candidates
    assert any("OpenAI agents updates enterprise users" in item for item in plan.query_candidates)


def test_query_plan_keeps_chinese_weather_out_of_news_topic():
    plan = search_service._build_query_plan("今天广东中山天气怎么样")  # noqa: SLF001

    assert "新闻" not in plan.effective_query
    assert "中国天气网" in plan.effective_query
    assert "weather.com.cn" in plan.effective_query
    assert plan.topic is None
    assert plan.time_range is None


def test_search_web_retries_with_simplified_query_variant(monkeypatch):
    class VariantProvider:
        def __init__(self):
            self.calls: list[str] = []

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
            del max_results, search_depth, include_answer, topic, time_range, include_raw_content
            self.calls.append(query)
            if len(query.split()) > 6:
                raise search_service.SearchProviderHTTPError(400, '{"detail":{"error":"Query is invalid."}}')
            return SearchResponse(
                query=query,
                provider="fake",
                results=[
                    SearchDocument(
                        doc_id="fake-1",
                        provider="fake",
                        title="OpenAI Agents Update",
                        url="https://example.com/agents",
                        snippet="Short successful query",
                    )
                ],
            )

    provider = VariantProvider()
    monkeypatch.setattr(search_service, "get_search_provider", lambda provider_name=None: provider)

    response = asyncio.run(
        search_service.search_web(
            "What are the latest OpenAI agents updates for enterprise users",
            provider="tavily",
        )
    )

    assert len(provider.calls) >= 2
    assert response.results[0].title == "OpenAI Agents Update"
    assert response.rewritten_query == provider.calls[-1]
    assert response.rewritten_query != provider.calls[0]
    assert any("simplified query variant" in item for item in response.provider_caveats)


def test_llm_search_query_planner_rewrites_without_hardcoded_domain_rules():
    class FakeLLM:
        async def ainvoke(self, prompt):
            assert "do not rely on backend hard-coded local rules" in prompt
            assert "Do not invent specific websites" in prompt
            return SimpleNamespace(
                content='{"query":"Guangdong public institution employee recruitment announcements May 2026"}'
            )

    planned = asyncio.run(
        search_service.rewrite_search_query_with_llm(
            FakeLLM(),
            "Where in Guangdong is hiring employees today?",
        )
    )

    assert planned == "Guangdong public institution employee recruitment announcements May 2026 latest news"


def test_quick_web_research_uses_llm_planned_query_when_model_config_is_available(monkeypatch):
    captured: dict[str, object] = {}

    class FakeLLM:
        async def ainvoke(self, prompt):
            assert "Where in Guangdong is hiring employees today?" in prompt
            return SimpleNamespace(
                content='{"query":"Guangdong public institution employee recruitment announcements May 2026"}'
            )

    async def fake_run_web_research(query, **kwargs):
        captured["query"] = query
        captured.update(kwargs)
        return WebResearchResult(
            query=query,
            provider="fake",
            provider_summary="fake",
            answer="ok",
            summary="ok",
            rewritten_query=str(kwargs.get("planned_query") or query),
            sources=[],
            caveats=[],
        )

    async def set_progress(_progress):
        return None

    monkeypatch.setattr(task_execution_helpers_module, "run_web_research", fake_run_web_research)

    record = TaskRecord(
        task_id="quick-plan-1",
        task_type="web_research",
        status=TaskStatus.PENDING,
        params={
            "query": "Where in Guangdong is hiring employees today?",
            "research_mode": "quick",
            "panel_config": {
                "provider": "ollama",
                "model": "qwen3.5-2B:latest",
                "base_url": "http://localhost:11434",
                "api_key": "",
                "temperature": 0.2,
            },
        },
        session_id=None,
        created_at=0,
        updated_at=0,
    )

    asyncio.run(
        run_web_research_task(
            record,
            set_progress=set_progress,
            normalize_model_config=lambda config: config,
            create_llm=lambda *_args: FakeLLM(),
        )
    )

    assert captured["query"] == "Where in Guangdong is hiring employees today?"
    assert (
        captured["planned_query"]
        == "Guangdong public institution employee recruitment announcements May 2026 latest news"
    )
    assert (
        record.params["search_planned_query"]
        == "Guangdong public institution employee recruitment announcements May 2026 latest news"
    )


def test_registry_exposes_provider_capabilities():
    capabilities = search_registry.get_search_provider_capabilities("duckduckgo")

    assert capabilities.name == "duckduckgo"
    assert capabilities.supports_time_range is False
    assert capabilities.supports_news_topic is False
    assert capabilities.supports_answer is False


def test_search_web_falls_back_to_duckduckgo_when_tavily_unauthorized(monkeypatch):
    class UnauthorizedProvider:
        async def search(self, *args, **kwargs):
            raise search_service.SearchProviderHTTPError(
                401, '{"detail":{"error":"Unauthorized: missing or invalid API key."}}'
            )

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
            return SearchResponse(
                query=query,
                provider="duckduckgo",
                results=[
                    SearchDocument(
                        doc_id="ddg-1",
                        provider="duckduckgo",
                        title="DuckDuckGo Result",
                        url="https://example.com/ddg",
                        snippet="fallback result",
                    )
                ],
            )

    def fake_get_provider(name=None):
        if name == "tavily":
            return UnauthorizedProvider()
        if name == "duckduckgo":
            return FallbackProvider()
        raise AssertionError(f"unexpected provider: {name}")

    monkeypatch.setattr(search_service, "get_search_provider", fake_get_provider)

    response = asyncio.run(search_service.search_web("fallback topic", provider="tavily"))

    assert response.provider == "duckduckgo"
    assert response.results[0].title == "DuckDuckGo Result"


def test_duckduckgo_provider_surfaces_clear_connectivity_error(monkeypatch):
    class FailingAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, *args, **kwargs):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr("search_runtime.providers.duckduckgo_provider.httpx.AsyncClient", FailingAsyncClient)
    monkeypatch.setattr(
        "search_runtime.providers.duckduckgo_provider._network_resolution_hint",
        lambda hostname: "duckduckgo.com resolved to non-public address(es): 198.18.0.125",
    )

    try:
        asyncio.run(DuckDuckGoSearchProvider().search("OpenAI agents"))
    except SearchRuntimeError as exc:
        message = str(exc)
        assert "DuckDuckGo endpoint unreachable" in message
        assert "198.18.0.125" in message
    else:
        raise AssertionError("expected SearchRuntimeError for DuckDuckGo connectivity failure")


def test_bing_provider_parses_rss_results(monkeypatch):
    rss_payload = """<?xml version="1.0" encoding="utf-8" ?>
<rss version="2.0">
  <channel>
    <item>
      <title>OpenAI ships new agents platform</title>
      <link>https://example.com/openai-agents</link>
      <description>Platform update for enterprise agent workflows.</description>
      <pubDate>Mon, 21 Apr 2026 08:30:00 GMT</pubDate>
    </item>
    <item>
      <title>Zhongshan weather forecast</title>
      <link>https://weather.example.com/zhongshan</link>
      <description>Localized Bing RSS date format.</description>
      <pubDate>周五, 08 5月 2026 17:56:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

    class FakeResponse:
        status_code = 200
        text = rss_payload

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("search_runtime.providers.bing_provider.httpx.AsyncClient", FakeAsyncClient)

    response = asyncio.run(BingSearchProvider().search("OpenAI agents latest", max_results=3))

    assert response.provider == "bing"
    assert len(response.results) == 2
    assert response.results[0].title == "OpenAI ships new agents platform"
    assert response.results[0].published_at == "2026-04-21"
    assert response.results[1].title == "Zhongshan weather forecast"
    assert response.results[1].published_at == "2026-05-08"


def test_search_web_does_not_fallback_when_provider_list_is_explicit(monkeypatch):
    class UnauthorizedProvider:
        async def search(self, *args, **kwargs):
            raise search_service.SearchProviderHTTPError(
                401, '{"detail":{"error":"Unauthorized: missing or invalid API key."}}'
            )

    monkeypatch.setattr(search_service, "get_search_provider", lambda provider=None: UnauthorizedProvider())

    try:
        asyncio.run(search_service.search_web("fallback topic", providers=["tavily"]))
    except search_service.SearchProviderHTTPError as exc:
        assert exc.status_code == 401
    else:
        raise AssertionError("expected explicit provider failure without fallback")


def test_search_web_respects_explicit_site_filter_and_scores_sources(monkeypatch):
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
            assert query == "OpenAI Agents"
            return SearchResponse(
                query=query,
                provider="fake",
                results=[
                    SearchDocument(
                        doc_id="match-1",
                        provider="fake",
                        title="OpenAI Agents launch",
                        url="https://openai.com/index/agents",
                        snippet="OpenAI agents launch details",
                        published_at="2026-04-17",
                        score=0.5,
                    ),
                    SearchDocument(
                        doc_id="drop-1",
                        provider="fake",
                        title="Mirror page",
                        url="https://mirror.example.com/openai-agents",
                        snippet="Mirror content",
                        published_at="2026-04-17",
                        score=0.99,
                    ),
                ],
            )

    monkeypatch.setattr(search_service, "get_search_provider", lambda provider=None: FakeProvider())

    response = asyncio.run(
        search_service.search_web(
            "OpenAI Agents site:openai.com",
            provider="tavily",
            max_results=5,
        )
    )

    assert response.include_domains == ["openai.com"]
    assert len(response.results) == 1
    assert response.results[0].domain == "openai.com"
    assert response.results[0].confidence is not None
    assert response.results[0].source_quality == "high"
    assert "explicit_domain_match" in response.results[0].evidence_tags


def test_search_web_upgrades_time_sensitive_queries(monkeypatch):
    captured: dict[str, str | None] = {}

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
            captured["query"] = query
            captured["search_depth"] = search_depth
            captured["topic"] = topic
            captured["time_range"] = time_range
            return SearchResponse(
                query=query,
                provider="fake",
                results=[
                    SearchDocument(
                        doc_id="news-1",
                        provider="fake",
                        title="OpenAI latest news",
                        url="https://example.com/news",
                        snippet="Latest update",
                        published_at="2026-04-17",
                    )
                ],
            )

    monkeypatch.setattr(search_service, "get_search_provider", lambda provider=None: FakeProvider())

    response = asyncio.run(search_service.search_web("OpenAI 最新新闻", provider="tavily"))

    assert captured["query"] == "OpenAI 最新新闻"
    assert captured["search_depth"] == "advanced"
    assert captured["topic"] == "news"
    assert captured["time_range"] == "week"
    assert response.search_depth == "advanced"
    assert response.topic == "news"
    assert response.time_range == "week"


def test_search_web_surfaces_provider_caveats_for_unsupported_time_filter(monkeypatch):
    class FakeProvider:
        def get_capabilities(self):
            return SearchProviderCapabilities(
                name="fake",
                supports_time_range=False,
                supports_news_topic=False,
                supports_answer=True,
                supports_raw_content=False,
                supports_domain_filter_native=False,
            )

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
            return SearchResponse(
                query=query,
                provider="fake",
                results=[
                    SearchDocument(
                        doc_id="fake-1",
                        provider="fake",
                        title="Latest update",
                        url="https://example.com/latest",
                        snippet="Recent update.",
                        published_at="2026-04-17",
                    )
                ],
            )

    monkeypatch.setattr(search_service, "get_search_provider", lambda provider=None: FakeProvider())

    response = asyncio.run(
        search_service.search_web(
            "latest finance news",
            provider="tavily",
            include_raw_content=True,
        )
    )

    assert response.provider == "fake"
    assert response.provider_capabilities[0].name == "fake"
    assert any("strict time filtering" in item for item in response.provider_caveats)
    assert any("dedicated news topic filter" in item for item in response.provider_caveats)
    assert any("raw content" in item for item in response.provider_caveats)


def test_search_web_filters_binary_like_download_results(monkeypatch):
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
            return SearchResponse(
                query=query,
                provider="fake",
                results=[
                    SearchDocument(
                        doc_id="pdf-1",
                        provider="fake",
                        title="report.pdf",
                        url="https://221.179.172.81/images/20241210/92391733821803495.pdf",
                        snippet="%PDF-1.7 291 0 obj <</Type /Page /Filter/FlateDecode>> stream endobj",
                    ),
                    SearchDocument(
                        doc_id="html-1",
                        provider="fake",
                        title="AI industry update 2026",
                        url="https://example.com/ai-industry-update",
                        snippet="AI investment and commercialization trends remain strong across enterprise software and infrastructure.",
                        published_at="2026-04-17",
                    ),
                ],
            )

    monkeypatch.setattr(search_service, "get_search_provider", lambda provider=None: FakeProvider())

    response = asyncio.run(search_service.search_web("AI industry update", provider="tavily"))

    assert len(response.results) == 1
    assert response.results[0].title == "AI industry update 2026"
    assert response.results[0].url == "https://example.com/ai-industry-update"
    assert "binary_excerpt" not in response.results[0].evidence_tags


def test_search_web_caps_same_domain_results(monkeypatch):
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
            return SearchResponse(
                query=query,
                provider="fake",
                results=[
                    SearchDocument(
                        doc_id="a-1",
                        provider="fake",
                        title="OpenAI agents overview",
                        url="https://openai.com/post-1",
                        snippet="OpenAI agents overview and launch notes.",
                        published_at="2026-04-17",
                    ),
                    SearchDocument(
                        doc_id="a-2",
                        provider="fake",
                        title="OpenAI agents pricing",
                        url="https://openai.com/post-2",
                        snippet="OpenAI agents pricing and packaging.",
                        published_at="2026-04-16",
                    ),
                    SearchDocument(
                        doc_id="a-3",
                        provider="fake",
                        title="OpenAI agents enterprise",
                        url="https://openai.com/post-3",
                        snippet="OpenAI agents enterprise adoption details.",
                        published_at="2026-04-15",
                    ),
                    SearchDocument(
                        doc_id="b-1",
                        provider="fake",
                        title="Anthropic agents comparison",
                        url="https://anthropic.com/agents",
                        snippet="Independent comparison of agent products.",
                        published_at="2026-04-17",
                    ),
                ],
            )

    monkeypatch.setattr(search_service, "get_search_provider", lambda provider=None: FakeProvider())

    response = asyncio.run(search_service.search_web("agents market", provider="tavily", max_results=4))

    assert len(response.results) == 3
    assert sum(1 for item in response.results if item.domain == "openai.com") == 2
    assert any(item.domain == "anthropic.com" for item in response.results)


def test_search_web_text_returns_classified_timeout_error(monkeypatch):
    class TimeoutProvider:
        async def search(self, *args, **kwargs):
            raise search_service.SearchTimeoutError("boom")

    monkeypatch.setattr(search_service, "get_search_provider", lambda provider=None: TimeoutProvider())

    result = asyncio.run(search_service.search_web_text("OpenAI latest", provider="tavily"))

    assert "[search_timeout]" in result
    assert "联网搜索超时" in result


def test_search_web_text_returns_auth_error_for_invalid_provider_key(monkeypatch):
    class UnauthorizedProvider:
        async def search(self, *args, **kwargs):
            raise search_service.SearchProviderHTTPError(
                401, '{"detail":{"error":"Unauthorized: missing or invalid API key."}}'
            )

    monkeypatch.setattr(search_service, "get_search_provider", lambda provider=None: UnauthorizedProvider())

    result = asyncio.run(search_service.search_web_text("OpenAI latest", provider="tavily"))

    assert "[search_auth]" in result
    assert "API Key" in result


def test_run_deep_research_builds_rounds_findings_and_workflow(monkeypatch):
    responses = iter(
        [
            '{"queries":["OpenAI agents latest", "OpenAI agents benchmarks", "OpenAI agents enterprise"]}',
            '{"sufficient": false, "follow_up_queries": ["OpenAI agents pricing", "OpenAI agents adoption"], "findings": [{"claim":"Agents are getting productized","status":"verified","note":"Seen across launch posts","evidence":["source-1"]}], "contradictions": [{"topic":"Pricing","details":"Different pages mention different plans","sources":["source-2"]}]}',
            '{"summary":"OpenAI agents research summary","highlights":["productization is visible","enterprise adoption is growing"],"findings":[{"claim":"OpenAI agents are moving into products","status":"verified","note":"Seen across multiple sources","evidence":["source-1","source-3"]}],"contradictions":[{"topic":"Pricing","details":"Different pages mention different plans","sources":["source-2"]}]}',
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

    assert result.summary == "OpenAI agents research summary"
    assert len(result.rounds) == 2
    assert result.rounds[0].queries[0] == "OpenAI agents latest"
    assert result.findings[0].claim.startswith("OpenAI agents")
    assert result.findings[0].evidence
    assert result.findings[0].evidence[0].startswith("[1] ")
    assert result.contradictions[0].topic == "Pricing"
    assert result.contradictions[0].sources
    assert len(result.workflow_nodes) == 6
    assert result.workflow_nodes[-1]["id"] == "synthesize_report"
    assert len(result.sources) >= 2
    assert "证据来源：" in result.to_text()


def test_run_deep_research_builds_structured_plan_metadata(monkeypatch):
    responses = iter(
        [
            '{"topic":"China finance updates","facets":["macro_policy","capital_markets"],"query_groups":[{"query":"China finance policy latest","facet":"macro_policy","bucket":"official","expected_source_tier":"primary"},{"query":"China capital markets latest","facet":"capital_markets","bucket":"news","expected_source_tier":"secondary"}]}',
            '{"sufficient": true, "follow_up_queries": [], "findings": [], "contradictions": [], "caveats": ["Need stricter official coverage for policy interpretation."]}',
            '{"summary":"China finance research summary","highlights":["policy remains active"],"findings":[],"contradictions":[],"caveats":["DuckDuckGo-like providers may approximate freshness."]}',
        ]
    )

    class FakeLLM:
        async def ainvoke(self, prompt: str):
            return type("Resp", (), {"content": next(responses)})()

    async def fake_search_web(query, **kwargs):
        return SearchResponse(
            query=query,
            provider="tavily",
            provider_capabilities=[
                SearchProviderCapabilities(
                    name="tavily",
                    supports_time_range=True,
                    supports_news_topic=True,
                    supports_answer=True,
                    supports_raw_content=True,
                    supports_domain_filter_native=False,
                )
            ],
            results=[
                SearchDocument(
                    doc_id=f"{query}-1",
                    provider="tavily",
                    title=f"{query} result",
                    url=f"https://example.com/{query.replace(' ', '-')}",
                    snippet=f"{query} snippet",
                    published_at="2026-04-17",
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
            "latest China finance industry updates",
            llm=FakeLLM(),
            providers=["tavily"],
            max_rounds=1,
            max_results_per_query=2,
        )
    )

    assert result.research_intent is not None
    assert result.research_intent.time_sensitive is True
    assert result.research_plan is not None
    assert result.research_plan.template_id == "finance"
    assert result.research_plan.resolution_strategy == "llm_with_template_hint"
    assert result.research_plan.queries[0].bucket == "official"
    assert any("official coverage" in item for item in result.caveats)


def test_run_deep_research_uses_template_fallback_when_llm_plan_is_empty(monkeypatch):
    responses = iter(
        [
            '{"topic":"latest finance updates","facets":[],"query_groups":[]}',
            '{"sufficient": true, "follow_up_queries": [], "findings": [], "contradictions": []}',
            '{"summary":"Finance fallback summary","highlights":["template fallback used"],"findings":[],"contradictions":[]}',
        ]
    )

    class FakeLLM:
        async def ainvoke(self, prompt: str):
            return type("Resp", (), {"content": next(responses)})()

    async def fake_search_web(query, **kwargs):
        return SearchResponse(
            query=query,
            provider="tavily",
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
            "latest finance industry updates",
            llm=FakeLLM(),
            providers=["tavily"],
            max_rounds=1,
            max_results_per_query=2,
        )
    )

    assert result.research_plan is not None
    assert result.research_plan.template_id == "finance"
    assert result.research_plan.resolution_strategy == "template_fallback"
    assert result.research_plan.facets == [
        "macro_policy",
        "banking_insurance",
        "capital_markets",
        "cross_border_fx",
        "fintech_funding",
        "regulation_risk",
    ]
    assert result.research_plan.queries
    assert result.research_plan.queries[0].bucket == "official"
    assert any("domain template" in item for item in result.caveats)
    assert any("deterministic query templates" in item for item in result.caveats)


def test_run_deep_research_uses_generic_fallback_when_no_template_matches(monkeypatch):
    responses = iter(
        [
            '{"topic":"latest AI infrastructure market outlook","facets":[],"query_groups":[]}',
            '{"sufficient": true, "follow_up_queries": [], "findings": [], "contradictions": []}',
            '{"summary":"Generic fallback summary","highlights":["generic fallback used"],"findings":[],"contradictions":[]}',
        ]
    )

    class FakeLLM:
        async def ainvoke(self, prompt: str):
            return type("Resp", (), {"content": next(responses)})()

    async def fake_search_web(query, **kwargs):
        return SearchResponse(
            query=query,
            provider="tavily",
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
            "latest AI infrastructure market outlook",
            llm=FakeLLM(),
            providers=["tavily"],
            max_rounds=1,
            max_results_per_query=2,
        )
    )

    assert result.research_plan is not None
    assert result.research_plan.template_id is None
    assert result.research_plan.resolution_strategy == "generic_fallback"
    assert result.research_plan.facets == [
        "market_structure",
        "policy_regulation",
        "data_metrics",
        "corporate_activity",
        "risks_controversies",
    ]
    assert result.research_plan.queries
    assert result.research_plan.queries[0].bucket == "official"
    assert any("generic facets" in item for item in result.caveats)
    assert any("deterministic query templates" in item for item in result.caveats)


def test_run_deep_research_normalizes_string_caveats(monkeypatch):
    responses = iter(
        [
            '{"topic":"OpenAI agents market","facets":["market_structure"],"query_groups":[{"query":"OpenAI agents market structure","facet":"market_structure","bucket":"news","expected_source_tier":"secondary"}],"caveats":"Need fresh market data."}',
            '{"sufficient": true, "follow_up_queries": [], "findings": [], "contradictions": [], "caveats": "Check date coverage."}',
            '{"summary":"OpenAI agents market summary","highlights":["market is evolving"],"findings":[],"contradictions":[],"caveats":"Some figures need confirmation."}',
        ]
    )

    class FakeLLM:
        async def ainvoke(self, prompt: str):
            return type("Resp", (), {"content": next(responses)})()

    async def fake_search_web(query, **kwargs):
        return SearchResponse(
            query=query,
            provider="searxng",
            results=[
                SearchDocument(
                    doc_id=f"{query}-1",
                    provider="searxng",
                    title=f"{query} result",
                    url=f"https://example.com/{query.replace(' ', '-')}",
                    snippet=f"{query} snippet",
                )
            ],
        )

    monkeypatch.setattr("search_runtime.research_service.search_web", fake_search_web)

    result = asyncio.run(
        run_deep_research(
            "OpenAI agents market",
            llm=FakeLLM(),
            providers=["searxng"],
            max_rounds=1,
            max_results_per_query=1,
            max_fetch_pages=0,
        )
    )

    assert "Need fresh market data." in result.caveats
    assert "Check date coverage." in result.caveats
    assert "Some figures need confirmation." in result.caveats
    assert "N" not in result.caveats
    assert "e" not in result.caveats


def test_run_deep_research_strips_think_tags_from_llm_output(monkeypatch):
    responses = iter(
        [
            '<think>internal planning</think>{"queries":["51job latest"]}',
            '<think>internal analysis</think>{"sufficient": true, "follow_up_queries": [], "findings": [], "contradictions": []}',
            '<think>internal synthesis</think>{"summary":"51job is active.","highlights":["platform still online"],"findings":[],"contradictions":[]}',
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
                    doc_id="src-1",
                    provider="tavily",
                    title="51job",
                    url="https://www.51job.com/",
                    snippet="51job remains online",
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
            "51job",
            llm=FakeLLM(),
            providers=["tavily"],
            max_rounds=1,
            max_results_per_query=1,
        )
    )

    assert result.summary == "51job is active."
    assert "<think>" not in result.summary
    assert all("<think>" not in item for item in result.highlights)
    assert result.rounds[0].queries == ["51job latest"]


def test_run_web_research_task_builds_summary(monkeypatch):
    async def fake_run_web_research(
        query,
        *,
        max_results=8,
        planned_query=None,
        provider=None,
        providers=None,
        search_depth="advanced",
        topic=None,
        time_range=None,
    ):
        assert query == "OpenAI agents"
        assert planned_query is None
        assert provider == "tavily"
        assert max_results == 6
        return WebResearchResult(
            query=query,
            provider="tavily",
            answer="research answer ready",
            sources=[
                SearchDocument(
                    doc_id="src-1",
                    provider="tavily",
                    title="OpenAI News",
                    url="https://example.com/openai-news",
                    snippet="A useful snippet",
                )
            ],
            highlights=["key highlight"],
        )

    monkeypatch.setattr(task_execution_helpers_module, "run_web_research", fake_run_web_research)

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
    assert "OpenAI agents" in record.result
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
            summary="deep research complete",
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

    monkeypatch.setattr(task_execution_helpers_module, "run_deep_research", fake_run_deep_research)

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
    assert record.params["research_summary"] == "deep research complete"
    assert record.params["research_workflow_nodes"][0]["id"] == "plan_research"
    assert "deep research complete" in (record.result or "")


def test_run_web_research_task_falls_back_to_quick_mode_when_deep_config_is_missing(monkeypatch):
    async def fake_run_web_research(
        query,
        *,
        max_results=8,
        planned_query=None,
        provider=None,
        providers=None,
        search_depth="advanced",
        topic=None,
        time_range=None,
    ):
        assert query == "OpenAI agents"
        assert planned_query is None
        assert provider == "tavily"
        return WebResearchResult(
            query=query,
            provider="tavily",
            provider_summary="tavily",
            summary="quick fallback complete",
            sources=[
                SearchDocument(
                    doc_id="src-quick-1",
                    provider="tavily",
                    title="Quick Source",
                    url="https://example.com/quick",
                    snippet="Quick snippet",
                )
            ],
            caveats=["provider note"],
        )

    monkeypatch.setattr(task_execution_helpers_module, "run_web_research", fake_run_web_research)

    record = TaskRecord(
        task_id="task-research-deep-fallback",
        task_type="web_research",
        status=TaskStatus.RUNNING,
        params={
            "query": "OpenAI agents",
            "provider": "tavily",
            "research_mode": "deep",
        },
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
    assert record.params["research_requested_mode"] == "deep"
    assert record.params["research_mode"] == "quick"
    assert "未提供研究模型配置" in record.params["research_fallback_note"]
    assert any(
        "已自动回退到 quick 模式" in str(item)
        for item in record.params.get("research_caveats", [])
    )
    assert "quick fallback complete" in (record.result or "")


def test_run_web_research_task_deep_mode_allows_default_provider_selection(monkeypatch):
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
        assert providers is None
        assert max_rounds == 2
        assert max_results_per_query == 4
        return WebResearchResult(
            query=query,
            provider="searxng",
            provider_summary="searxng",
            summary="deep research complete via default provider",
            sources=[
                SearchDocument(
                    doc_id="src-deep-default-1",
                    provider="searxng",
                    title="Deep Source",
                    url="https://example.com/deep-default",
                    snippet="Deep snippet",
                )
            ],
        )

    monkeypatch.setattr(task_execution_helpers_module, "run_deep_research", fake_run_deep_research)

    def fake_create_llm(provider, model_name, base_url, api_key, temperature):
        return object()

    record = TaskRecord(
        task_id="task-research-deep-default-provider",
        task_type="web_research",
        status=TaskStatus.RUNNING,
        params={
            "query": "OpenAI agents",
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
    assert record.params["research_mode"] == "deep"
    assert record.params["research_provider"] == "searxng"
    assert "default provider" in (record.result or "")


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
        content="research summary",
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
    assert rows[1][1] == "research summary"
    assert rows[1][2] == "panel-main"
    assert rows[1][3] == "grp-research"
    assert rows[1][4] == "task-research-persist"
    assert rows[1][5] == "web_research"
    assert "Example Source" in rows[1][6]
    assert "plan_research" in rows[1][7]
