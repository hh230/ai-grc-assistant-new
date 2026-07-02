"""Domain services for the Frameworks bounded context.

Pure functions over framework data: no I/O, no AI, no persistence.
"""
from __future__ import annotations

from ..shared.identifiers import FrameworkControlId
from .entities import FrameworkMappingSet
from .value_objects import FrameworkControlRef


class CrossFrameworkMappingService:
    """Resolves corresponding controls across frameworks using a mapping set."""

    @staticmethod
    def corresponding_controls(
        mapping_set: FrameworkMappingSet,
        source_control_id: FrameworkControlId,
    ) -> tuple[FrameworkControlRef, ...]:
        """Return the target controls mapped from a given source control."""
        return tuple(
            corr.target
            for corr in mapping_set.correspondences
            if corr.source.framework_control_id == source_control_id
        )
