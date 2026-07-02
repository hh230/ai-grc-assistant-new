"""Read DTOs for the Mission capability (plain, boundary-friendly data)."""

from __future__ import annotations

from dataclasses import dataclass, field

from grc_domain.missions.entities import ApprovalGate, Mission, MissionStep

from ..shared.messages import DataTransferObject


@dataclass(frozen=True)
class MissionStepDTO(DataTransferObject):
    id: str
    name: str
    status: str
    side_effect: str
    agent_id: str | None
    tool_ids: tuple[str, ...]
    output_ref: str | None

    @classmethod
    def from_domain(cls, step: MissionStep) -> MissionStepDTO:
        return cls(
            id=str(step.id),
            name=step.name,
            status=step.status.value,
            side_effect=step.side_effect.value,
            agent_id=str(step.agent_id) if step.agent_id else None,
            tool_ids=tuple(str(t) for t in step.tool_ids),
            output_ref=step.output_ref,
        )


@dataclass(frozen=True)
class ApprovalGateDTO(DataTransferObject):
    id: str
    step_id: str
    decision: str
    decided_by: str | None
    proposed_action: str

    @classmethod
    def from_domain(cls, gate: ApprovalGate) -> ApprovalGateDTO:
        return cls(
            id=str(gate.id),
            step_id=str(gate.step_id),
            decision=gate.decision.value,
            decided_by=str(gate.decided_by) if gate.decided_by else None,
            proposed_action=gate.proposed_action.description,
        )


@dataclass(frozen=True)
class MissionDTO(DataTransferObject):
    id: str
    organization_id: str
    workspace_id: str
    goal: str
    status: str
    owner_id: str
    created_by: str
    steps: tuple[MissionStepDTO, ...] = field(default_factory=tuple)
    approval_gates: tuple[ApprovalGateDTO, ...] = field(default_factory=tuple)

    @classmethod
    def from_domain(cls, mission: Mission) -> MissionDTO:
        return cls(
            id=str(mission.id),
            organization_id=str(mission.organization_id),
            workspace_id=str(mission.workspace_id),
            goal=mission.goal.statement,
            status=mission.status.value,
            owner_id=str(mission.owner_id),
            created_by=str(mission.created_by),
            steps=tuple(MissionStepDTO.from_domain(s) for s in mission.steps),
            approval_gates=tuple(ApprovalGateDTO.from_domain(g) for g in mission.approval_gates),
        )


@dataclass(frozen=True)
class MissionSummaryDTO(DataTransferObject):
    id: str
    goal: str
    status: str

    @classmethod
    def from_domain(cls, mission: Mission) -> MissionSummaryDTO:
        return cls(id=str(mission.id), goal=mission.goal.statement, status=mission.status.value)
