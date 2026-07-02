"""Command/Query bus interfaces (the dispatcher boundary).

Buses route a message to its handler and convert raised `ApplicationError`s into a
`Failure` result. Implementations (an in-memory mediator, etc.) live in infrastructure.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .context import ExecutionContext
from .messages import Command, Query
from .result import Result


class CommandBus(ABC):
    @abstractmethod
    async def dispatch(self, command: Command, context: ExecutionContext) -> Result: ...


class QueryBus(ABC):
    @abstractmethod
    async def ask(self, query: Query, context: ExecutionContext) -> Result: ...
