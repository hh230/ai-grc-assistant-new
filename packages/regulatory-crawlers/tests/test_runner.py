"""Unit tests for RegulatoryCrawlerRunner: duplicate detection (unchanged documents are
skipped), changed-document detection, removed-document detection, failed-source/failed-fetch
isolation, and observability — all against fake crawler/storage doubles, no real network or
database."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from grc_regulatory_crawlers import InMemoryCrawlObserver, RegulatoryCrawlerRunner
from grc_regulatory_crawlers.exceptions import CrawlerFetchError
from grc_regulatory_intelligence import (
    ControlDomain,
    DiscoveredDocumentRef,
    DocumentContentType,
    ObligationCandidate,
    ObligationClassification,
    ObligationClassificationError,
    ObligationClassifierPort,
    ObligationExtractorPort,
    ObligationType,
    PollingFrequency,
    RawRegulatoryDocument,
    RegulatoryDocumentInput,
    RegulatoryIntelligenceEngine,
    RegulatorySource,
    RegulatorySourceRegistry,
    Severity,
    SourceType,
)
from grc_regulatory_intelligence.ports import CrawlerPort


class StubExtractor(ObligationExtractorPort):
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def extract(self, document: RawRegulatoryDocument) -> tuple[ObligationCandidate, ...]:
        self.calls.append(document.url)
        return (
            ObligationCandidate(
                obligation_text=document.raw_text,
                source_char_start=0,
                source_char_end=len(document.raw_text),
            ),
        )


class StubClassifier(ObligationClassifierPort):
    def __init__(self, *, fail_for_url: str | None = None) -> None:
        self._fail_for_url = fail_for_url

    async def classify(
        self, candidate: ObligationCandidate, *, document: RawRegulatoryDocument
    ) -> ObligationClassification:
        if document.url == self._fail_for_url:
            raise ObligationClassificationError("malformed classifier output")
        return ObligationClassification(
            obligation_type=ObligationType.REQUIREMENT,
            control_domain=ControlDomain.DATA_PROTECTION,
            suggested_policy_title="Stub Policy",
            severity=Severity.MEDIUM,
            confidence=0.8,
        )


class StubCrawler(CrawlerPort):
    def __init__(
        self,
        *,
        refs: tuple[DiscoveredDocumentRef, ...] = (),
        documents: dict[str, RegulatoryDocumentInput] | None = None,
        discover_error: Exception | None = None,
        fetch_errors: dict[str, Exception] | None = None,
    ) -> None:
        self._refs = refs
        self._documents = documents or {}
        self._discover_error = discover_error
        self._fetch_errors = fetch_errors or {}

    async def discover(self, source: RegulatorySource) -> tuple[DiscoveredDocumentRef, ...]:
        if self._discover_error is not None:
            raise self._discover_error
        return self._refs

    async def fetch(
        self, source: RegulatorySource, ref: DiscoveredDocumentRef
    ) -> RegulatoryDocumentInput:
        if ref.url in self._fetch_errors:
            raise self._fetch_errors[ref.url]
        return self._documents[ref.url]


@dataclass(frozen=True)
class _RawRecord:
    id: str
    content_hash: str


@dataclass
class InMemoryRawDocumentStore:
    latest: dict[tuple[str, str], _RawRecord] = field(default_factory=dict)
    upsert_calls: list[dict[str, object]] = field(default_factory=list)

    async def get_latest_content_hash(self, source_id: str, url: str) -> str | None:
        record = self.latest.get((source_id, url))
        return record.content_hash if record is not None else None

    async def list_latest_urls_by_source(self, source_id: str) -> list[str]:
        return [url for (sid, url) in self.latest if sid == source_id]

    async def upsert(
        self,
        *,
        id: str,
        source_id: str,
        url: str,
        fetched_at: datetime,
        content_hash: str,
        raw_text: str,
    ) -> _RawRecord:
        self.upsert_calls.append({"id": id, "url": url, "content_hash": content_hash})
        record = _RawRecord(id=id, content_hash=content_hash)
        self.latest[(source_id, url)] = record
        return record


@dataclass
class InMemoryObligationStore:
    upsert_calls: list[dict[str, object]] = field(default_factory=list)

    async def upsert(self, **kwargs: object) -> None:
        self.upsert_calls.append(kwargs)


def _source(enabled: bool = True) -> RegulatorySource:
    return RegulatorySource(
        source_id="sa-example",
        regulator_name="Example Regulator",
        jurisdiction="SA",
        language="ar",
        base_url="https://example.gov",
        source_type=SourceType.WEBSITE,
        polling_frequency=PollingFrequency.WEEKLY,
        enabled=enabled,
    )


def _document_input(url: str, raw_text: str) -> RegulatoryDocumentInput:
    return RegulatoryDocumentInput(
        source_id="sa-example",
        url=url,
        raw_text=raw_text,
        content_type=DocumentContentType.HTML,
        discovered_at=datetime(2026, 7, 6, tzinfo=timezone.utc),
    )


def _runner(
    crawler: CrawlerPort,
    *,
    registry: RegulatorySourceRegistry | None = None,
    classifier: ObligationClassifierPort | None = None,
    extractor: ObligationExtractorPort | None = None,
    raw_documents: InMemoryRawDocumentStore | None = None,
    obligations: InMemoryObligationStore | None = None,
    observer: InMemoryCrawlObserver | None = None,
) -> tuple[
    RegulatoryCrawlerRunner,
    InMemoryRawDocumentStore,
    InMemoryObligationStore,
    InMemoryCrawlObserver,
]:
    raw_documents = raw_documents or InMemoryRawDocumentStore()
    obligations = obligations or InMemoryObligationStore()
    observer = observer or InMemoryCrawlObserver()
    engine = RegulatoryIntelligenceEngine(
        extractor=extractor or StubExtractor(), classifier=classifier or StubClassifier()
    )
    runner = RegulatoryCrawlerRunner(
        registry=registry if registry is not None else RegulatorySourceRegistry((_source(),)),
        crawler=crawler,
        engine=engine,
        raw_documents=raw_documents,
        obligations=obligations,
        observer=observer,
    )
    return runner, raw_documents, obligations, observer


async def test_new_document_is_extracted_classified_and_stored() -> None:
    url = "https://example.gov/circulars/1"
    crawler = StubCrawler(
        refs=(DiscoveredDocumentRef(url=url),),
        documents={url: _document_input(url, "Entities shall encrypt data at rest.")},
    )
    runner, raw_documents, obligations, observer = _runner(crawler)

    summaries = await runner.run()

    assert summaries[0].documents_found == 1
    assert summaries[0].documents_changed == 1
    assert len(raw_documents.upsert_calls) == 1
    assert len(obligations.upsert_calls) == 1
    assert observer.events_of("crawl_started")
    assert observer.events_of("document_found")
    assert observer.events_of("document_changed")[0].detail["change_type"] == "new"
    assert observer.events_of("crawl_completed")


async def test_unchanged_document_is_skipped_duplicate_detection() -> None:
    url = "https://example.gov/circulars/1"
    text = "Entities shall encrypt data at rest."
    crawler = StubCrawler(
        refs=(DiscoveredDocumentRef(url=url),), documents={url: _document_input(url, text)}
    )
    extractor = StubExtractor()
    runner, raw_documents, obligations, observer = _runner(crawler, extractor=extractor)

    await runner.run()
    await runner.run()  # second, identical crawl

    # The engine only ever ran once — the second crawl detected no change and skipped it.
    assert extractor.calls == [url]
    assert len(raw_documents.upsert_calls) == 1
    assert len(obligations.upsert_calls) == 1
    assert [e.detail.get("change_type") for e in observer.events_of("document_changed")] == ["new"]


async def test_updated_document_is_reprocessed_changed_detection() -> None:
    url = "https://example.gov/circulars/1"
    crawler = StubCrawler(
        refs=(DiscoveredDocumentRef(url=url),),
        documents={url: _document_input(url, "Entities shall encrypt data at rest.")},
    )
    extractor = StubExtractor()
    runner, raw_documents, obligations, observer = _runner(crawler, extractor=extractor)
    await runner.run()

    # Second crawl: the source now serves different content at the same URL.
    crawler._documents[url] = _document_input(
        url, "Entities shall encrypt data at rest AND in transit."
    )
    await runner.run()

    assert extractor.calls == [url, url]
    assert len(raw_documents.upsert_calls) == 2
    change_types = [e.detail.get("change_type") for e in observer.events_of("document_changed")]
    assert change_types == ["new", "updated"]


async def test_removed_document_is_detected_when_no_longer_discovered() -> None:
    url = "https://example.gov/circulars/1"
    crawler = StubCrawler(
        refs=(DiscoveredDocumentRef(url=url),),
        documents={url: _document_input(url, "Entities shall encrypt data at rest.")},
    )
    runner, raw_documents, obligations, observer = _runner(crawler)
    await runner.run()

    # Second crawl: discovery no longer finds this URL at all.
    crawler._refs = ()
    summaries = await runner.run()

    assert summaries[0].documents_removed == 1
    removed_events = [
        e
        for e in observer.events_of("document_changed")
        if e.detail.get("change_type") == "removed"
    ]
    assert [e.url for e in removed_events] == [url]


async def test_fetch_failure_for_one_document_does_not_block_others() -> None:
    good_url = "https://example.gov/circulars/1"
    bad_url = "https://example.gov/circulars/2"
    crawler = StubCrawler(
        refs=(DiscoveredDocumentRef(url=bad_url), DiscoveredDocumentRef(url=good_url)),
        documents={good_url: _document_input(good_url, "Entities shall log every access.")},
        fetch_errors={bad_url: CrawlerFetchError("connection reset")},
    )
    runner, raw_documents, obligations, observer = _runner(crawler)

    summaries = await runner.run()

    assert summaries[0].fetch_failures == 1
    assert summaries[0].documents_changed == 1  # only the good document made it through
    assert len(raw_documents.upsert_calls) == 1
    assert observer.events_of("fetch_failed")[0].url == bad_url


async def test_source_discovery_failure_is_isolated_and_reported() -> None:
    crawler = StubCrawler(discover_error=CrawlerFetchError("site is down"))
    runner, raw_documents, obligations, observer = _runner(crawler)

    summaries = await runner.run()

    assert summaries[0].fetch_failures == 1
    assert summaries[0].documents_found == 0
    assert raw_documents.upsert_calls == []
    assert observer.events_of("fetch_failed")
    assert observer.events_of("crawl_completed")


async def test_disabled_sources_are_never_crawled() -> None:
    registry = RegulatorySourceRegistry((_source(enabled=False),))
    crawler = StubCrawler(refs=(DiscoveredDocumentRef(url="https://example.gov/x"),))
    runner, raw_documents, obligations, observer = _runner(crawler, registry=registry)

    summaries = await runner.run()

    assert summaries == ()
    assert observer.events == []


async def test_classification_failure_is_observed_but_obligation_still_pending_review() -> None:
    url = "https://example.gov/circulars/1"
    crawler = StubCrawler(
        refs=(DiscoveredDocumentRef(url=url),), documents={url: _document_input(url, "text")}
    )
    classifier = StubClassifier(fail_for_url=url)
    runner, raw_documents, obligations, observer = _runner(crawler, classifier=classifier)

    await runner.run()

    assert observer.events_of("classification_failed")
    # The engine still records the obligation, fail-safe, as pending_review with a fallback
    # classification (PI-P1) — it is not silently dropped.
    assert len(obligations.upsert_calls) == 1
    assert obligations.upsert_calls[0]["classification_status"] == "pending_review"
    assert obligations.upsert_calls[0]["confidence"] == 0.0
