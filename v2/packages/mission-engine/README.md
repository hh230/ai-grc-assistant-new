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
CREATED ─→ PLANNED ─→ EXECUTING ─→ COMPLETED          (happy path — the only one exercised)
                          │
                          ├─→ AWAITING_APPROVAL        (human gate: pause BEFORE a side effect)
                          └─→ FAILED / CANCELLED        (fail-safe terminals)
```

The **full** state machine (`AWAITING_APPROVAL`, `RESUMED`, `ARCHIVED`) is implemented from
day one; only the happy path plus the fail-safe terminals and the human-gate **pause** are
exercised in this package (ADR 0042 §12.4). Nothing here reasons, calls a tool, resolves
tenancy, runs the bus, or persists itself.

It reaches the world through **two ports** (ports before adapters):

| Port | Purpose | Reference adapter (this package) | Production impl (later) |
|---|---|---|---|
| `ExecutionPort` | the single seam to all step execution | `EchoExecutor` (echoes, no grounding) | Pipeline-Tool executor (step 3) |
| `MissionStorePort` | the single persistence seam | `InMemoryMissionStore` (tenant-scoped dict) | Postgres store (step 4) |

It emits tenant- and mission-stamped domain events onto the **existing** Event Bus
(`event-bus`, ADR 0039) — no new transport.

**Out of scope for this package** (built *on top of* the Mission Engine in later steps): Tool
Registry, Human Approval (the decision surface — the *pause* lives here), Agent Runtime,
Mission Store persistence, and the Framework Engine.

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
