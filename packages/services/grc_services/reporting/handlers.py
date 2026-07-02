"""Use cases for the Reporting capability."""

from __future__ import annotations

from grc_domain.reporting.entities import Report
from grc_domain.shared.identifiers import ReportId

from ..shared.authorization import Action, ResourceType
from ..shared.context import ExecutionContext
from ..shared.exceptions import ResourceNotFoundError
from ..shared.handlers import QueryHandler, TransactionalCommandHandler
from ..shared.unit_of_work import UnitOfWork
from .commands import AttachReportContent, FinalizeReport, PublishReport, RequestReport
from .dtos import ReportDTO
from .queries import GetReport, ListReports


async def _load(uow: UnitOfWork, ctx: ExecutionContext, report_id: ReportId) -> Report:
    report = await uow.reports.get(ctx.organization_id, report_id)
    if report is None:
        raise ResourceNotFoundError(f"Report {report_id} not found")
    return report


class RequestReportHandler(TransactionalCommandHandler[RequestReport, ReportDTO]):
    async def _execute(self, command, context, uow):  # type: ignore[override]
        await self._authz.ensure_can(context, Action.CREATE, ResourceType.REPORT)
        report = Report.request(
            id=ReportId.generate(),
            organization_id=context.organization_id,
            report_type=command.report_type,
            title=command.title,
            source_mission_id=command.source_mission_id,
            source_assessment_id=command.source_assessment_id,
        )
        await uow.reports.add(report)
        return ReportDTO.from_domain(report)


class AttachReportContentHandler(TransactionalCommandHandler[AttachReportContent, ReportDTO]):
    async def _execute(self, command, context, uow):  # type: ignore[override]
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.REPORT, str(command.report_id)
        )
        report = await _load(uow, context, command.report_id)
        report.attach_content(command.sections)
        await uow.reports.save(report)
        return ReportDTO.from_domain(report)


class FinalizeReportHandler(TransactionalCommandHandler[FinalizeReport, ReportDTO]):
    async def _execute(self, command, context, uow):  # type: ignore[override]
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.REPORT, str(command.report_id)
        )
        report = await _load(uow, context, command.report_id)
        report.finalize()
        await uow.reports.save(report)
        return ReportDTO.from_domain(report)


class PublishReportHandler(TransactionalCommandHandler[PublishReport, ReportDTO]):
    async def _execute(self, command, context, uow):  # type: ignore[override]
        await self._authz.ensure_can(
            context, Action.PUBLISH, ResourceType.REPORT, str(command.report_id)
        )
        report = await _load(uow, context, command.report_id)
        report.publish()
        await uow.reports.save(report)
        return ReportDTO.from_domain(report)


class GetReportHandler(QueryHandler[GetReport, ReportDTO]):
    async def handle(self, query, context):  # type: ignore[override]
        await self._authz.ensure_can(
            context, Action.READ, ResourceType.REPORT, str(query.report_id)
        )
        async with self._uow as uow:
            report = await uow.reports.get(context.organization_id, query.report_id)
        if report is None:
            raise ResourceNotFoundError(f"Report {query.report_id} not found")
        return ReportDTO.from_domain(report)


class ListReportsHandler(QueryHandler[ListReports, list[ReportDTO]]):
    async def handle(self, query, context):  # type: ignore[override]
        await self._authz.ensure_can(context, Action.READ, ResourceType.REPORT)
        async with self._uow as uow:
            items = await uow.reports.list_for_organization(context.organization_id)
        return [ReportDTO.from_domain(r) for r in items]
