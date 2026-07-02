"""DTOs for the Framework capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.frameworks.entities import Framework

from ..shared.messages import DataTransferObject


@dataclass(frozen=True)
class FrameworkDTO(DataTransferObject):
    id: str
    name: str
    version: str
    status: str
    region: str | None
    languages: tuple[str, ...]
    control_count: int

    @classmethod
    def from_domain(cls, f: Framework) -> FrameworkDTO:
        return cls(
            id=str(f.id),
            name=f.name,
            version=str(f.version),
            status=f.status.value,
            region=f.region,
            languages=tuple(f.languages),
            control_count=len(f.controls),
        )
