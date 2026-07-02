"""Validation interfaces (ports).

`Validator` validates a command/query before a handler runs. Concrete validators live in
infrastructure or are composed in wiring; the application only declares the contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class Validator(ABC, Generic[T]):
    @abstractmethod
    def validate(self, candidate: T) -> None:
        """Raise `ValidationError` if the candidate is invalid."""
        ...
