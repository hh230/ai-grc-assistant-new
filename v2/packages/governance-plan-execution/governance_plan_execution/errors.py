from __future__ import annotations


class PlanExecutionError(Exception):
    """Base for everything this package raises."""


class PlanItemNotFound(PlanExecutionError):
    def __init__(self, item_id: str) -> None:
        self.item_id = item_id
        super().__init__(f"plan item not found: {item_id}")


class PlanItemConflict(PlanExecutionError):
    """Raised when `record_item_transition`'s optimistic lock fails (Phase 3 hardening, ADR 0066
    §5.3): someone else changed this item between the caller's read and this write. Never silently
    retried here — the caller re-reads the item and decides whether to retry or surface it."""

    def __init__(self, item_id: str) -> None:
        self.item_id = item_id
        super().__init__(f"plan item was changed by someone else, retry: {item_id}")
