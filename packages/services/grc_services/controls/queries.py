"""Queries for the Control capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.shared.identifiers import ControlId, WorkspaceId

from ..shared.messages import Query


@dataclass(frozen=True, kw_only=True)
class GetControl(Query):
    control_id: ControlId


@dataclass(frozen=True, kw_only=True)
class ListControlsForWorkspace(Query):
    workspace_id: WorkspaceId
