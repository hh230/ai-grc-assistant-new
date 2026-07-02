"""DTOs for the Reporting capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.reporting.entities import Report

from ..shared.messages import DataTransferObject


@dataclass(frozen=True)
class ReportDTO(DataTransferObject):
    id: str
    organization_id: str
    report_type: str
    title: str
    status: str
    section_count: int

    @classmethod
    def from_domain(cls, r: Report) -> ReportDTO:
        return cls(
            id=str(r.id),
            organization_id=str(r.organization_id),
            report_type=r.report_type.value,
            title=r.title,
            status=r.status.value,
            section_count=len(r.sections),
        )
