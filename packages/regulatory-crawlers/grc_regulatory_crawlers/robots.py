"""robots.txt compliance — the polite-crawling gate every request passes through first.

Wraps the standard library's ``urllib.robotparser.RobotFileParser`` (fed via ``HttpFetcher``
so it never does its own network I/O) with a per-origin cache, so one crawl only fetches a
given host's ``robots.txt`` once.
"""

from __future__ import annotations

from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from .exceptions import CrawlerFetchError
from .http_fetcher import HttpFetcher


class RobotsChecker:
    """Answers whether one URL may be fetched by ``user_agent``, per that host's
    ``robots.txt``. Best-effort: a host with no reachable ``robots.txt`` is treated as
    allowing everything (many regulator sites do not publish one at all)."""

    def __init__(self, fetcher: HttpFetcher, *, user_agent: str) -> None:
        self._fetcher = fetcher
        self._user_agent = user_agent
        self._parsers: dict[str, RobotFileParser | None] = {}

    async def is_allowed(self, url: str) -> bool:
        origin = _origin(url)
        if origin not in self._parsers:
            self._parsers[origin] = await self._fetch_parser(origin)
        parser = self._parsers[origin]
        if parser is None:
            return True
        return parser.can_fetch(self._user_agent, url)

    async def _fetch_parser(self, origin: str) -> RobotFileParser | None:
        robots_url = urljoin(origin, "/robots.txt")
        try:
            response = await self._fetcher.get(robots_url, user_agent=self._user_agent)
        except CrawlerFetchError:
            return None
        if response.status >= 400:
            return None
        parser = RobotFileParser()
        parser.parse(response.body.decode("utf-8", errors="replace").splitlines())
        return parser


def _origin(url: str) -> str:
    parts = urlparse(url)
    return f"{parts.scheme}://{parts.netloc}"
