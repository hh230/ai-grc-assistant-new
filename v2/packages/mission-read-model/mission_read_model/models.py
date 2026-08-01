"""The read-side data the Missions View needs — nothing more (V1 Execution Slice S1).

These are **read models**, not the Mission aggregate. The frozen Core `Mission` owns the goal,
the plan, the lifecycle, and the truth of status (ADR 0046 §6). This projection carries only what
a *list row* shows, including the two fields the Core deliberately does not persist:

- **`mission_type`** — the product's Mission Type id (Gap Assessment, Risk, …). It lives in the
  product's `MissionCatalog`, never on the aggregate (which stores a free-text `goal`). The read
  model is where that product concept becomes queryable.
- **`title`** — the human-readable scope/subject shown in the row (e.g. "Technological controls").

`status` is a **snapshot** of `MissionStatus.value` at the last time the product persisted the
mission. The Mission stays the source of truth; the list shows the snapshot, the detail view (S2)
reads the mission live. Representations never expose implementation (no tool names, no chunk ids).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MissionListItem:
    """One row in the Missions View — a tenant's mission as the list shows it."""

    mission_id: str
    tenant_id: str
    mission_type: str
    title: str
    status: str
    created_at: float
    updated_at: float


@dataclass(frozen=True)
class MissionPage:
    """A page of the tenant's missions plus the paging facts the UI needs to render controls.
    `total` is the count *after* filtering (so the UI can show "1–50 of N" and page correctly)."""

    items: tuple[MissionListItem, ...]
    page: int
    page_size: int
    total: int

    @property
    def has_next(self) -> bool:
        return self.page * self.page_size < self.total
