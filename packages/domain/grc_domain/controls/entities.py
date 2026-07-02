"""Aggregate root for the Controls bounded context.

A Control is the *customer's* implementation of one or more framework requirements,
backed by evidence. (Distinct from a FrameworkControl, which is reference data.)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..frameworks.value_objects import FrameworkControlRef
from ..shared.entity import AggregateRoot
from ..shared.identifiers import ControlId, EvidenceId, OrganizationId, UserId, WorkspaceId
from .enums import ControlImplementationStatus
from .events import (
    ControlCreated,
    ControlImplementationStatusChanged,
    ControlMappedToFramework,
    EvidenceLinkedToControl,
)


@dataclass(kw_only=True, eq=False)
class Control(AggregateRoot):
    id: ControlId
    organization_id: OrganizationId
    workspace_id: WorkspaceId
    title: str
    description: str | None = None
    owner_id: UserId | None = None
    implementation_status: ControlImplementationStatus = ControlImplementationStatus.NOT_IMPLEMENTED
    framework_controls: set[FrameworkControlRef] = field(default_factory=set)
    evidence_ids: set[EvidenceId] = field(default_factory=set)

    @classmethod
    def create(
        cls,
        *,
        id: ControlId,
        organization_id: OrganizationId,
        workspace_id: WorkspaceId,
        title: str,
        description: str | None = None,
        owner_id: UserId | None = None,
    ) -> Control:
        if not title.strip():
            raise ValueError("Control title must not be empty")
        control = cls(
            id=id,
            organization_id=organization_id,
            workspace_id=workspace_id,
            title=title,
            description=description,
            owner_id=owner_id,
        )
        control._record_event(
            ControlCreated(control_id=id, organization_id=organization_id, title=title)
        )
        return control

    def map_to_framework_control(self, ref: FrameworkControlRef) -> None:
        if ref not in self.framework_controls:
            self.framework_controls.add(ref)
            self._touch()
            self._record_event(ControlMappedToFramework(control_id=self.id, framework_control=ref))

    def link_evidence(self, evidence_id: EvidenceId) -> None:
        if evidence_id not in self.evidence_ids:
            self.evidence_ids.add(evidence_id)
            self._touch()
            self._record_event(
                EvidenceLinkedToControl(control_id=self.id, evidence_id=evidence_id)
            )

    def set_implementation_status(self, status: ControlImplementationStatus) -> None:
        if status is self.implementation_status:
            return
        self.implementation_status = status
        self._record_event(
            ControlImplementationStatusChanged(control_id=self.id, status=status)
        )

    @property
    def has_evidence(self) -> bool:
        return bool(self.evidence_ids)
