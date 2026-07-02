"""Queries for the Workspace capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.shared.identifiers import WorkspaceId

from ..shared.messages import Query


@dataclass(frozen=True, kw_only=True)
class GetWorkspace(Query):
    workspace_id: WorkspaceId


@dataclass(frozen=True, kw_only=True)
class ListWorkspaces(Query):
    pass
