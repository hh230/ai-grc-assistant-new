"""`MissionProjector` — the write side of the Missions-View read model (Execution Slice S1).

CQRS has two halves: `mission-read-model` reads the list; this projects into it. The projector is
the one place that reconciles the two facts S1 surfaced — the Core `Mission` carries `id`, `tenant`,
`status`, and timestamps, but **not** the product's Mission Type or scope. Those two the product
layer knows at creation (the chosen capability id and the scope input) and passes in here; every
other field is read straight off the mission.

Call `project` whenever the product persists a mission — at creation and after each transition — so
the list tracks the mission's latest **status snapshot**. Recording is an idempotent upsert by
mission id (a re-projection replaces the row), so re-projecting on every transition is safe.

It performs no I/O of its own and changes no Core: it maps a `Mission` to a `MissionListItem` and
hands it to the injected read model.

Architectural placement (ADR 0053): this is an **Application-layer projector**, called synchronously
by the product Application Service that owns the mission's create/drive transaction — not Core, not a
repository decorator, not (yet) a domain-event subscriber. The same pattern backs the Approvals,
Deliverables, and Dashboard read models.
"""

from __future__ import annotations

from mission_engine import Mission
from mission_read_model import MissionListItem, MissionListReadModel


class MissionProjector:
    """Projects a `Mission` (+ its product metadata) into the Missions-View read model."""

    def __init__(self, read_model: MissionListReadModel) -> None:
        self._read_model = read_model

    def project(self, mission: Mission, *, mission_type: str, scope: str) -> None:
        """Upsert the mission's list row. `mission_type` and `scope` come from the product layer
        (the Core does not persist them); `status` is the current snapshot."""
        self._read_model.record(
            MissionListItem(
                mission_id=mission.id,
                tenant_id=mission.tenant_id,
                mission_type=mission_type,
                title=scope,
                status=mission.status.value,
                created_at=mission.created_at,
                updated_at=mission.updated_at,
            )
        )
