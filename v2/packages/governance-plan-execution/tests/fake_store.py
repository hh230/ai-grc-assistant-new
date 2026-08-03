"""An in-memory `PlanExecutionStorePort` test double — no database."""

from __future__ import annotations

from governance_discovery.plan import PlanItem
from governance_discovery.signal import SignalSet


class FakePlanExecutionStore:
    def __init__(self) -> None:
        self._items: dict[str, PlanItem] = {}
        self.events: list[dict] = []
        self._baselines: dict[str, tuple[SignalSet, tuple[str, ...]]] = {}

    def seed_item(self, item: PlanItem) -> None:
        self._items[item.id] = item

    def seed_baseline(self, tenant_id: str, signals: SignalSet, active_pack_ids: tuple[str, ...]) -> None:
        self._baselines[tenant_id] = (signals, active_pack_ids)

    def get_plan_item(self, item_id: str, tenant_id: str) -> PlanItem | None:
        item = self._items.get(item_id)
        return item if item is not None and item.tenant_id == tenant_id else None

    def record_item_transition(
        self,
        item: PlanItem,
        *,
        expected_updated_at: float,
        event_id: str,
        event_type: str,
        actor_id: str,
        created_at: float,
    ) -> bool:
        """Mirrors `PostgresGovernanceStore.record_item_transition`'s optimistic lock: refuses
        (returns `False`, writes nothing) if the item currently stored doesn't have exactly the
        `updated_at` the caller last read — proving `PlanExecutionService`'s conflict handling
        without a database."""
        current = self._items.get(item.id)
        if current is None or current.tenant_id != item.tenant_id:
            return False
        if current.updated_at != expected_updated_at:
            return False
        self._items[item.id] = item
        self.events.append(
            {
                "event_id": event_id,
                "plan_item_id": item.id,
                "tenant_id": item.tenant_id,
                "event_type": event_type,
                "actor_id": actor_id,
                "created_at": created_at,
            }
        )
        return True

    def list_completed_resolutions(self, tenant_id: str) -> list[tuple[str, object, float]]:
        return [
            (item.resolves_signal["signal"], item.resolves_signal["value"], item.completed_at)
            for item in self._items.values()
            if item.tenant_id == tenant_id
            and item.status == "done"
            and item.resolves_signal is not None
            and item.completed_at is not None
        ]

    def get_organization_baseline(self, tenant_id: str) -> tuple[SignalSet, tuple[str, ...]] | None:
        return self._baselines.get(tenant_id)
