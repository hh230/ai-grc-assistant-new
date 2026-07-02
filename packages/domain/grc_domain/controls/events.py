"""Domain events for the Controls bounded context."""
from __future__ import annotations

from dataclasses import dataclass

from ..frameworks.value_objects import FrameworkControlRef
from ..shared.events import DomainEvent
from ..shared.identifiers import ControlId, EvidenceId, OrganizationId
from .enums import ControlImplementationStatus


@dataclass(frozen=True, kw_only=True)
class ControlCreated(DomainEvent):
    control_id: ControlId
    organization_id: OrganizationId
    title: str


@dataclass(frozen=True, kw_only=True)
class ControlMappedToFramework(DomainEvent):
    control_id: ControlId
    framework_control: FrameworkControlRef


@dataclass(frozen=True, kw_only=True)
class EvidenceLinkedToControl(DomainEvent):
    control_id: ControlId
    evidence_id: EvidenceId


@dataclass(frozen=True, kw_only=True)
class ControlImplementationStatusChanged(DomainEvent):
    control_id: ControlId
    status: ControlImplementationStatus
