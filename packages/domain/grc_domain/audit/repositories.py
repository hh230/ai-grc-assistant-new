"""Repository interface for the Audit bounded context.

The audit log is append-only: the interface intentionally exposes no update or delete.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from ..shared.identifiers import AuditRecordId, OrganizationId
from .entities import AuditRecord


class AuditRecordRepository(ABC):
    @abstractmethod
    async def append(self, record: AuditRecord) -> None: ...

    @abstractmethod
    async def get(
        self,
        organization_id: OrganizationId,
        record_id: AuditRecordId,
    ) -> AuditRecord | None: ...

    @abstractmethod
    async def query(
        self,
        organization_id: OrganizationId,
        *,
        object_type: str | None = None,
        object_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[AuditRecord]: ...
