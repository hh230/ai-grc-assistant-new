"""The Mission aggregate root (ADR 0042 §1).

A Mission is the platform's single top-level unit of governed work: a tenant-owned,
goal-directed, resumable envelope that owns its goal, its versioned plan, its lifecycle, its
step records, and its identity. It **owns the outcome and governs the path to it** — it does
not reason (agents do), execute capability (tools do), persist itself (the store does), or
run durably by itself. Everything else the mission composes.

State changes go through this root, which enforces its invariants (§1):

  * a mission cannot change tenant (bound at creation, immutable for life — ADR 0040 §5);
  * illegal lifecycle transitions are rejected (the closed table in `lifecycle`);
  * steps can only be recorded while `EXECUTING`;
  * a consequential step cannot run before its gate is approved — the engine pauses the
    mission in `AWAITING_APPROVAL` *before* dispatching it (§5, §12.5);
  * a terminal mission (completed/failed/cancelled) is immutable — the only move left is
    `ARCHIVED`.

The aggregate is **pure**: it holds no ports and performs no I/O. The `MissionEngine` drives
it and talks to the `ExecutionPort` / `MissionStorePort` / Event Bus around it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from pipeline_contracts import TenantContext, dataclass_dict

from mission_engine.errors import IllegalTransition, PlanError, TenantMismatch
from mission_engine.ids import new_mission_id, new_trace_id
from mission_engine.lifecycle import MissionStatus, can_transition, is_terminal
from mission_engine.plan import ExecutionProfile, Plan, PlanStep
from mission_engine.ports import StepResult


def _now() -> float:
    return time.time()


@dataclass
class Mission:
    """The aggregate. Mutable state, but every change goes through a method that enforces an
    invariant — never assign `status` or `tenant` directly. Construct via `Mission.create`."""

    id: str
    tenant: TenantContext
    goal: str
    trace_id: str
    status: MissionStatus = MissionStatus.CREATED
    plan: Plan | None = None
    step_results: list[StepResult] = field(default_factory=list)
    idempotency_key: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    _plan_versions: list[Plan] = field(default_factory=list, repr=False)

    # --- construction -------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        goal: str,
        tenant: TenantContext,
        idempotency_key: str = "",
        now: float | None = None,
    ) -> Mission:
        """Open a mission from a goal and a tenant. `tenant` is required (ADR 0042 §12.1): a
        tenant-less mission cannot be constructed — the type forces it. Identity (`id`,
        `trace_id`) is minted here and is immutable."""
        moment = now if now is not None else _now()
        return cls(
            id=new_mission_id(),
            tenant=tenant,
            goal=goal,
            trace_id=new_trace_id(),
            status=MissionStatus.CREATED,
            idempotency_key=idempotency_key,
            created_at=moment,
            updated_at=moment,
        )

    # --- derived views ------------------------------------------------------------------

    @property
    def tenant_id(self) -> str:
        return self.tenant.tenant_id

    @property
    def execution_profile(self) -> ExecutionProfile | None:
        """Derived from the plan (ADR 0042 §11); `None` before a plan exists."""
        return self.plan.execution_profile if self.plan is not None else None

    @property
    def plan_version(self) -> int:
        return self.plan.version if self.plan is not None else 0

    @property
    def plan_versions(self) -> tuple[Plan, ...]:
        """Every plan version in order — the audit trail of how the plan evolved (§12.6)."""
        return tuple(self._plan_versions)

    @property
    def is_terminal(self) -> bool:
        """Whether the mission has reached an end state (completed/failed/cancelled/archived)
        and is therefore immutable. The consumer-facing way to ask "is this mission done?"
        without reaching into the lifecycle machinery."""
        return is_terminal(self.status)

    # --- guards -------------------------------------------------------------------------

    def assert_tenant(self, tenant: TenantContext) -> None:
        """Reject any access from a foreign tenant. Called by the store/engine before acting
        on a mission on behalf of a caller (ADR 0040 §5)."""
        if not self.tenant.same_tenant(tenant):
            raise TenantMismatch(
                f"mission {self.id} belongs to another tenant; access denied"
            )

    def _transition(self, dst: MissionStatus) -> None:
        if not can_transition(self.status, dst):
            raise IllegalTransition(
                f"{self.status.value} → {dst.value} is not a legal mission transition"
            )
        self.status = dst
        self.updated_at = _now()

    # --- lifecycle: happy path ----------------------------------------------------------

    def set_plan(self, plan: Plan) -> None:
        """Store the first plan and move CREATED → PLANNED. Re-planning after a gate uses
        `replan` from RESUMED instead."""
        if self.status not in (MissionStatus.CREATED, MissionStatus.RESUMED):
            raise IllegalTransition(
                f"a plan can only be set from CREATED or RESUMED, not {self.status.value}"
            )
        self.plan = plan
        self._plan_versions.append(plan)
        self._transition(MissionStatus.PLANNED)

    def begin_execution(self) -> None:
        """PLANNED → EXECUTING."""
        if self.plan is None:
            raise PlanError("cannot begin execution without a plan")
        self._transition(MissionStatus.EXECUTING)

    def record_step(self, result: StepResult) -> None:
        """Record one completed step's result. Legal only while EXECUTING — a completed or
        failed mission is immutable, so this raises on any terminal state."""
        if self.status != MissionStatus.EXECUTING:
            raise IllegalTransition(
                f"steps can only be recorded while EXECUTING, not {self.status.value}"
            )
        self.step_results.append(result)
        self.updated_at = _now()

    def complete(self) -> None:
        """EXECUTING → COMPLETED. The mission is immutable afterwards (only ARCHIVED remains)."""
        self._transition(MissionStatus.COMPLETED)

    # --- lifecycle: human gate & re-plan (defined now, exercised when Human Approval lands) --

    def await_approval(self) -> None:
        """EXECUTING → AWAITING_APPROVAL: pause BEFORE a consequential step's side effect
        (ADR 0042 §2.5, §12.5). The engine calls this; the *decision* surface is Human
        Approval, a later phase."""
        self._transition(MissionStatus.AWAITING_APPROVAL)

    def resume(self) -> None:
        """AWAITING_APPROVAL → RESUMED, after an approval/edit. Resumption re-verifies the
        approver's tenant at the engine boundary (ADR 0040 §5) — a gate approved by an
        outsider is not a gate."""
        self._transition(MissionStatus.RESUMED)

    def replan(self, steps: tuple[PlanStep, ...]) -> None:
        """Create a new plan version on the same mission and return to PLANNED (§12.6). Legal
        from RESUMED (after a gate) — never a mutation of the accepted plan."""
        if self.status != MissionStatus.RESUMED:
            raise IllegalTransition("re-plan is only legal after RESUMED")
        if self.plan is None:
            raise PlanError("cannot re-plan a mission that was never planned")
        new_plan = self.plan.next_version(steps)
        self.plan = new_plan
        self._plan_versions.append(new_plan)
        self._transition(MissionStatus.PLANNED)

    # --- lifecycle: fail-safe terminals -------------------------------------------------

    def fail(self, reason: str = "") -> None:
        """Stop the mission fail-safe on an unrecoverable error (ADR 0042 §7)."""
        self._transition(MissionStatus.FAILED)

    def cancel(self, reason: str = "") -> None:
        """Stop the mission fail-safe on human cancellation (ADR 0042 §7)."""
        self._transition(MissionStatus.CANCELLED)

    def archive(self) -> None:
        """Move a terminal mission to ARCHIVED — reconstructable for audit (ADR 0042 §7)."""
        if not is_terminal(self.status):
            raise IllegalTransition("only a terminal mission can be archived")
        self._transition(MissionStatus.ARCHIVED)

    # --- serialization ------------------------------------------------------------------

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(
            self,
            exclude=("tenant", "plan", "step_results", "_plan_versions", "status"),
            extra={
                "status": self.status.value,
                "tenant": self.tenant.to_dict(),
                "execution_profile": (
                    self.execution_profile.value if self.execution_profile else None
                ),
                "plan": self.plan.to_dict() if self.plan is not None else None,
                "plan_version": self.plan_version,
                "step_results": [result.to_dict() for result in self.step_results],
            },
        )
