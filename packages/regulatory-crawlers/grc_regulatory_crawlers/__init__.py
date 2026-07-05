"""grc_regulatory_crawlers — the Regulatory Intelligence ingestion layer (Policy Intelligence
PI-P2): polite web crawlers, change detection wiring, observability, and the
``RegulatoryCrawlerRunner`` orchestrator. See README.md.
"""

from __future__ import annotations

from .crawler import DEFAULT_USER_AGENT, HttpRegulatoryCrawler
from .exceptions import CrawlerFetchError
from .html_extraction import discover_links, html_to_text
from .http_fetcher import HttpFetcher, HttpResponse, UrllibHttpFetcher
from .observability import CrawlEvent, CrawlObserver, InMemoryCrawlObserver, LoggingCrawlObserver
from .pdf_extraction import pdf_to_text
from .rate_limiter import PoliteRateLimiter
from .robots import RobotsChecker
from .runner import (
    ObligationStore,
    RawDocumentRecord,
    RawDocumentStore,
    RegulatoryCrawlerRunner,
    SourceCrawlSummary,
)

__all__ = [
    "DEFAULT_USER_AGENT",
    "CrawlEvent",
    "CrawlObserver",
    "CrawlerFetchError",
    "HttpFetcher",
    "HttpRegulatoryCrawler",
    "HttpResponse",
    "InMemoryCrawlObserver",
    "LoggingCrawlObserver",
    "ObligationStore",
    "PoliteRateLimiter",
    "RawDocumentRecord",
    "RawDocumentStore",
    "RegulatoryCrawlerRunner",
    "RobotsChecker",
    "SourceCrawlSummary",
    "UrllibHttpFetcher",
    "discover_links",
    "html_to_text",
    "pdf_to_text",
]
