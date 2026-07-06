"""``KnowledgeGapResearchRunner`` — the orchestration seam that ties the Knowledge Gap
Detector, the curated trusted-source catalog, the Research Coordinator, and storage together
into one "find and close gaps" run, the same role
``grc_regulatory_crawlers.RegulatoryCrawlerRunner`` already plays for regulatory crawling.

This is outer orchestration (CLAUDE.md §5), not core: it depends on structural storage
**protocols** below, never a concrete database driver — ``grc_persistence_web``'s
``KnowledgeItemRepository`` satisfies them without this package importing that one (or any DB
library) at all. Every question is researched fail-safe (CLAUDE.md §16): a failure
researching one question is observed and skipped, never aborting the rest of the run. This
runner is not itself a registered Tool — like ``RegulatoryCrawlerRunner``, it is a multi-step,
potentially long-running batch operation (Workflow-Engine-shaped), not a single
request/response capability; the one real LLM step it triggers, ``synthesize_knowledge_answer``
(via the injected ``ResearchCoordinator``'s ``KnowledgeDiscoveryEngine``), is already a
registered, audited Tool.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from grc_knowledge_intelligence import (
    GapFinding,
    KnowledgeDomain,
    KnowledgeItem,
    KnowledgeQuestion,
    TrustedSource,
    TrustedSourceType,
    VerificationStatus,
    actionable_gaps,
    detect_gaps,
)
from grc_knowledge_research import (
    CatalogedSource,
    ResearchCoordinator,
    ResearchStatus,
    build_research_plan,
)


class StoredKnowledgeItem(Protocol):
    """The shape one row from ``KnowledgeItemStore.list_all()`` must have — satisfied
    structurally by ``grc_persistence_web.KnowledgeItemRecord`` without importing it."""

    id: str
    question_id: str
    question: str
    answer: str
    domain: str
    category: str
    applicable_context: str
    source_id: str
    source_name: str
    source_type: str
    source_url: str
    jurisdiction: str
    citation: str
    confidence: float
    status: str
    last_verified: datetime | None
    version: int


class KnowledgeItemStore(Protocol):
    """Structural port matching ``grc_persistence_web.KnowledgeItemRepository``."""

    async def list_all(self) -> list[StoredKnowledgeItem]: ...

    async def upsert(
        self,
        *,
        id: str,
        question_id: str,
        question: str,
        answer: str,
        domain: str,
        category: str,
        applicable_context: str,
        source_id: str,
        source_name: str,
        source_type: str,
        source_url: str,
        jurisdiction: str,
        citation: str,
        confidence: float,
        version_hash: str,
    ) -> object: ...


@dataclass(frozen=True)
class GapResearchOutcome:
    """One question's result for this run: what gap was detected, what the research
    coordinator found, and whether anything was actually persisted."""

    question_id: str
    gap_status: str
    research_status: str
    stored: bool
    error: str | None = None


class KnowledgeGapResearchRunner:
    """Detects actionable gaps in the question catalog, researches each via the injected
    ``ResearchCoordinator`` over the curated trusted-source catalog, and stores every grounded
    result. One question's failure never blocks another's."""

    def __init__(
        self,
        *,
        catalog: tuple[CatalogedSource, ...],
        coordinator: ResearchCoordinator,
        store: KnowledgeItemStore,
    ) -> None:
        self._catalog = catalog
        self._coordinator = coordinator
        self._store = store

    async def run(
        self, questions: tuple[KnowledgeQuestion, ...], *, now: datetime
    ) -> tuple[GapResearchOutcome, ...]:
        existing_rows = await self._store.list_all()
        existing_items = tuple(_to_knowledge_item(row) for row in existing_rows)
        findings = detect_gaps(questions, existing_items, now=now)

        outcomes = []
        for finding in actionable_gaps(findings):
            outcomes.append(await self._research_one(finding))
        return tuple(outcomes)

    async def _research_one(self, finding: GapFinding) -> GapResearchOutcome:
        question = finding.question
        try:
            plan = build_research_plan(question, self._catalog)
            result = await self._coordinator.research(plan)
        except (
            Exception
        ) as exc:  # noqa: BLE001 - fail-safe: one question's failure never blocks another's
            return GapResearchOutcome(
                question_id=question.question_id,
                gap_status=finding.status.value,
                research_status="error",
                stored=False,
                error=str(exc),
            )

        if (
            result.status is not ResearchStatus.FOUND
            or result.item is None
            or result.version_hash is None
        ):
            return GapResearchOutcome(
                question_id=question.question_id,
                gap_status=finding.status.value,
                research_status=result.status.value,
                stored=False,
            )

        item = result.item
        try:
            await self._store.upsert(
                id=str(uuid.uuid4()),
                question_id=item.question_id,
                question=item.question,
                answer=item.answer,
                domain=item.domain.value,
                category=item.category,
                applicable_context=item.applicable_context,
                source_id=item.source.source_id,
                source_name=item.source.name,
                source_type=item.source.source_type.value,
                source_url=item.source.url,
                jurisdiction=item.jurisdiction,
                citation=item.citation,
                confidence=item.confidence,
                version_hash=result.version_hash,
            )
        except Exception as exc:  # noqa: BLE001 - fail-safe: a storage failure is isolated too
            return GapResearchOutcome(
                question_id=question.question_id,
                gap_status=finding.status.value,
                research_status=result.status.value,
                stored=False,
                error=str(exc),
            )

        return GapResearchOutcome(
            question_id=question.question_id,
            gap_status=finding.status.value,
            research_status=result.status.value,
            stored=True,
        )


def _to_knowledge_item(row: StoredKnowledgeItem) -> KnowledgeItem:
    """The anti-corruption translation (CLAUDE.md §15) from a stored row's plain strings back
    into the pure engine's typed ``KnowledgeItem`` — the same shape the gap detector already
    consumes for every other caller."""
    return KnowledgeItem(
        id=row.id,
        question_id=row.question_id,
        question=row.question,
        answer=row.answer,
        domain=KnowledgeDomain(row.domain),
        category=row.category,
        applicable_context=row.applicable_context,
        source=TrustedSource(
            source_id=row.source_id,
            name=row.source_name,
            source_type=TrustedSourceType(row.source_type),
            url=row.source_url,
            jurisdiction=row.jurisdiction,
        ),
        citation=row.citation,
        jurisdiction=row.jurisdiction,
        confidence=row.confidence,
        status=VerificationStatus(row.status),
        last_verified=row.last_verified,
        version=row.version,
    )
