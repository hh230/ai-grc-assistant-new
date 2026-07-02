"""Commands for the Control capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.controls.enums import ControlImplementationStatus
from grc_domain.shared.identifiers import (
    ControlId,
    EvidenceId,
    FrameworkControlId,
    FrameworkId,
    WorkspaceId,
)

from ..shared.messages import Command


@dataclass(frozen=True, kw_only=True)
class CreateControl(Command):
    workspace_id: WorkspaceId
    title: str
    description: str | None = None


@dataclass(frozen=True, kw_only=True)
class MapControlToFramework(Command):
    control_id: ControlId
    framework_id: FrameworkId
    framework_control_id: FrameworkControlId


@dataclass(frozen=True, kw_only=True)
class LinkControlEvidence(Command):
    control_id: ControlId
    evidence_id: EvidenceId


@dataclass(frozen=True, kw_only=True)
class SetControlImplementationStatus(Command):
    control_id: ControlId
    status: ControlImplementationStatus
