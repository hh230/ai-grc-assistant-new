"""Application service for the Audit capability."""

from __future__ import annotations

from ..shared.authorization import AuthorizationService
from ..shared.context import ExecutionContext
from ..shared.events import EventDispatcher
from ..shared.unit_of_work import UnitOfWork
from . import commands as c
from . import queries as q
from .dtos import AuditRecordDTO
from .handlers import GetAuditRecordHandler, QueryAuditTrailHandler, RecordAuditEntryHandler


class AuditApplicationService:
    def __init__(
        self, uow: UnitOfWork, events: EventDispatcher, authz: AuthorizationService
    ) -> None:
        self._uow, self._events, self._authz = uow, events, authz

    async def record(self, command: c.RecordAuditEntry, ctx: ExecutionContext) -> AuditRecordDTO:
        return await RecordAuditEntryHandler(self._uow, self._events, self._authz).handle(
            command, ctx
        )

    async def get(self, query: q.GetAuditRecord, ctx: ExecutionContext) -> AuditRecordDTO:
        return await GetAuditRecordHandler(self._uow, self._authz).handle(query, ctx)

    async def query_trail(
        self, query: q.QueryAuditTrail, ctx: ExecutionContext
    ) -> list[AuditRecordDTO]:
        return await QueryAuditTrailHandler(self._uow, self._authz).handle(query, ctx)
