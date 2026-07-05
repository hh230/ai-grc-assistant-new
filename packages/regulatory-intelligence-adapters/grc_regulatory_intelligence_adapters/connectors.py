"""Regulatory connectors foundation (CLAUDE.md §17: connectors are plugins behind a port).

A connector fetches one regulatory source's current text; the composition root hashes/dates
that into a `grc_regulatory_intelligence.RawRegulatoryDocument`, persists it via
`RegulatoryRawDocumentRepository` (deduping on `content_hash`), and only then runs it through
the engine. Concrete connectors (HTTP, file, a future regulator-specific feed, ...) implement
`RegulatoryConnectorPort`; this module ships two reference adapters.
"""

from __future__ import annotations

import asyncio
import hashlib
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.error import URLError

from .exceptions import ConnectorFetchError


@dataclass(frozen=True)
class FetchedRegulatoryDocument:
    """One connector fetch's raw payload, already hashed and dated."""

    source_id: str
    url: str
    raw_text: str
    fetched_at: datetime
    content_hash: str


class RegulatoryConnectorPort(ABC):
    """Fetches one regulatory source's current text."""

    @abstractmethod
    async def fetch(self, *, source_id: str, url: str) -> FetchedRegulatoryDocument: ...


def _content_hash(raw_text: str) -> str:
    return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()


class StaticRegulatoryConnector(RegulatoryConnectorPort):
    """A deterministic, offline connector backed by an in-memory ``source_id -> text`` map —
    the reference adapter for tests and any no-egress dev/demo flow (CLAUDE.md §22: mock
    external calls in unit tests)."""

    def __init__(self, documents: dict[str, str]) -> None:
        self._documents = documents

    async def fetch(self, *, source_id: str, url: str) -> FetchedRegulatoryDocument:
        try:
            raw_text = self._documents[source_id]
        except KeyError as exc:
            raise ConnectorFetchError(f"no static document registered for {source_id!r}") from exc
        return FetchedRegulatoryDocument(
            source_id=source_id,
            url=url,
            raw_text=raw_text,
            fetched_at=datetime.now(timezone.utc),
            content_hash=_content_hash(raw_text),
        )


class HttpRegulatoryConnector(RegulatoryConnectorPort):
    """A minimal, stdlib-only HTTP connector (``urllib.request`` — no new third-party HTTP
    dependency for this foundational phase). Only ``http``/``https`` URLs are accepted, closing
    off ``file://``/other schemes some regulator source lists might otherwise smuggle in.
    """

    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        self._timeout_seconds = timeout_seconds

    async def fetch(self, *, source_id: str, url: str) -> FetchedRegulatoryDocument:
        loop = asyncio.get_running_loop()
        raw_text = await loop.run_in_executor(None, self._fetch_sync, url)
        return FetchedRegulatoryDocument(
            source_id=source_id,
            url=url,
            raw_text=raw_text,
            fetched_at=datetime.now(timezone.utc),
            content_hash=_content_hash(raw_text),
        )

    def _fetch_sync(self, url: str) -> str:
        if not url.lower().startswith(("http://", "https://")):
            raise ConnectorFetchError(f"unsupported URL scheme: {url!r}")
        try:
            with urllib.request.urlopen(
                url, timeout=self._timeout_seconds
            ) as response:  # noqa: S310 - scheme checked above
                body: bytes = response.read()
                return body.decode("utf-8")
        except (URLError, TimeoutError) as exc:
            raise ConnectorFetchError(f"failed to fetch {url!r}: {exc}") from exc
