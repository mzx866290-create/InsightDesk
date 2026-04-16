from __future__ import annotations

import os
from urllib.parse import urlparse

import httpx

from .base import SearchProvider
from ..types import (
    SearchConfigError,
    SearchDocument,
    SearchProviderHTTPError,
    SearchResponse,
    SearchTimeoutError,
)


class TavilySearchProvider(SearchProvider):
    name = "tavily"

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
        api_key = str(os.getenv("TAVILY_API_KEY") or "").strip()
        if not api_key:
            raise SearchConfigError("未配置 TAVILY_API_KEY")

        payload = {
            "query": query,
            "max_results": max(1, int(max_results)),
            "api_key": api_key,
            "search_depth": search_depth or "basic",
            "include_answer": bool(include_answer),
            "include_raw_content": bool(include_raw_content),
        }
        if topic and topic.strip() and topic.strip().lower() != "general":
            payload["topic"] = topic.strip().lower()
        if time_range:
            days = {"day": 1, "week": 7, "month": 30}.get(str(time_range).strip().lower())
            if days:
                payload["days"] = days

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json=payload,
                )
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
            documents.append(
                SearchDocument(
                    doc_id=f"{self.name}:{index}:{url or 'result'}",
                    provider=self.name,
                    source_type="web",
                    title=str(item.get("title", "") or "无标题"),
                    url=url,
                    snippet=str(item.get("content", "") or ""),
                    published_at=str(
                        item.get("published_date")
                        or item.get("published_at")
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
            answer=str(payload.get("answer", "") or ""),
            search_depth=search_depth or "basic",
        )
