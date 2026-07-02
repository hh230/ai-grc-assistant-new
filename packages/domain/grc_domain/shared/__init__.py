"""Shared kernel: base building blocks reused by every bounded context."""
from __future__ import annotations

from .entity import AggregateRoot, Entity, utcnow
from .enums import ConfidenceLevel, DataClassification
from .events import DomainEvent
from .exceptions import (
    ApprovalRequired,
    DomainError,
    InvalidStateTransition,
    InvariantViolation,
    NotFoundError,
    TenantIsolationError,
)
from .identifiers import EntityId
from .value_object import ValueObject
from .value_objects import (
    Actor,
    ActorKind,
    Citation,
    Confidence,
    DateRange,
    SemanticVersion,
    TraceContext,
)

__all__ = [
    "AggregateRoot",
    "Entity",
    "utcnow",
    "DomainEvent",
    "ValueObject",
    "EntityId",
    "ConfidenceLevel",
    "DataClassification",
    "DomainError",
    "InvariantViolation",
    "InvalidStateTransition",
    "ApprovalRequired",
    "TenantIsolationError",
    "NotFoundError",
    "Actor",
    "ActorKind",
    "Citation",
    "Confidence",
    "DateRange",
    "SemanticVersion",
    "TraceContext",
]
