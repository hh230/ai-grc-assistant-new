"""``HttpResearchCrawler`` — the reference ``ResearchCrawlerPort`` adapter (CLAUDE.md §17:
connectors are plugins behind a port). Built from ``grc_regulatory_crawlers``'s already-built,
polite, robots.txt-respecting primitives — ADR-0025's explicit future-work note ("reuse
grc_regulatory_crawlers, not build a second crawler") — never its regulatory-specific
``HttpRegulatoryCrawler``, whose ``discover``/``fetch`` signatures are coupled to
``grc_regulatory_intelligence``'s own domain types.
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from grc_knowledge_intelligence import SourceExcerpt, TrustedSource
from grc_knowledge_research import DiscoveredDocumentRef, ResearchCrawlerPort
from grc_regulatory_crawlers.exceptions import CrawlerFetchError
from grc_regulatory_crawlers.html_extraction import discover_links, html_to_text
from grc_regulatory_crawlers.http_fetcher import HttpFetcher, HttpResponse
from grc_regulatory_crawlers.pdf_extraction import pdf_to_text
from grc_regulatory_crawlers.rate_limiter import PoliteRateLimiter
from grc_regulatory_crawlers.robots import RobotsChecker

DEFAULT_USER_AGENT = (
    "AIGRCAssistant-KnowledgeResearchCrawler/1.0 "
    "(+autonomous-knowledge-research; no aggressive crawling; robots.txt honored)"
)

# A fetched excerpt feeds an LLM prompt (CLAUDE.md §7: every call has a token/cost budget) —
# this caps one document's contribution regardless of how large the page it came from is.
DEFAULT_MAX_EXCERPT_CHARS = 20_000


class HttpResearchCrawler(ResearchCrawlerPort):
    """Discovers document links from a trusted source's ``url``, then fetches and normalizes
    each one (HTML/PDF/plain text) into a ``SourceExcerpt``."""

    def __init__(
        self,
        fetcher: HttpFetcher,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        rate_limiter: PoliteRateLimiter | None = None,
        robots: RobotsChecker | None = None,
        max_excerpt_chars: int = DEFAULT_MAX_EXCERPT_CHARS,
    ) -> None:
        self._fetcher = fetcher
        self._user_agent = user_agent
        self._rate_limiter = rate_limiter or PoliteRateLimiter()
        self._robots = robots or RobotsChecker(fetcher, user_agent=user_agent)
        self._max_excerpt_chars = max_excerpt_chars

    async def discover(self, source: TrustedSource) -> tuple[DiscoveredDocumentRef, ...]:
        response = await self._get(source.url)
        if "html" not in response.content_type.lower():
            return ()
        html = response.body.decode("utf-8", errors="replace")
        # Anti-corruption translation (CLAUDE.md §15): discover_links returns
        # grc_regulatory_intelligence's own DiscoveredDocumentRef — a foreign bounded
        # context's type never leaves this adapter.
        return tuple(
            DiscoveredDocumentRef(url=ref.url, title=ref.title)
            for ref in discover_links(html, base_url=source.url)
        )

    async def fetch(self, source: TrustedSource, ref: DiscoveredDocumentRef) -> SourceExcerpt:
        response = await self._get(ref.url)
        text = _normalize(response)
        return SourceExcerpt(
            source=source,
            text=text[: self._max_excerpt_chars],
            fetched_at=datetime.now(timezone.utc),
        )

    async def _get(self, url: str) -> HttpResponse:
        if not await self._robots.is_allowed(url):
            raise CrawlerFetchError(f"disallowed by robots.txt: {url!r}")
        await self._rate_limiter.wait(_host(url))
        return await self._fetcher.get(url, user_agent=self._user_agent)


def _normalize(response: HttpResponse) -> str:
    content_type = response.content_type.lower()
    if "pdf" in content_type:
        return pdf_to_text(response.body)
    if "html" in content_type:
        return html_to_text(response.body.decode("utf-8", errors="replace"))
    return response.body.decode("utf-8", errors="replace")


def _host(url: str) -> str:
    return urlparse(url).netloc
