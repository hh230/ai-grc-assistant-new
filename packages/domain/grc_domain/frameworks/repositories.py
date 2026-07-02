"""Repository interfaces for the Frameworks bounded context."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..shared.identifiers import FrameworkId, FrameworkMappingId
from .entities import Framework, FrameworkMappingSet
from .value_objects import FrameworkVersion


class FrameworkRepository(ABC):
    @abstractmethod
    async def get(
        self,
        framework_id: FrameworkId,
        version: FrameworkVersion,
    ) -> Framework | None: ...

    @abstractmethod
    async def list_published(self) -> list[Framework]: ...

    @abstractmethod
    async def add(self, framework: Framework) -> None: ...

    @abstractmethod
    async def save(self, framework: Framework) -> None: ...


class FrameworkMappingRepository(ABC):
    @abstractmethod
    async def get(self, mapping_id: FrameworkMappingId) -> FrameworkMappingSet | None: ...

    @abstractmethod
    async def find_between(
        self, source_framework_id: FrameworkId, target_framework_id: FrameworkId
    ) -> FrameworkMappingSet | None: ...

    @abstractmethod
    async def add(self, mapping_set: FrameworkMappingSet) -> None: ...
