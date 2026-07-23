"""Mission Projection — the write side of the Missions-View CQRS (Execution Slice S1).

`MissionProjector` turns a Core `Mission` plus its product-only metadata (Mission Type + scope) into
a read-model row and records it. It is the seam where the product layer keeps the Missions View in
step with the mission's lifecycle, without the Core ever learning about the read model.
"""

from __future__ import annotations

from mission_projection.projector import MissionProjector

__all__ = ["MissionProjector"]
