"""The Mission Engine (ADR 0042 §2) — creates missions and drives them through the lifecycle.

The engine is the coordinator. It **binds and preserves** the `TenantContext` (it never
derives it, §3), holds the plan as a versioned artifact, owns the lifecycle state machine,
dispatches steps to the `ExecutionPort`, records the results, persists every mission through
the `MissionStorePort` (no exception, §11), and emits tenant- and mission-stamped events onto
the Event Bus (§2.7). It does **not** reason, execute capability, resolve tenancy, run the
bus, or persist itself — those live behind the ports and in later phases (§3).

What this first package drives is the happy path `CREATED → PLANNED → EXECUTING → COMPLETED`
plus the fail-safe terminals (`FAILED`, `CANCELLED`) and the human-gate **pause**. When a
plan step is consequential, the engine pauses the mission in `AWAITING_APPROVAL` *before*
dispatching it and stops — the resolution surface (Human Approval) is a later phase, so the
mission simply stays paused, which is the correct fail-safe behaviour (§2.5, §12.5).
"""

from __future__ import annotations

import time
from collections.abc import Callable

from event_bus.bus import EventBus
from pipeline_contracts import TenantContext

from mission_engine.errors import MissionNotFound
from mission_engine.events import (
    MissionAwaitingApproval,
    MissionCancelled,
    MissionCompleted,
    MissionCreated,
    MissionEvent,
    MissionFailed,
    MissionPlanned,
    MissionStepCompleted,
)
from mission_engine.lifecycle import MissionStatus
from mission_engine.mission import Mission
from mission_engine.plan import Plan, single_step_plan
from mission_engine.ports import ExecutionPort, MissionStorePort, StepRequest


class MissionEngine:
    """Coordinates missions over the two ports and the Event Bus. Inject the port
    implementations (a real store/executor in production; the reference adapters in tests);
    the engine depends only on the `Protocol`s."""

    def __init__(
        self,
        store: MissionStorePort,
        executor: ExecutionPort,
        *,
        events: EventBus | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._store = store
        self._executor = executor
        self._events = events
        self._clock = clock

    # --- event emission -----------------------------------------------------------------

    def _emit(self, event: MissionEvent) -> None:
        """Publish a mission-stamped event onto the bus, if one is wired. Every mission event
        is constructed with the full trace/mission/tenant stamp at its call site (§2.7)."""
        if self._events is not None:
            self._events.publish(event)

    # --- creation -----------------------------------------------------------------------

    def create(
        self,
        goal: str,
        tenant: TenantContext,
        *,
        idempotency_key: str = "",
    ) -> Mission:
        """Open (or idempotently return) a mission. With an `idempotency_key`, a repeat call
        in the same tenant returns the existing mission instead of creating a duplicate
        (ADR 0042 §12.7); keys are scoped per tenant, so two tenants never collide."""
        if idempotency_key:
            existing = self._store.find_by_idempotency_key(tenant, idempotency_key)
            if existing is not None:
                return existing

        mission = Mission.create(
            goal=goal, tenant=tenant, idempotency_key=idempotency_key, now=self._clock()
        )
        # Every mission is stored — from creation, no exception (§11).
        self._store.save(mission)
        self._emit(
            MissionCreated(
                trace_id=mission.trace_id,
                occurred_at=self._clock(),
                mission_id=mission.id,
                tenant_id=mission.tenant_id,
                goal=mission.goal,
            )
        )
        return mission

    # --- planning -----------------------------------------------------------------------

    def plan(self, mission: Mission, plan: Plan) -> Mission:
        """Store the plan (versioned) and move the mission to PLANNED."""
        mission.set_plan(plan)
        self._store.save(mission)
        self._emit(
            MissionPlanned(
                trace_id=mission.trace_id,
                occurred_at=self._clock(),
                mission_id=mission.id,
                tenant_id=mission.tenant_id,
                execution_profile=plan.execution_profile.value,
                step_count=len(plan.steps),
                plan_version=plan.version,
            )
        )
        return mission

    # --- execution ----------------------------------------------------------------------

    def execute(self, mission: Mission) -> Mission:
        """Run the plan step by step through the ExecutionPort, recording each result, then
        complete the mission. Stops fail-safe on a failed/erroring step, and pauses at the
        human gate before any consequential step."""
        mission.begin_execution()  # raises unless a plan exists, so plan is set below
        self._store.save(mission)

        steps = mission.plan.steps if mission.plan is not None else ()
        for step in steps:
            if step.consequential:
                # Human gate: pause BEFORE the side effect and stop. Resolution is a later
                # phase, so the mission remains paused — the correct fail-safe (§2.5, §12.5).
                mission.await_approval()
                self._store.save(mission)
                self._emit(
                    MissionAwaitingApproval(
                        trace_id=mission.trace_id,
                        occurred_at=self._clock(),
                        mission_id=mission.id,
                        tenant_id=mission.tenant_id,
                        step_id=step.id,
                    )
                )
                return mission

            request = StepRequest(
                mission_id=mission.id,
                step_id=step.id,
                tenant=mission.tenant,
                instruction=step.instruction,
                consequential=step.consequential,
            )
            try:
                result = self._executor.execute(request)
            except Exception as exc:  # noqa: BLE001 - any executor failure fails the mission safe
                return self._fail(mission, f"step {step.id} raised: {exc}")

            if not result.ok:
                return self._fail(mission, f"step {step.id} failed")

            mission.record_step(result)
            self._store.save(mission)
            self._emit(
                MissionStepCompleted(
                    trace_id=mission.trace_id,
                    occurred_at=self._clock(),
                    mission_id=mission.id,
                    tenant_id=mission.tenant_id,
                    step_id=step.id,
                    ok=result.ok,
                    source_ids=result.source_ids,
                )
            )

        mission.complete()
        self._store.save(mission)
        self._emit(
            MissionCompleted(
                trace_id=mission.trace_id,
                occurred_at=self._clock(),
                mission_id=mission.id,
                tenant_id=mission.tenant_id,
                step_count=len(mission.step_results),
            )
        )
        return mission

    def _fail(self, mission: Mission, reason: str) -> Mission:
        mission.fail(reason)
        self._store.save(mission)
        self._emit(
            MissionFailed(
                trace_id=mission.trace_id,
                occurred_at=self._clock(),
                mission_id=mission.id,
                tenant_id=mission.tenant_id,
                reason=reason,
            )
        )
        return mission

    # --- convenience --------------------------------------------------------------------

    def run_simple(
        self,
        goal: str,
        tenant: TenantContext,
        instruction: str,
        *,
        idempotency_key: str = "",
    ) -> Mission:
        """The full happy path for a `simple` mission: create → plan (one step) → execute.
        This is the "even the simplest question is a Mission" path (ADR 0042 §11) — a single
        entry point that is nonetheless architecturally complete (tenant bound, plan
        versioned, lifecycle driven, persisted, events emitted). An idempotent hit returns the
        existing mission untouched."""
        mission = self.create(goal, tenant, idempotency_key=idempotency_key)
        if mission.status != MissionStatus.CREATED:
            # An idempotent create returned a mission already past creation — leave it as is.
            return mission
        self.plan(mission, single_step_plan(instruction, description=goal))
        return self.execute(mission)

    # --- cancellation & reads -----------------------------------------------------------

    def cancel(self, mission: Mission, reason: str = "") -> Mission:
        """Cancel a mission fail-safe (ADR 0042 §7)."""
        mission.cancel(reason)
        self._store.save(mission)
        self._emit(
            MissionCancelled(
                trace_id=mission.trace_id,
                occurred_at=self._clock(),
                mission_id=mission.id,
                tenant_id=mission.tenant_id,
                reason=reason,
            )
        )
        return mission

    def get(self, mission_id: str, tenant: TenantContext) -> Mission:
        """Fetch a mission within the caller's tenant scope. A mission that exists for another
        tenant is *not found*, never returned (ADR 0040 §5)."""
        mission = self._store.get(mission_id, tenant)
        if mission is None:
            raise MissionNotFound(f"no mission {mission_id} in this tenant")
        mission.assert_tenant(tenant)  # defence in depth: the store already scoped the read.
        return mission
