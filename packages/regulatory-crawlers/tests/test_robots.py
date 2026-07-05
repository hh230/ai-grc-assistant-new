"""Unit tests for RobotsChecker: polite crawling honors robots.txt where a source publishes
one, and defaults to allow where it doesn't (many regulator sites publish none at all)."""

from __future__ import annotations

from grc_regulatory_crawlers import HttpResponse, RobotsChecker
from grc_regulatory_crawlers.exceptions import CrawlerFetchError

from ._fakes import FakeHttpFetcher


async def test_allows_when_robots_txt_is_unreachable() -> None:
    fetcher = FakeHttpFetcher()  # no responses registered -> robots.txt fetch fails
    checker = RobotsChecker(fetcher, user_agent="TestBot")

    assert await checker.is_allowed("https://example.gov/page") is True


async def test_disallows_a_path_blocked_by_robots_txt() -> None:
    robots_txt = "User-agent: *\nDisallow: /private/\n"
    fetcher = FakeHttpFetcher(
        {
            "https://example.gov/robots.txt": HttpResponse(
                status=200, content_type="text/plain", body=robots_txt.encode("utf-8")
            )
        }
    )
    checker = RobotsChecker(fetcher, user_agent="TestBot")

    assert await checker.is_allowed("https://example.gov/private/secret") is False
    assert await checker.is_allowed("https://example.gov/public/page") is True


async def test_robots_txt_is_fetched_once_per_origin() -> None:
    robots_txt = "User-agent: *\nAllow: /\n"
    fetcher = FakeHttpFetcher(
        {
            "https://example.gov/robots.txt": HttpResponse(
                status=200, content_type="text/plain", body=robots_txt.encode("utf-8")
            )
        }
    )
    checker = RobotsChecker(fetcher, user_agent="TestBot")

    await checker.is_allowed("https://example.gov/a")
    await checker.is_allowed("https://example.gov/b")

    assert fetcher.requests.count("https://example.gov/robots.txt") == 1


async def test_allows_when_robots_txt_fetch_raises() -> None:
    fetcher = FakeHttpFetcher(
        {"https://example.gov/robots.txt": CrawlerFetchError("connection reset")}
    )
    checker = RobotsChecker(fetcher, user_agent="TestBot")

    assert await checker.is_allowed("https://example.gov/page") is True
