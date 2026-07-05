"""``HttpRegulatoryCrawler`` — the reference ``CrawlerPort`` adapter (CLAUDE.md §17: connectors
are plugins behind a port). Polite by construction: every fetch passes through robots.txt and
a per-host rate limit first, and identifies itself with a descriptive User-Agent.
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from grc_regulatory_intelligence import (
    DiscoveredDocumentRef,
    DocumentContentType,
    RegulatoryDocumentInput,
    RegulatorySource,
)
from grc_regulatory_intelligence.ports import CrawlerPort

from .exceptions import CrawlerFetchError
from .html_extraction import discover_links, html_to_text
from .http_fetcher import HttpFetcher, HttpResponse
from .pdf_extraction import pdf_to_text
from .rate_limiter import PoliteRateLimiter
from .robots import RobotsChecker

DEFAULT_USER_AGENT = (
    "AIGRCAssistant-RegulatoryCrawler/1.0 "
    "(+regulatory-compliance-monitoring; no aggressive crawling; robots.txt honored)"
)


class HttpRegulatoryCrawler(CrawlerPort):
    """Discovers document links from a source's ``base_url``, then fetches and normalizes
    each one (HTML/PDF/plain text) into a ``RegulatoryDocumentInput``."""

    def __init__(
        self,
        fetcher: HttpFetcher,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        rate_limiter: PoliteRateLimiter | None = None,
        robots: RobotsChecker | None = None,
    ) -> None:
        self._fetcher = fetcher
        self._user_agent = user_agent
        self._rate_limiter = rate_limiter or PoliteRateLimiter()
        self._robots = robots or RobotsChecker(fetcher, user_agent=user_agent)

    async def discover(self, source: RegulatorySource) -> tuple[DiscoveredDocumentRef, ...]:
        response = await self._get(source.base_url)
        if "html" not in response.content_type.lower():
            return ()
        html = response.body.decode("utf-8", errors="replace")
        return discover_links(html, base_url=source.base_url)

    async def fetch(
        self, source: RegulatorySource, ref: DiscoveredDocumentRef
    ) -> RegulatoryDocumentInput:
        response = await self._get(ref.url)
        content_type, raw_text = _normalize(response)
        return RegulatoryDocumentInput(
            source_id=source.source_id,
            url=ref.url,
            raw_text=raw_text,
            content_type=content_type,
            discovered_at=datetime.now(timezone.utc),
            title=ref.title,
            published_at=ref.published_at,
            updated_at=ref.updated_at,
        )

    async def _get(self, url: str) -> HttpResponse:
        if not await self._robots.is_allowed(url):
            raise CrawlerFetchError(f"disallowed by robots.txt: {url!r}")
        await self._rate_limiter.wait(_host(url))
        return await self._fetcher.get(url, user_agent=self._user_agent)


def _normalize(response: HttpResponse) -> tuple[DocumentContentType, str]:
    content_type = response.content_type.lower()
    if "pdf" in content_type:
        return DocumentContentType.PDF, pdf_to_text(response.body)
    if "html" in content_type:
        html = response.body.decode("utf-8", errors="replace")
        return DocumentContentType.HTML, html_to_text(html)
    return DocumentContentType.TEXT, response.body.decode("utf-8", errors="replace")


def _host(url: str) -> str:
    return urlparse(url).netloc
