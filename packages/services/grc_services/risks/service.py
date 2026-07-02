"""Application service for the Risk capability."""

from __future__ import annotations

from ..shared.authorization import AuthorizationService
from ..shared.context import ExecutionContext
from ..shared.events import EventDispatcher
from ..shared.unit_of_work import UnitOfWork
from . import commands as c
from . import queries as q
from .dtos import RiskDTO
from .handlers import (
    AcceptRiskHandler,
    AssessRiskHandler,
    CloseRiskHandler,
    GetRiskHandler,
    IdentifyRiskHandler,
    ListRisksHandler,
    PlanRiskTreatmentHandler,
)


class RiskApplicationService:
    def __init__(
        self, uow: UnitOfWork, events: EventDispatcher, authz: AuthorizationService
    ) -> None:
        self._uow, self._events, self._authz = uow, events, authz

    async def identify(self, command: c.IdentifyRisk, ctx: ExecutionContext) -> RiskDTO:
        return await IdentifyRiskHandler(self._uow, self._events, self._authz).handle(command, ctx)

    async def assess(self, command: c.AssessRisk, ctx: ExecutionContext) -> RiskDTO:
        return await AssessRiskHandler(self._uow, self._events, self._authz).handle(command, ctx)

    async def plan_treatment(self, command: c.PlanRiskTreatment, ctx: ExecutionContext) -> RiskDTO:
        return await PlanRiskTreatmentHandler(self._uow, self._events, self._authz).handle(
            command, ctx
        )

    async def accept(self, command: c.AcceptRisk, ctx: ExecutionContext) -> RiskDTO:
        return await AcceptRiskHandler(self._uow, self._events, self._authz).handle(command, ctx)

    async def close(self, command: c.CloseRisk, ctx: ExecutionContext) -> RiskDTO:
        return await CloseRiskHandler(self._uow, self._events, self._authz).handle(command, ctx)

    async def get(self, query: q.GetRisk, ctx: ExecutionContext) -> RiskDTO:
        return await GetRiskHandler(self._uow, self._authz).handle(query, ctx)

    async def list(self, query: q.ListRisks, ctx: ExecutionContext) -> list[RiskDTO]:
        return await ListRisksHandler(self._uow, self._authz).handle(query, ctx)
