"""Unit tests for HttpRegulatoryCrawler: HTML discovery, HTML/PDF/text fetch normalization,
robots.txt enforcement, and rate limiting — all against a fake HTTP transport, never a real
server."""

from __future__ import annotations

import pytest
from grc_regulatory_crawlers import HttpRegulatoryCrawler, HttpResponse, PoliteRateLimiter
from grc_regulatory_crawlers.exceptions import CrawlerFetchError
from grc_regulatory_intelligence import (
    DiscoveredDocumentRef,
    DocumentContentType,
    PollingFrequency,
    RegulatorySource,
    SourceType,
)

from ._fakes import FakeHttpFetcher
from .test_pdf_extraction import _minimal_pdf

_ALLOW_ALL_ROBOTS = HttpResponse(
    status=200, content_type="text/plain", body=b"User-agent: *\nAllow: /\n"
)


def _source(base_url: str = "https://example.gov") -> RegulatorySource:
    return RegulatorySource(
        source_id="sa-example",
        regulator_name="Example Regulator",
        jurisdiction="SA",
        language="ar",
        base_url=base_url,
        source_type=SourceType.WEBSITE,
        polling_frequency=PollingFrequency.WEEKLY,
    )


def _fetcher_allowing_all() -> FakeHttpFetcher:
    return FakeHttpFetcher({"https://example.gov/robots.txt": _ALLOW_ALL_ROBOTS})


async def test_discover_finds_links_on_an_html_listing_page() -> None:
    fetcher = _fetcher_allowing_all()
    fetcher.register(
        "https://example.gov",
        HttpResponse(
            status=200,
            content_type="text/html; charset=utf-8",
            body=b'<a href="/circulars/1">Circular 1</a>',
        ),
    )
    crawler = HttpRegulatoryCrawler(fetcher, rate_limiter=PoliteRateLimiter(min_interval_seconds=0))

    refs = await crawler.discover(_source())

    assert refs == (
        DiscoveredDocumentRef(url="https://example.gov/circulars/1", title="Circular 1"),
    )


async def test_discover_returns_empty_for_a_non_html_response() -> None:
    fetcher = _fetcher_allowing_all()
    fetcher.register(
        "https://example.gov",
        HttpResponse(status=200, content_type="application/pdf", body=b"%PDF-fake"),
    )
    crawler = HttpRegulatoryCrawler(fetcher, rate_limiter=PoliteRateLimiter(min_interval_seconds=0))

    assert await crawler.discover(_source()) == ()


async def test_fetch_normalizes_html_content() -> None:
    fetcher = _fetcher_allowing_all()
    fetcher.register(
        "https://example.gov/circulars/1",
        HttpResponse(
            status=200,
            content_type="text/html",
            body=b"<p>Entities shall encrypt data at rest.</p>",
        ),
    )
    crawler = HttpRegulatoryCrawler(fetcher, rate_limiter=PoliteRateLimiter(min_interval_seconds=0))

    document = await crawler.fetch(
        _source(), DiscoveredDocumentRef(url="https://example.gov/circulars/1", title="Circular 1")
    )

    assert document.content_type == DocumentContentType.HTML
    assert document.raw_text == "Entities shall encrypt data at rest."
    assert document.source_id == "sa-example"
    assert document.title == "Circular 1"


async def test_fetch_normalizes_pdf_content() -> None:
    fetcher = _fetcher_allowing_all()
    pdf_bytes = _minimal_pdf("Entities shall log every access attempt.")
    fetcher.register(
        "https://example.gov/circulars/2.pdf",
        HttpResponse(status=200, content_type="application/pdf", body=pdf_bytes),
    )
    crawler = HttpRegulatoryCrawler(fetcher, rate_limiter=PoliteRateLimiter(min_interval_seconds=0))

    document = await crawler.fetch(
        _source(), DiscoveredDocumentRef(url="https://example.gov/circulars/2.pdf")
    )

    assert document.content_type == DocumentContentType.PDF
    assert "Entities shall log every access attempt." in document.raw_text


async def test_fetch_normalizes_plain_text_content() -> None:
    fetcher = _fetcher_allowing_all()
    fetcher.register(
        "https://example.gov/circulars/3.txt",
        HttpResponse(status=200, content_type="text/plain", body=b"Plain regulatory text."),
    )
    crawler = HttpRegulatoryCrawler(fetcher, rate_limiter=PoliteRateLimiter(min_interval_seconds=0))

    document = await crawler.fetch(
        _source(), DiscoveredDocumentRef(url="https://example.gov/circulars/3.txt")
    )

    assert document.content_type == DocumentContentType.TEXT
    assert document.raw_text == "Plain regulatory text."


async def test_fetch_raises_when_disallowed_by_robots_txt() -> None:
    fetcher = FakeHttpFetcher(
        {
            "https://example.gov/robots.txt": HttpResponse(
                status=200, content_type="text/plain", body=b"User-agent: *\nDisallow: /private/\n"
            )
        }
    )
    crawler = HttpRegulatoryCrawler(fetcher, rate_limiter=PoliteRateLimiter(min_interval_seconds=0))

    with pytest.raises(CrawlerFetchError, match="disallowed by robots.txt"):
        await crawler.fetch(
            _source(), DiscoveredDocumentRef(url="https://example.gov/private/secret")
        )


async def test_fetch_propagates_network_failures() -> None:
    fetcher = _fetcher_allowing_all()
    # No response registered for this URL -> FakeHttpFetcher raises CrawlerFetchError.
    crawler = HttpRegulatoryCrawler(fetcher, rate_limiter=PoliteRateLimiter(min_interval_seconds=0))

    with pytest.raises(CrawlerFetchError):
        await crawler.fetch(_source(), DiscoveredDocumentRef(url="https://example.gov/missing"))
