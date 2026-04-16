from __future__ import annotations

import os

from collections.abc import Sequence

from .providers import SearchProvider, SearxngSearchProvider, TavilySearchProvider
from .types import UnsupportedSearchProviderError

DEFAULT_SEARCH_PROVIDER = (
    str(os.getenv("SEARCH_PROVIDER") or os.getenv("DEFAULT_SEARCH_PROVIDER") or "tavily")
    .strip()
    .lower()
    or "tavily"
)


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


DEFAULT_SEARCH_PROVIDER_SEQUENCE = _parse_provider_sequence(
    os.getenv("SEARCH_PROVIDER_SEQUENCE") or os.getenv("DEFAULT_SEARCH_PROVIDER_SEQUENCE")
)


def normalize_provider_name(provider: str | None) -> str:
    normalized = str(provider or DEFAULT_SEARCH_PROVIDER).strip().lower()
    return normalized or "tavily"


def normalize_provider_list(providers: Sequence[str] | str | None = None) -> list[str]:
    if providers is None:
        normalized = DEFAULT_SEARCH_PROVIDER_SEQUENCE[:] or [DEFAULT_SEARCH_PROVIDER]
    elif isinstance(providers, str):
        normalized = _parse_provider_sequence(providers) or [normalize_provider_name(providers)]
    else:
        normalized = []
        for provider in providers:
            item = normalize_provider_name(provider)
            if item not in normalized:
                normalized.append(item)

    if "searxng" not in normalized and os.getenv("SEARXNG_URL") and normalized == ["tavily"]:
        normalized.append("searxng")

    return normalized or ["tavily"]


def get_default_provider_sequence() -> list[str]:
    return normalize_provider_list(None)


def get_search_provider(provider: str | None = None) -> SearchProvider:
    normalized = normalize_provider_name(provider)
    if normalized == "tavily":
        return TavilySearchProvider()
    if normalized == "searxng":
        return SearxngSearchProvider()
    raise UnsupportedSearchProviderError(f"不支持的搜索 provider: {normalized}")
