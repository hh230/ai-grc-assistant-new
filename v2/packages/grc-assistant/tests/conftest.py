"""Fixtures that stand up the **real** pipeline behind fakes (mirroring pipeline-tool's own test
wiring): the DecisionEngine, RetrievalEngine, ContextBuilder and PromptOrchestrator run for real;
only the search + generation providers are fakes, so no test touches a network or an SDK. The DB
fixtures stand a MissionRuntime on throwaway PostgreSQL tables and auto-skip without a database.

This makes the grounded-answer test a genuine end-to-end run of the *whole* stack:
Assistant → Mission → RegistryExecutor → Tool Registry → PipelineTool → AI Orchestrator → answer.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from ai_orchestrator import AIOrchestrator
from context_builder import ContextBuilder
from decision_engine import DecisionEngine
from pipeline_contracts import Answer, CorpusChunk, Filter, LLMRequest, ScoredHit, TenantContext
from pipeline_tool import PipelineTool
from prompt_orchestrator import PromptOrchestrator
from retrieval_engine import RetrievalEngine
from tool_registry import ToolRegistry

psycopg = pytest.importorskip("psycopg")

from grc_assistant import build_tool_backed_mission_runtime  # noqa: E402
from mission_store.config import dsn as default_dsn  # noqa: E402
from mission_store.outbox_schema import apply_outbox_schema  # noqa: E402
from mission_store.schema import apply_schema  # noqa: E402


# ── the real pipeline, fake providers (copied from pipeline-tool's slice test) ──
def _chunk(chunk_id: str, text: str) -> CorpusChunk:
    return CorpusChunk(
        chunk_id=chunk_id,
        document_id="doc-pdpl",
        text=text,
        document_profile="law",
        structure_profile="regulation_article",
        category="laws",
        language="en",
        code="5-1",
        title="Data Processing",
        heading_path=("Chapter 2", "Article 5"),
        page_start=3,
        page_end=3,
        source_filename="pdpl.pdf",
        checksum="abc123",
        content_type="application/pdf",
    )


_CORPUS = [
    _chunk("c1", "Personal data may only be processed with the consent of the data subject."),
    _chunk("c2", "The controller shall implement appropriate security controls for personal data."),
]


class _FakeSearch:
    def __init__(self, source: str) -> None:
        self._source = source

    def search(self, query: str, filter: Filter, top_k: int) -> list[ScoredHit]:
        return [
            ScoredHit(chunk=c, score=1.0 - i * 0.1, source=self._source)
            for i, c in enumerate(_CORPUS[:top_k])
        ]


class _FakeGeneration:
    @property
    def name(self) -> str:
        return "fake"

    def generate(self, request: LLMRequest) -> Answer:
        return Answer(
            text="Grounded answer [1].",
            provider=self.name,
            model="fake-model-1",
            finish_reason="stop",
            usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        )


class _EchoingGeneration:
    """A `GenerationProvider` for the LLM tool that reflects the folded prompt (system + user) back
    into its answer — so a synthesis step's output visibly contains the prior steps' rendered text.
    That is the end-to-end proof that inter-step context (ADR 0051) flowed through the path."""

    @property
    def name(self) -> str:
        return "echo"

    def generate(self, request: LLMRequest) -> Answer:
        folded = " || ".join(m["content"] for m in request.messages())
        return Answer(text=f"SYNTHESIS[{folded}]", provider=self.name, model="echo-1")


@pytest.fixture
def orchestrator() -> AIOrchestrator:
    """The real AI Orchestrator with the real pipeline stages, only the search + generation
    providers faked — so tools that wrap it (PipelineTool) run a genuine end-to-end pass, not a
    mock."""
    return AIOrchestrator(
        decision_engine=DecisionEngine(),
        retrieval_engine=RetrievalEngine(_FakeSearch("vector"), _FakeSearch("keyword")),
        context_builder=ContextBuilder(),
        prompt_orchestrator=PromptOrchestrator(),
        generation_provider=_FakeGeneration(),
    )


@pytest.fixture
def registry(orchestrator: AIOrchestrator) -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(PipelineTool(orchestrator))
    return reg


@pytest.fixture
def generation_provider() -> _EchoingGeneration:
    """The provider behind `generate_text` in the composite capabilities' synthesis steps."""
    return _EchoingGeneration()


@pytest.fixture
def tenant() -> TenantContext:
    return TenantContext(tenant_id="org_acme", principal_id="u_owner", roles=("owner",))


# ── DB-gated MissionRuntime on throwaway tables ────────────────────────────────
def _connect() -> psycopg.Connection:
    try:
        return psycopg.connect(default_dsn(), connect_timeout=3, autocommit=True)
    except Exception as exc:  # noqa: BLE001 - any connect failure means "no DB": skip
        pytest.skip(f"no reachable PostgreSQL ({exc})")


@pytest.fixture
def observer() -> Iterator[psycopg.Connection]:
    conn = _connect()
    yield conn
    conn.close()


@pytest.fixture
def tool_backed_runtime(observer: psycopg.Connection, registry: ToolRegistry):
    suffix = uuid.uuid4().hex[:8]
    missions_table = f"missions_ga_{suffix}"
    outbox_table = f"outbox_ga_{suffix}"
    apply_schema(observer, missions_table)
    apply_outbox_schema(observer, outbox_table)
    yield build_tool_backed_mission_runtime(
        registry, missions_table=missions_table, outbox_table=outbox_table
    )
    observer.execute(f"DROP TABLE IF EXISTS {missions_table}")
    observer.execute(f"DROP TABLE IF EXISTS {outbox_table}")
