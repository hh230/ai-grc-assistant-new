"""Queries for the Mission capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.shared.identifiers import MissionId, WorkspaceId

from ..shared.messages import Query


@dataclass(frozen=True, kw_only=True)
class GetMission(Query):
    mission_id: MissionId


@dataclass(frozen=True, kw_only=True)
class ListMissionsForWorkspace(Query):
    workspace_id: WorkspaceId
