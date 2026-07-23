"""The read-model port — the single seam the API layer reads the Missions View through.

Two methods, both tenant-scoped:

- **`record`** projects a mission into the read model (upsert by `mission_id`). The product layer
  calls it whenever it persists a mission — at creation, and after each transition it drives — so
  the projection tracks the mission's status snapshot. It is idempotent: recording the same
  `mission_id` again updates the row, never duplicates it.
- **`list_missions`** answers the Missions View query for *one tenant only*. Tenant isolation is
  **fail-closed by construction** (ADR 0040 §5): the caller's `TenantContext` is the only tenant
  whose rows can be returned — there is no parameter that could widen the scope, so another
  tenant's missions cannot appear even by mistake.

CQRS read side: this port never mutates a mission. The frozen Core owns all writes; this is a
projection built beside it (Domain-Model §3 read-model gap).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pipeline_contracts import TenantContext

from mission_read_model.models import MissionListItem, MissionPage

# The default page size for the Missions View. Bounded so a tenant with thousands of missions
# never renders (or serializes) an unbounded list — the UI pages instead (Interaction Principle 10).
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


@runtime_checkable
class MissionListReadModel(Protocol):
    """The Missions-View read seam. An in-memory adapter backs tests and local runs; a Postgres
    adapter backs deployment — both implement exactly this, so the API layer never changes."""

    def record(self, item: MissionListItem) -> None:
        """Upsert one mission's projection (idempotent by `mission_id`)."""
        ...

    def get(self, mission_id: str, tenant: TenantContext) -> MissionListItem | None:
        """One mission's projection (its product type/scope + status snapshot), scoped to the
        caller's tenant — or `None` if absent or owned by another tenant (fail-closed)."""
        ...

    def list_missions(
        self,
        tenant: TenantContext,
        *,
        status: str | None = None,
        mission_type: str | None = None,
        query: str | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> MissionPage:
        """This tenant's missions, newest first, optionally filtered by status and/or type and/or
        a free-text query over the title. Paged (1-based). Never returns another tenant's rows."""
        ...
