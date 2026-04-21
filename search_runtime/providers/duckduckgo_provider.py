from __future__ import annotations

import html
import ipaddress
import re
import socket
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from .base import SearchProvider
from ..types import (
    SearchDocument,
    SearchProviderCapabilities,
    SearchProviderHTTPError,
    SearchRuntimeError,
    SearchResponse,
    SearchTimeoutError,
)

_RESULT_BLOCK_RE = re.compile(
    r'<div class="result results_links.*?<h2 class="result__title">\s*'
    r'<a[^>]*class="result__a"[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>.*?'
    r'<a class="result__snippet"[^>]*>(?P<snippet>.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(value: str) -> str:
    text = html.unescape(_TAG_RE.sub("", str(value or "")))
    return re.sub(r"\s+", " ", text).strip()


def _resolve_result_url(raw_url: str) -> str:
    candidate = html.unescape(str(raw_url or "").strip())
    if not candidate:
        return ""
    parsed = urlparse(candidate)
    if "duckduckgo.com" not in parsed.netloc.lower():
        return candidate
    redirect = parse_qs(parsed.query).get("uddg", [])
    if redirect:
        return unquote(redirect[0])
    return candidate


def _network_resolution_hint(hostname: str) -> str:
    try:
        records = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    except OSError:
        return ""

    suspicious: list[str] = []
    for record in records:
        try:
            address = str(record[4][0]).strip()
            ip = ipaddress.ip_address(address)
        except (IndexError, ValueError):
            continue
        if not ip.is_global and address not in suspicious:
            suspicious.append(address)

    if not suspicious:
        return ""
    return f"{hostname} resolved to non-public address(es): {', '.join(suspicious)}"


class DuckDuckGoSearchProvider(SearchProvider):
    name = "duckduckgo"
    capabilities = SearchProviderCapabilities(
        name="duckduckgo",
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
        del include_answer, topic, time_range, include_raw_content

        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                response = await client.post(
                    "https://html.duckduckgo.com/html/",
                    data={"q": query},
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                response.raise_for_status()
        except httpx.ConnectError as exc:
            resolution_hint = _network_resolution_hint("duckduckgo.com")
            message = "DuckDuckGo endpoint unreachable."
            if resolution_hint:
                message = f"{message} {resolution_hint}."
            raise SearchRuntimeError(message) from exc
        except httpx.HTTPStatusError as exc:
            raise SearchProviderHTTPError(exc.response.status_code, exc.response.text) from exc
        except httpx.TimeoutException as exc:
            raise SearchTimeoutError("搜索请求超时") from exc

        documents: list[SearchDocument] = []
        for index, match in enumerate(_RESULT_BLOCK_RE.finditer(response.text), start=1):
            if len(documents) >= max(1, int(max_results)):
                break
            url = _resolve_result_url(match.group("href"))
            parsed = urlparse(url) if url else None
            documents.append(
                SearchDocument(
                    doc_id=f"{self.name}:{index}:{url or 'result'}",
                    provider=self.name,
                    source_type="web",
                    title=_strip_html(match.group("title")) or "无标题",
                    url=url,
                    snippet=_strip_html(match.group("snippet")),
                    domain=parsed.netloc if parsed and parsed.netloc else None,
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
