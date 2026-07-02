"""Domain events for the Frameworks bounded context."""
from __future__ import annotations

from dataclasses import dataclass

from ..shared.events import DomainEvent
from ..shared.identifiers import FrameworkId


@dataclass(frozen=True, kw_only=True)
class FrameworkImported(DomainEvent):
    framework_id: FrameworkId
    version: str


@dataclass(frozen=True, kw_only=True)
class FrameworkPublished(DomainEvent):
    framework_id: FrameworkId
    version: str


@dataclass(frozen=True, kw_only=True)
class FrameworkDeprecated(DomainEvent):
    framework_id: FrameworkId
    version: str
