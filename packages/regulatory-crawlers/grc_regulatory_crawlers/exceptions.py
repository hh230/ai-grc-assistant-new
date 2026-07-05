"""Exceptions raised by the Regulatory Crawlers adapters."""

from __future__ import annotations


class CrawlerFetchError(Exception):
    """A crawler could not fetch or normalize one URL (network failure, unsupported scheme,
    disallowed by robots.txt, or unreadable content)."""
