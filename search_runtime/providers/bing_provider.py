from __future__ import annotations

import html
import email.utils
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urlparse

import httpx

from .base import SearchProvider
from ..types import (
    SearchDocument,
    SearchProviderCapabilities,
    SearchProviderHTTPError,
    SearchResponse,
    SearchTimeoutError,
)

_TAG_RE = re.compile(r"<[^>]+>")
_DATE_COMPONENT_RE = re.compile(r"(\d{1,2})\D+(\d{1,2})\D+(\d{4})")


def _contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", str(text or "")))


def _clean_text(value: str | None) -> str:
    text = html.unescape(_TAG_RE.sub(" ", str(value or "")))
    return re.sub(r"\s+", " ", text).strip()


def _extract_published_at(raw_value: str | None) -> str | None:
    raw_text = str(raw_value or "").strip()
    if not raw_text:
        return None

    try:
        parsed = email.utils.parsedate_to_datetime(raw_text)
    except (TypeError, ValueError):
        parsed = None
    if parsed is not None:
        return parsed.strftime("%Y-%m-%d")

    match = _DATE_COMPONENT_RE.search(raw_text)
    if match is None:
        return None

    day = int(match.group(1))
    month = int(match.group(2))
    year = int(match.group(3))
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return None


class BingSearchProvider(SearchProvider):
    name = "bing"
    capabilities = SearchProviderCapabilities(
        name="bing",
        supports_time_range=False,
        supports_news_topic=False,
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
        del include_answer, search_depth, topic, time_range, include_raw_content

        params: dict[str, str] = {
            "q": query,
            "format": "rss",
            "count": str(max(1, int(max_results))),
        }
        if not _contains_cjk(query):
            params.update(
                {
                    "setlang": "en-US",
                    "cc": "us",
                    "ensearch": "1",
                }
            )

        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, trust_env=False) as client:
                response = await client.get(
                    "https://www.bing.com/search",
                    params=params,
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SearchProviderHTTPError(exc.response.status_code, exc.response.text) from exc
        except httpx.TimeoutException as exc:
            raise SearchTimeoutError("搜索请求超时") from exc

        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            raise SearchProviderHTTPError(502, "Invalid Bing RSS response.") from exc

        documents: list[SearchDocument] = []
        for index, item in enumerate(root.findall("./channel/item"), start=1):
            if len(documents) >= max(1, int(max_results)):
                break

            title = _clean_text(item.findtext("title"))
            url = str(item.findtext("link") or "").strip()
            if not title or not url:
                continue

            parsed = urlparse(url)
            documents.append(
                SearchDocument(
                    doc_id=f"{self.name}:{index}:{url}",
                    provider=self.name,
                    source_type="web",
                    title=title,
                    url=url,
                    snippet=_clean_text(item.findtext("description")),
                    published_at=_extract_published_at(item.findtext("pubDate")),
                    domain=parsed.netloc or None,
                )
            )

        return SearchResponse(
            query=query,
            provider=self.name,
            results=documents,
            answer="",
            search_depth="basic",
            provider_capabilities=[self.get_capabilities()],
        )
