"""The one seam real network I/O crosses (CLAUDE.md §22: mock external calls in unit tests).

``HttpFetcher`` is deliberately tiny (one method, one response shape) so tests can supply a
fully deterministic fake instead of a real HTTP server — every other module in this package
(robots checking, the crawler itself) is written against this abstraction, never against
``urllib`` directly. ``UrllibHttpFetcher`` is the one concrete implementation that actually
touches the network, using only the standard library (no new third-party HTTP dependency).
"""

from __future__ import annotations

import asyncio
import ssl
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from importlib import resources
from urllib.error import URLError

import certifi

from .exceptions import CrawlerFetchError


def _build_ssl_context() -> ssl.SSLContext:
    """Built once, from certifi's CA bundle rather than relying on
    ``ssl.create_default_context()``'s platform default: several CPython builds (notably
    python.org's macOS installer and some standalone/uv-managed builds) don't link to the OS
    trust store at all, so a real, correctly publicly-CA-signed site fails verification purely
    for environment reasons — reproducible in a container the same way it is here.

    ``_ca_supplement.pem`` additionally covers a real server-misconfiguration case found live
    against the Saudi Board of Experts legal portal (``laws.boe.gov.sa``): its TLS handshake
    sends only the leaf certificate, omitting the DigiCert intermediate CA a compliant server
    should include — most browsers paper over this via out-of-band AIA chasing, which Python's
    ``ssl`` module does not do. The missing intermediate is a well-known, public DigiCert
    certificate (fetched once from DigiCert's own official ``cacerts.digicert.com`` repository,
    verified by its published SHA-256 fingerprint, and vendored here) — not a workaround that
    weakens verification, just the chain the server should have sent itself.
    """
    context = ssl.create_default_context(cafile=certifi.where())
    supplement = resources.files(__package__).joinpath("_ca_supplement.pem").read_text()
    context.load_verify_locations(cadata=supplement)
    return context


_SSL_CONTEXT = _build_ssl_context()


@dataclass(frozen=True)
class HttpResponse:
    """A provider-agnostic HTTP response — just enough for content-type sniffing and
    normalization; never a library-specific response object."""

    status: int
    content_type: str
    body: bytes
    last_modified: str | None = None


class HttpFetcher(ABC):
    """Performs one polite HTTP GET. Callers (RobotsChecker, HttpRegulatoryCrawler) apply
    robots.txt/rate-limiting decisions *before* calling this — this port only fetches."""

    @abstractmethod
    async def get(self, url: str, *, user_agent: str) -> HttpResponse: ...


class UrllibHttpFetcher(HttpFetcher):
    """stdlib-only HTTP GET. Only ``http``/``https`` URLs are accepted, closing off
    ``file://``/other schemes a regulator source's discovered links might otherwise smuggle
    in."""

    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        self._timeout_seconds = timeout_seconds

    async def get(self, url: str, *, user_agent: str) -> HttpResponse:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_sync, url, user_agent)

    def _get_sync(self, url: str, user_agent: str) -> HttpResponse:
        if not url.lower().startswith(("http://", "https://")):
            raise CrawlerFetchError(f"unsupported URL scheme: {url!r}")
        request = urllib.request.Request(url, headers={"User-Agent": user_agent})
        try:
            with urllib.request.urlopen(  # noqa: S310 - scheme checked above
                request, timeout=self._timeout_seconds, context=_SSL_CONTEXT
            ) as response:
                body: bytes = response.read()
                content_type = response.headers.get("Content-Type", "")
                last_modified = response.headers.get("Last-Modified")
        except (URLError, TimeoutError) as exc:
            raise CrawlerFetchError(f"failed to fetch {url!r}: {exc}") from exc
        return HttpResponse(
            status=200, content_type=content_type, body=body, last_modified=last_modified
        )
