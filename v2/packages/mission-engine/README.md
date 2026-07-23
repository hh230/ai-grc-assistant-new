# mission-engine

Rasheed V2 **Mission Engine** (Phase 15) — the smallest production-quality realization of
[ADR 0042](../../../docs/adr/0042-v2-mission-engine.md). It is the first package of the
**Product layer** built on top of the finished V2 **Platform** (the AI pipeline of Phases
1–14.8).

> **Everything is a Mission.** There is no Query, Workflow, Session, or Job as an independent
> executable unit. Even the simplest grounded question is a Mission from birth — it is never
> "promoted" into one. The only thing that varies between a trivial read and a large
> engagement is the mission's `execution_profile`, not its model, its store, or its execution
> path (ADR 0042 §11).

## What a Mission is

A **Mission** is the platform's single top-level unit of governed work: a tenant-owned,
goal-directed, resumable, auditable envelope that owns its goal, a versioned plan, a
lifecycle, its step records, and its identity. It **owns the outcome and governs the path to
it** — it does not reason (agents do), execute capability (tools do), persist itself (the
store does), or run durably by itself. Everything else the mission composes.

## What this package does — and does not do

The **`MissionEngine`** creates missions and drives them through the lifecycle:

```
CREATED ─→ PLANNED ─→ EXECUTING ─→ COMPLETED                       (happy path)
                          │
                          ├─→ AWAITING_APPROVAL ─→ RESUMED ─→ …     (human gate: pause → approve → resume)
                          │              └────────→ CANCELLED       (reject, fail-safe)
                          └─→ FAILED / CANCELLED                    (fail-safe terminals)
```

The **full** state machine is implemented and now **fully exercised**: the happy path, the
fail-safe terminals, and — since **[ADR 0044](../../../docs/adr/0044-v2-human-approval-lifecycle.md)
(Human Approval, Slices 1–3)** — the complete human gate (pause → `approve`/`reject` → `resume`,
continuing execution from the pause point). `ARCHIVED` remains defined but undriven (a retention
concern for a later phase). Nothing here reasons, calls a tool, resolves tenancy, runs the bus, or
persists itself.

It reaches the world through **two ports** (ports before adapters):

| Port | Purpose | Reference adapter (this package) | Production impl |
|---|---|---|---|
| `ExecutionPort` | the single seam to all step execution | `EchoExecutor` (echoes, no grounding) | Pipeline-Tool executor (later) |
| `MissionStorePort` | the single persistence seam | `InMemoryMissionStore` (tenant-scoped dict) | **`PostgresMissionStore`** — shipped in `mission-store` (ADR 0043) |

It emits tenant- and mission-stamped domain events onto the **existing** Event Bus
(`event-bus`, ADR 0039) — no new transport.

**Out of scope for this package** (built *on top of* the Mission Engine, or in sibling packages):
the Tool Registry, the Agent Runtime, and the Framework Engine. Mission Store persistence ships in
`mission-store` (ADR 0043); the Human Approval **decision surface** (`approve`/`reject`/`resume`)
ships here and in `mission-integration` (ADR 0044). What remains deferred of Human Approval is only
**Slice 4 — Advanced Approval** (multi-approver, timeout, escalation, expiry, SLA).

### Human Approval — Slice 1 (ADR 0044): the aggregate carries the request

Following [ADR 0044](../../../docs/adr/0044-v2-human-approval-lifecycle.md), the mission now *carries*
its human-approval state as **two frozen value objects inside the aggregate** (not a separate
aggregate): `ApprovalRequest` (`id` / `reason` / `requested_at` / `requested_by`) and its optional
`ApprovalDecision` (`approved` / `approver` / `comment` / `decided_at`). `Mission.approval` is the
one active request (0-or-1); `await_approval(request=None)` optionally attaches it at the pause and
enforces the **one-active-request invariant** (`has_active_approval`); the no-arg call is unchanged.

**Slice 2 (resolve the gate)** adds `Mission.approve(approver, comment=…)` (→ `RESUMED`) and
`Mission.reject(approver, comment=…)` (→ `CANCELLED`, fail-safe, reusing the frozen terminal — no
`REJECTED` state). Both re-check the approver's **tenant** (ADR 0040 §5), require an active pending
request, and record the decision as a **new** `ApprovalRequest` carrying its `ApprovalDecision`
(`approved` / `approver` / `comment` / `decided_at`) — a gate is decided exactly once. The two
decision events `MissionApproved` / `MissionRejected` are defined and registered in the outbox.

**Slice 3 (resume orchestration)** wires the human gate end-to-end. The engine now **attaches** the
`ApprovalRequest` when it pauses; `engine.approve` / `engine.reject` persist the decision and **emit**
`MissionApproved` / `MissionRejected`; and `engine.resume` emits `MissionResumed`, re-enters
`RESUMED → EXECUTING`, and continues from the pause point (a single approval authorizes exactly the
gated step — later consequential steps pause again). *Detecting* an approved mission and *reloading*
it is the Integration Runtime's job (`mission-integration`); this package is the engine half.

**Still deferred (Slice 4):** multi-approver, timeout, escalation, expiry, SLA, reject-and-replan;
and RBAC (whether a principal *may* approve stays above the pure aggregate).

## The locked invariants (ADR 0042)

- **Tenant bound at creation.** `Mission.create` requires a `TenantContext`; a tenant-less
  mission cannot be constructed, and a mission never changes tenant (ADR 0040 §5). The engine
  *binds and preserves* the tenant — it never derives or widens it.
- **`mission_id` + `tenant_id` on every event.** Every emitted event is stamped, so every
  audit/event fact is reachable through exactly one mission (Invariant #3).
- **Every mission is stored — no exception.** `simple` and `composite` alike. Display,
  retention, deletion, and archival are policies applied *above* the store in a later phase,
  never branches in the engine.
- **Plan is a versioned, first-class artifact.** Even a `simple` mission has a plan of exactly
  one step; re-planning creates a new version on the same aggregate.
- **Human gate is a lifecycle state.** A consequential step pauses the mission in
  `AWAITING_APPROVAL` *before* its side effect; with no approver wired yet, it stays paused —
  the correct fail-safe.

## Usage

```python
from event_bus.bus import InProcessEventBus
from pipeline_contracts import TenantContext
from mission_engine import EchoExecutor, InMemoryMissionStore, MissionEngine

engine = MissionEngine(
    store=InMemoryMissionStore(),
    executor=EchoExecutor(),          # the Pipeline Tool replaces this in step 3
    events=InProcessEventBus(),
)

tenant = TenantContext(tenant_id="org_acme", principal_id="u_owner", roles=("owner",))

# A trivial grounded question is a Mission — created, planned (one step), executed, completed,
# persisted, and audited — all through the ports.
mission = engine.run_simple("MFA lookup", tenant, "what does NCA ECC say about MFA?")
assert mission.status.value == "completed"
```

For a multi-step or consequential mission, drive the stages explicitly:

```python
from mission_engine import Plan, PlanStep

mission = engine.create("draft an access-control policy", tenant)
engine.plan(mission, Plan(steps=(PlanStep(instruction="draft", consequential=True),)))
engine.execute(mission)               # pauses at the human gate before the consequential step
assert mission.status.value == "awaiting_approval"
```

A step may also **name the registered Tool it routes to** — `PlanStep(instruction=..., tool="assess_risk")`
(ADR 0048). The engine copies `tool` onto the `StepRequest`; the executor resolves it (or its default
when `tool=""`). The engine still inspects neither `instruction` nor `tool` — it only dispatches. This
is what lets one composite plan run each step on a different tool (a multi-tool mission).

## Architecture & dependencies

```
mission-engine ─→ pipeline-contracts   (TenantContext, serialization — pure)
              └─→ event-bus            (DomainEvent base, EventBus port — pure)
```

The package is **pure domain**: no database, no LLM SDK, no framework, no tool registry, no
messaging infrastructure. This is enforced by `tests/test_purity.py`. Both dependencies are
themselves pure V2 contract/event packages.

## Tests

```
uv run pytest
```

Behavioral tests cover the lifecycle table, plan/`execution_profile` derivation, the aggregate
invariants (tenant immutability, terminal immutability, illegal transitions), event stamping,
tenant-scoped storage, and the engine end-to-end (happy path, human-gate pause, fail-safe on
executor error, idempotent creation, tenant-scoped reads), plus purity and public-surface
checks.
