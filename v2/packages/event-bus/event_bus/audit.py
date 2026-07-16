"""The Audit Trail — the domain model and its interface, nothing more.

`AuditRecord` is the immutable, per-run audit fact an external reviewer needs to reconstruct
how an answer was produced (CLAUDE.md §19): the trace id and timestamps, the workflow and
intent that ran, the provider and model that answered, the versioned prompts that shaped the
call, the sources that grounded it, what it consumed, any warnings, and the validation
outcome. `AuditSink` is the port a persistence layer will implement in a later phase — this
module ships only the model and the interface (no database, no file, no retention policy).
`InMemoryAuditSink` is a trivial reference/testing implementation that holds records in a
list; it is explicitly *not* persistence.

`AuditTrailBuilder` assembles an `AuditRecord` from the domain events of one run, so the
audit trail is derived from the same event stream everything else observes — one source of
truth, not a parallel bookkeeping path. It closes a run on the terminal `PipelineCompleted`
event, which every run publishes; optional stages (retrieval, validation) only *enrich* the
record, so a pipeline wired without a validator still produces a complete, finalized one.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from event_bus.events import (
    AnswerValidated,
    DomainEvent,
    GenerationCompleted,
    PipelineCompleted,
    PromptBuilt,
    RetrievalCompleted,
)

# The validation outcome of a run that had no validator wired. Recorded explicitly rather
# than left blank: "nobody checked" and "the check passed" are different audit facts, and an
# auditor must never have to guess which one an empty field meant.
VALIDATION_NOT_CONFIGURED = "not_configured"


@dataclass(frozen=True)
class AuditRecord:
    """One run's audit fact. Immutable by construction; carries only what an auditor needs
    to reconstruct *that a run happened and how it was governed* — not the full artifacts,
    which live on the `PipelineResult`."""

    trace_id: str
    # Ownership (ADR 0040 §6; ADR 0042 §12.2): required, stamped at finalization from the run's
    # events. A record without a tenant cannot live in a tenant-scoped, append-only log; a
    # record without a mission is unreachable from the mission it belongs to.
    tenant_id: str
    mission_id: str
    workflow: str = ""
    intent: str = ""
    provider: str = ""
    model: str = ""
    prompt_versions: dict[str, str] = field(default_factory=dict)
    source_ids: tuple[str, ...] = ()
    usage: dict[str, int] = field(default_factory=dict)
    estimated_cost: float | None = None
    started_at: float = 0.0
    completed_at: float = 0.0
    status: str = ""
    warnings: tuple[str, ...] = ()
    validation_status: str = VALIDATION_NOT_CONFIGURED
    validation_passed: bool = True

    @property
    def duration_s(self) -> float:
        return max(0.0, self.completed_at - self.started_at)

    @property
    def total_tokens(self) -> int:
        return int(self.usage.get("total_tokens", 0))

    def to_dict(self) -> dict[str, object]:
        return {
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "mission_id": self.mission_id,
            "workflow": self.workflow,
            "intent": self.intent,
            "provider": self.provider,
            "model": self.model,
            "prompt_versions": dict(self.prompt_versions),
            "source_ids": list(self.source_ids),
            "usage": dict(self.usage),
            "estimated_cost": self.estimated_cost,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_s": round(self.duration_s, 6),
            "status": self.status,
            "warnings": list(self.warnings),
            "validation_status": self.validation_status,
            "validation_passed": self.validation_passed,
        }


@runtime_checkable
class AuditSink(Protocol):
    """The port a future persistence layer implements. No persistence exists this phase."""

    def record(self, record: AuditRecord) -> None: ...


class InMemoryAuditSink:
    """A non-persistent reference `AuditSink`: keeps records in a list for tests and demos.
    Not durable storage — a real sink (DB, append-only log) arrives in a later phase."""

    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    def record(self, record: AuditRecord) -> None:
        self.records.append(record)

    def latest(self) -> AuditRecord | None:
        return self.records[-1] if self.records else None


@dataclass
class _RunAudit:
    """Mutable per-trace scratch state while events for a run arrive."""

    trace_id: str
    tenant_id: str = ""
    mission_id: str = ""
    workflow: str = ""
    intent: str = ""
    provider: str = ""
    model: str = ""
    prompt_versions: dict[str, str] = field(default_factory=dict)
    source_ids: tuple[str, ...] = ()
    usage: dict[str, int] = field(default_factory=dict)
    estimated_cost: float | None = None
    started_at: float = 0.0
    completed_at: float = 0.0
    status: str = ""
    warnings: list[str] = field(default_factory=list)
    validation_status: str = VALIDATION_NOT_CONFIGURED
    validation_passed: bool = True

    def freeze(self) -> AuditRecord:
        return AuditRecord(
            trace_id=self.trace_id,
            tenant_id=self.tenant_id,
            mission_id=self.mission_id,
            workflow=self.workflow,
            intent=self.intent,
            provider=self.provider,
            model=self.model,
            prompt_versions=dict(self.prompt_versions),
            source_ids=self.source_ids,
            usage=dict(self.usage),
            estimated_cost=self.estimated_cost,
            started_at=self.started_at,
            completed_at=self.completed_at or self.started_at,
            status=self.status,
            warnings=tuple(self.warnings),
            validation_status=self.validation_status,
            validation_passed=self.validation_passed,
        )


class AuditTrailBuilder:
    """Assembles `AuditRecord`s from the event stream. Subscribe `handle` to an `EventBus`
    (or feed events directly); the builder accumulates per `trace_id` and, when an
    `AuditSink` is provided, emits a finalized record on `PipelineCompleted` — the terminal
    event every run publishes, so finalization never depends on an optional stage having
    run. A caller that publishes no terminal event (feeding stage events by hand) can still
    close a run explicitly via `finalize`."""

    def __init__(self, *, sink: AuditSink | None = None) -> None:
        self._sink = sink
        self._runs: dict[str, _RunAudit] = {}

    def _run(self, trace_id: str, when: float) -> _RunAudit:
        run = self._runs.get(trace_id)
        if run is None:
            run = _RunAudit(trace_id=trace_id, started_at=when)
            self._runs[trace_id] = run
        return run

    def handle(self, event: DomainEvent) -> None:
        run = self._run(event.trace_id, event.occurred_at)
        run.completed_at = max(run.completed_at, event.occurred_at)
        # Every event of a run carries the same tenant/mission; capture them once. Stamped on
        # the record at finalization, never inferred (ADR 0040 §6).
        if not run.tenant_id and event.tenant_id:
            run.tenant_id = event.tenant_id
        if not run.mission_id and event.mission_id:
            run.mission_id = event.mission_id
        if isinstance(event, RetrievalCompleted):
            run.source_ids = event.source_ids
            if event.warnings:
                run.warnings.append(f"retrieval: {event.warnings} warning(s)")
        elif isinstance(event, PromptBuilt):
            run.workflow = event.workflow
            run.intent = event.intent
            run.prompt_versions = dict(event.prompt_versions)
            if not event.valid:
                run.warnings.append("prompt: failed validation")
        elif isinstance(event, GenerationCompleted):
            run.provider = event.provider
            run.model = event.model
            run.usage = dict(event.usage)
            run.estimated_cost = event.estimated_cost
        elif isinstance(event, AnswerValidated):
            run.validation_status = event.status
            run.validation_passed = event.valid
        elif isinstance(event, PipelineCompleted):
            run.status = event.status
            self.finalize(event.trace_id)

    def finalize(self, trace_id: str) -> AuditRecord | None:
        """Freeze and emit the record for a trace, then drop its scratch state."""
        run = self._runs.pop(trace_id, None)
        if run is None:
            return None
        if not run.completed_at:
            run.completed_at = time.time()
        record = run.freeze()
        if self._sink is not None:
            self._sink.record(record)
        return record
