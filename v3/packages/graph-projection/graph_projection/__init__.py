"""Rasheed V3 — Graph Projection (ADR 0059). The boundary between the append-only Knowledge
Graph (System of Record) and any serving store.

`ProjectionRequest` (what to project) → `GraphProjector` (target-agnostic transform) →
immutable `ProjectionPackage` (operations, no SQL) → a `ProjectionTarget` realization
(`MemoryProjectionTarget` now; `SupabaseProjection`/`Neo4jProjection`/… later).
"""
from graph_projection.package import (
    OperationKind,
    ProjectionOperation,
    ProjectionPackage,
    edge_key,
)
from graph_projection.projector import GraphProjector
from graph_projection.request import (
    ProjectDelta,
    ProjectionRequest,
    ProjectSnapshot,
    ProjectSource,
)
from graph_projection.target import (
    MemoryProjectionTarget,
    ProjectionResult,
    ProjectionTarget,
)

__all__ = [
    "ProjectSource",
    "ProjectDelta",
    "ProjectSnapshot",
    "ProjectionRequest",
    "GraphProjector",
    "ProjectionPackage",
    "ProjectionOperation",
    "OperationKind",
    "edge_key",
    "ProjectionTarget",
    "ProjectionResult",
    "MemoryProjectionTarget",
]
