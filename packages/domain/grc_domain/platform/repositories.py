"""Repository interfaces for the Platform bounded context."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..shared.identifiers import AgentId, PluginId, ToolId
from .entities import AgentDescriptor, PluginDescriptor, ToolDescriptor


class ToolDescriptorRepository(ABC):
    @abstractmethod
    async def get(self, tool_id: ToolId) -> ToolDescriptor | None: ...

    @abstractmethod
    async def find_by_name(self, name: str) -> list[ToolDescriptor]: ...

    @abstractmethod
    async def list_active(self) -> list[ToolDescriptor]: ...

    @abstractmethod
    async def add(self, tool: ToolDescriptor) -> None: ...

    @abstractmethod
    async def save(self, tool: ToolDescriptor) -> None: ...


class AgentDescriptorRepository(ABC):
    @abstractmethod
    async def get(self, agent_id: AgentId) -> AgentDescriptor | None: ...

    @abstractmethod
    async def list_active(self) -> list[AgentDescriptor]: ...

    @abstractmethod
    async def add(self, agent: AgentDescriptor) -> None: ...

    @abstractmethod
    async def save(self, agent: AgentDescriptor) -> None: ...


class PluginDescriptorRepository(ABC):
    @abstractmethod
    async def get(self, plugin_id: PluginId) -> PluginDescriptor | None: ...

    @abstractmethod
    async def list_installed(self) -> list[PluginDescriptor]: ...

    @abstractmethod
    async def add(self, plugin: PluginDescriptor) -> None: ...

    @abstractmethod
    async def save(self, plugin: PluginDescriptor) -> None: ...
