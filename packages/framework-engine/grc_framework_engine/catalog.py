"""The in-memory framework catalog: register, look up, map across, and compute coverage.

The catalog is the engine's queryable model over loaded framework *data*. It exposes the
operations the platform surfaces as Tools (``get_framework``, cross-framework mapping,
``compute_coverage``) and feeds the RAG framework library (CLAUDE.md §13, ADR-0007). Pure and
in-memory; no I/O. Versioning is first-class — assessments pin the version they ran against.
"""
from __future__ import annotations

from dataclasses import dataclass

from grc_domain.frameworks import (
    CrossFrameworkMappingService,
    Framework,
    FrameworkControlRef,
    FrameworkMappingSet,
)
from grc_domain.shared.identifiers import FrameworkControlId, FrameworkId, FrameworkMappingId

from .exceptions import UnknownFrameworkError, UnknownMappingSetError


@dataclass(frozen=True)
class CoverageReport:
    """Coverage of a framework given a set of satisfied controls: covered, gaps, and percentage."""

    framework_id: FrameworkId
    framework_version: str
    total_controls: int
    covered_controls: int
    gaps: tuple[FrameworkControlId, ...]

    @property
    def percentage(self) -> float:
        if self.total_controls == 0:
            return 0.0
        return round(self.covered_controls / self.total_controls * 100, 2)


class FrameworkCatalog:
    """Holds loaded frameworks and mapping sets, keyed for versioned lookup."""

    def __init__(self) -> None:
        self._frameworks: dict[tuple[str, str], Framework] = {}
        self._latest: dict[str, Framework] = {}
        self._mapping_sets: dict[str, FrameworkMappingSet] = {}

    # --- registration -----------------------------------------------------------------------
    def register_framework(self, framework: Framework) -> None:
        self._frameworks[(str(framework.id), framework.version.label)] = framework
        # The most recently registered version of an id is treated as its latest.
        self._latest[str(framework.id)] = framework

    def register_mapping_set(self, mapping_set: FrameworkMappingSet) -> None:
        self._mapping_sets[str(mapping_set.id)] = mapping_set

    # --- lookup -----------------------------------------------------------------------------
    def get_framework(self, framework_id: FrameworkId, version: str | None = None) -> Framework:
        if version is not None:
            framework = self._frameworks.get((str(framework_id), version))
            if framework is None:
                raise UnknownFrameworkError(f"No framework {framework_id} v{version}")
            return framework
        latest = self._latest.get(str(framework_id))
        if latest is None:
            raise UnknownFrameworkError(f"No framework registered with id {framework_id}")
        return latest

    def list_frameworks(self) -> tuple[Framework, ...]:
        return tuple(self._frameworks.values())

    def get_mapping_set(self, mapping_set_id: FrameworkMappingId) -> FrameworkMappingSet:
        mapping_set = self._mapping_sets.get(str(mapping_set_id))
        if mapping_set is None:
            raise UnknownMappingSetError(f"No mapping set {mapping_set_id}")
        return mapping_set

    # --- operations -------------------------------------------------------------------------
    def corresponding_controls(
        self, mapping_set_id: FrameworkMappingId, source_control_id: FrameworkControlId
    ) -> tuple[FrameworkControlRef, ...]:
        """Resolve the controls in the target framework mapped from a source control."""
        mapping_set = self.get_mapping_set(mapping_set_id)
        return CrossFrameworkMappingService.corresponding_controls(mapping_set, source_control_id)

    def compute_coverage(
        self,
        framework_id: FrameworkId,
        satisfied_control_ids: frozenset[FrameworkControlId],
        *,
        version: str | None = None,
    ) -> CoverageReport:
        """Coverage of a framework given the set of controls considered satisfied."""
        framework = self.get_framework(framework_id, version)
        gaps = tuple(
            control.id for control in framework.controls if control.id not in satisfied_control_ids
        )
        total = len(framework.controls)
        return CoverageReport(
            framework_id=framework.id,
            framework_version=framework.version.label,
            total_controls=total,
            covered_controls=total - len(gaps),
            gaps=gaps,
        )
