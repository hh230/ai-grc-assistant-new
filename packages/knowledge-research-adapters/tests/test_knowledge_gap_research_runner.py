"""Unit tests for KnowledgeGapResearchRunner: gap detection against the stored knowledge
base, wiring a grounded result into the idempotent upsert, skipping already-answered
questions, and fail-safe isolation of an insufficient-evidence question or a storage failure
— all against fake crawler/extractor/store doubles and the real (pure) ResearchCoordinator,
no real network, LLM, or database."""

from __future__ import annotations

from dataclasses import dataclass, field
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
)
from grc_knowledge_research import (
    CatalogedSource,
    DiscoveredDocumentRef,
    ResearchCoordinator,
    ResearchCrawlerPort,
)
from grc_knowledge_research_adapters import KnowledgeGapResearchRunner
from grc_knowledge_worker import WorkerEvent

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)

_SOURCE = TrustedSource(
    source_id="sa-nca",
    name="National Cybersecurity Authority (NCA)",
    source_type=TrustedSourceType.GOVERNMENT_REGULATOR,
    url="https://nca.gov.sa",
    jurisdiction="SA",
)

_CATALOG = (CatalogedSource(source=_SOURCE, domains=(KnowledgeDomain.VENDOR_MANAGEMENT,)),)

_QUESTION = KnowledgeQuestion(
    question_id="vendor_management.contract_clauses",
    question="What clauses should exist in a vendor contract?",
    domain=KnowledgeDomain.VENDOR_MANAGEMENT,
    category="contract_requirements",
)

_UNRESEARCHABLE_QUESTION = KnowledgeQuestion(
    question_id="audit.independence",
    question="What safeguards protect internal audit independence?",
    domain=KnowledgeDomain.AUDIT,  # nothing in _CATALOG is tagged for this domain
    category="independence",
)


class FakeCrawler(ResearchCrawlerPort):
    def __init__(
        self, *, refs_and_excerpts: dict[str, tuple[DiscoveredDocumentRef, SourceExcerpt]]
    ) -> None:
        self._by_source = refs_and_excerpts

    async def discover(self, source: TrustedSource) -> tuple[DiscoveredDocumentRef, ...]:
        entry = self._by_source.get(source.source_id)
        return (entry[0],) if entry else ()

    async def fetch(self, source: TrustedSource, ref: DiscoveredDocumentRef) -> SourceExcerpt:
        return self._by_source[source.source_id][1]


class FakeExtractor(KnowledgeExtractorPort):
    def __init__(self, answers: dict[str, KnowledgeAnswer]) -> None:
        self._answers = answers

    async def extract(self, question: KnowledgeQuestion, excerpt: SourceExcerpt) -> KnowledgeAnswer:
        answer = self._answers.get(excerpt.text)
        if answer is None:
            raise KnowledgeExtractionError("the excerpt does not address this question")
        return answer


@dataclass(frozen=True)
class _Row:
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


@dataclass
class InMemoryKnowledgeItemStore:
    rows: list[_Row] = field(default_factory=list)
    upsert_calls: list[dict[str, object]] = field(default_factory=list)
    fail_upsert: bool = False

    async def list_all(self) -> list[_Row]:
        return list(self.rows)

    async def upsert(self, **kwargs: object) -> None:
        if self.fail_upsert:
            raise RuntimeError("database unavailable")
        self.upsert_calls.append(kwargs)


class FakeEventSink:
    def __init__(self) -> None:
        self.events: list[WorkerEvent] = []

    async def record(self, event: WorkerEvent) -> None:
        self.events.append(event)


def _runner(
    *,
    crawler: FakeCrawler,
    extractor: FakeExtractor,
    store: InMemoryKnowledgeItemStore,
    event_sink: FakeEventSink | None = None,
) -> KnowledgeGapResearchRunner:
    engine = KnowledgeDiscoveryEngine(extractor=extractor, id_factory=lambda: "item-1")
    coordinator = ResearchCoordinator(crawler=crawler, discovery_engine=engine, clock=lambda: _NOW)
    return KnowledgeGapResearchRunner(
        catalog=_CATALOG, coordinator=coordinator, store=store, event_sink=event_sink
    )


async def test_a_missing_question_is_researched_and_stored() -> None:
    ref = DiscoveredDocumentRef(url="https://nca.gov.sa/contracts")
    excerpt = SourceExcerpt(
        source=_SOURCE, text="vendor contracts must include audit rights", fetched_at=_NOW
    )
    crawler = FakeCrawler(refs_and_excerpts={"sa-nca": (ref, excerpt)})
    extractor = FakeExtractor(
        {
            excerpt.text: KnowledgeAnswer(
                answer="Audit rights.", applicable_context="Any vendor.", confidence=0.9
            )
        }
    )
    store = InMemoryKnowledgeItemStore()
    runner = _runner(crawler=crawler, extractor=extractor, store=store)

    outcomes = await runner.run((_QUESTION,), now=_NOW)

    assert len(outcomes) == 1
    assert outcomes[0].question_id == _QUESTION.question_id
    assert outcomes[0].gap_status == "missing"
    assert outcomes[0].research_status == "found"
    assert outcomes[0].stored is True
    assert len(store.upsert_calls) == 1
    assert store.upsert_calls[0]["question_id"] == _QUESTION.question_id
    assert store.upsert_calls[0]["confidence"] == 0.9
    assert store.upsert_calls[0]["source_id"] == "sa-nca"


async def test_an_already_answered_question_is_never_researched() -> None:
    row = _Row(
        id="row-1",
        question_id=_QUESTION.question_id,
        question=_QUESTION.question,
        answer="Existing answer.",
        domain=_QUESTION.domain.value,
        category=_QUESTION.category,
        applicable_context="Any vendor.",
        source_id="sa-nca",
        source_name="NCA",
        source_type="government_regulator",
        source_url="https://nca.gov.sa",
        jurisdiction="SA",
        citation="sa-nca#vendor_management.contract_clauses",
        confidence=0.9,
        status="verified",
        last_verified=_NOW,
        version=1,
    )
    store = InMemoryKnowledgeItemStore(rows=[row])
    crawler = FakeCrawler(refs_and_excerpts={})
    extractor = FakeExtractor({})
    runner = _runner(crawler=crawler, extractor=extractor, store=store)

    outcomes = await runner.run((_QUESTION,), now=_NOW)

    assert outcomes == ()
    assert store.upsert_calls == []


async def test_a_question_with_no_cataloged_source_is_insufficient_evidence_and_not_stored() -> (
    None
):
    store = InMemoryKnowledgeItemStore()
    crawler = FakeCrawler(refs_and_excerpts={})
    extractor = FakeExtractor({})
    runner = _runner(crawler=crawler, extractor=extractor, store=store)

    outcomes = await runner.run((_UNRESEARCHABLE_QUESTION,), now=_NOW)

    assert len(outcomes) == 1
    assert outcomes[0].research_status == "insufficient_evidence"
    assert outcomes[0].stored is False
    assert store.upsert_calls == []


async def test_one_questions_lack_of_evidence_does_not_block_another_questions_success() -> None:
    ref = DiscoveredDocumentRef(url="https://nca.gov.sa/contracts")
    excerpt = SourceExcerpt(
        source=_SOURCE, text="vendor contracts must include audit rights", fetched_at=_NOW
    )
    crawler = FakeCrawler(refs_and_excerpts={"sa-nca": (ref, excerpt)})
    extractor = FakeExtractor(
        {
            excerpt.text: KnowledgeAnswer(
                answer="Audit rights.", applicable_context="Any vendor.", confidence=0.9
            )
        }
    )
    store = InMemoryKnowledgeItemStore()
    runner = _runner(crawler=crawler, extractor=extractor, store=store)

    outcomes = await runner.run((_UNRESEARCHABLE_QUESTION, _QUESTION), now=_NOW)

    outcomes_by_question = {outcome.question_id: outcome for outcome in outcomes}
    assert outcomes_by_question[_UNRESEARCHABLE_QUESTION.question_id].stored is False
    assert outcomes_by_question[_QUESTION.question_id].stored is True
    assert len(store.upsert_calls) == 1


async def test_a_storage_failure_is_isolated_and_reported_not_raised() -> None:
    ref = DiscoveredDocumentRef(url="https://nca.gov.sa/contracts")
    excerpt = SourceExcerpt(
        source=_SOURCE, text="vendor contracts must include audit rights", fetched_at=_NOW
    )
    crawler = FakeCrawler(refs_and_excerpts={"sa-nca": (ref, excerpt)})
    extractor = FakeExtractor(
        {
            excerpt.text: KnowledgeAnswer(
                answer="Audit rights.", applicable_context="Any vendor.", confidence=0.9
            )
        }
    )
    store = InMemoryKnowledgeItemStore(fail_upsert=True)
    runner = _runner(crawler=crawler, extractor=extractor, store=store)

    outcomes = await runner.run((_QUESTION,), now=_NOW)

    assert outcomes[0].stored is False
    assert outcomes[0].error == "database unavailable"


async def test_a_successful_run_emits_the_full_activity_timeline() -> None:
    ref = DiscoveredDocumentRef(url="https://nca.gov.sa/contracts")
    excerpt = SourceExcerpt(
        source=_SOURCE, text="vendor contracts must include audit rights", fetched_at=_NOW
    )
    crawler = FakeCrawler(refs_and_excerpts={"sa-nca": (ref, excerpt)})
    extractor = FakeExtractor(
        {
            excerpt.text: KnowledgeAnswer(
                answer="Audit rights.", applicable_context="Any vendor.", confidence=0.9
            )
        }
    )
    store = InMemoryKnowledgeItemStore()
    sink = FakeEventSink()
    runner = _runner(crawler=crawler, extractor=extractor, store=store, event_sink=sink)

    await runner.run((_QUESTION,), now=_NOW)

    assert [event.event_type.value for event in sink.events] == [
        "questions_loaded",
        "gap_detected",
        "source_searched",
        "knowledge_discovered",
        "item_saved",
    ]
    assert all(event.occurred_at == _NOW for event in sink.events)
    assert sink.events[1].question_id == _QUESTION.question_id


async def test_a_storage_failure_emits_an_error_event_instead_of_item_saved() -> None:
    ref = DiscoveredDocumentRef(url="https://nca.gov.sa/contracts")
    excerpt = SourceExcerpt(
        source=_SOURCE, text="vendor contracts must include audit rights", fetched_at=_NOW
    )
    crawler = FakeCrawler(refs_and_excerpts={"sa-nca": (ref, excerpt)})
    extractor = FakeExtractor(
        {
            excerpt.text: KnowledgeAnswer(
                answer="Audit rights.", applicable_context="Any vendor.", confidence=0.9
            )
        }
    )
    store = InMemoryKnowledgeItemStore(fail_upsert=True)
    sink = FakeEventSink()
    runner = _runner(crawler=crawler, extractor=extractor, store=store, event_sink=sink)

    await runner.run((_QUESTION,), now=_NOW)

    assert [event.event_type.value for event in sink.events] == [
        "questions_loaded",
        "gap_detected",
        "source_searched",
        "knowledge_discovered",
        "error",
    ]
