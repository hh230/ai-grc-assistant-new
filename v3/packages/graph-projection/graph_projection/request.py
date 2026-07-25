"""ProjectionRequest — *what* to project (ADR 0059). The projector resolves the request
against the Knowledge Graph, so no stage ever loads the whole graph unless asked to."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProjectSource:
    """Project one source's current subgraph."""

    source_id: str
    version: str


@dataclass(frozen=True, slots=True)
class ProjectDelta:
    """Project the subgraph contributed by one artifact, by its `content_hash` — a delta."""

    content_hash: str


@dataclass(frozen=True, slots=True)
class ProjectSnapshot:
    """Project the entire current graph (e.g. building a fresh environment)."""


ProjectionRequest = ProjectSource | ProjectDelta | ProjectSnapshot
