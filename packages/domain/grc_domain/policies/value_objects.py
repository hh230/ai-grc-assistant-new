"""Value objects for the Policies bounded context."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyVersion:
    number: int

    def __post_init__(self) -> None:
        if self.number < 1:
            raise ValueError("PolicyVersion number must be >= 1")

    def next(self) -> PolicyVersion:
        return PolicyVersion(self.number + 1)


@dataclass(frozen=True)
class PolicyBody:
    """The policy text. Authoring/AI generation happens elsewhere; this is just content."""

    text: str

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("PolicyBody text must not be empty")
