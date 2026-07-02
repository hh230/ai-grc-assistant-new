"""The Mission aggregate: the fundamental, governed, auditable unit of work.

The aggregate enforces the Mission Lifecycle (CLAUDE.md §8) and the human-gate rule: a
consequential step cannot complete unless its approval gate has been granted.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..platform.enums import ToolSideEffect
from ..shared.entity import AggregateRoot, Entity
from ..shared.identifiers import (
    AgentId,
    ApprovalGateId,
    MissionId,
    MissionStepId,
    OrganizationId,
    ToolId,
    UserId,
    WorkspaceId,
)
from .enums import ApprovalDecision, MissionStatus, MissionStepStatus
from .events import (
    ApprovalGranted,
    ApprovalRejected,
    ApprovalRequested,
    MissionArchived,
    MissionCancelled,
    MissionCompleted,
    MissionCreated,
    MissionFailed,
    MissionPlanned,
    MissionStarted,
    MissionStepCompleted,
    MissionStepStarted,
)
from .exceptions import (
    ConsequentialStepNeedsApproval,
    IllegalMissionTransition,
    MissionStepNotFound,
)
from .value_objects import MissionGoal, ProposedAction

# Allowed lifecycle transitions (status -> set of reachable statuses).
_ALLOWED: dict[MissionStatus, frozenset[MissionStatus]] = {
    MissionStatus.CREATED: frozenset({MissionStatus.PLANNED, MissionStatus.CANCELLED}),
    MissionStatus.PLANNED: frozenset(
        {MissionStatus.EXECUTING, MissionStatus.CANCELLED}
    ),
    MissionStatus.EXECUTING: frozenset(
        {
            MissionStatus.AWAITING_APPROVAL,
            MissionStatus.COMPLETED,
            MissionStatus.FAILED,
            MissionStatus.CANCELLED,
        }
    ),
    MissionStatus.AWAITING_APPROVAL: frozenset(
        {MissionStatus.EXECUTING, MissionStatus.FAILED, MissionStatus.CANCELLED}
    ),
    MissionStatus.COMPLETED: frozenset({MissionStatus.ARCHIVED}),
    MissionStatus.FAILED: frozenset({MissionStatus.ARCHIVED}),
    MissionStatus.CANCELLED: frozenset({MissionStatus.ARCHIVED}),
    MissionStatus.ARCHIVED: frozenset(),
}


@dataclass(eq=False)
class ApprovalGate(Entity):
    """A human-in-the-loop gate guarding a consequential step."""

    id: ApprovalGateId
    step_id: MissionStepId
    proposed_action: ProposedAction
    decision: ApprovalDecision = ApprovalDecision.PENDING
    decided_by: UserId | None = None
    rejection_reason: str | None = None

    @property
    def is_granted(self) -> bool:
        return self.decision is ApprovalDecision.APPROVED


@dataclass(eq=False)
class MissionStep(Entity):
    """A single planned step, executed by an agent and/or a set of tools."""

    id: MissionStepId
    name: str
    side_effect: ToolSideEffect = ToolSideEffect.READ_ONLY
    agent_id: AgentId | None = None
    tool_ids: tuple[ToolId, ...] = field(default_factory=tuple)
    status: MissionStepStatus = MissionStepStatus.PENDING
    output_ref: str | None = None

    @property
    def is_consequential(self) -> bool:
        return self.side_effect is ToolSideEffect.CONSEQUENTIAL


@dataclass(kw_only=True, eq=False)
class Mission(AggregateRoot):
    id: MissionId
    organization_id: OrganizationId
    workspace_id: WorkspaceId
    goal: MissionGoal
    created_by: UserId
    owner_id: UserId
    status: MissionStatus = MissionStatus.CREATED
    steps: list[MissionStep] = field(default_factory=list)
    approval_gates: list[ApprovalGate] = field(default_factory=list)
    failure_reason: str | None = None

    # ---- construction ----
    @classmethod
    def create(
        cls,
        *,
        id: MissionId,
        organization_id: OrganizationId,
        workspace_id: WorkspaceId,
        goal: MissionGoal,
        created_by: UserId,
        owner_id: UserId | None = None,
    ) -> Mission:
        mission = cls(
            id=id,
            organization_id=organization_id,
            workspace_id=workspace_id,
            goal=goal,
            created_by=created_by,
            owner_id=owner_id or created_by,
        )
        mission._record_event(
            MissionCreated(
                mission_id=id,
                organization_id=organization_id,
                workspace_id=workspace_id,
                goal=goal.statement,
            )
        )
        return mission

    # ---- helpers ----
    def _transition(self, target: MissionStatus) -> None:
        if target not in _ALLOWED[self.status]:
            raise IllegalMissionTransition(
                f"Cannot move mission from {self.status.value} to {target.value}"
            )
        self.status = target

    def _step(self, step_id: MissionStepId) -> MissionStep:
        for step in self.steps:
            if step.id == step_id:
                return step
        raise MissionStepNotFound(str(step_id))

    def _gate_for_step(self, step_id: MissionStepId) -> ApprovalGate | None:
        for gate in self.approval_gates:
            if gate.step_id == step_id:
                return gate
        return None

    # ---- lifecycle ----
    def plan(self, steps: list[MissionStep]) -> None:
        if not steps:
            raise ValueError("A mission plan must contain at least one step")
        self._transition(MissionStatus.PLANNED)
        self.steps = list(steps)
        self._record_event(MissionPlanned(mission_id=self.id, step_count=len(steps)))

    def start(self) -> None:
        self._transition(MissionStatus.EXECUTING)
        self._record_event(MissionStarted(mission_id=self.id))

    def start_step(self, step_id: MissionStepId) -> None:
        if self.status is not MissionStatus.EXECUTING:
            raise IllegalMissionTransition("Steps run only while the mission is executing")
        step = self._step(step_id)
        step.status = MissionStepStatus.RUNNING
        step._touch()
        self._touch()
        self._record_event(MissionStepStarted(mission_id=self.id, step_id=step_id))

    def request_approval(
        self,
        *,
        step_id: MissionStepId,
        gate_id: ApprovalGateId,
        proposed_action: ProposedAction,
    ) -> None:
        """Pause the mission at a human gate before a consequential step proceeds."""
        step = self._step(step_id)
        gate = ApprovalGate(id=gate_id, step_id=step_id, proposed_action=proposed_action)
        self.approval_gates.append(gate)
        step.status = MissionStepStatus.AWAITING_APPROVAL
        self._transition(MissionStatus.AWAITING_APPROVAL)
        self._record_event(
            ApprovalRequested(mission_id=self.id, step_id=step_id, gate_id=gate_id)
        )

    def approve_gate(self, *, gate_id: ApprovalGateId, approver_id: UserId) -> None:
        gate = self._find_gate(gate_id)
        gate.decision = ApprovalDecision.APPROVED
        gate.decided_by = approver_id
        gate._touch()
        # Resume execution; the step may now complete.
        self._transition(MissionStatus.EXECUTING)
        self._record_event(
            ApprovalGranted(mission_id=self.id, gate_id=gate_id, decided_by=approver_id)
        )

    def reject_gate(self, *, gate_id: ApprovalGateId, approver_id: UserId, reason: str) -> None:
        if not reason.strip():
            raise ValueError("Rejection reason must not be empty")
        gate = self._find_gate(gate_id)
        gate.decision = ApprovalDecision.REJECTED
        gate.decided_by = approver_id
        gate.rejection_reason = reason
        gate._touch()
        step = self._step(gate.step_id)
        step.status = MissionStepStatus.FAILED
        self._record_event(
            ApprovalRejected(
                mission_id=self.id, gate_id=gate_id, decided_by=approver_id, reason=reason
            )
        )

    def complete_step(self, step_id: MissionStepId, *, output_ref: str | None = None) -> None:
        step = self._step(step_id)
        if step.is_consequential:
            gate = self._gate_for_step(step_id)
            if gate is None or not gate.is_granted:
                raise ConsequentialStepNeedsApproval(
                    "Consequential step requires a granted approval gate before completing"
                )
        step.status = MissionStepStatus.COMPLETED
        step.output_ref = output_ref
        step._touch()
        self._touch()
        self._record_event(MissionStepCompleted(mission_id=self.id, step_id=step_id))

    def complete(self) -> None:
        pending = [s for s in self.steps if s.status not in _FINAL_STEP_STATUSES]
        if pending:
            raise IllegalMissionTransition("All steps must be finalized before completion")
        self._transition(MissionStatus.COMPLETED)
        self._record_event(MissionCompleted(mission_id=self.id))

    def fail(self, *, reason: str) -> None:
        if self.status in (MissionStatus.COMPLETED, MissionStatus.ARCHIVED):
            raise IllegalMissionTransition("A finished mission cannot fail")
        self.failure_reason = reason
        self.status = MissionStatus.FAILED  # fail-safe from any active state
        self._record_event(MissionFailed(mission_id=self.id, reason=reason))

    def cancel(self) -> None:
        self._transition(MissionStatus.CANCELLED)
        self._record_event(MissionCancelled(mission_id=self.id))

    def archive(self) -> None:
        self._transition(MissionStatus.ARCHIVED)
        self._record_event(MissionArchived(mission_id=self.id))

    def _find_gate(self, gate_id: ApprovalGateId) -> ApprovalGate:
        for gate in self.approval_gates:
            if gate.id == gate_id:
                return gate
        raise MissionStepNotFound(str(gate_id))


_FINAL_STEP_STATUSES: frozenset[MissionStepStatus] = frozenset(
    {MissionStepStatus.COMPLETED, MissionStepStatus.SKIPPED, MissionStepStatus.FAILED}
)
