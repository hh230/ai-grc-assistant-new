"""Aggregate root for the Workspace bounded context.

A Workspace is the structured, object-centric environment in which missions, controls,
risks, policies, evidence, and reports are organized (Workspace-first UX).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..shared.entity import AggregateRoot
from ..shared.identifiers import OrganizationId, UserId, WorkspaceId
from .enums import WorkspaceStatus
from .events import (
    WorkspaceArchived,
    WorkspaceCreated,
    WorkspaceMemberAdded,
    WorkspaceMemberRemoved,
)
from .exceptions import WorkspaceArchivedError


@dataclass(kw_only=True, eq=False)
class Workspace(AggregateRoot):
    id: WorkspaceId
    organization_id: OrganizationId
    name: str
    owner_id: UserId
    description: str | None = None
    status: WorkspaceStatus = WorkspaceStatus.ACTIVE
    member_ids: set[UserId] = field(default_factory=set)

    @classmethod
    def create(
        cls,
        *,
        id: WorkspaceId,
        organization_id: OrganizationId,
        name: str,
        owner_id: UserId,
        description: str | None = None,
    ) -> Workspace:
        if not name.strip():
            raise ValueError("Workspace name must not be empty")
        ws = cls(
            id=id,
            organization_id=organization_id,
            name=name,
            owner_id=owner_id,
            description=description,
            member_ids={owner_id},
        )
        ws._record_event(
            WorkspaceCreated(workspace_id=id, organization_id=organization_id, name=name)
        )
        return ws

    def _guard_active(self) -> None:
        if self.status is WorkspaceStatus.ARCHIVED:
            raise WorkspaceArchivedError("Workspace is archived")

    def add_member(self, user_id: UserId) -> None:
        self._guard_active()
        if user_id not in self.member_ids:
            self.member_ids.add(user_id)
            self._touch()
            self._record_event(WorkspaceMemberAdded(workspace_id=self.id, user_id=user_id))

    def remove_member(self, user_id: UserId) -> None:
        self._guard_active()
        if user_id == self.owner_id:
            raise WorkspaceArchivedError("Cannot remove the workspace owner")
        if user_id in self.member_ids:
            self.member_ids.discard(user_id)
            self._touch()
            self._record_event(WorkspaceMemberRemoved(workspace_id=self.id, user_id=user_id))

    def archive(self) -> None:
        if self.status is WorkspaceStatus.ARCHIVED:
            return
        self.status = WorkspaceStatus.ARCHIVED
        self._record_event(
            WorkspaceArchived(workspace_id=self.id, organization_id=self.organization_id)
        )
