"""Use cases for the Audit capability (append-only trail)."""

from __future__ import annotations

from grc_domain.audit.entities import AuditRecord
from grc_domain.shared.identifiers import AuditRecordId
from grc_domain.shared.value_objects import Actor, ActorKind, TraceContext

from ..shared.authorization import Action, ResourceType
from ..shared.context import ExecutionContext
from ..shared.exceptions import ResourceNotFoundError
from ..shared.handlers import QueryHandler, TransactionalCommandHandler
from ..shared.unit_of_work import UnitOfWork
from .commands import RecordAuditEntry
from .dtos import AuditRecordDTO
from .queries import GetAuditRecord, QueryAuditTrail


class RecordAuditEntryHandler(TransactionalCommandHandler[RecordAuditEntry, AuditRecordDTO]):
    async def _execute(
        self, command: RecordAuditEntry, context: ExecutionContext, uow: UnitOfWork
    ) -> AuditRecordDTO:
        # Recording an audit entry is itself an audited, authorized action.
        await self._authz.ensure_can(context, Action.CREATE, ResourceType.AUDIT)
        trace: TraceContext | None = context.trace
        record = AuditRecord.record(
            id=AuditRecordId.generate(),
            organization_id=context.organization_id,
            actor=Actor(kind=ActorKind.USER, reference=str(context.user_id)),
            category=command.category,
            action=command.action,
            object_type=command.object_type,
            object_id=command.object_id,
            trace=trace,
            payload_hash=command.payload_hash,
            outcome=command.outcome,
        )
        await uow.audit.append(record)
        return AuditRecordDTO.from_domain(record)


class GetAuditRecordHandler(QueryHandler[GetAuditRecord, AuditRecordDTO]):
    async def handle(
        self, query: GetAuditRecord, context: ExecutionContext
    ) -> AuditRecordDTO:
        await self._authz.ensure_can(context, Action.READ, ResourceType.AUDIT, str(query.record_id))
        async with self._uow as uow:
            record = await uow.audit.get(context.organization_id, query.record_id)
        if record is None:
            raise ResourceNotFoundError(f"AuditRecord {query.record_id} not found")
        return AuditRecordDTO.from_domain(record)


class QueryAuditTrailHandler(QueryHandler[QueryAuditTrail, list[AuditRecordDTO]]):
    async def handle(
        self, query: QueryAuditTrail, context: ExecutionContext
    ) -> list[AuditRecordDTO]:
        await self._authz.ensure_can(context, Action.READ, ResourceType.AUDIT)
        async with self._uow as uow:
            records = await uow.audit.query(
                context.organization_id,
                object_type=query.object_type,
                object_id=query.object_id,
                since=query.since,
                until=query.until,
            )
        return [AuditRecordDTO.from_domain(r) for r in records]
