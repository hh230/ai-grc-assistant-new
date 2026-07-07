"""``RegulationGapRunner`` — the fetch -> parse -> store orchestration for one regulation
catalog entry (Knowledge Intelligence KI-P6, ADR-0030), structurally matching
``grc_knowledge_research_adapters.KnowledgeGapResearchRunner``'s role in KI-P4/P5: one
regulation's failure never blocks the next (fail-safe, CLAUDE.md §16), every stage logs at
the process level (not just the DB timeline), and it emits the shared
``grc_knowledge_worker.WorkerEvent`` vocabulary the AI Worker Control Center already renders
— no second event vocabulary.

Every stored version lands ``status = 'in_review'`` ("pending_review") — this runner never
approves/publishes anything; that is an explicit human decision (KI-P7).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from grc_knowledge_worker import WorkerEvent, WorkerEventSink, WorkerEventType
from grc_regulation_ingestion import RegulationCatalogEntry

from .boe_fetcher import BoeRegulationPageFetcher
from .boe_parser import ParsedSection

logger = logging.getLogger(__name__)

_DEFAULT_AUTHORITY = "هيئة الخبراء بمجلس الوزراء"
_DEFAULT_JURISDICTION = "SA"
_DEFAULT_KNOWLEDGE_DOMAIN = "legal_regulatory"
_DEFAULT_DOCUMENT_TYPE = "law"


def short_code_for(source_url: str) -> str:
    """A stable identity key derived from the BOE URL's own law-detail id (the last
    non-numeric path segment) — the regulation catalog's own name text is not used as the key
    since re-ingestion must recognize the same law even if its displayed name text changes
    slightly between catalog runs."""
    segments = [segment for segment in source_url.rstrip("/").split("/") if segment]
    law_id = next((segment for segment in reversed(segments) if not segment.isdigit()), None)
    return f"boe-{law_id}" if law_id else f"boe-{uuid.uuid5(uuid.NAMESPACE_URL, source_url)}"


@dataclass(frozen=True)
class RegulationIngestionOutcome:
    """One catalog entry's result for this run — satisfies
    ``grc_regulation_ingestion.RegulationOutcomeLike`` structurally."""

    source_url: str
    short_code: str
    stored: bool
    articles_extracted: int = 0
    error: str | None = None


class RegulationSource(Protocol):
    @property
    def id(self) -> str: ...


class RegulationSourceStore(Protocol):
    """Structural port matching ``grc_persistence_web.RegulationSourceRepository`` (only the
    method this runner actually calls — `get_by_short_code` is real on the concrete
    repository but unused here)."""

    async def upsert(
        self,
        *,
        id: str,
        short_code: str,
        title_ar: str,
        authority: str,
        jurisdiction: str,
        knowledge_domain: str,
        document_type: str,
        boe_source_url: str,
        title_en: str | None = None,
    ) -> RegulationSource: ...


class RegulationSourceVersion(Protocol):
    @property
    def id(self) -> str: ...


class RegulationSourceVersionStore(Protocol):
    """Structural port matching ``grc_persistence_web.RegulationSourceVersionRepository``."""

    async def upsert_draft(
        self,
        *,
        id: str,
        source_id: str,
        version_label: str,
        content_hash: str,
        official_citation: str | None = None,
        effective_start: date | None = None,
        effective_end: date | None = None,
        publication_date: date | None = None,
        change_summary_ar: str | None = None,
        change_summary_en: str | None = None,
    ) -> tuple[RegulationSourceVersion, bool]: ...


class RegulationDocument(Protocol):
    @property
    def id(self) -> str: ...


class RegulationDocumentStore(Protocol):
    """Structural port matching ``grc_persistence_web.RegulationDocumentRepository``."""

    async def insert(
        self,
        *,
        id: str,
        version_id: str,
        language: str,
        document_format: str,
        source_url: str,
        content_hash: str,
        byte_size: int | None = None,
    ) -> RegulationDocument: ...


class NewSectionLike(Protocol):
    """Mirrors ``grc_persistence_web.NewSectionLike``/``NewRegulationSection``'s fields
    structurally so this package never imports ``grc_persistence_web`` (an adapters package
    should not depend on a sibling adapters package; the composition root wires the concrete
    type in) — two independently-declared Protocols with the same shape are still mutually
    assignable under mypy's structural typing."""

    @property
    def id(self) -> str: ...
    @property
    def document_id(self) -> str: ...
    @property
    def section_type(self) -> str: ...
    @property
    def code(self) -> str: ...
    @property
    def path(self) -> tuple[str, ...]: ...
    @property
    def position(self) -> int: ...
    @property
    def title_ar(self) -> str | None: ...
    @property
    def title_en(self) -> str | None: ...
    @property
    def text_ar(self) -> str | None: ...
    @property
    def text_en(self) -> str | None: ...
    @property
    def parent_section_id(self) -> str | None: ...
    @property
    def amendment_note_ar(self) -> str | None: ...
    @property
    def amendment_note_en(self) -> str | None: ...


class RegulationSectionStore(Protocol):
    """Structural port matching ``grc_persistence_web.RegulationSectionRepository``. The return
    type is ``Sequence`` (covariant), not ``list`` (invariant): a concrete
    ``list[RegulationSectionRecord]`` satisfies ``Sequence[object]`` under mypy strict, the same
    reasoning ``grc_knowledge_research_adapters.KnowledgeItemStore.list_all`` already documents
    for its own ``Sequence`` return type."""

    async def bulk_insert(self, sections: tuple[NewSectionLike, ...]) -> Sequence[object]: ...


class NewSectionFactory(Protocol):
    """Matches ``grc_persistence_web.NewRegulationSection``'s constructor signature — kept as
    a Protocol so this package never imports ``grc_persistence_web`` (an adapters package
    should not depend on a sibling adapters package; the composition root wires the concrete
    type in)."""

    def __call__(
        self,
        *,
        id: str,
        document_id: str,
        section_type: str,
        code: str,
        path: tuple[str, ...],
        position: int,
        title_ar: str | None = None,
        title_en: str | None = None,
        text_ar: str | None = None,
        text_en: str | None = None,
        parent_section_id: str | None = None,
        amendment_note_ar: str | None = None,
        amendment_note_en: str | None = None,
    ) -> NewSectionLike: ...


class RegulationGapRunner:
    """Detects which catalog entries are new or changed, fetches+parses each via the injected
    ``BoeRegulationPageFetcher``, and stores every result as a pending-review version. One
    regulation's failure never blocks another's."""

    def __init__(
        self,
        *,
        fetcher: BoeRegulationPageFetcher,
        sources: RegulationSourceStore,
        versions: RegulationSourceVersionStore,
        documents: RegulationDocumentStore,
        sections: RegulationSectionStore,
        new_section: NewSectionFactory,
        event_sink: WorkerEventSink | None = None,
    ) -> None:
        self._fetcher = fetcher
        self._sources = sources
        self._versions = versions
        self._documents = documents
        self._sections = sections
        self._new_section = new_section
        self._event_sink = event_sink

    async def _emit(self, event_type: WorkerEventType, message: str, *, now: datetime) -> None:
        if self._event_sink is None:
            return
        await self._event_sink.record(
            WorkerEvent(event_type=event_type, message=message, occurred_at=now)
        )

    async def run(
        self, catalog: tuple[RegulationCatalogEntry, ...], *, now: datetime
    ) -> tuple[RegulationIngestionOutcome, ...]:
        logger.info("regulation_ingestion.cycle_started catalog_size=%d", len(catalog))
        outcomes = []
        for entry in catalog:
            outcomes.append(await self._ingest_one(entry, now=now))
        stored = sum(1 for outcome in outcomes if outcome.stored)
        failed = sum(1 for outcome in outcomes if outcome.error is not None)
        total_articles = sum(outcome.articles_extracted for outcome in outcomes)
        logger.info(
            "regulation_ingestion.cycle_completed documents_processed=%d articles_extracted=%d "
            "failed_documents=%d total_knowledge_items_created=%d",
            len(catalog),
            total_articles,
            failed,
            stored,
        )
        return tuple(outcomes)

    async def _ingest_one(
        self, entry: RegulationCatalogEntry, *, now: datetime
    ) -> RegulationIngestionOutcome:
        short_code = short_code_for(entry.source_url)
        logger.info(
            "regulation_ingestion.entry_started short_code=%s name_ar=%s",
            short_code,
            entry.name_ar,
        )
        await self._emit(
            WorkerEventType.GAP_DETECTED,
            f"Checking regulation: {entry.name_ar}",
            now=now,
        )

        try:
            source = await self._sources.upsert(
                id=str(uuid.uuid4()),
                short_code=short_code,
                title_ar=entry.name_ar,
                authority=_DEFAULT_AUTHORITY,
                jurisdiction=_DEFAULT_JURISDICTION,
                knowledge_domain=_DEFAULT_KNOWLEDGE_DOMAIN,
                document_type=_DEFAULT_DOCUMENT_TYPE,
                boe_source_url=entry.source_url,
            )

            fetched = await self._fetcher.fetch_and_parse(entry.source_url, name_ar=entry.name_ar)
            logger.info(
                "regulation_ingestion.fetched short_code=%s bytes=%d",
                short_code,
                len(fetched.raw_html),
            )
            await self._emit(
                WorkerEventType.SOURCE_SEARCHED,
                f"Fetched {entry.name_ar} from the official Board of Experts portal",
                now=now,
            )
        except Exception as exc:  # noqa: BLE001 - fail-safe: one regulation's failure is isolated
            logger.error(
                "regulation_ingestion.fetch_failed short_code=%s error=%s", short_code, exc
            )
            await self._emit(
                WorkerEventType.ERROR,
                f"Failed to fetch/parse {entry.name_ar}: {exc}",
                now=now,
            )
            return RegulationIngestionOutcome(
                source_url=entry.source_url, short_code=short_code, stored=False, error=str(exc)
            )

        articles_extracted = sum(
            1 for section in fetched.parsed.sections if section.section_type == "article"
        )
        logger.info(
            "regulation_ingestion.parsed short_code=%s chapters=%d articles=%d",
            short_code,
            len(fetched.parsed.sections) - articles_extracted,
            articles_extracted,
        )
        await self._emit(
            WorkerEventType.KNOWLEDGE_DISCOVERED,
            f"Parsed {entry.name_ar}: {articles_extracted} article(s)",
            now=now,
        )

        try:
            version, created = await self._versions.upsert_draft(
                id=str(uuid.uuid4()),
                source_id=source.id,
                version_label=fetched.parsed.issuance_date_raw or "unknown",
                content_hash=fetched.content_hash,
                official_citation=fetched.parsed.official_citation,
            )
            if not created:
                logger.info(
                    "regulation_ingestion.unchanged short_code=%s version_id=%s",
                    short_code,
                    version.id,
                )
                return RegulationIngestionOutcome(
                    source_url=entry.source_url,
                    short_code=short_code,
                    stored=False,
                    articles_extracted=articles_extracted,
                )

            document = await self._documents.insert(
                id=str(uuid.uuid4()),
                version_id=version.id,
                language="ar",
                document_format="html",
                source_url=entry.source_url,
                content_hash=fetched.content_hash,
                byte_size=len(fetched.raw_html),
            )
            await self._store_sections(fetched.parsed.sections, document_id=document.id)
        except Exception as exc:  # noqa: BLE001 - fail-safe: a storage failure is isolated too
            logger.error("regulation_ingestion.save_failed short_code=%s error=%s", short_code, exc)
            await self._emit(
                WorkerEventType.ERROR, f"Failed to store {entry.name_ar}: {exc}", now=now
            )
            return RegulationIngestionOutcome(
                source_url=entry.source_url,
                short_code=short_code,
                stored=False,
                articles_extracted=articles_extracted,
                error=str(exc),
            )

        logger.info("regulation_ingestion.save_success short_code=%s", short_code)
        await self._emit(
            WorkerEventType.ITEM_SAVED,
            f"Saved {entry.name_ar} for review ({articles_extracted} article(s))",
            now=now,
        )
        return RegulationIngestionOutcome(
            source_url=entry.source_url,
            short_code=short_code,
            stored=True,
            articles_extracted=articles_extracted,
        )

    async def _store_sections(
        self, parsed_sections: tuple[ParsedSection, ...], *, document_id: str
    ) -> None:
        section_ids = [str(uuid.uuid4()) for _ in parsed_sections]
        new_sections = tuple(
            self._new_section(
                id=section_ids[index],
                document_id=document_id,
                section_type=section.section_type,
                code=section.code,
                path=section.path,
                position=section.position,
                title_ar=section.title_ar,
                text_ar=section.text_ar,
                amendment_note_ar=section.amendment_note_ar,
                parent_section_id=(
                    section_ids[section.parent_index] if section.parent_index is not None else None
                ),
            )
            for index, section in enumerate(parsed_sections)
        )
        await self._sections.bulk_insert(new_sections)
