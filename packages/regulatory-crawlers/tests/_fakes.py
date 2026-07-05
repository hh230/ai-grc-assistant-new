"""Shared, deterministic test doubles — no real network in any test in this package
(CLAUDE.md §22: mock external calls in unit tests)."""

from __future__ import annotations

from grc_regulatory_crawlers import HttpFetcher, HttpResponse
from grc_regulatory_crawlers.exceptions import CrawlerFetchError


class FakeHttpFetcher(HttpFetcher):
    """Scripted HTTP responses keyed by URL. Raises ``CrawlerFetchError`` for any URL with no
    registered response (mirrors an unreachable host)."""

    def __init__(self, responses: dict[str, HttpResponse | Exception] | None = None) -> None:
        self._responses = dict(responses or {})
        self.requests: list[str] = []

    def register(self, url: str, response: HttpResponse | Exception) -> None:
        self._responses[url] = response

    async def get(self, url: str, *, user_agent: str) -> HttpResponse:
        self.requests.append(url)
        result = self._responses.get(url)
        if result is None:
            raise CrawlerFetchError(f"no fake response registered for {url!r}")
        if isinstance(result, Exception):
            raise result
        return result
