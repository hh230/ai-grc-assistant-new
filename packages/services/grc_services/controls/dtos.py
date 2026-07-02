"""DTOs for the Control capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.controls.entities import Control

from ..shared.messages import DataTransferObject


@dataclass(frozen=True)
class ControlDTO(DataTransferObject):
    id: str
    organization_id: str
    workspace_id: str
    title: str
    implementation_status: str
    has_evidence: bool
    framework_control_count: int

    @classmethod
    def from_domain(cls, c: Control) -> ControlDTO:
        return cls(
            id=str(c.id),
            organization_id=str(c.organization_id),
            workspace_id=str(c.workspace_id),
            title=c.title,
            implementation_status=c.implementation_status.value,
            has_evidence=c.has_evidence,
            framework_control_count=len(c.framework_controls),
        )
