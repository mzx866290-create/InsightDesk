from __future__ import annotations

import os
from collections.abc import Sequence

from .providers import (
    DuckDuckGoSearchProvider,
    SearchProvider,
    SearxngSearchProvider,
    TavilySearchProvider,
)
from .types import SearchProviderCapabilities, UnsupportedSearchProviderError


def _parse_provider_sequence(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []

    sequence: list[str] = []
    seen: set[str] = set()
    for part in raw_value.split(","):
        normalized = part.strip().lower()
        if not normalized or normalized in seen:
            continue
        sequence.append(normalized)
        seen.add(normalized)
    return sequence


def _dedupe_provider_sequence(sequence: Sequence[str]) -> list[str]:
    deduped: list[str] = []
    for item in sequence:
        normalized = str(item or "").strip().lower()
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped


def _env_provider_sequence() -> list[str]:
    explicit_sequence = _parse_provider_sequence(
        os.getenv("SEARCH_PROVIDER_SEQUENCE") or os.getenv("DEFAULT_SEARCH_PROVIDER_SEQUENCE")
    )
    if explicit_sequence:
        return explicit_sequence

    explicit_default = _parse_provider_sequence(
        os.getenv("SEARCH_PROVIDER") or os.getenv("DEFAULT_SEARCH_PROVIDER")
    )
    if explicit_default:
        return explicit_default

    sequence: list[str] = []
    if str(os.getenv("TAVILY_API_KEY") or "").strip():
        sequence.append("tavily")
    if str(os.getenv("SEARXNG_URL") or "").strip():
        sequence.append("searxng")
    sequence.append("duckduckgo")
    return sequence


def _default_provider_sequence() -> list[str]:
    sequence = _env_provider_sequence()
    if "searxng" not in sequence and str(os.getenv("SEARXNG_URL") or "").strip():
        sequence.append("searxng")
    if "duckduckgo" not in sequence:
        sequence.append("duckduckgo")
    return _dedupe_provider_sequence(sequence) or ["duckduckgo"]


def normalize_provider_name(provider: str | None) -> str:
    if provider is not None and str(provider).strip():
        return str(provider).strip().lower()
    return _default_provider_sequence()[0]


def normalize_provider_list(providers: Sequence[str] | str | None = None) -> list[str]:
    if providers is None:
        return _default_provider_sequence()
    if isinstance(providers, str):
        parsed = _parse_provider_sequence(providers) or [normalize_provider_name(providers)]
        normalized = _dedupe_provider_sequence(parsed)
        if normalized == ["tavily"] and str(os.getenv("SEARXNG_URL") or "").strip():
            normalized.append("searxng")
        if normalized and normalized[0] == "tavily":
            normalized.append("duckduckgo")
        return _dedupe_provider_sequence(normalized)

    return _dedupe_provider_sequence(str(provider or "") for provider in providers)


def get_default_provider_sequence() -> list[str]:
    return normalize_provider_list(None)


def get_search_provider(provider: str | None = None) -> SearchProvider:
    normalized = normalize_provider_name(provider)
    if normalized == "tavily":
        return TavilySearchProvider()
    if normalized == "searxng":
        return SearxngSearchProvider()
    if normalized == "duckduckgo":
        return DuckDuckGoSearchProvider()
    raise UnsupportedSearchProviderError(f"不支持的搜索 provider: {normalized}")


def get_search_provider_capabilities(provider: str | None = None) -> SearchProviderCapabilities:
    return get_search_provider(provider).get_capabilities()
