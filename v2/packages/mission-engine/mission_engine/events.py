"""Mission domain events — immutable, past-tense facts about lifecycle transitions
(ADR 0042 §8; CLAUDE.md §16).

Every mission event is **`mission_id`-stamped and `tenant_id`-stamped** (ADR 0042 §2.7,
§12.2) and threads the mission's `trace_id`, so the mission is the top of the existing trace
tree (§4) and every event is reachable through exactly one mission (Invariant #3). Events
subclass the platform's existing `DomainEvent` and publish onto the existing Event Bus
(ADR 0039) — the engine adds no new transport.

Events carry **summary** fields only (ids, status, counts, profile) — never the plan's full
instructions or a step's output text — keeping the bus a thin notification layer, exactly as
the pipeline events do. The full artifacts live on the mission record and the store.

The vocabulary below is fixed by ADR 0042 §12 so the audit sink, tracer, and workspace stream are
built once against a stable event set. The happy path publishes `MissionCreated → MissionPlanned →
MissionStepCompleted* → MissionCompleted`; `MissionFailed` / `MissionCancelled` close a run
fail-safe; `MissionAwaitingApproval` / `MissionResumed` mark the human gate's pause and resume.
**ADR 0044 (Human Approval) extends this vocabulary** with `MissionApproved` / `MissionRejected`
— the gate's decision facts (Slice 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from event_bus.events import DomainEvent


@dataclass(frozen=True)
class MissionEvent(DomainEvent):
    """Base for mission lifecycle events: adds the mission and tenant stamps every mission
    fact carries. Fields default (as the pipeline events do) so subclasses may add their own
    without fighting dataclass default-ordering; the engine always supplies real values."""

    name: ClassVar[str] = "mission.event"

    mission_id: str = ""
    tenant_id: str = ""

    def _payload(self) -> dict[str, object]:
        return {
            "mission_id": self.mission_id,
            "tenant_id": self.tenant_id,
            **self._mission_payload(),
        }

    def _mission_payload(self) -> dict[str, object]:
        """Event-specific fields beyond the mission/tenant stamp. Subclasses extend."""
        return {}


@dataclass(frozen=True)
class MissionCreated(MissionEvent):
    name: ClassVar[str] = "mission.created"

    goal: str = ""

    def _mission_payload(self) -> dict[str, object]:
        return {"goal": self.goal}


@dataclass(frozen=True)
class MissionPlanned(MissionEvent):
    name: ClassVar[str] = "mission.planned"

    execution_profile: str = ""
    step_count: int = 0
    plan_version: int = 0

    def _mission_payload(self) -> dict[str, object]:
        return {
            "execution_profile": self.execution_profile,
            "step_count": self.step_count,
            "plan_version": self.plan_version,
        }


@dataclass(frozen=True)
class MissionStepCompleted(MissionEvent):
    name: ClassVar[str] = "mission.step_completed"

    step_id: str = ""
    ok: bool = True
    # Ids only — never the step's output text — so the event stays a summary while an auditor
    # can still answer "which sources grounded this step?" (CLAUDE.md §19).
    source_ids: tuple[str, ...] = ()

    def _mission_payload(self) -> dict[str, object]:
        return {"step_id": self.step_id, "ok": self.ok, "source_ids": list(self.source_ids)}


@dataclass(frozen=True)
class MissionAwaitingApproval(MissionEvent):
    """Published when a consequential step pauses the mission BEFORE its side effect
    (ADR 0042 §2.5, §12.5). The resolution surface is Human Approval, a later phase; this
    engine owns only the pause."""

    name: ClassVar[str] = "mission.awaiting_approval"

    step_id: str = ""

    def _mission_payload(self) -> dict[str, object]:
        return {"step_id": self.step_id}


@dataclass(frozen=True)
class MissionResumed(MissionEvent):
    name: ClassVar[str] = "mission.resumed"

    plan_version: int = 0

    def _mission_payload(self) -> dict[str, object]:
        return {"plan_version": self.plan_version}


@dataclass(frozen=True)
class MissionApproved(MissionEvent):
    """A human approved the mission's pending gate (ADR 0044 §Q4, Slice 2). Past-tense fact carrying
    the resolved `ApprovalRequest`'s id and the approver's principal id (the "when" is
    `occurred_at`). Emission is the engine's job in a later slice; the event type and its outbox
    registration land in Slice 2 so the audit vocabulary is complete."""

    name: ClassVar[str] = "mission.approved"

    approval_id: str = ""
    approver: str = ""

    def _mission_payload(self) -> dict[str, object]:
        return {"approval_id": self.approval_id, "approver": self.approver}


@dataclass(frozen=True)
class MissionRejected(MissionEvent):
    """A human rejected the mission's pending gate; the mission stops fail-safe as `CANCELLED`
    (ADR 0044 §Q5, Slice 2). Carries the request id, the approver, and the rejection `comment` — the
    who/why an auditor needs (CLAUDE.md §19)."""

    name: ClassVar[str] = "mission.rejected"

    approval_id: str = ""
    approver: str = ""
    comment: str = ""

    def _mission_payload(self) -> dict[str, object]:
        return {
            "approval_id": self.approval_id,
            "approver": self.approver,
            "comment": self.comment,
        }


@dataclass(frozen=True)
class MissionCompleted(MissionEvent):
    name: ClassVar[str] = "mission.completed"

    step_count: int = 0

    def _mission_payload(self) -> dict[str, object]:
        return {"step_count": self.step_count}


@dataclass(frozen=True)
class MissionFailed(MissionEvent):
    """A run reached an unrecoverable error and stopped fail-safe (ADR 0042 §7)."""

    name: ClassVar[str] = "mission.failed"

    reason: str = ""

    def _mission_payload(self) -> dict[str, object]:
        return {"reason": self.reason}


@dataclass(frozen=True)
class MissionCancelled(MissionEvent):
    """A run was cancelled by a human and stopped fail-safe (ADR 0042 §7)."""

    name: ClassVar[str] = "mission.cancelled"

    reason: str = ""

    def _mission_payload(self) -> dict[str, object]:
        return {"reason": self.reason}
