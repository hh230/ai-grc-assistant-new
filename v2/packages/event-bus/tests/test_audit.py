"""The Audit Trail model, its sink interface, and the event-driven builder."""

from __future__ import annotations

import json

from event_bus import (
    VALIDATION_NOT_CONFIGURED,
    AnswerValidated,
    AuditRecord,
    AuditSink,
    AuditTrailBuilder,
    GenerationCompleted,
    InMemoryAuditSink,
    InProcessEventBus,
    PipelineCompleted,
    PromptBuilt,
    RetrievalCompleted,
)


def test_audit_record_is_frozen_and_serializable():
    record = AuditRecord(
        trace_id="t", tenant_id="org_acme", mission_id="mis_1", workflow="lookup", provider="openai", model="gpt-4o-mini",
        started_at=1.0, completed_at=3.5, warnings=("x",),
        validation_status="passed", validation_passed=True,
    )
    data = record.to_dict()
    assert data["trace_id"] == "t"
    assert data["duration_s"] == 2.5
    assert data["warnings"] == ["x"]
    assert data["validation_status"] == "passed"
    json.dumps(data)


def test_in_memory_sink_satisfies_the_port():
    assert isinstance(InMemoryAuditSink(), AuditSink)


def test_builder_assembles_a_record_from_the_event_stream():
    sink = InMemoryAuditSink()
    builder = AuditTrailBuilder(sink=sink)
    for event in (
        RetrievalCompleted(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=1.0, results=8, warnings=0),
        PromptBuilt(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=2.0, workflow="compliance_review", valid=True),
        GenerationCompleted(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=3.0, provider="claude", model="opus"),
        AnswerValidated(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=4.0, status="passed", valid=True),
        PipelineCompleted(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=5.0, status="completed"),
    ):
        builder.handle(event)

    record = sink.latest()
    assert record is not None
    assert record.trace_id == "t"
    assert record.tenant_id == "org_acme"   # stamped from the event stream (ADR 0040 §6)
    assert record.mission_id == "mis_1"     # (ADR 0042 §12.2)
    assert record.workflow == "compliance_review"
    assert record.provider == "claude"
    assert record.model == "opus"
    assert record.started_at == 1.0
    assert record.completed_at == 5.0
    assert record.validation_status == "passed"
    assert record.validation_passed is True


def test_builder_emits_on_the_terminal_pipeline_event():
    sink = InMemoryAuditSink()
    builder = AuditTrailBuilder(sink=sink)
    builder.handle(GenerationCompleted(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=1.0, provider="openai"))
    builder.handle(AnswerValidated(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=2.0, status="warnings", valid=True))
    assert sink.records == []  # validation is not terminal — the run may still be going
    builder.handle(PipelineCompleted(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=3.0, status="completed"))
    assert len(sink.records) == 1


def test_record_captures_every_reproducibility_fact_of_a_run():
    sink = InMemoryAuditSink()
    builder = AuditTrailBuilder(sink=sink)
    for event in (
        RetrievalCompleted(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=1.0, results=2, source_ids=("c1", "c2")),
        PromptBuilt(
            trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=2.0, workflow="compliance_workflow", intent="compliance_review",
            prompt_versions={"system": "rasheed_system.v1", "workflow": "compliance_workflow.v1"},
        ),
        GenerationCompleted(
            trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=3.0, provider="claude", model="opus",
            usage={"prompt_tokens": 900, "completion_tokens": 300, "total_tokens": 1200},
        ),
        AnswerValidated(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=4.0, status="passed", valid=True),
        PipelineCompleted(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=5.0, status="completed"),
    ):
        builder.handle(event)

    record = sink.latest()
    assert record.trace_id == "t"
    assert record.workflow == "compliance_workflow"
    assert record.intent == "compliance_review"
    assert record.provider == "claude"
    assert record.model == "opus"
    assert record.prompt_versions["workflow"] == "compliance_workflow.v1"
    assert record.source_ids == ("c1", "c2")
    assert record.usage["total_tokens"] == 1200
    assert record.total_tokens == 1200
    assert record.estimated_cost is None  # no cost model yet — absent, never fabricated
    assert record.started_at == 1.0 and record.completed_at == 5.0
    assert record.status == "completed"
    assert record.validation_status == "passed"
    json.dumps(record.to_dict())


def test_record_finalizes_completely_when_no_validator_is_configured():
    sink = InMemoryAuditSink()
    builder = AuditTrailBuilder(sink=sink)
    # exactly the event stream of a pipeline wired without an AnswerValidator
    builder.handle(RetrievalCompleted(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=1.0, source_ids=("c1",)))
    builder.handle(PromptBuilt(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=2.0, workflow="lookup_workflow", intent="lookup"))
    builder.handle(GenerationCompleted(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=3.0, provider="ollama", model="llama3"))
    builder.handle(PipelineCompleted(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=4.0, status="completed"))

    record = sink.latest()
    assert record is not None
    assert record.status == "completed"
    assert record.workflow == "lookup_workflow"
    assert record.provider == "ollama"
    assert record.source_ids == ("c1",)
    # "nobody checked" is recorded as its own outcome, never as a silent pass
    assert record.validation_status == VALIDATION_NOT_CONFIGURED


def test_a_run_that_never_generated_is_still_audited():
    """A prompt rejected before generation, or a run paused at a human gate, is an
    audit-worthy fact: the record exists and says what happened."""
    sink = InMemoryAuditSink()
    builder = AuditTrailBuilder(sink=sink)
    builder.handle(PromptBuilt(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=1.0, workflow="lookup_workflow", valid=False))
    builder.handle(PipelineCompleted(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=2.0, status="invalid_prompt"))

    record = sink.latest()
    assert record.status == "invalid_prompt"
    assert record.provider == ""  # nothing generated
    assert "prompt: failed validation" in record.warnings


def test_builder_records_prompt_and_retrieval_warnings():
    builder = AuditTrailBuilder()
    builder.handle(RetrievalCompleted(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=1.0, warnings=2))
    builder.handle(PromptBuilt(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=2.0, workflow="lookup", valid=False))
    record = builder.finalize("t")
    assert record is not None
    assert "retrieval: 2 warning(s)" in record.warnings
    assert "prompt: failed validation" in record.warnings


def test_finalize_closes_a_run_with_no_terminal_event():
    sink = InMemoryAuditSink()
    builder = AuditTrailBuilder(sink=sink)
    builder.handle(GenerationCompleted(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=1.0, provider="ollama", model="llama3"))
    record = builder.finalize("t")
    assert record is not None
    assert record.provider == "ollama"
    assert sink.records == [record]


def test_finalize_unknown_trace_returns_none():
    assert AuditTrailBuilder().finalize("nope") is None


def test_a_trace_is_finalized_once():
    sink = InMemoryAuditSink()
    builder = AuditTrailBuilder(sink=sink)
    builder.handle(GenerationCompleted(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=1.0, provider="openai"))
    builder.handle(PipelineCompleted(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=2.0, status="completed"))
    assert builder.finalize("t") is None  # scratch state already dropped
    assert len(sink.records) == 1


def test_builder_keeps_traces_independent():
    builder = AuditTrailBuilder()
    builder.handle(
        GenerationCompleted(
            trace_id="a", tenant_id="org_acme", mission_id="mis_1", occurred_at=1.0, provider="openai"
        )
    )
    builder.handle(
        GenerationCompleted(
            trace_id="b", tenant_id="org_acme", mission_id="mis_1", occurred_at=1.0, provider="claude"
        )
    )
    assert builder.finalize("a").provider == "openai"
    assert builder.finalize("b").provider == "claude"


def test_builder_wires_onto_the_bus_as_a_subscriber():
    sink = InMemoryAuditSink()
    builder = AuditTrailBuilder(sink=sink)
    bus = InProcessEventBus()
    bus.subscribe_all(builder.handle)
    bus.publish(PromptBuilt(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=1.0, workflow="lookup"))
    bus.publish(GenerationCompleted(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=2.0, provider="openai", model="m"))
    bus.publish(AnswerValidated(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=3.0, status="passed", valid=True))
    bus.publish(PipelineCompleted(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=4.0, status="completed"))
    assert sink.latest().workflow == "lookup"
    assert sink.latest().provider == "openai"
