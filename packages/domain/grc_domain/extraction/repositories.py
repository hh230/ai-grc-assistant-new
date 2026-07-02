"""Repository interface for the Knowledge Extraction bounded context.

Abstract only; concrete implementations live in the persistence layer. Every method is
tenant-scoped (default deny). ``find_by_idempotency_key`` is what makes run creation
idempotent: re-submitting identical inputs returns the existing run instead of duplicating.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..knowledge import KnowledgeScope
from ..shared.identifiers import ExtractionRunId, KnowledgeSourceVersionId
from .entities import ExtractionRun


class ExtractionRunRepository(ABC):
    @abstractmethod
    async def get(
        self, scope: KnowledgeScope, run_id: ExtractionRunId
    ) -> ExtractionRun | None: ...

    @abstractmethod
    async def list_for_version(
        self, scope: KnowledgeScope, version_id: KnowledgeSourceVersionId
    ) -> list[ExtractionRun]: ...

    @abstractmethod
    async def find_by_idempotency_key(
        self, scope: KnowledgeScope, idempotency_key: str
    ) -> ExtractionRun | None: ...

    @abstractmethod
    async def add(self, run: ExtractionRun) -> None: ...

    @abstractmethod
    async def save(self, run: ExtractionRun) -> None: ...
