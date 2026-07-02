"""Application service for the Reporting capability."""

from __future__ import annotations

from ..shared.authorization import AuthorizationService
from ..shared.context import ExecutionContext
from ..shared.events import EventDispatcher
from ..shared.unit_of_work import UnitOfWork
from . import commands as c
from . import queries as q
from .dtos import ReportDTO
from .handlers import (
    AttachReportContentHandler,
    FinalizeReportHandler,
    GetReportHandler,
    ListReportsHandler,
    PublishReportHandler,
    RequestReportHandler,
)


class ReportingApplicationService:
    def __init__(
        self, uow: UnitOfWork, events: EventDispatcher, authz: AuthorizationService
    ) -> None:
        self._uow, self._events, self._authz = uow, events, authz

    async def request(self, command: c.RequestReport, ctx: ExecutionContext) -> ReportDTO:
        return await RequestReportHandler(self._uow, self._events, self._authz).handle(command, ctx)

    async def attach_content(
        self, command: c.AttachReportContent, ctx: ExecutionContext
    ) -> ReportDTO:
        return await AttachReportContentHandler(self._uow, self._events, self._authz).handle(
            command, ctx
        )

    async def finalize(self, command: c.FinalizeReport, ctx: ExecutionContext) -> ReportDTO:
        return await FinalizeReportHandler(self._uow, self._events, self._authz).handle(
            command, ctx
        )

    async def publish(self, command: c.PublishReport, ctx: ExecutionContext) -> ReportDTO:
        return await PublishReportHandler(self._uow, self._events, self._authz).handle(command, ctx)

    async def get(self, query: q.GetReport, ctx: ExecutionContext) -> ReportDTO:
        return await GetReportHandler(self._uow, self._authz).handle(query, ctx)

    async def list(self, query: q.ListReports, ctx: ExecutionContext) -> list[ReportDTO]:
        return await ListReportsHandler(self._uow, self._authz).handle(query, ctx)
