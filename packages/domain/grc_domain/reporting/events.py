"""Domain events for the Reporting bounded context."""
from __future__ import annotations

from dataclasses import dataclass

from ..shared.events import DomainEvent
from ..shared.identifiers import OrganizationId, ReportId


@dataclass(frozen=True, kw_only=True)
class ReportRequested(DomainEvent):
    report_id: ReportId
    organization_id: OrganizationId


@dataclass(frozen=True, kw_only=True)
class ReportGenerated(DomainEvent):
    report_id: ReportId


@dataclass(frozen=True, kw_only=True)
class ReportFinalized(DomainEvent):
    report_id: ReportId


@dataclass(frozen=True, kw_only=True)
class ReportPublished(DomainEvent):
    report_id: ReportId
