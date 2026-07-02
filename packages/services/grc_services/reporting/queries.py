"""Queries for the Reporting capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.shared.identifiers import ReportId

from ..shared.messages import Query


@dataclass(frozen=True, kw_only=True)
class GetReport(Query):
    report_id: ReportId


@dataclass(frozen=True, kw_only=True)
class ListReports(Query):
    pass
