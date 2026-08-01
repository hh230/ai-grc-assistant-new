"""Assistant-runtime errors — a small, purpose-built taxonomy so misconfiguration fails loud
(CLAUDE.md §22). These are *product-layer* errors; they never leak into the frozen Core.

    AssistantError                     — base
     ├── FallbackCapabilityMissing     — the deterministic selector's fallback is not registered
     └── UnknownMissionType            — a capability resolves to a Mission type the catalog lacks
"""

from __future__ import annotations


class AssistantError(Exception):
    """Base of every assistant-runtime error."""


class FallbackCapabilityMissing(AssistantError):
    """The Capability Selector had to fall back (no candidate matched) but the fallback capability
    id is not registered in the Capability Catalog. A registry-wiring bug, surfaced loudly rather
    than returning nothing (ADR 0046 §4)."""

    def __init__(self, fallback_id: str) -> None:
        self.fallback_id = fallback_id
        super().__init__(
            f"fallback capability {fallback_id!r} is not registered in the Capability Catalog"
        )


class UnknownMissionType(AssistantError):
    """A capability resolved to a Mission type id the Mission Catalog does not contain — a catalog
    wiring bug (the Capability Catalog and Mission Catalog disagree)."""

    def __init__(self, mission_type_id: str) -> None:
        self.mission_type_id = mission_type_id
        super().__init__(f"no Mission type {mission_type_id!r} registered in the Mission Catalog")
