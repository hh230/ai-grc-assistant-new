"""Value objects for the Platform bounded context."""
from __future__ import annotations

from dataclasses import dataclass

from ..shared.value_objects import SemanticVersion


@dataclass(frozen=True)
class Permission:
    """A named permission a tool/agent/plugin requires (least privilege)."""

    name: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Permission name must not be empty")


@dataclass(frozen=True)
class SchemaRef:
    """A reference to a versioned I/O schema. The schema itself lives outside the domain."""

    name: str
    version: SemanticVersion


@dataclass(frozen=True)
class VersionRange:
    """An inclusive compatibility range for plugins."""

    minimum: SemanticVersion
    maximum: SemanticVersion | None = None

    def includes(self, version: SemanticVersion) -> bool:
        if version < self.minimum:
            return False
        return self.maximum is None or version <= self.maximum
