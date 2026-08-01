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

from mission_engine.approval import ApprovalRequest
from mission_engine.errors import IllegalTransition, MissionNotFound
from mission_engine.events import (
    MissionApproved,
    MissionAwaitingApproval,
    MissionCancelled,
    MissionCompleted,
    MissionCreated,
    MissionEvent,
    MissionFailed,
    MissionPlanned,
    MissionRejected,
    MissionResumed,
    MissionStepCompleted,
)
from mission_engine.lifecycle import MissionStatus
from mission_engine.mission import Mission
from mission_engine.plan import Plan, PlanStep, single_step_plan
from mission_engine.ports import ExecutionPort, MissionStorePort, StepRequest

# The `ApprovalRequest.requested_by` value for a human gate the engine raised automatically:
# `requested_by` is the request *origin*, and an engine-detected gate has no human requester, so it
# records the platform's system principal. A dedicated service-principal identity (and/or renaming
# the frozen field to something like `request_origin`) is a tracked future ADR — see ADR 0044.
SYSTEM_REQUESTER = "system"


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
        return self._drive(mission, resuming=False)

    def _drive(self, mission: Mission, *, resuming: bool) -> Mission:
        """Run the plan from the mission's current progress (`len(step_results)`) to completion,
        the next gate, or a failure. The single execution loop shared by first-run `execute` and
        post-approval `resume` (ADR 0044 Slice 3): resuming only differs in that the **already
        approved** gate at the resume point is run instead of re-paused. All other steps behave
        identically, so `execution_profile` still drives no control flow (ADR 0042 §11)."""
        steps = mission.plan.steps if mission.plan is not None else ()
        start = len(mission.step_results)  # steps already recorded — resume continues after them
        for index in range(start, len(steps)):
            step = steps[index]
            if step.consequential and not self._gate_is_approved(mission, index, start, resuming):
                # Human gate: attach the approval request, pause BEFORE the side effect, and stop.
                # The mission stays paused until a human approves/rejects it (§2.5, §12.5).
                mission.await_approval(self._build_request(mission, step))
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
                tool=step.tool,  # ADR 0048: executor resolves this per-step tool, else its default
                # ADR 0051: the results of all steps before this one, so a step runs from them.
                prior_results=tuple(mission.step_results),
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

    @staticmethod
    def _gate_is_approved(mission: Mission, index: int, start: int, resuming: bool) -> bool:
        """True only for the **one** consequential step a resume was approved to run: the step at
        the resume point (`index == start`) when the mission carries an approved decision. Any later
        consequential step is a fresh gate and still pauses — a single approval authorizes a single
        step, never the rest of the plan."""
        return (
            resuming
            and index == start
            and mission.approval is not None
            and mission.approval.decision is not None
            and mission.approval.decision.approved
        )

    def _build_request(self, mission: Mission, step: PlanStep) -> ApprovalRequest:
        """The approval request the engine attaches at the pause (ADR 0044). `requested_by` records
        the request **origin**, not the deciding human (that is `ApprovalDecision.approver`, set at
        approve/reject). An engine-detected gate has no human requester, so it records the platform
        **system principal** (`SYSTEM_REQUESTER`) — deliberately NOT the mission id (already stamped
        on the record and every event) and never a human subject (RBAC lives above the pure
        aggregate, ADR 0044 assumption 3). The field *name* is frozen from Slice 1; a clearer name
        (e.g. `request_origin`) is a tracked future ADR (see ADR 0044 → Future ADRs)."""
        return ApprovalRequest(
            reason=f"approval required before step {step.id}: {step.description}",
            requested_by=SYSTEM_REQUESTER,
            requested_at=self._clock(),
        )

    # --- human-gate resolution & resume (ADR 0044) --------------------------------------

    def approve(self, mission: Mission, approver: TenantContext, *, comment: str = "") -> Mission:
        """Apply a human approval to a paused mission and emit `MissionApproved` (ADR 0044 §Q4).
        The decision and tenant re-check live in the aggregate (`Mission.approve`); the engine
        persists the transition and emits the event so the outbox/audit carry it. It does **not**
        resume execution — call `resume` for that."""
        mission.approve(approver, comment=comment, now=self._clock())
        self._store.save(mission)
        decision = mission.approval.decision if mission.approval is not None else None
        approval_id = mission.approval.id if mission.approval is not None else ""
        self._emit(
            MissionApproved(
                trace_id=mission.trace_id,
                occurred_at=self._clock(),
                mission_id=mission.id,
                tenant_id=mission.tenant_id,
                approval_id=approval_id,
                approver=decision.approver if decision is not None else "",
            )
        )
        return mission

    def reject(self, mission: Mission, approver: TenantContext, *, comment: str = "") -> Mission:
        """Apply a human rejection to a paused mission and emit `MissionRejected` (ADR 0044 §Q5).
        The mission stops fail-safe as CANCELLED; the recorded decision distinguishes it from a
        plain cancel."""
        mission.reject(approver, comment=comment, now=self._clock())
        self._store.save(mission)
        decision = mission.approval.decision if mission.approval is not None else None
        approval_id = mission.approval.id if mission.approval is not None else ""
        self._emit(
            MissionRejected(
                trace_id=mission.trace_id,
                occurred_at=self._clock(),
                mission_id=mission.id,
                tenant_id=mission.tenant_id,
                approval_id=approval_id,
                approver=decision.approver if decision is not None else "",
                comment=comment,
            )
        )
        return mission

    def resume(self, mission: Mission) -> Mission:
        """Continue an approved (RESUMED) mission's execution from where it paused (ADR 0044
        Slice 3): emit `MissionResumed`, re-enter EXECUTING, run the **approved** gated step, and
        drive the rest of the plan to completion or the next gate. This is the engine half of resume
        *orchestration* — detecting the approval and reloading the mission is the Runtime's job."""
        if mission.status is not MissionStatus.RESUMED:
            raise IllegalTransition(
                f"resume requires a RESUMED mission, not {mission.status.value}"
            )
        mission.begin_execution()  # RESUMED → EXECUTING (legal; continues from the pause point)
        self._store.save(mission)
        self._emit(
            MissionResumed(
                trace_id=mission.trace_id,
                occurred_at=self._clock(),
                mission_id=mission.id,
                tenant_id=mission.tenant_id,
                plan_version=mission.plan_version,
            )
        )
        return self._drive(mission, resuming=True)

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
