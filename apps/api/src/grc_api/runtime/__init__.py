"""Runtime adapters — the concrete implementations bound at the composition root.

These satisfy the Application layer's outbound ports (``UnitOfWork``, ``Clock``,
``IdGenerator``, ``EventDispatcher``, ``AuthorizationService``, ``CommandBus`` / ``QueryBus``)
so the API can drive real use cases. Nothing here contains business logic; it is wiring and
infrastructure. Swapping any adapter (e.g. the in-memory store for ``SqlAlchemyUnitOfWork``) is
a composition-root change that never touches a use case.
"""

from __future__ import annotations

from .authorization import RbacAuthorizationService
from .buses import InProcessCommandBus, InProcessQueryBus, UnregisteredMessageError
from .clock import SystemClock
from .events import LoggingEventDispatcher
from .ids import UuidGenerator
from .in_memory_uow import InMemoryDatabase, InMemoryUnitOfWork
from .registry import HandlerRegistry, build_registry

__all__ = [
    "RbacAuthorizationService",
    "InProcessCommandBus",
    "InProcessQueryBus",
    "UnregisteredMessageError",
    "SystemClock",
    "LoggingEventDispatcher",
    "UuidGenerator",
    "InMemoryDatabase",
    "InMemoryUnitOfWork",
    "HandlerRegistry",
    "build_registry",
]
