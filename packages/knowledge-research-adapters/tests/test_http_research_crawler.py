"""Unit tests for HttpResearchCrawler: HTML discovery, HTML/PDF/text fetch normalization,
excerpt truncation, robots.txt enforcement, and fetch-failure propagation — all against a
fake HTTP transport, never a real server.

The fake fetcher and minimal-PDF builder are inlined here (rather than a shared ``_fakes``
module imported by bare name, the pattern ``grc_regulatory_crawlers``'s own tests use) because
a bare cross-file import in a `tests/` package collides with another package's same-named
helper once the whole monorepo suite collects together under pytest's importlib import mode —
duplicating ~30 lines here avoids that collision entirely."""

from __future__ import annotations

import pytest
from grc_knowledge_intelligence import TrustedSource, TrustedSourceType
from grc_knowledge_research import DiscoveredDocumentRef
from grc_knowledge_research_adapters import HttpResearchCrawler
from grc_regulatory_crawlers.exceptions import CrawlerFetchError
from grc_regulatory_crawlers.http_fetcher import HttpFetcher, HttpResponse
from grc_regulatory_crawlers.rate_limiter import PoliteRateLimiter

_ALLOW_ALL_ROBOTS = HttpResponse(
    status=200, content_type="text/plain", body=b"User-agent: *\nAllow: /\n"
)


class FakeHttpFetcher(HttpFetcher):
    """Scripted HTTP responses keyed by URL. Raises ``CrawlerFetchError`` for any URL with no
    registered response (mirrors an unreachable host)."""

    def __init__(self, responses: dict[str, HttpResponse | Exception] | None = None) -> None:
        self._responses = dict(responses or {})

    def register(self, url: str, response: HttpResponse | Exception) -> None:
        self._responses[url] = response

    async def get(self, url: str, *, user_agent: str) -> HttpResponse:
        result = self._responses.get(url)
        if result is None:
            raise CrawlerFetchError(f"no fake response registered for {url!r}")
        if isinstance(result, Exception):
            raise result
        return result


def _minimal_pdf(text: str) -> bytes:
    """Build a minimal, valid single-page PDF containing `text` as a content stream — enough
    to exercise pypdf's real extraction path without any external fixture file."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    ]
    stream = f"BT /F1 12 Tf 10 100 Td ({text}) Tj ET".encode("latin-1")
    objects.append(
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
    )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_offset = len(out)
    count = len(objects) + 1
    out += f"xref\n0 {count}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += b"trailer\n" + f"<< /Size {count} /Root 1 0 R >>\n".encode()
    out += f"startxref\n{xref_offset}\n".encode()
    out += b"%%EOF"
    return bytes(out)


def _source(url: str = "https://example.gov") -> TrustedSource:
    return TrustedSource(
        source_id="sa-example",
        name="Example Regulator",
        source_type=TrustedSourceType.GOVERNMENT_REGULATOR,
        url=url,
        jurisdiction="SA",
    )


def _fetcher_allowing_all() -> FakeHttpFetcher:
    return FakeHttpFetcher({"https://example.gov/robots.txt": _ALLOW_ALL_ROBOTS})


def _crawler(fetcher: FakeHttpFetcher, *, max_excerpt_chars: int = 20_000) -> HttpResearchCrawler:
    return HttpResearchCrawler(
        fetcher,
        rate_limiter=PoliteRateLimiter(min_interval_seconds=0),
        max_excerpt_chars=max_excerpt_chars,
    )


async def test_discover_finds_links_on_an_html_listing_page() -> None:
    fetcher = _fetcher_allowing_all()
    fetcher.register(
        "https://example.gov",
        HttpResponse(
            status=200,
            content_type="text/html; charset=utf-8",
            body=b'<a href="/contracts">Vendor contract requirements</a>',
        ),
    )

    refs = await _crawler(fetcher).discover(_source())

    assert refs == (
        DiscoveredDocumentRef(
            url="https://example.gov/contracts", title="Vendor contract requirements"
        ),
    )


async def test_discover_returns_empty_for_a_non_html_response() -> None:
    fetcher = _fetcher_allowing_all()
    fetcher.register(
        "https://example.gov",
        HttpResponse(status=200, content_type="application/pdf", body=b"%PDF-fake"),
    )

    assert await _crawler(fetcher).discover(_source()) == ()


async def test_fetch_normalizes_html_content() -> None:
    fetcher = _fetcher_allowing_all()
    fetcher.register(
        "https://example.gov/contracts",
        HttpResponse(
            status=200,
            content_type="text/html",
            body=b"<p>Vendor contracts must include audit rights.</p>",
        ),
    )

    excerpt = await _crawler(fetcher).fetch(
        _source(), DiscoveredDocumentRef(url="https://example.gov/contracts")
    )

    assert excerpt.text == "Vendor contracts must include audit rights."
    assert excerpt.source.source_id == "sa-example"


async def test_fetch_normalizes_pdf_content() -> None:
    fetcher = _fetcher_allowing_all()
    pdf_bytes = _minimal_pdf("Vendor contracts must include exit terms.")
    fetcher.register(
        "https://example.gov/contracts.pdf",
        HttpResponse(status=200, content_type="application/pdf", body=pdf_bytes),
    )

    excerpt = await _crawler(fetcher).fetch(
        _source(), DiscoveredDocumentRef(url="https://example.gov/contracts.pdf")
    )

    assert "Vendor contracts must include exit terms." in excerpt.text


async def test_fetch_normalizes_plain_text_content() -> None:
    fetcher = _fetcher_allowing_all()
    fetcher.register(
        "https://example.gov/contracts.txt",
        HttpResponse(status=200, content_type="text/plain", body=b"Plain contract text."),
    )

    excerpt = await _crawler(fetcher).fetch(
        _source(), DiscoveredDocumentRef(url="https://example.gov/contracts.txt")
    )

    assert excerpt.text == "Plain contract text."


async def test_fetch_truncates_to_max_excerpt_chars() -> None:
    fetcher = _fetcher_allowing_all()
    fetcher.register(
        "https://example.gov/contracts.txt",
        HttpResponse(status=200, content_type="text/plain", body=b"x" * 100),
    )

    excerpt = await _crawler(fetcher, max_excerpt_chars=10).fetch(
        _source(), DiscoveredDocumentRef(url="https://example.gov/contracts.txt")
    )

    assert excerpt.text == "x" * 10


async def test_fetch_raises_when_disallowed_by_robots_txt() -> None:
    fetcher = FakeHttpFetcher(
        {
            "https://example.gov/robots.txt": HttpResponse(
                status=200, content_type="text/plain", body=b"User-agent: *\nDisallow: /private/\n"
            )
        }
    )

    with pytest.raises(CrawlerFetchError, match="disallowed by robots.txt"):
        await _crawler(fetcher).fetch(
            _source(), DiscoveredDocumentRef(url="https://example.gov/private/secret")
        )


async def test_fetch_propagates_network_failures() -> None:
    fetcher = _fetcher_allowing_all()
    # No response registered for this URL -> FakeHttpFetcher raises CrawlerFetchError.
    with pytest.raises(CrawlerFetchError):
        await _crawler(fetcher).fetch(
            _source(), DiscoveredDocumentRef(url="https://example.gov/missing")
        )
