"""Domain events for the Workspace bounded context."""
from __future__ import annotations

from dataclasses import dataclass

from ..shared.events import DomainEvent
from ..shared.identifiers import OrganizationId, UserId, WorkspaceId


@dataclass(frozen=True, kw_only=True)
class WorkspaceCreated(DomainEvent):
    workspace_id: WorkspaceId
    organization_id: OrganizationId
    name: str


@dataclass(frozen=True, kw_only=True)
class WorkspaceArchived(DomainEvent):
    workspace_id: WorkspaceId
    organization_id: OrganizationId


@dataclass(frozen=True, kw_only=True)
class WorkspaceMemberAdded(DomainEvent):
    workspace_id: WorkspaceId
    user_id: UserId


@dataclass(frozen=True, kw_only=True)
class WorkspaceMemberRemoved(DomainEvent):
    workspace_id: WorkspaceId
    user_id: UserId
