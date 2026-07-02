"""Domain events for the Missions bounded context (the primary audit object)."""
from __future__ import annotations

from dataclasses import dataclass

from ..shared.events import DomainEvent
from ..shared.identifiers import (
    ApprovalGateId,
    MissionId,
    MissionStepId,
    OrganizationId,
    UserId,
    WorkspaceId,
)


@dataclass(frozen=True, kw_only=True)
class MissionCreated(DomainEvent):
    mission_id: MissionId
    organization_id: OrganizationId
    workspace_id: WorkspaceId
    goal: str


@dataclass(frozen=True, kw_only=True)
class MissionPlanned(DomainEvent):
    mission_id: MissionId
    step_count: int


@dataclass(frozen=True, kw_only=True)
class MissionStarted(DomainEvent):
    mission_id: MissionId


@dataclass(frozen=True, kw_only=True)
class MissionStepStarted(DomainEvent):
    mission_id: MissionId
    step_id: MissionStepId


@dataclass(frozen=True, kw_only=True)
class MissionStepCompleted(DomainEvent):
    mission_id: MissionId
    step_id: MissionStepId


@dataclass(frozen=True, kw_only=True)
class ApprovalRequested(DomainEvent):
    mission_id: MissionId
    step_id: MissionStepId
    gate_id: ApprovalGateId


@dataclass(frozen=True, kw_only=True)
class ApprovalGranted(DomainEvent):
    mission_id: MissionId
    gate_id: ApprovalGateId
    decided_by: UserId


@dataclass(frozen=True, kw_only=True)
class ApprovalRejected(DomainEvent):
    mission_id: MissionId
    gate_id: ApprovalGateId
    decided_by: UserId
    reason: str


@dataclass(frozen=True, kw_only=True)
class MissionCompleted(DomainEvent):
    mission_id: MissionId


@dataclass(frozen=True, kw_only=True)
class MissionFailed(DomainEvent):
    mission_id: MissionId
    reason: str


@dataclass(frozen=True, kw_only=True)
class MissionCancelled(DomainEvent):
    mission_id: MissionId


@dataclass(frozen=True, kw_only=True)
class MissionArchived(DomainEvent):
    mission_id: MissionId
