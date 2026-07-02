"""Value objects for the Tenancy/Identity bounded context."""
from __future__ import annotations

import re
from dataclasses import dataclass

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        if not _EMAIL_RE.match(self.value):
            raise ValueError(f"Invalid email address: {self.value!r}")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Region:
    """Data-residency region (e.g. 'sa', 'eu'). Lowercase ISO-like code."""

    code: str

    def __post_init__(self) -> None:
        if not self.code or not self.code.isascii() or self.code != self.code.lower():
            raise ValueError("Region code must be a lowercase ASCII string")
