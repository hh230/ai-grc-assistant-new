"""`PlanExecutionService` — the living lifecycle of an approved Governance Plan (ADR 0066 §5).

Deliberately NOT a Mission: execution can run for a year, and a Mission cannot (§5.1). Mirrors
`governance-session`'s role relative to Discovery exactly — a thin orchestration layer composing
the pure `governance-discovery` engine with `governance-store` persistence, outside the Mission
Engine. Owns sequencing and boundary translation only; every actual number (current maturity) is
computed by pure functions this service merely calls with fresh data.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from governance_discovery.analysis import rate_maturity_scores, score_maturity
from governance_discovery.engine import DiscoveryEngine
from governance_discovery.execution import effective_signals
from governance_discovery.plan import PlanItem
from governance_discovery.signal import SignalSet

from governance_plan_execution.errors import PlanItemConflict, PlanItemNotFound


class PlanExecutionStorePort(Protocol):
    """The subset of `PostgresGovernanceStore`'s surface this service depends on — a Protocol so
    tests can supply a lightweight in-memory fake without a database."""

    def get_plan_item(self, item_id: str, tenant_id: str) -> PlanItem | None: ...
    def record_item_transition(
        self,
        item: PlanItem,
        *,
        expected_updated_at: float,
        event_id: str,
        event_type: str,
        actor_id: str,
        created_at: float,
    ) -> bool: ...
    def list_completed_resolutions(self, tenant_id: str) -> list[tuple[str, object, float]]: ...
    def get_organization_baseline(
        self, tenant_id: str
    ) -> tuple[SignalSet, tuple[str, ...]] | None: ...


@dataclass(frozen=True)
class CurrentMaturity:
    """`None` baseline means no discovery session has ever concluded for this tenant — there is
    nothing to recalculate against yet (distinct from a tenant whose maturity is genuinely all
    zeros)."""

    maturity: dict[str, dict] | None
    active_pack_ids: tuple[str, ...]


class PlanExecutionService:
    def __init__(
        self,
        engine: DiscoveryEngine,
        store: PlanExecutionStorePort,
        *,
        new_id: Callable[[], str],
        now: Callable[[], float],
    ) -> None:
        self._engine = engine
        self._store = store
        self._new_id = new_id
        self._now = now

    def _require_item(self, item_id: str, tenant_id: str) -> PlanItem:
        item = self._store.get_plan_item(item_id, tenant_id)
        if item is None:
            raise PlanItemNotFound(item_id)
        return item

    def _transition(
        self, item: PlanItem, updated: PlanItem, event_type: str, actor_id: str
    ) -> PlanItem:
        """Applies one state change through the atomic, optimistically-locked store call (Phase 3
        hardening, ADR 0066 §5.3): `item.updated_at` (the version this call read) is the lock's
        expected value, so a concurrent writer who changed the item first makes this call lose,
        cleanly, as `PlanItemConflict` — never a silent lost update. The caller re-reads and
        decides whether to retry."""
        applied = self._store.record_item_transition(
            updated,
            expected_updated_at=item.updated_at,
            event_id=self._new_id(),
            event_type=event_type,
            actor_id=actor_id,
            created_at=self._now(),
        )
        if not applied:
            raise PlanItemConflict(item.id)
        return updated

    # --- status transitions ------------------------------------------------------------------

    def start(self, item_id: str, tenant_id: str, actor_id: str) -> PlanItem:
        """Not started -> in progress (Phase 4): a practitioner has picked this item up.
        Idempotent from `not_started` only — an already `in_progress` or `done` item is a no-op,
        never a conflict; `mark_done` still works directly from `not_started` too (jumping
        straight to done without an explicit "start" is a real, allowed workflow, not an error)."""
        item = self._require_item(item_id, tenant_id)
        if item.status != "not_started":
            return item
        return self._transition(item, item.marked_in_progress(self._now()), "started", actor_id)

    def mark_done(self, item_id: str, tenant_id: str, actor_id: str) -> PlanItem:
        """Evidence is never checked here (ADR 0066 §5.4) — completion is the practitioner's own
        attestation, with or without evidence attached. Idempotent: marking an already-`done` item
        done again is a no-op, not an error (and not a conflict — nothing is written)."""
        item = self._require_item(item_id, tenant_id)
        if item.status == "done":
            return item
        return self._transition(item, item.marked_done(self._now()), "completed", actor_id)

    def reopen(self, item_id: str, tenant_id: str, actor_id: str) -> PlanItem:
        """No undo logic beyond this call (ADR 0066 §5.3) — the item simply stops appearing in
        `list_completed_resolutions()`, and the next `current_maturity()` call reflects that
        automatically."""
        item = self._require_item(item_id, tenant_id)
        if item.status != "done":
            return item
        return self._transition(item, item.reopened(self._now()), "reopened", actor_id)

    def attach_evidence(
        self, item_id: str, tenant_id: str, evidence_ids: tuple[str, ...], actor_id: str
    ) -> PlanItem:
        """Always additive and optional (ADR 0066 §5.4) — never required for `mark_done`, and
        callable before OR after completion."""
        item = self._require_item(item_id, tenant_id)
        return self._transition(
            item, item.with_evidence(evidence_ids, self._now()), "evidence_attached", actor_id
        )

    # --- maturity recalculation (ADR 0066 §5.3) ---------------------------------------------

    def current_maturity(self, tenant_id: str) -> CurrentMaturity:
        """Reversible by construction: computed fresh from the frozen baseline plus whatever is
        CURRENTLY `done`, every call — never a stored, mutated value. No new inference: the exact
        same `score_maturity`/`rate_maturity_scores` Tier B's `analyze()` already uses."""
        baseline_result = self._store.get_organization_baseline(tenant_id)
        if baseline_result is None:
            return CurrentMaturity(maturity=None, active_pack_ids=())
        baseline_signals, active_pack_ids = baseline_result

        resolutions = self._store.list_completed_resolutions(tenant_id)
        current_signals = effective_signals(baseline_signals, resolutions)

        active_packs = [
            pack
            for pack in (self._engine.pack_by_id(pid) for pid in active_pack_ids)
            if pack is not None
        ]
        scores = score_maturity(current_signals, active_packs)
        return CurrentMaturity(
            maturity=rate_maturity_scores(scores), active_pack_ids=active_pack_ids
        )


__all__ = ["PlanExecutionService", "PlanExecutionStorePort", "CurrentMaturity"]
