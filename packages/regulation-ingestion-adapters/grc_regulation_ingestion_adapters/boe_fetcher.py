"""Fetches one Board of Experts law page and parses it (Knowledge Intelligence KI-P6,
ADR-0030) — the one seam real network I/O crosses in this module; ``boe_parser.py`` itself
stays pure text-in/struct-out and is unit-tested without any network access.

Polite by the same rules ``grc_knowledge_research_adapters.HttpResearchCrawler`` already
established for KI-P2: robots.txt is checked before every fetch, and a rate limiter paces
requests per host — this pipeline hits the same real government portal for every regulation in
the catalog (hundreds of pages), so it must not behave like an aggressive scraper.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from urllib.parse import urlparse

from grc_regulatory_crawlers import (
    CrawlerFetchError,
    HttpFetcher,
    PoliteRateLimiter,
    RobotsChecker,
    html_to_text,
)

from .boe_parser import ParsedRegulation, parse_boe_page

DEFAULT_USER_AGENT = (
    "AIGRCAssistant-RegulationIngestion/1.0 "
    "(+autonomous-regulation-ingestion; no aggressive crawling; robots.txt honored)"
)


@dataclass(frozen=True)
class FetchedRegulationPage:
    parsed: ParsedRegulation
    raw_html: bytes
    content_hash: str


def _host(url: str) -> str:
    return urlparse(url).netloc


class BoeRegulationPageFetcher:
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

    async def fetch_and_parse(self, source_url: str, *, name_ar: str) -> FetchedRegulationPage:
        if not await self._robots.is_allowed(source_url):
            raise CrawlerFetchError(f"disallowed by robots.txt: {source_url!r}")
        await self._rate_limiter.wait(_host(source_url))

        response = await self._fetcher.get(source_url, user_agent=self._user_agent)
        if "html" not in response.content_type.lower():
            raise CrawlerFetchError(
                f"expected an HTML law page, got content-type {response.content_type!r}: "
                f"{source_url!r}"
            )
        html = response.body.decode("utf-8", errors="replace")
        text = html_to_text(html)
        parsed = parse_boe_page(text, name_ar=name_ar)
        content_hash = hashlib.sha256(response.body).hexdigest()
        return FetchedRegulationPage(
            parsed=parsed, raw_html=response.body, content_hash=content_hash
        )
