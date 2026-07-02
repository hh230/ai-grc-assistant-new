"""Base message types for CQRS: Command and Query.

Commands express an intent to change state; Queries express an intent to read. Both are
immutable data carriers — they contain no behavior.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class Command:
    """Marker base for commands (state-changing intents)."""


@dataclass(frozen=True, kw_only=True)
class Query:
    """Marker base for queries (read-only intents)."""


@dataclass(frozen=True)
class DataTransferObject:
    """Marker base for DTOs returned across the application boundary (plain data)."""
