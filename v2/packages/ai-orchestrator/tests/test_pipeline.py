"""End-to-end coordination tests: the real engines run; only search hits and generation
are faked. What is asserted is the orchestrator's own responsibilities — sequencing,
skipping, metrics, tracing, warnings, statuses — never engine internals."""

from __future__ import annotations

import pytest
from ai_orchestrator import (
    CancellationToken,
    PipelineCancelled,
    PipelineHooks,
    PipelineStage,
    PipelineStageError,
    PipelineStatus,
)
from pipeline_contracts import DecisionPlan, SegmentKind, TenantContext, UserRequest

from tests.conftest import FakeGenerationProvider, orchestrator_with

_TENANT = TenantContext(tenant_id="org_acme", principal_id="u1")


def make_plan(**overrides) -> DecisionPlan:
    base = dict(
        intent="conversation", workflow="conversation", requires_retrieval=False,
        requires_document=False, requires_reranker=False, requires_human_gate=False,
        multi_step=False, retrieval_passes=0, context_budget=4000, target_profiles=[],
        confidence=0.9, reason="stub",
    )
    base.update(overrides)
    return DecisionPlan(**base)


class StubDecisionEngine:
    def __init__(self, plan: DecisionPlan) -> None:
        self._plan = plan

    def decide(self, request) -> DecisionPlan:
        return self._plan


# ── the grounded happy path ────────────────────────────────────────────────────
def test_grounded_run_walks_every_stage(orchestrator, fake_generation):
    result = orchestrator.run(UserRequest(tenant=_TENANT, query="Explain the consent requirements under PDPL"), mission_id="mis_test")

    assert result.status is PipelineStatus.COMPLETED
    assert result.plan.requires_retrieval is True
    assert result.retrieved is not None and result.retrieved.results
    assert result.context is not None and result.context.valid
    assert result.llm_request is not None and result.llm_request.valid
    assert result.answer is not None and result.answer.text == "Grounded answer [1]."
    assert result.answer.provider == "fake"
    # the provider received the exact assembled request
    assert fake_generation.requests == [result.llm_request]
    # every stage was timed, in order
    assert list(result.metrics.timings_ms) == ["decision", "retrieval", "context", "prompt", "generation"]
    assert result.metrics.total_ms > 0
    assert result.metrics.usage["total_tokens"] == 120
    assert result.metrics.estimated_prompt_tokens > 0


def test_citations_flow_end_to_end(orchestrator):
    result = orchestrator.run(
        UserRequest.from_dict(
            {"query": "Explain the consent requirements under PDPL"}, tenant=_TENANT
        ),
        mission_id="mis_test",
    )

    assert result.context.all_citations(), "citations must survive into the context package"
    context_segment = result.llm_request.segment(SegmentKind.CONTEXT)
    assert context_segment is not None
    assert "pdpl.pdf" in context_segment.content


def test_conversation_skips_retrieval_and_context(orchestrator):
    result = orchestrator.run(UserRequest(tenant=_TENANT, query="hello"), mission_id="mis_test")

    assert result.status is PipelineStatus.COMPLETED
    assert result.plan.requires_retrieval is False
    assert result.retrieved is None and result.context is None
    assert "retrieval" not in result.metrics.timings_ms
    assert "context" not in result.metrics.timings_ms
    assert result.answer is not None


def test_missing_retrieval_engine_degrades_with_warning():
    orch = orchestrator_with(retrieval=None)
    result = orch.run(UserRequest(tenant=_TENANT, query="Explain the consent requirements under PDPL"), mission_id="mis_test")

    assert result.status is PipelineStatus.COMPLETED
    assert result.retrieved is None
    assert any("no retrieval engine is wired" in w for w in result.warnings)
    # the prompt layer flags the missing grounding explicitly
    assert any("insufficient-evidence" in w for w in result.llm_request.warnings)


# ── tracing, hooks, events ────────────────────────────────────────────────────
def test_trace_id_is_propagated_and_stages_hooked():
    events: list[str] = []
    stages: list[tuple[str, str]] = []
    hooks = PipelineHooks(
        on_stage_start=lambda stage, trace: stages.append((stage.value, trace)),
        on_event=lambda name, payload: events.append(name),
    )
    orch = orchestrator_with(hooks)
    result = orch.run(UserRequest(tenant=_TENANT, query="hello"), mission_id="mis_test", trace_id="trace-42")

    assert result.trace_id == "trace-42"
    assert all(trace == "trace-42" for _, trace in stages)
    assert events[0] == "pipeline.started"
    assert events[-1] == "pipeline.finished"
    assert "stage.decision.completed" in events
    assert "stage.generation.completed" in events


# ── cancellation ──────────────────────────────────────────────────────────────
def test_pre_cancelled_token_stops_before_first_stage():
    orch = orchestrator_with()
    token = CancellationToken()
    token.cancel()

    with pytest.raises(PipelineCancelled) as excinfo:
        orch.run(UserRequest(tenant=_TENANT, query="hello"), cancellation=token, mission_id="mis_test")
    assert excinfo.value.stage is PipelineStage.DECISION


def test_mid_run_cancellation_stops_at_next_stage():
    token = CancellationToken()
    hooks = PipelineHooks(
        on_stage_end=lambda stage, trace, ms: token.cancel() if stage is PipelineStage.DECISION else None
    )
    orch = orchestrator_with(hooks)

    with pytest.raises(PipelineCancelled) as excinfo:
        orch.run(UserRequest(tenant=_TENANT, query="Explain the consent requirements under PDPL"), cancellation=token, mission_id="mis_test")
    assert excinfo.value.stage is PipelineStage.RETRIEVAL


# ── error propagation ─────────────────────────────────────────────────────────
def test_stage_failure_is_wrapped_with_stage_and_cause():
    class ExplodingProvider(FakeGenerationProvider):
        def generate(self, request):
            raise RuntimeError("provider unreachable")

    orch = orchestrator_with(generation=ExplodingProvider())
    with pytest.raises(PipelineStageError) as excinfo:
        orch.run(UserRequest(tenant=_TENANT, query="hello"), mission_id="mis_test", trace_id="t-err")

    assert excinfo.value.stage is PipelineStage.GENERATION
    assert excinfo.value.trace_id == "t-err"
    assert isinstance(excinfo.value.__cause__, RuntimeError)


# ── human gate ────────────────────────────────────────────────────────────────
def test_human_gate_pauses_before_generation():
    seen = []
    hooks = PipelineHooks(approval_gate=lambda req: (seen.append(req), False)[1])
    generation = FakeGenerationProvider()
    orch = orchestrator_with(
        hooks,
        decision=StubDecisionEngine(make_plan(requires_human_gate=True)),
        generation=generation,
    )
    result = orch.run(UserRequest(tenant=_TENANT, query="hello"), mission_id="mis_test")

    assert result.status is PipelineStatus.AWAITING_APPROVAL
    assert result.answer is None
    assert generation.requests == [], "generation must not run past a closed gate"
    assert seen and seen[0].plan.requires_human_gate is True
    assert seen[0].llm_request is result.llm_request


def test_human_gate_approval_lets_generation_run():
    hooks = PipelineHooks(approval_gate=lambda req: True)
    orch = orchestrator_with(hooks, decision=StubDecisionEngine(make_plan(requires_human_gate=True)))
    result = orch.run(UserRequest(tenant=_TENANT, query="hello"), mission_id="mis_test")

    assert result.status is PipelineStatus.COMPLETED
    assert result.answer is not None
    assert "approval" in result.metrics.timings_ms


def test_human_gate_without_hook_warns_and_proceeds():
    orch = orchestrator_with(decision=StubDecisionEngine(make_plan(requires_human_gate=True)))
    result = orch.run(UserRequest(tenant=_TENANT, query="hello"), mission_id="mis_test")

    assert result.status is PipelineStatus.COMPLETED
    assert any("no approval hook" in w for w in result.warnings)


# ── audit record ──────────────────────────────────────────────────────────────
def test_result_serializes_the_full_audit_trail(orchestrator):
    result = orchestrator.run(UserRequest(tenant=_TENANT, query="Explain the consent requirements under PDPL"), mission_id="mis_test")
    record = result.to_dict()

    assert record["status"] == "completed"
    assert record["plan"]["intent"] == result.plan.intent
    assert record["retrieved"]["results"]
    assert record["llm_request"]["segments"]
    assert record["answer"]["provider"] == "fake"
    assert record["metrics"]["trace_id"] == result.trace_id


# ── Phase 12: the GenerationEngine drops into the orchestrator's port ─────────
def test_generation_engine_wires_through_the_orchestrator():
    """Target pipeline shape: AI Orchestrator → GenerationEngine → provider adapter. A
    transient provider failure is retried inside the engine — the orchestrator never sees
    it and the run completes normally."""
    from generation_engine import GenerationEngine, RetryPolicy
    from pipeline_contracts import RateLimitError

    class FlakyOnce(FakeGenerationProvider):
        def __init__(self) -> None:
            super().__init__()
            self._failed = False

        def generate(self, request):
            if not self._failed:
                self._failed = True
                raise RateLimitError("throttled", provider=self.name)
            return super().generate(request)

    sleeps: list[float] = []
    engine = GenerationEngine(FlakyOnce(), retry_policy=RetryPolicy(max_attempts=3),
                              sleep=sleeps.append)
    orchestrator = orchestrator_with(generation=engine)

    result = orchestrator.run(UserRequest(tenant=_TENANT, query="What does PDPL require for consent?"), mission_id="mis_test")

    assert result.status is PipelineStatus.COMPLETED
    assert result.answer is not None and result.answer.text.startswith("Grounded answer")
    assert sleeps == [0.5]                                # the retry happened inside the engine
    assert engine.last_metrics.attempts == 2
    assert engine.last_metrics.retries == 1
    assert "generation" in result.metrics.timings_ms      # orchestrator timing untouched
