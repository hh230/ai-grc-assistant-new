"""Unit tests for ``ResearchCoordinator``: fail-safe isolation of source/document failures,
best-item retention across weak-then-strong answers, early stopping, and the empty-discovery
fallback to the source's own URL. All fakes — no network, no LLM, no database."""

from __future__ import annotations

from datetime import datetime, timezone

from grc_knowledge_intelligence import (
    KnowledgeAnswer,
    KnowledgeDiscoveryEngine,
    KnowledgeDomain,
    KnowledgeExtractionError,
    KnowledgeExtractorPort,
    KnowledgeQuestion,
    SourceExcerpt,
    TrustedSource,
    TrustedSourceType,
    compute_version_hash,
)
from grc_knowledge_research import (
    AttemptOutcome,
    CatalogedSource,
    DiscoveredDocumentRef,
    ResearchCoordinator,
    ResearchCrawlerPort,
    ResearchPlan,
    ResearchStatus,
    ResearchStep,
)

_QUESTION = KnowledgeQuestion(
    question_id="vendor_management.contract_clauses",
    question="What clauses should exist in a vendor contract?",
    domain=KnowledgeDomain.VENDOR_MANAGEMENT,
    category="contract_requirements",
)

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _source(source_id: str) -> TrustedSource:
    return TrustedSource(
        source_id=source_id,
        name=source_id,
        source_type=TrustedSourceType.GOVERNMENT_REGULATOR,
        url=f"https://{source_id}.example.gov",
        jurisdiction="SA",
    )


def _step(source: TrustedSource, rank: int) -> ResearchStep:
    return ResearchStep(
        source=CatalogedSource(source=source, domains=(KnowledgeDomain.VENDOR_MANAGEMENT,)),
        rank=rank,
    )


def _excerpt(source: TrustedSource, text: str) -> SourceExcerpt:
    return SourceExcerpt(source=source, text=text, fetched_at=_NOW)


class FakeCrawler(ResearchCrawlerPort):
    def __init__(
        self,
        *,
        discover: dict[str, object],
        fetch: dict[tuple[str, str], object],
    ) -> None:
        self._discover = discover
        self._fetch = fetch
        self.discovered_sources: list[str] = []
        self.fetched: list[tuple[str, str]] = []

    async def discover(self, source: TrustedSource) -> tuple[DiscoveredDocumentRef, ...]:
        self.discovered_sources.append(source.source_id)
        result = self._discover.get(source.source_id, ())
        if isinstance(result, Exception):
            raise result
        return result  # type: ignore[return-value]

    async def fetch(self, source: TrustedSource, ref: DiscoveredDocumentRef) -> SourceExcerpt:
        self.fetched.append((source.source_id, ref.url))
        result = self._fetch[(source.source_id, ref.url)]
        if isinstance(result, Exception):
            raise result
        return result  # type: ignore[return-value]


class FakeExtractor(KnowledgeExtractorPort):
    def __init__(self, answers: dict[str, KnowledgeAnswer]) -> None:
        self._answers = answers

    async def extract(self, question: KnowledgeQuestion, excerpt: SourceExcerpt) -> KnowledgeAnswer:
        answer = self._answers.get(excerpt.text)
        if answer is None:
            raise KnowledgeExtractionError("the excerpt does not address this question")
        return answer


async def test_research_returns_found_when_the_first_candidate_grounds_an_answer() -> None:
    source = _source("sa-nca")
    ref = DiscoveredDocumentRef(url="https://sa-nca.example.gov/contracts")
    excerpt = _excerpt(source, "vendor contracts must include audit rights")
    crawler = FakeCrawler(
        discover={"sa-nca": (ref,)},
        fetch={("sa-nca", ref.url): excerpt},
    )
    extractor = FakeExtractor(
        {
            excerpt.text: KnowledgeAnswer(
                answer="Audit rights.", applicable_context="Any vendor.", confidence=0.9
            )
        }
    )
    coordinator = ResearchCoordinator(
        crawler=crawler,
        discovery_engine=KnowledgeDiscoveryEngine(extractor=extractor, id_factory=lambda: "item-1"),
        clock=lambda: _NOW,
    )
    plan = ResearchPlan(question=_QUESTION, steps=(_step(source, 0),))

    result = await coordinator.research(plan)

    assert result.status is ResearchStatus.FOUND
    assert result.item is not None
    assert result.item.confidence == 0.9
    assert result.version_hash == compute_version_hash(_QUESTION, excerpt)
    assert len(result.attempts) == 1
    assert result.attempts[0].outcome is AttemptOutcome.GROUNDED
    assert result.researched_at == _NOW


async def test_a_failed_discovery_is_isolated_and_the_next_source_is_still_checked() -> None:
    failing = _source("sa-broken")
    working = _source("sa-nca")
    ref = DiscoveredDocumentRef(url="https://sa-nca.example.gov/contracts")
    excerpt = _excerpt(working, "vendor contracts must include audit rights")
    crawler = FakeCrawler(
        discover={"sa-broken": RuntimeError("network unreachable"), "sa-nca": (ref,)},
        fetch={("sa-nca", ref.url): excerpt},
    )
    extractor = FakeExtractor(
        {
            excerpt.text: KnowledgeAnswer(
                answer="Audit rights.", applicable_context="Any vendor.", confidence=0.8
            )
        }
    )
    coordinator = ResearchCoordinator(
        crawler=crawler,
        discovery_engine=KnowledgeDiscoveryEngine(extractor=extractor, id_factory=lambda: "item-1"),
        clock=lambda: _NOW,
    )
    plan = ResearchPlan(question=_QUESTION, steps=(_step(failing, 0), _step(working, 1)))

    result = await coordinator.research(plan)

    assert result.status is ResearchStatus.FOUND
    assert [attempt.outcome for attempt in result.attempts] == [
        AttemptOutcome.DISCOVERY_FAILED,
        AttemptOutcome.GROUNDED,
    ]


async def test_a_failed_fetch_is_isolated_and_the_next_document_is_still_checked() -> None:
    source = _source("sa-nca")
    broken_ref = DiscoveredDocumentRef(url="https://sa-nca.example.gov/broken")
    good_ref = DiscoveredDocumentRef(url="https://sa-nca.example.gov/contracts")
    excerpt = _excerpt(source, "vendor contracts must include audit rights")
    crawler = FakeCrawler(
        discover={"sa-nca": (broken_ref, good_ref)},
        fetch={
            ("sa-nca", broken_ref.url): RuntimeError("404"),
            ("sa-nca", good_ref.url): excerpt,
        },
    )
    extractor = FakeExtractor(
        {
            excerpt.text: KnowledgeAnswer(
                answer="Audit rights.", applicable_context="Any vendor.", confidence=0.8
            )
        }
    )
    coordinator = ResearchCoordinator(
        crawler=crawler,
        discovery_engine=KnowledgeDiscoveryEngine(extractor=extractor, id_factory=lambda: "item-1"),
        max_documents_per_source=2,
        clock=lambda: _NOW,
    )
    plan = ResearchPlan(question=_QUESTION, steps=(_step(source, 0),))

    result = await coordinator.research(plan)

    assert result.status is ResearchStatus.FOUND
    outcomes = {
        (attempt.ref.url if attempt.ref else None): attempt.outcome for attempt in result.attempts
    }
    assert outcomes[broken_ref.url] is AttemptOutcome.FETCH_FAILED
    assert outcomes[good_ref.url] is AttemptOutcome.GROUNDED


async def test_no_candidate_grounding_anything_yields_insufficient_evidence() -> None:
    source = _source("sa-nca")
    ref = DiscoveredDocumentRef(url="https://sa-nca.example.gov/unrelated")
    excerpt = _excerpt(source, "this page is about public holidays")
    crawler = FakeCrawler(discover={"sa-nca": (ref,)}, fetch={("sa-nca", ref.url): excerpt})
    extractor = FakeExtractor({})  # nothing grounds
    coordinator = ResearchCoordinator(
        crawler=crawler,
        discovery_engine=KnowledgeDiscoveryEngine(extractor=extractor, id_factory=lambda: "item-1"),
        clock=lambda: _NOW,
    )
    plan = ResearchPlan(question=_QUESTION, steps=(_step(source, 0),))

    result = await coordinator.research(plan)

    assert result.status is ResearchStatus.INSUFFICIENT_EVIDENCE
    assert result.item is None
    assert result.version_hash is None
    assert result.attempts[0].outcome is AttemptOutcome.NOT_GROUNDED


async def test_the_best_confidence_item_across_sources_is_kept_not_just_the_first() -> None:
    weak_source = _source("sa-weak")
    strong_source = _source("sa-strong")
    weak_ref = DiscoveredDocumentRef(url="https://sa-weak.example.gov/contracts")
    strong_ref = DiscoveredDocumentRef(url="https://sa-strong.example.gov/contracts")
    weak_excerpt = _excerpt(weak_source, "vendor contracts should probably mention audits")
    strong_excerpt = _excerpt(strong_source, "vendor contracts must include audit rights")
    crawler = FakeCrawler(
        discover={"sa-weak": (weak_ref,), "sa-strong": (strong_ref,)},
        fetch={
            ("sa-weak", weak_ref.url): weak_excerpt,
            ("sa-strong", strong_ref.url): strong_excerpt,
        },
    )
    extractor = FakeExtractor(
        {
            weak_excerpt.text: KnowledgeAnswer(
                answer="Maybe audits.", applicable_context="Any vendor.", confidence=0.4
            ),
            strong_excerpt.text: KnowledgeAnswer(
                answer="Audit rights.", applicable_context="Any vendor.", confidence=0.6
            ),
        }
    )
    coordinator = ResearchCoordinator(
        crawler=crawler,
        discovery_engine=KnowledgeDiscoveryEngine(extractor=extractor, id_factory=lambda: "item-1"),
        early_stop_confidence=0.95,  # neither answer is confident enough to stop early
        clock=lambda: _NOW,
    )
    plan = ResearchPlan(question=_QUESTION, steps=(_step(weak_source, 0), _step(strong_source, 1)))

    result = await coordinator.research(plan)

    assert result.status is ResearchStatus.FOUND
    assert result.item is not None
    assert result.item.confidence == 0.6


async def test_early_stop_confidence_skips_checking_the_remaining_sources() -> None:
    first = _source("sa-first")
    second = _source("sa-second")
    ref = DiscoveredDocumentRef(url="https://sa-first.example.gov/contracts")
    excerpt = _excerpt(first, "vendor contracts must include audit rights")
    crawler = FakeCrawler(discover={"sa-first": (ref,)}, fetch={("sa-first", ref.url): excerpt})
    extractor = FakeExtractor(
        {
            excerpt.text: KnowledgeAnswer(
                answer="Audit rights.", applicable_context="Any vendor.", confidence=0.95
            )
        }
    )
    coordinator = ResearchCoordinator(
        crawler=crawler,
        discovery_engine=KnowledgeDiscoveryEngine(extractor=extractor, id_factory=lambda: "item-1"),
        early_stop_confidence=0.9,
        clock=lambda: _NOW,
    )
    plan = ResearchPlan(question=_QUESTION, steps=(_step(first, 0), _step(second, 1)))

    result = await coordinator.research(plan)

    assert result.status is ResearchStatus.FOUND
    assert crawler.discovered_sources == ["sa-first"]  # "sa-second" was never even discovered


async def test_empty_discovery_falls_back_to_the_source_url_itself() -> None:
    source = _source("sa-nca")
    excerpt = _excerpt(source, "vendor contracts must include audit rights")
    crawler = FakeCrawler(
        discover={"sa-nca": ()},
        fetch={("sa-nca", source.url): excerpt},
    )
    extractor = FakeExtractor(
        {
            excerpt.text: KnowledgeAnswer(
                answer="Audit rights.", applicable_context="Any vendor.", confidence=0.7
            )
        }
    )
    coordinator = ResearchCoordinator(
        crawler=crawler,
        discovery_engine=KnowledgeDiscoveryEngine(extractor=extractor, id_factory=lambda: "item-1"),
        clock=lambda: _NOW,
    )
    plan = ResearchPlan(question=_QUESTION, steps=(_step(source, 0),))

    result = await coordinator.research(plan)

    assert result.status is ResearchStatus.FOUND
    assert crawler.fetched == [("sa-nca", source.url)]


async def test_max_sources_bounds_how_many_plan_steps_are_checked() -> None:
    first = _source("sa-first")
    second = _source("sa-second")
    crawler = FakeCrawler(discover={}, fetch={})
    extractor = FakeExtractor({})
    coordinator = ResearchCoordinator(
        crawler=crawler,
        discovery_engine=KnowledgeDiscoveryEngine(extractor=extractor, id_factory=lambda: "item-1"),
        max_sources=1,
        clock=lambda: _NOW,
    )
    plan = ResearchPlan(question=_QUESTION, steps=(_step(first, 0), _step(second, 1)))

    result = await coordinator.research(plan)

    assert result.status is ResearchStatus.INSUFFICIENT_EVIDENCE
    assert crawler.discovered_sources == ["sa-first"]
