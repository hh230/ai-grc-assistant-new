"""Generic outbound ports the application may depend on.

Concrete implementations (system clock, UUID generator) live in infrastructure.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime: ...


class IdGenerator(ABC):
    @abstractmethod
    def new_id(self) -> str: ...
