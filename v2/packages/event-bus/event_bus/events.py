"""Domain events — immutable facts about what happened at each completed pipeline stage.

Every event is a past-tense fact (CLAUDE.md §16), frozen, and carries the `trace_id` that
threads a whole run together plus the wall-clock moment it occurred. Events carry *summary*
fields (counts, provider, model, workflow) — never whole `ContextPackage`s or SDK objects —
so the bus stays a thin, decoupled notification layer with no dependency on the pipeline
contracts. The composition root maps rich artifacts down to these summaries when it
publishes.

The events mirror the stage boundaries worth auditing, closed by a terminal fact:

    RetrievalCompleted → PromptBuilt → GenerationCompleted → AnswerValidated
                                                           → PipelineCompleted

`PipelineCompleted` is the terminal event: the composition root publishes it on *every*
path a run can end on (answered, prompt rejected, awaiting approval), which is what lets the
audit trail close a run whose validation stage never ran. Everything before it is optional;
it is not.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import ClassVar


def now() -> float:
    """The single wall-clock source events default to, so it can be swapped in tests."""
    return time.time()


@dataclass(frozen=True)
class DomainEvent:
    """Base of every domain event. `name` is a stable, past-tense identifier used for
    subscription-by-name and for the audit/event log; subclasses override it.

    `tenant_id` and `mission_id` are carried on the **base**, required exactly as `trace_id`
    is — so it is structurally impossible to publish an event without them (ADR 0040 §6; ADR
    0042 §12.2). Every event is thereby reachable through exactly one tenant and one mission.
    They are plain strings (not `TenantContext`/`Mission`) so the bus stays a thin, dependency-
    free notification layer."""

    name: ClassVar[str] = "domain_event"

    trace_id: str
    tenant_id: str
    mission_id: str
    occurred_at: float = field(default_factory=now)

    def _payload(self) -> dict[str, object]:
        """Event-specific fields for `to_dict`. Subclasses extend; base adds none."""
        return {}

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "mission_id": self.mission_id,
            "occurred_at": self.occurred_at,
            **self._payload(),
        }


@dataclass(frozen=True)
class RetrievalCompleted(DomainEvent):
    name: ClassVar[str] = "retrieval.completed"

    query: str = ""
    candidates: int = 0
    results: int = 0
    overall_confidence: float = 0.0
    warnings: int = 0
    # The identifiers of the chunks retrieval admitted, in rank order. Ids only — never the
    # chunk text — so the event stays a summary while an auditor can still answer "which
    # sources grounded this answer?" (CLAUDE.md §19).
    source_ids: tuple[str, ...] = ()

    def _payload(self) -> dict[str, object]:
        return {
            "query": self.query,
            "candidates": self.candidates,
            "results": self.results,
            "overall_confidence": self.overall_confidence,
            "warnings": self.warnings,
            "source_ids": list(self.source_ids),
        }


@dataclass(frozen=True)
class PromptBuilt(DomainEvent):
    name: ClassVar[str] = "prompt.built"

    workflow: str = ""
    family: str = ""
    language: str = ""
    estimated_tokens: int = 0
    segment_count: int = 0
    valid: bool = True
    # The intent the plan classified, and the versioned prompt artifacts that produced the
    # request (`{"system": "rasheed_system.v1", "workflow": "lookup_workflow.v1", ...}`).
    # Without these an answer cannot be reproduced (CLAUDE.md §19).
    intent: str = ""
    prompt_versions: dict[str, str] = field(default_factory=dict)

    def _payload(self) -> dict[str, object]:
        return {
            "workflow": self.workflow,
            "family": self.family,
            "language": self.language,
            "estimated_tokens": self.estimated_tokens,
            "segment_count": self.segment_count,
            "valid": self.valid,
            "intent": self.intent,
            "prompt_versions": dict(self.prompt_versions),
        }


@dataclass(frozen=True)
class GenerationCompleted(DomainEvent):
    name: ClassVar[str] = "generation.completed"

    provider: str = ""
    model: str = ""
    finish_reason: str = ""
    total_tokens: int = 0
    # The provider's full token breakdown (prompt/completion/total — whatever it reported),
    # and the run's cost if the caller could price it. There is no cost model in the platform
    # yet, so `estimated_cost` is None on every run today; the field exists so the audit
    # record's shape does not have to change when one arrives.
    usage: dict[str, int] = field(default_factory=dict)
    estimated_cost: float | None = None

    def _payload(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model,
            "finish_reason": self.finish_reason,
            "total_tokens": self.total_tokens,
            "usage": dict(self.usage),
            "estimated_cost": self.estimated_cost,
        }


@dataclass(frozen=True)
class PipelineCompleted(DomainEvent):
    """The terminal fact: a run reached one of its end states. Published on every terminal
    path — including the ones that never generate (an invalid prompt, a run paused at a
    human gate) — because those runs are audit-worthy too: an auditor must be able to see
    that a request was refused or gated, not just that it was answered."""

    name: ClassVar[str] = "pipeline.completed"

    # The `PipelineStatus` value as a plain string, so the bus never imports the
    # orchestrator — the composition root passes `status.value`.
    status: str = ""
    warnings: int = 0
    duration_ms: float = 0.0

    def _payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "warnings": self.warnings,
            "duration_ms": self.duration_ms,
        }


@dataclass(frozen=True)
class AnswerValidated(DomainEvent):
    name: ClassVar[str] = "answer.validated"

    # `status` is the validation engine's outcome as a plain string, so the bus never has to
    # import answer-validation — the composition root passes `validated.status.value`.
    status: str = ""
    valid: bool = True
    error_count: int = 0
    warning_count: int = 0
    confidence_adjustment: float = 0.0

    def _payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "valid": self.valid,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "confidence_adjustment": self.confidence_adjustment,
        }
