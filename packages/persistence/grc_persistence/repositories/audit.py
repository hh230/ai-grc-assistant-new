"""Repository for the Audit context — append-only, tenant-scoped.

The audit log has no update or delete path (CLAUDE.md §19). Records are not aggregate roots
and record no events, so this repository deliberately does not use the aggregate base; it
just appends rows and runs tenant-scoped queries.
"""

from __future__ import annotations

from datetime import datetime

from grc_domain.audit.entities import AuditRecord
from grc_domain.audit.repositories import AuditRecordRepository
from grc_domain.shared.identifiers import AuditRecordId, OrganizationId
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..contracts.cache import RepositoryCache
from ..contracts.tracking import AggregateTracker
from ..mappers.audit import audit_record_mapper
from ..models.audit import AuditRecordModel


class SqlAlchemyAuditRecordRepository(AuditRecordRepository):
    def __init__(
        self, session: AsyncSession, tracker: AggregateTracker, cache: RepositoryCache
    ) -> None:
        # ``tracker`` / ``cache`` are accepted for uniform construction by the Unit of Work;
        # audit records record no events and are never cached.
        self._session = session
        self._mapper = audit_record_mapper

    async def append(self, record: AuditRecord) -> None:
        self._session.add(self._mapper.to_orm(record))

    async def get(
        self, organization_id: OrganizationId, record_id: AuditRecordId
    ) -> AuditRecord | None:
        stmt = select(AuditRecordModel).where(
            AuditRecordModel.id == str(record_id),
            AuditRecordModel.organization_id == str(organization_id),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._mapper.to_domain(model) if model is not None else None

    async def query(
        self,
        organization_id: OrganizationId,
        *,
        object_type: str | None = None,
        object_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[AuditRecord]:
        conditions = [AuditRecordModel.organization_id == str(organization_id)]
        if object_type is not None:
            conditions.append(AuditRecordModel.object_type == object_type)
        if object_id is not None:
            conditions.append(AuditRecordModel.object_id == object_id)
        if since is not None:
            conditions.append(AuditRecordModel.occurred_at >= since)
        if until is not None:
            conditions.append(AuditRecordModel.occurred_at <= until)
        stmt = select(AuditRecordModel).where(*conditions).order_by(AuditRecordModel.occurred_at)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._mapper.to_domain(model) for model in rows]
