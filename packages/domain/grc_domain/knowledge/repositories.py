"""Repository interface for the Knowledge bounded context."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..shared.identifiers import KnowledgeSourceId, OrganizationId
from .entities import KnowledgeSource


class KnowledgeSourceRepository(ABC):
    @abstractmethod
    async def get(
        self,
        organization_id: OrganizationId,
        source_id: KnowledgeSourceId,
    ) -> KnowledgeSource | None: ...

    @abstractmethod
    async def list_for_organization(
        self,
        organization_id: OrganizationId,
    ) -> list[KnowledgeSource]: ...

    @abstractmethod
    async def add(self, source: KnowledgeSource) -> None: ...

    @abstractmethod
    async def save(self, source: KnowledgeSource) -> None: ...
