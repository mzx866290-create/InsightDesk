from __future__ import annotations

import json
import logging
import re
from collections.abc import Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from .registry import (
    get_search_provider,
    normalize_provider_name,
    normalize_provider_list,
)
from .types import (
    SearchConfigError,
    SearchDocument,
    SearchProviderHTTPError,
    SearchResponse,
    SearchRuntimeError,
    SearchTimeoutError,
    UnsupportedSearchProviderError,
    WebResearchResult,
)

logger = logging.getLogger(__name__)


def _source_marker(documents: list[SearchDocument]) -> str:
    return json.dumps(
        [document.to_source_item(index) for index, document in enumerate(documents, 1)],
        ensure_ascii=False,
    )


def _append_sources_marker(text: str, documents: list[SearchDocument]) -> str:
    return f"{text}\n\n__SOURCES__:{_source_marker(documents)}"


def _describe_search_error(exc: Exception, *, config_message: str) -> str:
    if isinstance(exc, SearchConfigError):
        return config_message
    if isinstance(exc, SearchProviderHTTPError):
        return f"❌ 搜索 API 请求失败 (HTTP {exc.status_code}): {exc.response_text}"
    if isinstance(exc, SearchTimeoutError):
        return "❌ 搜索请求超时,请稍后重试"
    if isinstance(exc, UnsupportedSearchProviderError):
        return f"❌ {exc}"
    return f"❌ 搜索失败: {exc}"


def _canonicalize_url(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""

    try:
        parsed = urlparse(raw)
    except ValueError:
        return raw

    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]

    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if not key.lower().startswith("utm_")
    ]
    query = urlencode(sorted(query_pairs))
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((scheme, netloc, path, "", query, ""))


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\u4e00-\u9fff]+", " ", str(title or "").lower())).strip()


def _titles_similar(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True
    if left in right or right in left:
        return min(len(left), len(right)) >= 18
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return False
    overlap = len(left_tokens & right_tokens) / max(len(left_tokens), len(right_tokens))
    return overlap >= 0.8 and min(len(left_tokens), len(right_tokens)) >= 3


def dedupe_search_documents(
    documents: Sequence[SearchDocument],
    *,
    limit: int | None = None,
) -> list[SearchDocument]:
    deduped: list[SearchDocument] = []
    seen_urls: set[str] = set()
    seen_titles: list[str] = []
    seen_title_snippets: set[tuple[str, str]] = set()

    for document in documents:
        canonical_url = _canonicalize_url(document.url)
        normalized_title = _normalize_title(document.title)
        normalized_snippet = re.sub(r"\s+", " ", (document.raw_text or document.snippet or "").lower()).strip()[:180]

        if canonical_url and canonical_url in seen_urls:
            continue
        if normalized_title and any(_titles_similar(normalized_title, item) for item in seen_titles):
            if not canonical_url or not normalized_snippet:
                continue
            title_signature = (normalized_title, normalized_snippet)
            if title_signature in seen_title_snippets:
                continue
            seen_title_snippets.add(title_signature)

        normalized_document = SearchDocument(
            doc_id=document.doc_id,
            provider=document.provider,
            source_type=document.source_type,
            title=document.title,
            url=canonical_url or document.url,
            snippet=document.snippet,
            raw_text=document.raw_text,
            published_at=document.published_at,
            fetched_at=document.fetched_at,
            domain=document.domain,
            author=document.author,
            score=document.score,
            trust_score=document.trust_score,
            freshness_score=document.freshness_score,
            evidence_tags=list(document.evidence_tags or []),
        )

        if canonical_url:
            seen_urls.add(canonical_url)
        if normalized_title:
            seen_titles.append(normalized_title)
        if normalized_title and normalized_snippet:
            seen_title_snippets.add((normalized_title, normalized_snippet))

        deduped.append(normalized_document)
        if limit is not None and len(deduped) >= limit:
            break

    return deduped


async def search_web(
    query: str,
    *,
    max_results: int = 5,
    provider: str | None = None,
    providers: Sequence[str] | None = None,
    search_depth: str = "basic",
    topic: str | None = None,
    time_range: str | None = None,
    include_answer: bool = True,
    include_raw_content: bool = False,
) -> SearchResponse:
    explicit_provider_list = providers is not None
    provider_names = normalize_provider_list(providers if explicit_provider_list else provider)
    responses: list[SearchResponse] = []
    errors: list[Exception] = []

    for provider_name in provider_names:
        try:
            response = await get_search_provider(provider_name).search(
                query,
                max_results=max_results,
                search_depth=search_depth,
                include_answer=include_answer,
                topic=topic,
                time_range=time_range,
                include_raw_content=include_raw_content,
            )
        except SearchRuntimeError as exc:
            logger.warning("search_web runtime issue provider=%s error=%s", provider_name, exc)
            errors.append(exc)
            continue
        except Exception as exc:
            logger.exception("search_web failed provider=%s", provider_name)
            errors.append(exc)
            continue

        responses.append(response)
        if response.results and not explicit_provider_list:
            break

    if not responses:
        if errors:
            first_error = errors[0]
            if isinstance(first_error, SearchRuntimeError):
                raise first_error
            raise SearchRuntimeError(str(first_error)) from first_error
        return SearchResponse(query=query, provider="+".join(provider_names), results=[], search_depth=search_depth)

    merged_results: list[SearchDocument] = []
    provider_labels: list[str] = []
    answer = ""
    for response in responses:
        provider_labels.append(response.provider)
        if response.answer and not answer:
            answer = response.answer
        merged_results.extend(response.results)

    return SearchResponse(
        query=query,
        provider=" + ".join(dict.fromkeys(provider_labels)),
        results=dedupe_search_documents(merged_results, limit=max_results),
        answer=answer,
        search_depth=search_depth or "basic",
    )


def format_search_results(query: str, response: SearchResponse) -> str:
    output: list[str] = []

    if response.answer:
        output.append(f"【AI 总结】\n{response.answer}\n")

    output.append(f"【搜索结果 - {query}】\n")

    for index, result in enumerate(response.results, 1):
        output.append(
            f"{index}. {result.title or '无标题'}\n"
            f"链接: {result.url}\n"
            f"摘要: {result.snippet}"
        )

    return _append_sources_marker("\n\n---\n\n".join(output), response.results)


async def search_web_text(
    query: str,
    *,
    max_results: int = 5,
    provider: str | None = None,
    search_depth: str = "basic",
) -> str:
    provider_name = normalize_provider_name(provider)

    try:
        response = await search_web(
            query,
            max_results=max_results,
            provider=provider_name,
            search_depth=search_depth,
            include_answer=True,
        )
    except SearchRuntimeError as exc:
        return _describe_search_error(
            exc,
            config_message="❌ 未配置可用的联网搜索 provider,无法使用联网搜索功能",
        )
    except Exception as exc:
        logger.exception("search_web_text failed provider=%s", provider_name)
        return _describe_search_error(
            exc,
            config_message="❌ 未配置可用的联网搜索 provider,无法使用联网搜索功能",
        )

    if not response.results:
        return f"未找到相关搜索结果: {query}"

    return format_search_results(query, response)


async def quick_answer_text(
    user_question: str,
    *,
    provider: str | None = None,
    max_results: int = 3,
    search_depth: str = "basic",
) -> str:
    provider_name = normalize_provider_name(provider)

    try:
        response = await search_web(
            user_question,
            max_results=max_results,
            provider=provider_name,
            search_depth=search_depth,
            include_answer=True,
        )
    except SearchRuntimeError as exc:
        return _describe_search_error(
            exc,
            config_message="❌ 未配置可用的联网搜索 provider",
        )
    except Exception as exc:
        logger.exception("quick_answer_text failed provider=%s", provider_name)
        return _describe_search_error(
            exc,
            config_message="❌ 未配置可用的联网搜索 provider",
        )

    if response.answer:
        return f"【网络搜索答案】\n{response.answer}"
    return "未能生成答案,请使用 web_search 查看详细结果"


async def fetch_webpage_document(url: str, *, max_chars: int = 8000) -> SearchDocument:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise SearchRuntimeError("缺少 beautifulsoup4 依赖，请运行: pip install beautifulsoup4") from exc

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("fetch_webpage_document HTTP error status=%d url=%s", exc.response.status_code, url)
        raise SearchProviderHTTPError(exc.response.status_code, exc.response.text) from exc
    except httpx.TimeoutException as exc:
        logger.warning("fetch_webpage_document timeout url=%s", url)
        raise SearchTimeoutError("网页请求超时") from exc
    except Exception as exc:
        logger.exception("fetch_webpage_document failed url=%s", url)
        raise SearchRuntimeError(f"抓取网页失败: {exc}") from exc

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    lines = [line.strip() for line in soup.get_text(separator="\n", strip=True).split("\n") if line.strip()]
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n...[内容已截断]"

    parsed = urlparse(url)
    return SearchDocument(
        doc_id=f"fetch:{url}",
        provider="fetch",
        source_type="web",
        title=url,
        url=_canonicalize_url(url) or url,
        snippet=text[:200],
        raw_text=text,
        domain=parsed.netloc or None,
    )


async def fetch_webpage_text(url: str, *, max_chars: int = 8000) -> str:
    try:
        document = await fetch_webpage_document(url, max_chars=max_chars)
    except SearchRuntimeError as exc:
        return _describe_search_error(
            exc,
            config_message="❌ 缺少网页抓取依赖",
        )
    return _append_sources_marker(f"【网页内容 - {url}】\n\n{document.raw_text}", [document])


async def run_web_research(
    query: str,
    *,
    max_results: int = 8,
    provider: str | None = None,
    providers: Sequence[str] | None = None,
    search_depth: str = "advanced",
    topic: str | None = None,
    time_range: str | None = None,
) -> WebResearchResult:
    provider_names = providers if providers is not None else provider
    response = await search_web(
        query,
        max_results=max_results,
        providers=provider_names if isinstance(provider_names, Sequence) and not isinstance(provider_names, str) else None,
        provider=provider if isinstance(provider_names, str) or provider_names is None else None,
        search_depth=search_depth,
        topic=topic,
        time_range=time_range,
        include_answer=True,
    )

    highlights: list[str] = []
    for result in response.results[:3]:
        snippet = result.snippet.strip()
        if snippet:
            highlights.append(snippet if len(snippet) <= 160 else f"{snippet[:157]}...")

    summary = (response.answer or "").strip()
    return WebResearchResult(
        query=query,
        provider=response.provider or normalize_provider_name(provider),
        provider_summary=response.provider or normalize_provider_name(provider),
        answer=response.answer,
        summary=summary,
        sources=response.results,
        highlights=highlights,
    )


def describe_runtime_error(exc: Exception) -> str:
    if isinstance(exc, SearchRuntimeError):
        return _describe_search_error(
            exc,
            config_message="未配置可用的联网搜索 provider,无法使用联网搜索功能",
        )
    return str(exc)
