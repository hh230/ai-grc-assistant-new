"""Application shared kernel: CQRS bases, ports, transaction boundary, and cross-cutting
abstractions used by every capability's use cases."""

from __future__ import annotations

from .authorization import Action, AuthorizationService, ResourceType
from .bus import CommandBus, QueryBus
from .context import ExecutionContext, Principal
from .events import EventDispatcher
from .exceptions import (
    ApplicationError,
    AuthorizationError,
    ConcurrencyError,
    ConflictError,
    ResourceNotFoundError,
    UnitOfWorkError,
    ValidationError,
)
from .handlers import (
    CommandHandler,
    QueryHandler,
    TransactionalCommandHandler,
)
from .messages import Command, DataTransferObject, Query
from .ports import Clock, IdGenerator
from .result import Failure, Result, Success, fail, ok
from .unit_of_work import UnitOfWork
from .validation import Validator

__all__ = [
    "Action",
    "AuthorizationService",
    "ResourceType",
    "CommandBus",
    "QueryBus",
    "ExecutionContext",
    "Principal",
    "EventDispatcher",
    "ApplicationError",
    "AuthorizationError",
    "ConcurrencyError",
    "ConflictError",
    "ResourceNotFoundError",
    "UnitOfWorkError",
    "ValidationError",
    "CommandHandler",
    "QueryHandler",
    "TransactionalCommandHandler",
    "Command",
    "Query",
    "DataTransferObject",
    "Clock",
    "IdGenerator",
    "Failure",
    "Result",
    "Success",
    "fail",
    "ok",
    "UnitOfWork",
    "Validator",
]
