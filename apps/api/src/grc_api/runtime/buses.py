"""In-process Command/Query bus (the dispatcher boundary, CLAUDE.md §6).

These mediators implement the application's ``CommandBus`` / ``QueryBus`` ports. They are the
single place where a message is routed to its handler, a **fresh unit of work** is provisioned
per dispatch (one transaction per message), and a raised ``ApplicationError`` is converted into
a ``Failure`` result. Centralizing this keeps routers thin and gives one chokepoint for
cross-cutting concerns (error translation, and — at the HTTP edge — audit/observability).
"""

from __future__ import annotations

from collections.abc import Callable

from grc_services.shared.authorization import AuthorizationService
from grc_services.shared.bus import CommandBus, QueryBus
from grc_services.shared.context import ExecutionContext
from grc_services.shared.events import EventDispatcher
from grc_services.shared.exceptions import ApplicationError
from grc_services.shared.messages import Command, Query
from grc_services.shared.result import Failure, Result, fail, ok
from grc_services.shared.unit_of_work import UnitOfWork

from .registry import HandlerRegistry

UnitOfWorkFactory = Callable[[], UnitOfWork]


class UnregisteredMessageError(ApplicationError):
    """Raised when no handler is registered for a dispatched message type."""

    code = "unregistered_message"


class InProcessCommandBus(CommandBus):
    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactory,
        events: EventDispatcher,
        authz: AuthorizationService,
        registry: HandlerRegistry,
    ) -> None:
        self._uow_factory = uow_factory
        self._events = events
        self._authz = authz
        self._registry = registry

    async def dispatch(self, command: Command, context: ExecutionContext) -> Result[object]:
        handler_cls = self._registry.commands.get(type(command))
        if handler_cls is None:
            return Failure(
                UnregisteredMessageError(f"no handler for command {type(command).__name__}")
            )
        handler = handler_cls(self._uow_factory(), self._events, self._authz)
        try:
            return ok(await handler.handle(command, context))
        except ApplicationError as error:
            return fail(error)


class InProcessQueryBus(QueryBus):
    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactory,
        authz: AuthorizationService,
        registry: HandlerRegistry,
    ) -> None:
        self._uow_factory = uow_factory
        self._authz = authz
        self._registry = registry

    async def ask(self, query: Query, context: ExecutionContext) -> Result[object]:
        handler_cls = self._registry.queries.get(type(query))
        if handler_cls is None:
            return Failure(UnregisteredMessageError(f"no handler for query {type(query).__name__}"))
        handler = handler_cls(self._uow_factory(), self._authz)
        try:
            return ok(await handler.handle(query, context))
        except ApplicationError as error:
            return fail(error)
