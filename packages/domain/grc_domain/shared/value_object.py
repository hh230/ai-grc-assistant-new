"""Marker base for value objects (shared kernel)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ValueObject:
    """Base for immutable, value-equality objects.

    Concrete value objects are frozen dataclasses with their own fields; this base
    exists to make intent explicit and to allow `isinstance` checks.
    """
