"""`InMemoryMissionListReadModel` — the driver-free adapter (V1 Execution Slice S1).

It backs unit tests and local runs with no database, and defines the read model's semantics that
the Postgres adapter must match: tenant-scoped fail-closed reads, newest-first ordering, exact
filters on status and type, a case-insensitive substring search over the title, and 1-based
paging. It is a projection: `record` upserts by `mission_id`; a re-record (e.g. a status change)
replaces the row rather than adding one.
"""

from __future__ import annotations

from pipeline_contracts import TenantContext

from mission_read_model.models import MissionListItem, MissionPage
from mission_read_model.ports import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


class InMemoryMissionListReadModel:
    """A dict-backed projection keyed by `mission_id`. Reads filter strictly by the caller's
    tenant, so cross-tenant leakage is impossible regardless of what was recorded."""

    def __init__(self) -> None:
        self._by_id: dict[str, MissionListItem] = {}

    def record(self, item: MissionListItem) -> None:
        """Upsert by `mission_id`. Idempotent: recording the same id again overwrites the previous
        projection (the mission's latest snapshot wins)."""
        self._by_id[item.mission_id] = item

    def get(self, mission_id: str, tenant: TenantContext) -> MissionListItem | None:
        item = self._by_id.get(mission_id)
        # Fail-closed: a row owned by another tenant is not found.
        if item is None or item.tenant_id != tenant.tenant_id:
            return None
        return item

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
        page = max(page, 1)
        page_size = max(1, min(page_size, MAX_PAGE_SIZE))
        needle = query.strip().lower() if query else ""

        # Fail-closed: start from *this tenant's* rows only. No later step can widen the scope.
        rows = [item for item in self._by_id.values() if item.tenant_id == tenant.tenant_id]
        if status:
            rows = [item for item in rows if item.status == status]
        if mission_type:
            rows = [item for item in rows if item.mission_type == mission_type]
        if needle:
            rows = [item for item in rows if needle in item.title.lower()]

        # Newest first; ties broken deterministically so paging is stable across calls.
        rows.sort(
            key=lambda item: (item.updated_at, item.created_at, item.mission_id),
            reverse=True,
        )

        total = len(rows)
        start = (page - 1) * page_size
        window = rows[start : start + page_size]
        return MissionPage(
            items=tuple(window), page=page, page_size=page_size, total=total
        )
