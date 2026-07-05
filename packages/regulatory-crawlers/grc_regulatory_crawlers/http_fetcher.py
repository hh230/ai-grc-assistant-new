"""The one seam real network I/O crosses (CLAUDE.md §22: mock external calls in unit tests).

``HttpFetcher`` is deliberately tiny (one method, one response shape) so tests can supply a
fully deterministic fake instead of a real HTTP server — every other module in this package
(robots checking, the crawler itself) is written against this abstraction, never against
``urllib`` directly. ``UrllibHttpFetcher`` is the one concrete implementation that actually
touches the network, using only the standard library (no new third-party HTTP dependency).
"""

from __future__ import annotations

import asyncio
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.error import URLError

from .exceptions import CrawlerFetchError


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
                request, timeout=self._timeout_seconds
            ) as response:
                body: bytes = response.read()
                content_type = response.headers.get("Content-Type", "")
                last_modified = response.headers.get("Last-Modified")
        except (URLError, TimeoutError) as exc:
            raise CrawlerFetchError(f"failed to fetch {url!r}: {exc}") from exc
        return HttpResponse(
            status=200, content_type=content_type, body=body, last_modified=last_modified
        )
