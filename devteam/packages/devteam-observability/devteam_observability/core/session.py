"""``AgentSession`` — one immutable record of one agent executing one step.

Where ``AgentRuntimeState`` is the agent's *current live state*, an ``AgentSession`` is *one
execution instance*: the span from an agent starting a step to finishing it, with everything that
happened in between. It is a frozen value — while a session is in flight the registry holds an
``ACTIVE`` one and replaces it functionally (``dataclasses.replace``) as facts arrive; the moment it
finishes it is sealed and appended to history, never mutated again ("completed sessions become
immutable history").

This is the foundation the owner asked for: a Live Pipeline view, deterministic replay from the
event journal, analytics over durations/verdicts, and dashboard timelines are all just queries over
these records.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from devteam_observability.core.ids import AgentId


class SessionStatus(str, Enum):
    """The lifecycle of one execution instance. Distinct from ``AgentStatus``: a session can be
    ``COMPLETED`` while the agent is ``BLOCKED`` (it finished and recommended a block)."""

    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class ArtifactRef:
    """A thin reference to an artifact an agent produced — kind/title/media-type only, never the
    content (events and sessions stay summaries, CLAUDE.md §16/§19). Full artifacts live on the
    mission record."""

    kind: str
    title: str
    media_type: str = "text/plain"

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "title": self.title, "media_type": self.media_type}


@dataclass(frozen=True)
class DecisionRecord:
    """One verdict an agent reached and why, when — the entry in a decision history and the decision
    attached to a session."""

    verdict: str
    rationale: str
    mission_id: str
    occurred_at: float
    confidence: float | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "verdict": self.verdict,
            "rationale": self.rationale,
            "mission_id": self.mission_id,
            "occurred_at": self.occurred_at,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class AgentSession:
    """One agent's execution of one step, as an immutable record. Built ``ACTIVE`` at
    ``AgentStarted``, enriched with the decision at ``AgentDecisionRecorded``, and sealed
    (``COMPLETED``/``FAILED``) at ``AgentCompleted`` — after which its execution facts are history.

    Sessions form a tree via ``parent_session_id`` (the session this one followed on the mission —
    the relay predecessor, set at open) and ``child_session_ids`` (its successors). A session's
    execution facts (duration, decision, output, errors, status) never change once sealed; only
    ``child_session_ids`` grows append-only — a child appears only after its parent sealed.
    This tree is the foundation for a Live Pipeline view and replay."""

    session_id: str
    agent_id: AgentId
    mission_id: str
    step_id: str
    started_at: float
    status: SessionStatus = SessionStatus.ACTIVE
    ended_at: float | None = None
    duration_ms: float | None = None
    decision: DecisionRecord | None = None
    artifacts: tuple[ArtifactRef, ...] = ()
    output_summary: str = ""
    errors: tuple[str, ...] = ()
    parent_session_id: str | None = None
    child_session_ids: tuple[str, ...] = ()

    @property
    def is_active(self) -> bool:
        return self.status is SessionStatus.ACTIVE

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "agent": self.agent_id.to_dict(),
            "mission_id": self.mission_id,
            "step_id": self.step_id,
            "status": self.status.value,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_ms": self.duration_ms,
            "decision": self.decision.to_dict() if self.decision is not None else None,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "output_summary": self.output_summary,
            "errors": list(self.errors),
            "parent_session_id": self.parent_session_id,
            "child_session_ids": list(self.child_session_ids),
        }
