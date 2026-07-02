"""Aggregate roots for the Frameworks bounded context."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..shared.entity import AggregateRoot
from ..shared.identifiers import (
    FrameworkControlId,
    FrameworkId,
    FrameworkMappingId,
)
from .enums import FrameworkStatus
from .events import FrameworkDeprecated, FrameworkImported, FrameworkPublished
from .exceptions import FrameworkControlNotFoundError
from .value_objects import ControlCorrespondence, FrameworkControl, FrameworkVersion


@dataclass(kw_only=True, eq=False)
class Framework(AggregateRoot):
    """A compliance framework definition. Identity is a stable id (e.g. 'framework:nca_ecc')."""

    id: FrameworkId
    name: str
    version: FrameworkVersion
    region: str | None = None
    languages: tuple[str, ...] = field(default_factory=tuple)
    status: FrameworkStatus = FrameworkStatus.DRAFT
    controls: tuple[FrameworkControl, ...] = field(default_factory=tuple)

    @classmethod
    def import_definition(
        cls,
        *,
        id: FrameworkId,
        name: str,
        version: FrameworkVersion,
        controls: tuple[FrameworkControl, ...],
        region: str | None = None,
        languages: tuple[str, ...] = (),
    ) -> Framework:
        framework = cls(
            id=id,
            name=name,
            version=version,
            region=region,
            languages=languages,
            controls=controls,
        )
        framework._record_event(FrameworkImported(framework_id=id, version=str(version)))
        return framework

    def control(self, control_id: FrameworkControlId) -> FrameworkControl:
        for ctrl in self.controls:
            if ctrl.id == control_id:
                return ctrl
        raise FrameworkControlNotFoundError(str(control_id))

    def publish(self) -> None:
        self.status = FrameworkStatus.PUBLISHED
        self._record_event(FrameworkPublished(framework_id=self.id, version=str(self.version)))

    def deprecate(self) -> None:
        self.status = FrameworkStatus.DEPRECATED
        self._record_event(FrameworkDeprecated(framework_id=self.id, version=str(self.version)))


@dataclass(kw_only=True, eq=False)
class FrameworkMappingSet(AggregateRoot):
    """A curated set of cross-framework control correspondences (data, CLAUDE.md §13)."""

    id: FrameworkMappingId
    source_framework_id: FrameworkId
    target_framework_id: FrameworkId
    correspondences: tuple[ControlCorrespondence, ...] = field(default_factory=tuple)
