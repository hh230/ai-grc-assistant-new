"""Commands for the Workspace capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.shared.identifiers import UserId, WorkspaceId

from ..shared.messages import Command


@dataclass(frozen=True, kw_only=True)
class CreateWorkspace(Command):
    name: str
    description: str | None = None
    owner_id: UserId | None = None


@dataclass(frozen=True, kw_only=True)
class AddWorkspaceMember(Command):
    workspace_id: WorkspaceId
    user_id: UserId


@dataclass(frozen=True, kw_only=True)
class RemoveWorkspaceMember(Command):
    workspace_id: WorkspaceId
    user_id: UserId


@dataclass(frozen=True, kw_only=True)
class ArchiveWorkspace(Command):
    workspace_id: WorkspaceId
