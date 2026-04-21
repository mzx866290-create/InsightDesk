from __future__ import annotations

import os
from urllib.parse import urlparse

import httpx

from .base import SearchProvider
from ..types import (
    SearchConfigError,
    SearchDocument,
    SearchProviderCapabilities,
    SearchProviderHTTPError,
    SearchResponse,
    SearchTimeoutError,
)


class SearxngSearchProvider(SearchProvider):
    name = "searxng"
    capabilities = SearchProviderCapabilities(
        name="searxng",
        supports_time_range=True,
        supports_news_topic=True,
        supports_answer=False,
        supports_raw_content=False,
        supports_domain_filter_native=False,
    )

    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        search_depth: str = "basic",
        include_answer: bool = True,
        topic: str | None = None,
        time_range: str | None = None,
        include_raw_content: bool = False,
    ) -> SearchResponse:
        base_url = str(os.getenv("SEARXNG_URL") or "").strip().rstrip("/")
        if not base_url:
            raise SearchConfigError("未配置 SEARXNG_URL")

        params: dict[str, object] = {
            "q": query,
            "format": "json",
            "language": "auto",
            "safesearch": 0,
            "pageno": 1,
        }
        if max_results > 0:
            params["number_of_results"] = max(1, int(max_results))

        normalized_topic = str(topic or "").strip().lower()
        if normalized_topic == "news":
            params["categories"] = "news"
        elif normalized_topic == "academic":
            params["categories"] = "science"

        normalized_time_range = str(time_range or "").strip().lower()
        if normalized_time_range in {"day", "week", "month", "year"}:
            params["time_range"] = normalized_time_range

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(f"{base_url}/search", params=params)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SearchProviderHTTPError(
                exc.response.status_code,
                exc.response.text,
            ) from exc
        except httpx.TimeoutException as exc:
            raise SearchTimeoutError("搜索请求超时") from exc

        payload = response.json()
        results = payload.get("results", [])
        documents: list[SearchDocument] = []
        for index, item in enumerate(results, 1):
            url = str(item.get("url", "") or "")
            parsed = urlparse(url) if url else None
            snippet = str(item.get("content") or item.get("snippet") or "")
            source_type = "news" if normalized_topic == "news" else "web"
            documents.append(
                SearchDocument(
                    doc_id=f"{self.name}:{index}:{url or 'result'}",
                    provider=self.name,
                    source_type=source_type,
                    title=str(item.get("title", "") or "无标题"),
                    url=url,
                    snippet=snippet,
                    raw_text=snippet if include_raw_content else "",
                    published_at=str(
                        item.get("publishedDate")
                        or item.get("published_at")
                        or item.get("published_date")
                        or ""
                    ).strip()
                    or None,
                    domain=parsed.netloc if parsed and parsed.netloc else None,
                    score=float(item.get("score")) if item.get("score") is not None else None,
                )
            )

        return SearchResponse(
            query=query,
            provider=self.name,
            results=documents,
            answer="",
            search_depth=search_depth or "basic",
            provider_capabilities=[self.get_capabilities()],
        )
