"""Base handler types and the transactional command-handler pattern.

- `CommandHandler` / `QueryHandler` are the abstract CQRS contracts.
- `TransactionalCommandHandler` implements the standard orchestration: open the unit of
  work, run the use case, commit, then dispatch the recorded domain events. Concrete
  command handlers only implement `_execute`, keeping use cases focused on business
  orchestration.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from .authorization import AuthorizationService
from .context import ExecutionContext
from .events import EventDispatcher
from .messages import Command, Query
from .unit_of_work import UnitOfWork

TCommand = TypeVar("TCommand", bound=Command)
TQuery = TypeVar("TQuery", bound=Query)
TResult = TypeVar("TResult")


class CommandHandler(ABC, Generic[TCommand, TResult]):
    @abstractmethod
    async def handle(self, command: TCommand, context: ExecutionContext) -> TResult: ...


class QueryHandler(ABC, Generic[TQuery, TResult]):
    def __init__(self, uow: UnitOfWork, authz: AuthorizationService) -> None:
        self._uow = uow
        self._authz = authz

    @abstractmethod
    async def handle(self, query: TQuery, context: ExecutionContext) -> TResult: ...


class TransactionalCommandHandler(CommandHandler[TCommand, TResult]):
    """Command handler that owns the transaction boundary and event dispatch."""

    def __init__(
        self,
        uow: UnitOfWork,
        events: EventDispatcher,
        authz: AuthorizationService,
    ) -> None:
        self._uow = uow
        self._events = events
        self._authz = authz

    async def handle(self, command: TCommand, context: ExecutionContext) -> TResult:
        async with self._uow as uow:
            result = await self._execute(command, context, uow)
            recorded = uow.collect_new_events()
            await uow.commit()
        await self._events.dispatch(recorded)
        return result

    @abstractmethod
    async def _execute(
        self, command: TCommand, context: ExecutionContext, uow: UnitOfWork
    ) -> TResult:
        """Run the use case against the open unit of work. No commit here."""
        ...
