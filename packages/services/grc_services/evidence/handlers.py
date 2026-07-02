"""Use cases for the Evidence capability."""

from __future__ import annotations

from grc_domain.evidence.entities import Evidence
from grc_domain.shared.identifiers import EvidenceId

from ..shared.authorization import Action, ResourceType
from ..shared.context import ExecutionContext
from ..shared.exceptions import ResourceNotFoundError
from ..shared.handlers import QueryHandler, TransactionalCommandHandler
from ..shared.unit_of_work import UnitOfWork
from .commands import (
    CollectEvidence,
    LinkEvidenceToControl,
    RejectEvidence,
    ValidateEvidence,
)
from .dtos import EvidenceDTO
from .queries import GetEvidence, ListEvidenceForControl


async def _load(uow: UnitOfWork, ctx: ExecutionContext, evidence_id: EvidenceId) -> Evidence:
    e = await uow.evidence.get(ctx.organization_id, evidence_id)
    if e is None:
        raise ResourceNotFoundError(f"Evidence {evidence_id} not found")
    return e


class CollectEvidenceHandler(TransactionalCommandHandler[CollectEvidence, EvidenceDTO]):
    async def _execute(self, command, context, uow):  # type: ignore[override]
        await self._authz.ensure_can(context, Action.CREATE, ResourceType.EVIDENCE)
        evidence = Evidence.collect(
            id=EvidenceId.generate(),
            organization_id=context.organization_id,
            title=command.title,
            evidence_type=command.evidence_type,
            knowledge_source_id=command.knowledge_source_id,
        )
        await uow.evidence.add(evidence)
        return EvidenceDTO.from_domain(evidence)


class ValidateEvidenceHandler(TransactionalCommandHandler[ValidateEvidence, EvidenceDTO]):
    async def _execute(self, command, context, uow):  # type: ignore[override]
        await self._authz.ensure_can(
            context, Action.APPROVE, ResourceType.EVIDENCE, str(command.evidence_id)
        )
        evidence = await _load(uow, context, command.evidence_id)
        evidence.validate(validated_by=context.user_id)
        await uow.evidence.save(evidence)
        return EvidenceDTO.from_domain(evidence)


class RejectEvidenceHandler(TransactionalCommandHandler[RejectEvidence, EvidenceDTO]):
    async def _execute(self, command, context, uow):  # type: ignore[override]
        await self._authz.ensure_can(
            context, Action.APPROVE, ResourceType.EVIDENCE, str(command.evidence_id)
        )
        evidence = await _load(uow, context, command.evidence_id)
        evidence.reject(reason=command.reason)
        await uow.evidence.save(evidence)
        return EvidenceDTO.from_domain(evidence)


class LinkEvidenceToControlHandler(TransactionalCommandHandler[LinkEvidenceToControl, EvidenceDTO]):
    async def _execute(self, command, context, uow):  # type: ignore[override]
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.EVIDENCE, str(command.evidence_id)
        )
        evidence = await _load(uow, context, command.evidence_id)
        evidence.link_control(command.control_id)
        await uow.evidence.save(evidence)
        return EvidenceDTO.from_domain(evidence)


class GetEvidenceHandler(QueryHandler[GetEvidence, EvidenceDTO]):
    async def handle(self, query, context):  # type: ignore[override]
        await self._authz.ensure_can(
            context, Action.READ, ResourceType.EVIDENCE, str(query.evidence_id)
        )
        async with self._uow as uow:
            e = await uow.evidence.get(context.organization_id, query.evidence_id)
        if e is None:
            raise ResourceNotFoundError(f"Evidence {query.evidence_id} not found")
        return EvidenceDTO.from_domain(e)


class ListEvidenceForControlHandler(QueryHandler[ListEvidenceForControl, list[EvidenceDTO]]):
    async def handle(self, query, context):  # type: ignore[override]
        await self._authz.ensure_can(context, Action.READ, ResourceType.EVIDENCE)
        async with self._uow as uow:
            items = await uow.evidence.list_for_control(context.organization_id, query.control_id)
        return [EvidenceDTO.from_domain(e) for e in items]
