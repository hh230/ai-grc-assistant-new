"""The runtime facts an observable agent system emits — the event model (CLAUDE.md §16, §19).

These are roster-neutral, immutable, past-tense facts (like the platform's ``DomainEvent``s, and
deliberately shaped after them). An adapter translates its own runtime into these; the registry
folds them into live state. Two families:

- **Agent-level** (new here — the frozen Core never names an agent): ``AgentAssigned`` (a step was
  routed to an agent — the dashboard's *MissionAssigned*), ``AgentStarted`` / ``AgentCompleted``
  (the invocation boundary that drives status + duration), ``AgentHandoffOccurred`` (one agent
  passed work to the next — *MissionTransferred*), ``AgentDecisionRecorded`` (a verdict, for the
  decision history).
- **Mission-level** ``MissionObserved`` — a thin re-statement of a mission lifecycle fact the Core
  ALREADY emits (created/started/completed/failed/awaiting-approval/approved/rejected). The adapter
  maps the Core's events onto this; it does not re-emit or duplicate them.

``AgentStatusChanged`` is different: it is *derived* — the registry emits it when a fold changes an
agent's status, so a downstream consumer (a live feed, the journal) sees transitions without
recomputing. It is never an input to the registry.

Timestamps default to wall-clock via ``now()``, which is injectable so tests are deterministic —
the same seam the Core's ``event_bus`` and ``MissionEngine`` use.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

from devteam_observability.core.ids import AgentId, AgentStatus
from devteam_observability.core.session import ArtifactRef


def now() -> float:
    """The single wall-clock source events default to, so it can be swapped in tests."""
    return time.time()


class AgentPhase(str, Enum):
    """The kind of work an ``AgentStarted`` span represents. The DevTeam adapter always uses
    ``WORKING`` (an agent's ``handle`` is one call); ``THINKING`` exists for a future system that
    streams a distinct reasoning phase before acting."""

    THINKING = "thinking"
    WORKING = "working"


class HandoffSource(str, Enum):
    """Where a handoff fact came from — its provenance, made explicit so a consumer can tell an
    agent's own declaration from an inference. ``DECLARED`` = the completing agent's
    ``AgentResult.handoff`` said so (the source of truth, preferred). ``OBSERVED`` = derived from
    the routing transition between two steps, the documented fallback for a runtime whose agents do
    not yet declare handoffs."""

    DECLARED = "declared"
    OBSERVED = "observed"


class MissionEventKind(str, Enum):
    """The mission lifecycle facts the Core emits (``mission_engine.events``), named for the
    dashboard. The adapter maps one Core event to one of these; the set is closed to the Core's
    vocabulary so nothing invents a lifecycle the engine does not have."""

    CREATED = "created"
    PLANNED = "planned"
    STEP_COMPLETED = "step_completed"
    AWAITING_APPROVAL = "awaiting_approval"
    RESUMED = "resumed"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class RuntimeEvent:
    """Base of every observability fact. ``mission_id`` / ``tenant_id`` mirror the Core's stamps so
    a runtime fact is always reachable through one mission and one tenant (ADR 0040/0042)."""

    mission_id: str = ""
    tenant_id: str = ""
    occurred_at: float = field(default_factory=now)

    def _payload(self) -> dict[str, object]:
        """Event-specific fields for ``to_dict``. Subclasses extend; base adds none."""
        return {}

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": type(self).__name__,
            "mission_id": self.mission_id,
            "tenant_id": self.tenant_id,
            "occurred_at": self.occurred_at,
            **self._payload(),
        }


@dataclass(frozen=True)
class AgentAssigned(RuntimeEvent):
    """A mission step was routed to an agent (the dashboard's *MissionAssigned*). Marks the agent a
    participant/owner of the mission and moves it to WAITING until it starts.

    RESERVED forward-compatible capability (owner decision): today's single DevTeam adapter starts a
    step directly (``AgentStarted``) and never emits this, so the WAITING-before-start state is
    unused now. It is kept for a future multi-agent runtime that assigns work ahead of execution
    (e.g. a planner fanning steps out); the registry already folds it, so that runtime needs no
    change here."""

    agent: AgentId | None = None
    step_id: str = ""

    def _payload(self) -> dict[str, object]:
        return {"agent": _agent_dict(self.agent), "step_id": self.step_id}


@dataclass(frozen=True)
class AgentStarted(RuntimeEvent):
    """An agent began executing a step (``handle`` invoked) — the start half of the invocation
    boundary. Drives status -> WORKING (or THINKING) and starts the duration clock."""

    agent: AgentId | None = None
    step_id: str = ""
    phase: AgentPhase = AgentPhase.WORKING

    def _payload(self) -> dict[str, object]:
        return {
            "agent": _agent_dict(self.agent),
            "step_id": self.step_id,
            "phase": self.phase.value,
        }


@dataclass(frozen=True)
class AgentCompleted(RuntimeEvent):
    """An agent finished a step (``handle`` returned) — the end half of the boundary. Carries the
    measured ``duration_ms`` and the machine ``verdict`` (if any; a BLOCK/ESCALATE moves the agent
    to BLOCKED, else IDLE), plus the work-product that seals the session: an ``output_summary``,
    lightweight ``artifacts`` refs, and any ``errors`` (a raised step or ``ok=False``, and the
    agent's warnings)."""

    agent: AgentId | None = None
    step_id: str = ""
    ok: bool = True
    duration_ms: float = 0.0
    verdict: str | None = None
    output_summary: str = ""
    artifacts: tuple[ArtifactRef, ...] = ()
    errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        object.__setattr__(self, "errors", tuple(self.errors))

    def _payload(self) -> dict[str, object]:
        return {
            "agent": _agent_dict(self.agent),
            "step_id": self.step_id,
            "ok": self.ok,
            "duration_ms": self.duration_ms,
            "verdict": self.verdict,
            "output_summary": self.output_summary,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class AgentHandoffOccurred(RuntimeEvent):
    """One agent passed work to the next (the dashboard's *MissionTransferred*). An explicit runtime
    fact — the source of truth for the mission's handoff chain — carrying its ``source`` provenance
    (``DECLARED`` by the agent, or ``OBSERVED`` from routing). The registry records it; it never
    infers a handoff of its own."""

    from_agent: AgentId | None = None
    to_agent: AgentId | None = None
    reason: str = ""
    source: HandoffSource = HandoffSource.OBSERVED

    def _payload(self) -> dict[str, object]:
        return {
            "from_agent": _agent_dict(self.from_agent),
            "to_agent": _agent_dict(self.to_agent),
            "reason": self.reason,
            "source": self.source.value,
        }


@dataclass(frozen=True)
class AgentDecisionRecorded(RuntimeEvent):
    """An agent reached a verdict on the work in hand (the Core's ``AgentDecision``). Appended to
    the agent's decision history — a recommendation, never an authorization (CLAUDE.md §9)."""

    agent: AgentId | None = None
    verdict: str = ""
    rationale: str = ""
    confidence: float | None = None

    def _payload(self) -> dict[str, object]:
        return {
            "agent": _agent_dict(self.agent),
            "verdict": self.verdict,
            "rationale": self.rationale,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class MissionObserved(RuntimeEvent):
    """A mission lifecycle fact the Core already emitted, restated for the runtime view. ``agent``
    is the step's agent when the Core event carries one (step-completed), else ``None`` (a
    mission-wide fact)."""

    kind: MissionEventKind = MissionEventKind.CREATED
    agent: AgentId | None = None
    step_id: str = ""
    detail: str = ""

    def _payload(self) -> dict[str, object]:
        return {
            "mission_kind": self.kind.value,
            "agent": _agent_dict(self.agent),
            "step_id": self.step_id,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class AgentStatusChanged(RuntimeEvent):
    """Derived: the registry emits this when a fold changes an agent's status, so a downstream
    consumer sees the transition directly. Never an input to the registry."""

    agent: AgentId | None = None
    previous: AgentStatus = AgentStatus.OFFLINE
    current: AgentStatus = AgentStatus.OFFLINE

    def _payload(self) -> dict[str, object]:
        return {
            "agent": _agent_dict(self.agent),
            "previous": self.previous.value,
            "current": self.current.value,
        }


def _agent_dict(agent: AgentId | None) -> dict[str, str] | None:
    return agent.to_dict() if agent is not None else None
