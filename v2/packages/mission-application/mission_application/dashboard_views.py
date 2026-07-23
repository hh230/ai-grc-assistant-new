"""The **Dashboard** View Models (Slice S5) — the read side of "What needs my attention right now?".

Framework-agnostic dataclasses, the shape `GET /v1/dashboard` returns. The whole `DashboardView` is
a **computed-on-read** projection — assembled from existing read models, never stored — so these
carry only what the attention landing shows: the three attention counts, the recently-completed
list, and a **Coverage Snapshot** (a point-in-time picture from the latest completed Gap Assessments
— *not* a compliance score; Result ≠ Report, Dashboard ≠ Analytics). Nothing here exposes a tool, a
pipeline, or coverage math.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecentMissionView:
    """One recently-completed mission, as the Dashboard lists it (a link to its Work Surface)."""

    mission_id: str
    mission_type: str
    title: str
    completed_at: float


@dataclass(frozen=True)
class CoverageSnapshotView:
    """The Coverage **Snapshot** — a point-in-time picture rolled up from the tenant's completed Gap
    Assessments. `percent` is `covered / total` across them; `assessments` is how many fed it. A
    snapshot, never an attestation."""

    percent: float
    covered: int
    total: int
    assessments: int


@dataclass(frozen=True)
class DashboardView:
    """"System state now" for one tenant: the attention counts, recently completed, and the Coverage
    Snapshot (`None` until at least one Gap Assessment has completed). Attention-first — coverage is
    last, by design."""

    waiting: int
    running: int
    failed: int
    recent: tuple[RecentMissionView, ...]
    coverage: CoverageSnapshotView | None
