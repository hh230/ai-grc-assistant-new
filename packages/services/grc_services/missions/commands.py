"""Commands for the Mission capability."""

from __future__ import annotations

from dataclasses import dataclass, field

from grc_domain.platform.enums import ToolSideEffect
from grc_domain.shared.identifiers import (
    AgentId,
    ApprovalGateId,
    MissionId,
    MissionStepId,
    ToolId,
    UserId,
    WorkspaceId,
)

from ..shared.messages import Command


@dataclass(frozen=True)
class MissionStepInput:
    """Input description of a planned step (translated into a domain MissionStep)."""

    name: str
    side_effect: ToolSideEffect = ToolSideEffect.READ_ONLY
    agent_id: AgentId | None = None
    tool_ids: tuple[ToolId, ...] = field(default_factory=tuple)


@dataclass(frozen=True, kw_only=True)
class CreateMission(Command):
    workspace_id: WorkspaceId
    goal: str
    owner_id: UserId | None = None


@dataclass(frozen=True, kw_only=True)
class PlanMission(Command):
    mission_id: MissionId
    steps: tuple[MissionStepInput, ...]


@dataclass(frozen=True, kw_only=True)
class StartMission(Command):
    mission_id: MissionId


@dataclass(frozen=True, kw_only=True)
class StartStep(Command):
    mission_id: MissionId
    step_id: MissionStepId


@dataclass(frozen=True, kw_only=True)
class RequestStepApproval(Command):
    mission_id: MissionId
    step_id: MissionStepId
    action_description: str


@dataclass(frozen=True, kw_only=True)
class ApproveGate(Command):
    mission_id: MissionId
    gate_id: ApprovalGateId


@dataclass(frozen=True, kw_only=True)
class RejectGate(Command):
    mission_id: MissionId
    gate_id: ApprovalGateId
    reason: str


@dataclass(frozen=True, kw_only=True)
class CompleteStep(Command):
    mission_id: MissionId
    step_id: MissionStepId
    output_ref: str | None = None


@dataclass(frozen=True, kw_only=True)
class CompleteMission(Command):
    mission_id: MissionId


@dataclass(frozen=True, kw_only=True)
class CancelMission(Command):
    mission_id: MissionId
