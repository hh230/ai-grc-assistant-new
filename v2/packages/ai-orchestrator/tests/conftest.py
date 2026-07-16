"""Fixtures: a tiny citable corpus, fake search providers (retrieval stays real — plan,
fusion, ranking, citation gate all run), and a fake generation provider so no test ever
touches a network or an SDK."""

from __future__ import annotations

import pytest
from ai_orchestrator import AIOrchestrator, PipelineHooks
from context_builder import ContextBuilder
from decision_engine import DecisionEngine
from pipeline_contracts import Answer, CorpusChunk, Filter, LLMRequest, ScoredHit
from prompt_orchestrator import PromptOrchestrator
from retrieval_engine import RetrievalEngine


def make_chunk(chunk_id: str, text: str, *, code: str | None = "5-1", page: int | None = 3,
               profile: str = "law", language: str = "en") -> CorpusChunk:
    return CorpusChunk(
        chunk_id=chunk_id,
        document_id="doc-pdpl",
        text=text,
        document_profile=profile,
        structure_profile="regulation_article",
        category="laws",
        language=language,
        code=code,
        title="Data Processing",
        heading_path=("Chapter 2", "Article 5"),
        page_start=page,
        page_end=page,
        source_filename="pdpl.pdf",
        checksum="abc123",
        content_type="application/pdf",
    )


CORPUS = [
    make_chunk("c1", "Personal data may only be processed with the consent of the data subject."),
    make_chunk("c2", "The controller shall implement appropriate security controls for personal data."),
    make_chunk("c3", "Data subjects have the right to access their personal data held by controllers."),
]


class FakeSearchProvider:
    """Returns the corpus as descending-score hits, honouring the metadata filter — enough
    for the real RetrievalEngine pipeline (fusion, ranking, citation gate) to run."""

    def __init__(self, source: str) -> None:
        self._source = source

    def search(self, query: str, filter: Filter, top_k: int) -> list[ScoredHit]:
        hits = [
            c for c in CORPUS
            if not filter.document_profiles or c.document_profile in filter.document_profiles
        ]
        return [
            ScoredHit(chunk=c, score=1.0 - i * 0.1, source=self._source)
            for i, c in enumerate(hits[:top_k])
        ]


class FakeGenerationProvider:
    """`GenerationProvider` test double: records the request, returns a canned answer."""

    def __init__(self, text: str = "Grounded answer [1].") -> None:
        self.requests: list[LLMRequest] = []
        self._text = text

    @property
    def name(self) -> str:
        return "fake"

    def generate(self, request: LLMRequest) -> Answer:
        self.requests.append(request)
        return Answer(
            text=self._text,
            provider=self.name,
            model="fake-model-1",
            finish_reason="stop",
            usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        )


@pytest.fixture
def fake_generation() -> FakeGenerationProvider:
    return FakeGenerationProvider()


@pytest.fixture
def orchestrator(fake_generation: FakeGenerationProvider) -> AIOrchestrator:
    return AIOrchestrator(
        decision_engine=DecisionEngine(),
        retrieval_engine=RetrievalEngine(FakeSearchProvider("vector"), FakeSearchProvider("keyword")),
        context_builder=ContextBuilder(),
        prompt_orchestrator=PromptOrchestrator(),
        generation_provider=fake_generation,
    )


def orchestrator_with(hooks: PipelineHooks | None = None, *, decision=None, retrieval="default",
                      generation=None) -> AIOrchestrator:
    """Wiring helper for tests that need a custom hook set, a stubbed decision engine, or
    no retrieval engine (pass retrieval=None)."""
    return AIOrchestrator(
        decision_engine=decision or DecisionEngine(),
        retrieval_engine=(
            RetrievalEngine(FakeSearchProvider("vector"), FakeSearchProvider("keyword"))
            if retrieval == "default" else retrieval
        ),
        context_builder=ContextBuilder(),
        prompt_orchestrator=PromptOrchestrator(),
        generation_provider=generation or FakeGenerationProvider(),
        hooks=hooks,
    )
