"""Phase 13 additive wiring: tracing, domain events, and answer validation compose into
the orchestrator without changing the default run. Every capability is opt-in — the first
test proves a bare run behaves exactly as before."""

from __future__ import annotations

from ai_orchestrator import AIOrchestrator, PipelineStatus
from answer_validation import AnswerValidator, ValidationStatus
from context_builder import ContextBuilder
from decision_engine import DecisionEngine
from event_bus import (
    VALIDATION_NOT_CONFIGURED,
    AnswerValidated,
    AuditTrailBuilder,
    GenerationCompleted,
    InMemoryAuditSink,
    InProcessEventBus,
    PromptBuilt,
    RecordingEventBus,
    RetrievalCompleted,
)
from pipeline_contracts import Answer, LLMRequest, TenantContext, UserRequest
from prompt_orchestrator import PromptOrchestrator
from retrieval_engine import RetrievalEngine

from tests.conftest import FakeGenerationProvider, FakeSearchProvider

QUERY = "Explain the consent requirements under PDPL"
_TENANT = TenantContext(tenant_id="org_acme", principal_id="u1")


class CitingProvider(FakeGenerationProvider):
    """A provider whose answer is properly grounded with an [S1] marker."""

    def generate(self, request: LLMRequest) -> Answer:
        self.requests.append(request)
        return Answer(text="Consent must be explicit [S1].", provider="fake",
                      model="fake-model-1", finish_reason="stop",
                      usage={"total_tokens": 120})


class RejectingPromptOrchestrator(PromptOrchestrator):
    """Builds the request exactly as normal, then marks it invalid — the fail-safe path
    where the orchestrator must refuse to call a provider at all."""

    def orchestrate(self, plan, context, request, **kwargs) -> LLMRequest:
        llm_request = super().orchestrate(plan, context, request, **kwargs)
        llm_request.valid = False
        llm_request.warnings.append("test: forced invalid prompt")
        return llm_request


def build(*, generation=None, event_bus=None, answer_validator=None, enable_tracing=False,
          prompt=None):
    return AIOrchestrator(
        decision_engine=DecisionEngine(),
        retrieval_engine=RetrievalEngine(FakeSearchProvider("vector"), FakeSearchProvider("keyword")),
        context_builder=ContextBuilder(),
        prompt_orchestrator=prompt or PromptOrchestrator(),
        generation_provider=generation or FakeGenerationProvider(),
        event_bus=event_bus,
        answer_validator=answer_validator,
        enable_tracing=enable_tracing,
    )


# ── the zero-change guarantee ─────────────────────────────────────────────────
def test_default_run_is_unchanged_when_nothing_is_wired():
    result = build().run(UserRequest(tenant=_TENANT, query=QUERY), mission_id="mis_test")
    assert result.status is PipelineStatus.COMPLETED
    assert result.validated is None          # no validator → no verdict
    assert result.trace is None              # tracing off → no trace object
    assert list(result.metrics.timings_ms) == ["decision", "retrieval", "context", "prompt", "generation"]


# ── tracing ───────────────────────────────────────────────────────────────────
def test_tracing_produces_a_trace_with_stage_timings():
    result = build(enable_tracing=True).run(UserRequest(tenant=_TENANT, query=QUERY), mission_id="mis_test", trace_id="trace-xyz")
    assert result.trace is not None
    assert result.trace.trace_id == "trace-xyz"
    assert [s.name for s in result.trace.stages] == ["decision", "retrieval", "context", "prompt", "generation"]
    assert result.trace.total_ms >= 0
    assert all(s.ok for s in result.trace.stages)


def test_trace_serializes_into_the_audit_record():
    result = build(enable_tracing=True).run(UserRequest(tenant=_TENANT, query=QUERY), mission_id="mis_test")
    data = result.to_dict()
    assert data["trace"]["trace_id"] == result.trace_id
    assert data["trace"]["stages"]


# ── domain events ─────────────────────────────────────────────────────────────
def test_events_are_published_for_each_completed_stage():
    bus = RecordingEventBus()
    build(event_bus=bus).run(UserRequest(tenant=_TENANT, query=QUERY), mission_id="mis_test")
    names = [e.name for e in bus.events]
    assert names == [
        "retrieval.completed", "prompt.built", "generation.completed", "pipeline.completed",
    ]


def test_generation_event_carries_provider_and_usage():
    bus = RecordingEventBus()
    build(event_bus=bus, generation=CitingProvider()).run(UserRequest(tenant=_TENANT, query=QUERY), mission_id="mis_test")
    gen = next(e for e in bus.events if isinstance(e, GenerationCompleted))
    assert gen.provider == "fake"
    assert gen.model == "fake-model-1"
    assert gen.total_tokens == 120


def test_retrieval_and_prompt_events_carry_summaries():
    bus = RecordingEventBus()
    build(event_bus=bus).run(UserRequest(tenant=_TENANT, query=QUERY), mission_id="mis_test")
    retrieval = next(e for e in bus.events if isinstance(e, RetrievalCompleted))
    prompt = next(e for e in bus.events if isinstance(e, PromptBuilt))
    assert retrieval.results > 0
    assert prompt.workflow
    assert prompt.segment_count > 0
    assert prompt.valid is True


def test_event_publication_failure_never_breaks_the_run():
    class BrokenBus:
        def subscribe(self, *_): ...
        def publish(self, _event): raise RuntimeError("bus down")

    result = build(event_bus=BrokenBus()).run(UserRequest(tenant=_TENANT, query=QUERY), mission_id="mis_test")
    assert result.status is PipelineStatus.COMPLETED
    assert any("event publication failed" in w for w in result.warnings)


# ── answer validation ─────────────────────────────────────────────────────────
def test_validation_attaches_a_verdict_without_changing_the_answer():
    provider = CitingProvider()
    result = build(generation=provider, answer_validator=AnswerValidator()).run(UserRequest(tenant=_TENANT, query=QUERY), mission_id="mis_test")
    assert result.status is PipelineStatus.COMPLETED
    assert result.validated is not None
    assert result.validated.is_valid
    assert result.validated.answer is result.answer          # same object, untouched
    assert "validation" in result.metrics.timings_ms


def test_ungrounded_answer_fails_validation_but_run_still_completes():
    # the default fake answer cites "[1]" (not the [S1] style) → uncited → validation fails,
    # yet the run completes: validation reports, it never suppresses the answer.
    result = build(answer_validator=AnswerValidator()).run(UserRequest(tenant=_TENANT, query=QUERY), mission_id="mis_test")
    assert result.status is PipelineStatus.COMPLETED
    assert result.validated.status is ValidationStatus.FAILED
    assert result.answer is not None
    assert any("validation error" in w for w in result.warnings)


def test_validation_publishes_the_answer_validated_event():
    bus = RecordingEventBus()
    build(event_bus=bus, generation=CitingProvider(),
          answer_validator=AnswerValidator()).run(UserRequest(tenant=_TENANT, query=QUERY), mission_id="mis_test")
    names = [e.name for e in bus.events]
    assert names[-2:] == ["answer.validated", "pipeline.completed"]
    validated_event = next(e for e in bus.events if isinstance(e, AnswerValidated))
    assert validated_event.valid is True


# ── the audit trail assembles end to end from the live bus ────────────────────
def test_audit_trail_builds_from_the_live_event_stream():
    sink = InMemoryAuditSink()
    bus = InProcessEventBus()
    bus.subscribe_all(AuditTrailBuilder(sink=sink).handle)

    build(event_bus=bus, generation=CitingProvider(),
          answer_validator=AnswerValidator()).run(UserRequest(tenant=_TENANT, query=QUERY), mission_id="mis_test", trace_id="audit-1")

    record = sink.latest()
    assert record is not None
    assert record.trace_id == "audit-1"
    assert record.provider == "fake"
    assert record.workflow
    assert record.validation_passed is True


def test_audit_record_of_a_live_run_carries_every_reproducibility_fact():
    """CLAUDE.md §19: given the record, an auditor can say what ran, on which model, under
    which prompt versions, grounded on which sources, at what token cost."""
    sink = InMemoryAuditSink()
    bus = InProcessEventBus()
    bus.subscribe_all(AuditTrailBuilder(sink=sink).handle)

    build(event_bus=bus, generation=CitingProvider(),
          answer_validator=AnswerValidator()).run(UserRequest(tenant=_TENANT, query=QUERY), mission_id="mis_test", trace_id="audit-2")

    record = sink.latest()
    assert record.intent                                  # what was asked for
    assert record.model == "fake-model-1"                 # which model answered
    assert record.prompt_versions["system"]               # which prompt produced it
    assert record.source_ids                              # what grounded it
    assert record.usage["total_tokens"] == 120            # what it consumed
    assert record.status == "completed"
    assert record.started_at > 0 and record.completed_at >= record.started_at


def test_audit_trail_finalizes_when_no_validator_is_wired():
    """The gap this closes: with validation unconfigured the run has no terminal
    `answer.validated`, yet the audit record must still exist and be complete."""
    sink = InMemoryAuditSink()
    bus = InProcessEventBus()
    bus.subscribe_all(AuditTrailBuilder(sink=sink).handle)

    build(event_bus=bus, generation=CitingProvider()).run(UserRequest(tenant=_TENANT, query=QUERY), mission_id="mis_test", trace_id="audit-3")

    record = sink.latest()
    assert record is not None
    assert record.trace_id == "audit-3"
    assert record.status == "completed"
    assert record.provider == "fake"
    assert record.source_ids
    assert record.validation_status == VALIDATION_NOT_CONFIGURED


def test_a_run_rejected_before_generation_is_still_audited():
    """An invalid prompt is never sent to a provider — but the refusal is an audit fact."""
    sink = InMemoryAuditSink()
    bus = InProcessEventBus()
    bus.subscribe_all(AuditTrailBuilder(sink=sink).handle)

    result = build(event_bus=bus, prompt=RejectingPromptOrchestrator()).run(
        UserRequest(tenant=_TENANT, query=QUERY), mission_id="mis_test", trace_id="audit-4"
    )

    assert result.status is PipelineStatus.INVALID_PROMPT
    record = sink.latest()
    assert record is not None
    assert record.trace_id == "audit-4"
    assert record.status == "invalid_prompt"
    assert record.provider == ""  # nothing generated
