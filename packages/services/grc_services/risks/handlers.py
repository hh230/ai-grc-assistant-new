"""Use cases for the Risk capability (acceptance is a human-gated, consequential action)."""

from __future__ import annotations

from grc_domain.risks.entities import Risk
from grc_domain.shared.identifiers import RiskId

from ..shared.authorization import Action, ResourceType
from ..shared.context import ExecutionContext
from ..shared.exceptions import ResourceNotFoundError
from ..shared.handlers import QueryHandler, TransactionalCommandHandler
from ..shared.unit_of_work import UnitOfWork
from .commands import AcceptRisk, AssessRisk, CloseRisk, IdentifyRisk, PlanRiskTreatment
from .dtos import RiskDTO
from .queries import GetRisk, ListRisks


async def _load(uow: UnitOfWork, ctx: ExecutionContext, risk_id: RiskId) -> Risk:
    risk = await uow.risks.get(ctx.organization_id, risk_id)
    if risk is None:
        raise ResourceNotFoundError(f"Risk {risk_id} not found")
    return risk


class IdentifyRiskHandler(TransactionalCommandHandler[IdentifyRisk, RiskDTO]):
    async def _execute(
        self, command: IdentifyRisk, context: ExecutionContext, uow: UnitOfWork
    ) -> RiskDTO:
        await self._authz.ensure_can(context, Action.CREATE, ResourceType.RISK)
        risk = Risk.identify(
            id=RiskId.generate(),
            organization_id=context.organization_id,
            title=command.title,
            description=command.description,
            category=command.category,
            owner_id=context.user_id,
        )
        await uow.risks.add(risk)
        return RiskDTO.from_domain(risk)


class AssessRiskHandler(TransactionalCommandHandler[AssessRisk, RiskDTO]):
    async def _execute(
        self, command: AssessRisk, context: ExecutionContext, uow: UnitOfWork
    ) -> RiskDTO:
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.RISK, str(command.risk_id)
        )
        risk = await _load(uow, context, command.risk_id)
        risk.assess(likelihood=command.likelihood, impact=command.impact)
        await uow.risks.save(risk)
        return RiskDTO.from_domain(risk)


class PlanRiskTreatmentHandler(TransactionalCommandHandler[PlanRiskTreatment, RiskDTO]):
    async def _execute(
        self, command: PlanRiskTreatment, context: ExecutionContext, uow: UnitOfWork
    ) -> RiskDTO:
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.RISK, str(command.risk_id)
        )
        risk = await _load(uow, context, command.risk_id)
        risk.plan_treatment(command.treatment)
        await uow.risks.save(risk)
        return RiskDTO.from_domain(risk)


class AcceptRiskHandler(TransactionalCommandHandler[AcceptRisk, RiskDTO]):
    async def _execute(
        self, command: AcceptRisk, context: ExecutionContext, uow: UnitOfWork
    ) -> RiskDTO:
        # Risk acceptance is consequential — requires APPROVE authority.
        await self._authz.ensure_can(
            context, Action.APPROVE, ResourceType.RISK, str(command.risk_id)
        )
        risk = await _load(uow, context, command.risk_id)
        risk.accept(approver_id=context.user_id, rationale=command.rationale)
        await uow.risks.save(risk)
        return RiskDTO.from_domain(risk)


class CloseRiskHandler(TransactionalCommandHandler[CloseRisk, RiskDTO]):
    async def _execute(
        self, command: CloseRisk, context: ExecutionContext, uow: UnitOfWork
    ) -> RiskDTO:
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.RISK, str(command.risk_id)
        )
        risk = await _load(uow, context, command.risk_id)
        risk.close()
        await uow.risks.save(risk)
        return RiskDTO.from_domain(risk)


class GetRiskHandler(QueryHandler[GetRisk, RiskDTO]):
    async def handle(
        self, query: GetRisk, context: ExecutionContext
    ) -> RiskDTO:
        await self._authz.ensure_can(context, Action.READ, ResourceType.RISK, str(query.risk_id))
        async with self._uow as uow:
            risk = await uow.risks.get(context.organization_id, query.risk_id)
        if risk is None:
            raise ResourceNotFoundError(f"Risk {query.risk_id} not found")
        return RiskDTO.from_domain(risk)


class ListRisksHandler(QueryHandler[ListRisks, list[RiskDTO]]):
    async def handle(
        self, query: ListRisks, context: ExecutionContext
    ) -> list[RiskDTO]:
        await self._authz.ensure_can(context, Action.READ, ResourceType.RISK)
        async with self._uow as uow:
            items = await uow.risks.list_for_organization(context.organization_id)
        return [RiskDTO.from_domain(r) for r in items]
