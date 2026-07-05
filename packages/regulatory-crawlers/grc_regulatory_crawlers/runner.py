"""``RegulatoryCrawlerRunner`` — the orchestration seam that ties a ``CrawlerPort``, the
``RegulatoryIntelligenceEngine``, and storage together into one crawl.

This is outer orchestration (CLAUDE.md §5), not core: it depends on structural storage
**protocols** below, never a concrete database driver — ``grc_persistence_web``'s
``RegulatoryRawDocumentRepository``/``RegulatoryObligationRepository`` satisfy them without
this package importing that one (or any DB library) at all. Every document is processed
fail-safe (CLAUDE.md §16): a failure on one document is observed and skipped, never aborting
the rest of the source's crawl or another source's.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from grc_regulatory_intelligence import (
    ClassifiedObligation,
    DocumentChangeType,
    RawRegulatoryDocument,
    RegulatoryIntelligenceEngine,
    RegulatorySource,
    RegulatorySourceRegistry,
    detect_change,
)
from grc_regulatory_intelligence.ports import CrawlerPort

from .observability import CrawlObserver


class RawDocumentRecord(Protocol):
    """The shape this runner needs back from a raw-document upsert — satisfied structurally
    by ``grc_persistence_web.RegulatoryRawDocumentRecord`` without importing it."""

    @property
    def id(self) -> str: ...


class RawDocumentStore(Protocol):
    """Structural port matching ``grc_persistence_web.RegulatoryRawDocumentRepository``."""

    async def get_latest_content_hash(self, source_id: str, url: str) -> str | None: ...

    async def list_latest_urls_by_source(self, source_id: str) -> list[str]: ...

    async def upsert(
        self,
        *,
        id: str,
        source_id: str,
        url: str,
        fetched_at: datetime,
        content_hash: str,
        raw_text: str,
    ) -> RawDocumentRecord: ...


class ObligationStore(Protocol):
    """Structural port matching ``grc_persistence_web.RegulatoryObligationRepository``."""

    async def upsert(
        self,
        *,
        id: str,
        raw_document_id: str,
        obligation_text: str,
        obligation_type: str,
        control_domain: str,
        suggested_policy_title: str,
        severity: str,
        confidence: float,
        source_char_start: int,
        source_char_end: int,
        version_hash: str,
        classifier_model: str | None = None,
        prompt_version: str | None = None,
        classification_status: str = "pending_review",
    ) -> object: ...


@dataclass(frozen=True)
class SourceCrawlSummary:
    source_id: str
    documents_found: int
    documents_changed: int
    documents_removed: int
    fetch_failures: int
    extraction_failures: int


class RegulatoryCrawlerRunner:
    """Loads enabled sources, runs a ``CrawlerPort`` over each, and feeds new/updated
    documents through the ``RegulatoryIntelligenceEngine`` into storage."""

    def __init__(
        self,
        *,
        registry: RegulatorySourceRegistry,
        crawler: CrawlerPort,
        engine: RegulatoryIntelligenceEngine,
        raw_documents: RawDocumentStore,
        obligations: ObligationStore,
        observer: CrawlObserver,
    ) -> None:
        self._registry = registry
        self._crawler = crawler
        self._engine = engine
        self._raw_documents = raw_documents
        self._obligations = obligations
        self._observer = observer

    async def run(self) -> tuple[SourceCrawlSummary, ...]:
        """Crawl every enabled source. One source's failure never blocks another's."""
        summaries = []
        for source in self._registry.list_enabled():
            summaries.append(await self._run_source(source))
        return tuple(summaries)

    async def _run_source(self, source: RegulatorySource) -> SourceCrawlSummary:
        self._observer.crawl_started(source.source_id)
        try:
            refs = await self._crawler.discover(source)
        except Exception as exc:  # noqa: BLE001 - fail-safe: one bad source never aborts the run
            self._observer.fetch_failed(source.source_id, source.base_url, error=str(exc))
            self._observer.crawl_completed(source.source_id, documents_found=0, documents_changed=0)
            return SourceCrawlSummary(source.source_id, 0, 0, 0, 1, 0)

        documents_found = 0
        documents_changed = 0
        fetch_failures = 0
        extraction_failures = 0
        discovered_urls: set[str] = set()

        for ref in refs:
            documents_found += 1
            discovered_urls.add(ref.url)
            self._observer.document_found(source.source_id, ref.url)

            try:
                document_input = await self._crawler.fetch(source, ref)
            except Exception as exc:  # noqa: BLE001 - one document's failure is isolated
                fetch_failures += 1
                self._observer.fetch_failed(source.source_id, ref.url, error=str(exc))
                continue

            raw_document = document_input.to_raw_regulatory_document()
            previous_hash = await self._raw_documents.get_latest_content_hash(
                source.source_id, ref.url
            )
            change = detect_change(
                previous_content_hash=previous_hash,
                current_content_hash=raw_document.content_hash,
            )
            if change is DocumentChangeType.UNCHANGED:
                continue

            documents_changed += 1
            self._observer.document_changed(source.source_id, ref.url, change_type=change.value)

            processed = await self._process_document(source, ref.url, raw_document)
            if not processed:
                extraction_failures += 1

        documents_removed = await self._report_removed_documents(source, discovered_urls)

        self._observer.crawl_completed(
            source.source_id, documents_found=documents_found, documents_changed=documents_changed
        )
        return SourceCrawlSummary(
            source.source_id,
            documents_found,
            documents_changed,
            documents_removed,
            fetch_failures,
            extraction_failures,
        )

    async def _process_document(
        self, source: RegulatorySource, url: str, raw_document: RawRegulatoryDocument
    ) -> bool:
        """Persist the raw document, run it through the engine, and store its obligations.
        Returns ``False`` (and records an ``extraction_failed`` event) if the engine itself
        could not run — per-obligation classification failures are surfaced separately via
        ``classification_failed`` without aborting storage of the obligations that did
        classify (the engine already isolates those; see
        ``RegulatoryIntelligenceEngine.run``)."""
        try:
            raw_record = await self._raw_documents.upsert(
                id=str(uuid.uuid4()),
                source_id=source.source_id,
                url=raw_document.url,
                fetched_at=raw_document.fetched_at,
                content_hash=raw_document.content_hash,
                raw_text=raw_document.raw_text,
            )
            result = await self._engine.run(raw_document)
        except Exception as exc:  # noqa: BLE001 - fail-safe: isolate this document, keep going
            self._observer.extraction_failed(source.source_id, url, error=str(exc))
            return False

        if result.failed_classifications:
            self._observer.classification_failed(
                source.source_id,
                url,
                error=f"{result.failed_classifications} obligation(s) failed classification",
            )

        for obligation in result.obligations:
            await self._store_obligation(source.source_id, url, raw_record.id, obligation)
        return True

    async def _store_obligation(
        self, source_id: str, url: str, raw_document_id: str, obligation: ClassifiedObligation
    ) -> None:
        try:
            await self._obligations.upsert(
                id=str(uuid.uuid4()),
                raw_document_id=raw_document_id,
                obligation_text=obligation.candidate.obligation_text,
                obligation_type=obligation.classification.obligation_type.value,
                control_domain=obligation.classification.control_domain.value,
                suggested_policy_title=obligation.classification.suggested_policy_title,
                severity=obligation.classification.severity.value,
                confidence=obligation.classification.confidence,
                source_char_start=obligation.candidate.source_char_start,
                source_char_end=obligation.candidate.source_char_end,
                version_hash=obligation.version_hash,
                classifier_model=obligation.classification.classifier_model,
                prompt_version=obligation.classification.prompt_version,
                classification_status=obligation.classification_status.value,
            )
        except Exception as exc:  # noqa: BLE001 - one obligation's storage failure is isolated
            self._observer.classification_failed(source_id, url, error=str(exc))

    async def _report_removed_documents(
        self, source: RegulatorySource, discovered_urls: set[str]
    ) -> int:
        """Any URL previously stored for this source that discovery no longer found is
        reported as removed/unavailable — observability only; nothing is deleted."""
        previously_known = await self._raw_documents.list_latest_urls_by_source(source.source_id)
        removed = [url for url in previously_known if url not in discovered_urls]
        for url in removed:
            self._observer.document_changed(
                source.source_id, url, change_type=DocumentChangeType.REMOVED.value
            )
        return len(removed)
