"""Domain events are immutable, named, past-tense, and serialize to plain dicts."""

from __future__ import annotations

import json

import pytest
from event_bus import (
    AnswerValidated,
    DomainEvent,
    GenerationCompleted,
    PipelineCompleted,
    PromptBuilt,
    RetrievalCompleted,
)


def test_events_are_frozen():
    event = GenerationCompleted(trace_id="t", tenant_id="org_acme", mission_id="mis_1", provider="openai", model="gpt-4o-mini")
    with pytest.raises(Exception):
        event.provider = "other"  # type: ignore[misc]


def test_event_names_are_stable_past_tense():
    assert RetrievalCompleted.name == "retrieval.completed"
    assert PromptBuilt.name == "prompt.built"
    assert GenerationCompleted.name == "generation.completed"
    assert AnswerValidated.name == "answer.validated"
    assert PipelineCompleted.name == "pipeline.completed"


def test_all_events_are_domain_events():
    for evt in (
        RetrievalCompleted, PromptBuilt, GenerationCompleted, AnswerValidated, PipelineCompleted,
    ):
        assert issubclass(evt, DomainEvent)


def test_occurred_at_defaults_and_is_overridable():
    auto = PromptBuilt(trace_id="t", tenant_id="org_acme", mission_id="mis_1")
    assert auto.occurred_at > 0
    fixed = PromptBuilt(trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=123.0)
    assert fixed.occurred_at == 123.0


def test_to_dict_carries_name_trace_and_payload():
    event = RetrievalCompleted(
        trace_id="trace-1", tenant_id="org_acme", mission_id="mis_1", occurred_at=1.0,
        query="What is PDPL?",
        candidates=40, results=8, overall_confidence=0.72, warnings=1,
    )
    data = event.to_dict()
    assert data["name"] == "retrieval.completed"
    assert data["trace_id"] == "trace-1"
    assert data["tenant_id"] == "org_acme"   # stamped on every event (ADR 0040 §6)
    assert data["mission_id"] == "mis_1"     # (ADR 0042 §12.2)
    assert data["query"] == "What is PDPL?"
    assert data["candidates"] == 40
    assert data["results"] == 8
    assert data["overall_confidence"] == 0.72
    assert data["warnings"] == 1
    json.dumps(data)  # plain + serializable


def test_answer_validated_carries_status_as_plain_string():
    event = AnswerValidated(
        trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=2.0, status="warnings", valid=True,
        error_count=0, warning_count=2, confidence_adjustment=-0.1,
    )
    data = event.to_dict()
    assert data["status"] == "warnings"
    assert data["valid"] is True
    assert data["warning_count"] == 2
    assert data["confidence_adjustment"] == -0.1


def test_retrieval_completed_carries_the_source_ids_it_admitted():
    event = RetrievalCompleted(trace_id="t", tenant_id="org_acme", mission_id="mis_1", source_ids=("chunk-a", "chunk-b"))
    data = event.to_dict()
    assert data["source_ids"] == ["chunk-a", "chunk-b"]  # a list, in rank order
    json.dumps(data)


def test_prompt_built_carries_intent_and_prompt_versions():
    event = PromptBuilt(
        trace_id="t", tenant_id="org_acme", mission_id="mis_1", workflow="lookup_workflow", intent="lookup",
        prompt_versions={"system": "rasheed_system.v1", "workflow": "lookup_workflow.v1"},
    )
    data = event.to_dict()
    assert data["intent"] == "lookup"
    assert data["prompt_versions"]["system"] == "rasheed_system.v1"
    json.dumps(data)


def test_generation_completed_carries_full_usage_and_absent_cost():
    event = GenerationCompleted(
        trace_id="t", tenant_id="org_acme", mission_id="mis_1", provider="claude", model="opus", total_tokens=300,
        usage={"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300},
    )
    data = event.to_dict()
    assert data["usage"] == {"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300}
    assert data["estimated_cost"] is None  # no cost model in the platform yet
    json.dumps(data)


def test_pipeline_completed_carries_the_terminal_status():
    event = PipelineCompleted(
        trace_id="t", tenant_id="org_acme", mission_id="mis_1", occurred_at=5.0, status="completed", warnings=2, duration_ms=12.5,
    )
    data = event.to_dict()
    assert data["name"] == "pipeline.completed"
    assert data["status"] == "completed"
    assert data["warnings"] == 2
    assert data["duration_ms"] == 12.5
    json.dumps(data)
