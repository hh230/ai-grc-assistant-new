# mission-integration

Rasheed V2 **Mission Integration** — the composition root that runs the *frozen* Mission Store
slices 1–4 as **one system, end to end**. This package is **Integration & Verification only**: it
adds no feature, starts no new slice, and changes **nothing** in the frozen components
([Mission Engine](../mission-engine/README.md) / ADR 0042, [Mission Store](../mission-store/README.md)
/ ADR 0043, [Event Bus](../event-bus/README.md)). No ADR, port, engine, aggregate, or `EventBus`
protocol is touched. It owns only the *wiring*.

## The path it wires

```
Mission Engine → Mission Store → Unit of Work → Transactional Outbox
              → Outbox Relay → Delivery Bus → Audit Sink
```

The Transactional Outbox pattern splits this into two halves that the composition root keeps
deliberately separate:

- **Capture half** — one engine *transition* runs inside one `UnitOfWork`. The
  `PostgresMissionStore` and the `OutboxSink` are both bound to `uow.connection`, and the engine
  emits onto a synchronous **Capture Bus** whose only subscriber is that sink. So the mission's
  state change (`save`) and its domain events (outbox rows) commit **atomically** — no dual write.
  Per ADR 0043-S4 Rev.3 the capture is **per-transition**: one transition, one transaction.
- **Delivery half** — the `OutboxRelay` later drains committed-but-unpublished rows, in insertion
  order, onto the **Delivery Bus** (a *different* `EventBus`, outside any write transaction) via a
  `DeliveryBusPublisher`. The Delivery Bus's subscriber is the **`MissionAuditSink`** — the audit
  terminal. At-least-once: a lost publish-mark re-delivers on the next drain.

## What this package adds (glue only)

- **`MissionRuntime`** (`runtime.py`) — the composition root. `run_transition(apply)` runs the
  capture half for one transition; `relay()` runs the delivery half; `load(id, tenant)` reloads a
  mission from the durable store (the seam a *resume* uses). Every object it composes is frozen; it
  adds no behaviour beyond assembly. psycopg is imported lazily, so the module imports without the
  driver.
  - **Resume orchestration (ADR 0044 Slice 3):** `approve(id, approver, comment=…)` /
    `reject(id, approver, comment=…)` reload a paused mission and apply the human decision in its own
    transaction (so `MissionApproved` / `MissionRejected` are captured to the outbox);
    `resume_if_approved(id, tenant)` is the orchestration seam — it **detects** the approval
    (persisted status `RESUMED`), **reloads** the mission, and **re-enters** it into the Mission
    Engine to continue execution from the pause point. No scheduler/queue/polling — the caller names
    the mission; a non-`RESUMED` mission is a deliberate no-op.
- **`MissionAuditSink`** (`audit.py`) — the Delivery Bus's terminal subscriber, recording the
  delivered event stream so a run can prove the committed, published events reached audit. It is
  deliberately minimal and **not** the pipeline-shaped `event_bus.AuditTrailBuilder` (which
  finalizes an `AuditRecord` on `PipelineCompleted`, an event a *mission* run never emits — see the
  architectural note below).

```python
from mission_integration import MissionRuntime
from pipeline_contracts import TenantContext

runtime = MissionRuntime()  # canonical missions/outbox tables + an in-process Delivery Bus + Audit
tenant = TenantContext(tenant_id="org_acme", principal_id="u_owner", roles=("owner",))

# capture: create → plan → execute, one atomic transition
mission = runtime.run_transition(
    lambda e: e.run_simple("MFA lookup", tenant, "what does NCA ECC say about MFA?")
)
# deliver: drain the committed outbox onto the Delivery Bus and into the Audit Sink
runtime.relay()
assert runtime.audit.event_names_for(mission.id) == [
    "mission.created", "mission.planned", "mission.step_completed", "mission.completed",
]
```

## Scenarios verified

The suite (`tests/test_end_to_end.py`, DB-gated, auto-skips without a database) drives the *seams
between* the slices — not a re-test of any one slice, which the frozen packages already cover:

1. **Simple Mission** — the one-transition `run_simple` path persists the mission (COMPLETED) and
   captures all four events atomically; the relay delivers them into Audit.
2. **Composite Mission** — a three-step mission driven as separate `create` / `plan` / `execute`
   transitions; every transition saves, every event reaches the outbox, and the relay delivers the
   whole stream in insertion order.
3. **Resume** — run, stop at the PLANNED→EXECUTING boundary, reload the aggregate **only** from the
   store, and execute the reloaded object to completion: state survives, no data loss, no missing
   events. (No human-approval gate — that surface is a later phase and out of scope.)
4. **Outbox atomicity** — a failing event write inside the transaction rolls the mission `save`
   back too (both tables empty); a healthy transition commits the mission *and* its event together.
5. **Relay** — marks delivered rows published and re-drains to nothing (idempotent); at-least-once
   on a lost mark (re-delivers); unpublished rows wait in the outbox until relayed.
6. **Audit** — every published event reaches the `MissionAuditSink`, across two missions, in order,
   each event keeping its tenant/mission stamp intact through the whole path.

## Architectural note (for the record, not acted on here)

The frozen `event_bus.AuditTrailBuilder` / `AuditRecord` are **pipeline-shaped**: the builder
accumulates per `trace_id` and finalizes on `PipelineCompleted`, which mission runs never emit. So a
durable, *mission-shaped* audit sink (one that folds `mission.*` events into an audit record and
persists it) does not yet exist — this package uses a minimal recording sink to prove *delivery
reaches audit*, which is all the integration phase asks. Building the mission audit projection is a
future slice, not part of this integration.

## Tests

```
uv run pytest
```

Needs a reachable PostgreSQL (DSN from `MISSION_STORE_DSN`, default `rasheed_v2`); every test
auto-skips cleanly when none is reachable. Lint/type: `ruff check .` and `mypy --strict` (root
config) both pass.
