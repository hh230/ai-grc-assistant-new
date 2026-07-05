"""Crawl observability (CLAUDE.md §19 applied to ingestion): every crawl run's lifecycle and
failures are observable, not a black box. ``CrawlObserver`` is the port
``RegulatoryCrawlerRunner`` reports through; ``LoggingCrawlObserver`` is the production
default (structured `logging`), ``InMemoryCrawlObserver`` is the reference test double.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class CrawlObserver(ABC):
    @abstractmethod
    def crawl_started(self, source_id: str) -> None: ...

    @abstractmethod
    def crawl_completed(
        self, source_id: str, *, documents_found: int, documents_changed: int
    ) -> None: ...

    @abstractmethod
    def document_found(self, source_id: str, url: str) -> None: ...

    @abstractmethod
    def document_changed(self, source_id: str, url: str, *, change_type: str) -> None: ...

    @abstractmethod
    def fetch_failed(self, source_id: str, url: str, *, error: str) -> None: ...

    @abstractmethod
    def extraction_failed(self, source_id: str, url: str, *, error: str) -> None: ...

    @abstractmethod
    def classification_failed(self, source_id: str, url: str, *, error: str) -> None: ...


class LoggingCrawlObserver(CrawlObserver):
    """Structured-logging observer — the production default."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("grc_regulatory_crawlers")

    def crawl_started(self, source_id: str) -> None:
        self._logger.info("crawl_started", extra={"source_id": source_id})

    def crawl_completed(
        self, source_id: str, *, documents_found: int, documents_changed: int
    ) -> None:
        self._logger.info(
            "crawl_completed",
            extra={
                "source_id": source_id,
                "documents_found": documents_found,
                "documents_changed": documents_changed,
            },
        )

    def document_found(self, source_id: str, url: str) -> None:
        self._logger.info("document_found", extra={"source_id": source_id, "url": url})

    def document_changed(self, source_id: str, url: str, *, change_type: str) -> None:
        self._logger.info(
            "document_changed",
            extra={"source_id": source_id, "url": url, "change_type": change_type},
        )

    def fetch_failed(self, source_id: str, url: str, *, error: str) -> None:
        self._logger.warning(
            "fetch_failed", extra={"source_id": source_id, "url": url, "error": error}
        )

    def extraction_failed(self, source_id: str, url: str, *, error: str) -> None:
        self._logger.warning(
            "extraction_failed", extra={"source_id": source_id, "url": url, "error": error}
        )

    def classification_failed(self, source_id: str, url: str, *, error: str) -> None:
        self._logger.warning(
            "classification_failed", extra={"source_id": source_id, "url": url, "error": error}
        )


@dataclass(frozen=True)
class CrawlEvent:
    kind: str
    source_id: str
    url: str | None = None
    detail: dict[str, object] = field(default_factory=dict)


class InMemoryCrawlObserver(CrawlObserver):
    """Records every event in order — the reference test double (CLAUDE.md §22)."""

    def __init__(self) -> None:
        self.events: list[CrawlEvent] = []

    def crawl_started(self, source_id: str) -> None:
        self.events.append(CrawlEvent("crawl_started", source_id))

    def crawl_completed(
        self, source_id: str, *, documents_found: int, documents_changed: int
    ) -> None:
        self.events.append(
            CrawlEvent(
                "crawl_completed",
                source_id,
                detail={"documents_found": documents_found, "documents_changed": documents_changed},
            )
        )

    def document_found(self, source_id: str, url: str) -> None:
        self.events.append(CrawlEvent("document_found", source_id, url))

    def document_changed(self, source_id: str, url: str, *, change_type: str) -> None:
        self.events.append(
            CrawlEvent("document_changed", source_id, url, detail={"change_type": change_type})
        )

    def fetch_failed(self, source_id: str, url: str, *, error: str) -> None:
        self.events.append(CrawlEvent("fetch_failed", source_id, url, detail={"error": error}))

    def extraction_failed(self, source_id: str, url: str, *, error: str) -> None:
        self.events.append(CrawlEvent("extraction_failed", source_id, url, detail={"error": error}))

    def classification_failed(self, source_id: str, url: str, *, error: str) -> None:
        self.events.append(
            CrawlEvent("classification_failed", source_id, url, detail={"error": error})
        )

    def events_of(self, kind: str) -> list[CrawlEvent]:
        return [event for event in self.events if event.kind == kind]
