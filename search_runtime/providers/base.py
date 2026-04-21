from __future__ import annotations

from abc import ABC, abstractmethod

from ..types import SearchProviderCapabilities, SearchResponse


class SearchProvider(ABC):
    name: str
    capabilities = SearchProviderCapabilities(name="unknown")

    def get_capabilities(self) -> SearchProviderCapabilities:
        return self.capabilities

    @abstractmethod
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
        raise NotImplementedError
