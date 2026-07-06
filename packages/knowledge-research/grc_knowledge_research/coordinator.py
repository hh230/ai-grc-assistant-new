"""The Research Coordinator — pure orchestration (CLAUDE.md §5), the same shape
``grc_regulatory_crawlers.RegulatoryCrawlerRunner`` already established for regulatory
crawling: it depends only on the injected ``ResearchCrawlerPort`` and
``KnowledgeDiscoveryEngine`` (reused from ``grc_knowledge_intelligence`` unmodified), never a
concrete HTTP client, LLM SDK, or database. Every actual grounding attempt runs through
``KnowledgeDiscoveryEngine.discover``, whose own extractor port is (in the adapters package)
backed by the Tool Registry — so every synthesis call this coordinator triggers is already
authorized, validated, and audited exactly like any other Tool invocation, with no new Tool
needed here.

Fail-safe by construction (CLAUDE.md §16): a discovery or fetch failure on one source or
document is recorded as an attempt and never aborts the rest of the plan.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from grc_knowledge_intelligence import KnowledgeDiscoveryEngine, KnowledgeItem, compute_version_hash

from .enums import AttemptOutcome, ResearchStatus
from .models import DiscoveredDocumentRef, ResearchAttempt, ResearchPlan, ResearchResult
from .ports import ResearchCrawlerPort
from .relevance import rank_refs

DEFAULT_MAX_SOURCES = 3
DEFAULT_MAX_DOCUMENTS_PER_SOURCE = 3
DEFAULT_EARLY_STOP_CONFIDENCE = 0.85


class ResearchCoordinator:
    """Walks a ``ResearchPlan``'s sources in priority order, discovering and ranking
    candidate documents at each, until a sufficiently confident answer is grounded or the
    plan (and its budget) is exhausted. Keeps the single best-grounded item seen across the
    whole run, even a weak one — a genuine-but-weak answer is still worth storing as a
    ``WEAK_CONFIDENCE`` gap for a later cycle (the same posture ADR-0025 already takes for
    knowledge that is answered, but not confidently)."""

    def __init__(
        self,
        *,
        crawler: ResearchCrawlerPort,
        discovery_engine: KnowledgeDiscoveryEngine,
        max_sources: int = DEFAULT_MAX_SOURCES,
        max_documents_per_source: int = DEFAULT_MAX_DOCUMENTS_PER_SOURCE,
        early_stop_confidence: float = DEFAULT_EARLY_STOP_CONFIDENCE,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        if max_sources < 1:
            raise ValueError("max_sources must be >= 1")
        if max_documents_per_source < 1:
            raise ValueError("max_documents_per_source must be >= 1")
        if not 0.0 <= early_stop_confidence <= 1.0:
            raise ValueError("early_stop_confidence must be within [0, 1]")
        self._crawler = crawler
        self._discovery_engine = discovery_engine
        self._max_sources = max_sources
        self._max_documents_per_source = max_documents_per_source
        self._early_stop_confidence = early_stop_confidence
        self._clock = clock

    async def research(self, plan: ResearchPlan) -> ResearchResult:
        attempts: list[ResearchAttempt] = []
        best_item: KnowledgeItem | None = None
        best_version_hash: str | None = None

        for step in plan.steps[: self._max_sources]:
            source = step.source.source

            try:
                refs = await self._crawler.discover(source)
            except Exception as exc:  # noqa: BLE001 - fail-safe: isolate one source's failure
                attempts.append(
                    ResearchAttempt(
                        source=source,
                        ref=None,
                        outcome=AttemptOutcome.DISCOVERY_FAILED,
                        confidence=None,
                        detail=str(exc),
                    )
                )
                continue

            # A source with no discoverable links (e.g. a single, already-specific page) is
            # still worth checking directly, rather than being skipped for lack of a listing.
            candidates: tuple[DiscoveredDocumentRef, ...] = refs or (
                DiscoveredDocumentRef(url=source.url),
            )
            ranked = rank_refs(plan.question, candidates)[: self._max_documents_per_source]

            for ref in ranked:
                try:
                    excerpt = await self._crawler.fetch(source, ref)
                except Exception as exc:  # noqa: BLE001 - one document's failure is isolated
                    attempts.append(
                        ResearchAttempt(
                            source=source,
                            ref=ref,
                            outcome=AttemptOutcome.FETCH_FAILED,
                            confidence=None,
                            detail=str(exc),
                        )
                    )
                    continue

                item = await self._discovery_engine.discover(plan.question, excerpt)
                if item is None:
                    attempts.append(
                        ResearchAttempt(
                            source=source,
                            ref=ref,
                            outcome=AttemptOutcome.NOT_GROUNDED,
                            confidence=None,
                            detail="the excerpt did not address the question",
                        )
                    )
                    continue

                attempts.append(
                    ResearchAttempt(
                        source=source,
                        ref=ref,
                        outcome=AttemptOutcome.GROUNDED,
                        confidence=item.confidence,
                        detail="synthesized a grounded answer from this excerpt",
                    )
                )
                if best_item is None or item.confidence > best_item.confidence:
                    best_item = item
                    best_version_hash = compute_version_hash(plan.question, excerpt)
                if item.confidence >= self._early_stop_confidence:
                    return self._conclude(plan, best_item, best_version_hash, attempts)

        return self._conclude(plan, best_item, best_version_hash, attempts)

    def _conclude(
        self,
        plan: ResearchPlan,
        best_item: KnowledgeItem | None,
        best_version_hash: str | None,
        attempts: list[ResearchAttempt],
    ) -> ResearchResult:
        status = (
            ResearchStatus.FOUND if best_item is not None else ResearchStatus.INSUFFICIENT_EVIDENCE
        )
        return ResearchResult(
            question=plan.question,
            status=status,
            item=best_item,
            version_hash=best_version_hash,
            attempts=tuple(attempts),
            researched_at=self._clock(),
        )
