"""Concrete adapters wiring the Application-layer ports to the frozen Core (ADR 0054, wired here per
ADR 0052 — the composition root). These are the only place `grc-api` reaches into the Core engine /
store; the commands and queries above them see only the ports.

- `StoreMissionAccess` — `MissionAccess` over `MissionStorePort.get` (tenant-scoped, fail-closed).
- `ReadModelProjection` — `ProjectionPort` over the Mission List read model: a status re-projection
  that preserves the product type/scope stamped at creation.
- `EngineWorkflow` — `MissionWorkflow` over the `MissionEngine`. Note `approve_step` is a **business
  action**, not a mirror of the engine: it *approves the gate **and** resumes execution* — two
  engine operations behind one workflow verb. (Retry is a "re-run = new mission" create, not a
  transition — it lands with the create flow in Slice S7, per the owner's S2 decision.)
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from mission_application import CreatedMission
from mission_read_model import MissionListItem, MissionListReadModel
from pipeline_contracts import TenantContext


class StoreMissionAccess:
    """Loads a mission for a write through the Core store, scoped to the tenant."""

    def __init__(self, store: Any) -> None:
        self._store = store

    def load_for_update(self, tenant_id: str, mission_id: str) -> Any | None:
        # store.get is tenant-scoped: a missing OR cross-tenant mission comes back None (fail-safe).
        return self._store.get(mission_id, TenantContext(tenant_id=tenant_id))


class ReadModelProjection:
    """Updates the Mission List projection's status snapshot after a mission changes. Read-modify-
    write preserves the product `type`/`scope` (stamped at creation); a not-yet-projected mission is
    left alone (its creation projection lands in Slice S7)."""

    def __init__(self, read_model: MissionListReadModel) -> None:
        self._read_model = read_model

    def project(self, subject: Any) -> None:
        existing: MissionListItem | None = self._read_model.get(
            subject.id, TenantContext(tenant_id=subject.tenant_id)
        )
        if existing is None:
            return
        self._read_model.record(
            replace(existing, status=subject.status.value, updated_at=subject.updated_at)
        )


class EngineWorkflow:
    """Drives Core transitions for the write commands — and, per ADR 0055, **stops short of starting
    execution**. Where a command would once have run the drive loop (`start` → `execute`,
    `approve_step` → `resume`), it now records a **launch request** into the scope's buffer instead.
    The scope fires those requests through the `MissionLaunchPort` *after its transaction commits*,
    so the command owns the decision but never owns progress (ADR 0055, Realization).

    The decision half stays here, inside the command's transaction: `approve` and `reject` are Core
    transitions with events, driven and persisted transactionally. Only the *drive* is deferred to
    the launch boundary."""

    def __init__(self, engine: Any, launches: list[tuple[str, TenantContext]]) -> None:
        self._engine = engine
        self._launches = launches

    def approve_step(
        self, mission: Any, *, step_id: str, approver: TenantContext, comment: str = ""
    ) -> None:
        # The approval decision itself — a Core transition with events, inside the transaction.
        self._engine.approve(mission, approver, comment=comment)
        # The resume (execution past the gate) is a launch, fired after commit (not engine.resume).
        self._launches.append((mission.id, approver))

    def reject_step(
        self, mission: Any, *, step_id: str, approver: TenantContext, comment: str = ""
    ) -> None:
        self._engine.reject(mission, approver, comment=comment)  # a decision; no execution follows

    def start(self, mission: Any) -> None:
        # The product's "Start mission": a launch, not a direct `engine.execute`. Recorded now,
        # fired after the command's transaction commits (ADR 0055).
        self._launches.append((mission.id, mission.tenant))


class CatalogDefinitionProvider:
    """`MissionDefinitionProvider` over the bundled Mission Catalog (assistant-runtime): a Mission
    type + scope → the Core's `(goal, Plan)`. The scope is the catalog's `request` input; the plan
    factories reference tool *names* only, so nothing heavier is pulled in."""

    def __init__(self, catalog: Any) -> None:
        self._catalog = catalog

    def define(self, mission_type: str, scope: str, tenant: TenantContext) -> tuple[str, Any]:
        definition: tuple[str, Any] = self._catalog.build(mission_type, {"request": scope}, tenant)
        return definition


class EngineMissionCreator:
    """`MissionCreator` over the Core engine: create the mission from its goal, then set its plan —
    the two ops `AssistantRuntime._drive` uses, behind one seam. Idempotent by key (the engine
    returns the existing mission on a repeat)."""

    def __init__(self, engine: Any) -> None:
        self._engine = engine

    def create(
        self, goal: str, plan: Any, tenant: TenantContext, *, idempotency_key: str = ""
    ) -> Any:
        mission = self._engine.create(goal, tenant, idempotency_key=idempotency_key)
        # Plan only a freshly-created mission. An idempotent repeat returns the existing (already
        # planned) mission — re-planning it would be an illegal transition (PLANNED can't re-plan).
        if mission.status.value == "created":
            self._engine.plan(mission, plan)
        return mission


class CreationProjection:
    """`ProjectionPort` for the **creation** — records the new mission into the Mission List with
    the product `type`/`scope` the Core does not store (the first projection; the S1 read-model
    gap). The seam every downstream surface then reads through — no special "new mission" path."""

    def __init__(self, read_model: MissionListReadModel) -> None:
        self._read_model = read_model

    def project(self, subject: CreatedMission) -> None:
        mission = subject.mission
        self._read_model.record(
            MissionListItem(
                mission_id=mission.id,
                tenant_id=mission.tenant_id,
                mission_type=subject.mission_type,
                title=subject.scope,
                status=mission.status.value,
                created_at=mission.created_at,
                updated_at=mission.updated_at,
            )
        )
