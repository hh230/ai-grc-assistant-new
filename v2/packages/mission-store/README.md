# mission-store

Rasheed V2 **Mission Store** — the durable `MissionStorePort` ([ADR 0043](../../../docs/adr/0043-v2-mission-store.md)),
built on the *frozen* [Mission Engine](../mission-engine/README.md) (ADR 0042). It is the production
persistence layer behind the port Phase 15 shipped with only a reference `InMemoryMissionStore`.

> **Delivered as vertical slices.** Following the Phase 15 method: a small end-to-end
> implementation, fully tested, then reviewed and frozen before the next slice — not everything at
> once.
>
> - **Slice 1 — persistence round-trip** (frozen): `save` / `get` / `find_by_idempotency_key` over a
>   state-snapshot row, tenant-scoped, faithful aggregate round-trip.
> - **Slice 2 — idempotency completion** (frozen): a duplicate
>   `(tenant_id, idempotency_key)` from a *different* mission raises a typed **`IdempotencyConflict`**
>   instead of leaking a raw driver exception (ADR 0043 §9, §11). No other behavior changes.
> - **Slice 3 — Unit of Work** (frozen): a caller-owned **`UnitOfWork`** that owns a single flat
>   transaction over one connection (`BEGIN` / `COMMIT` / `ROLLBACK`), so several store operations
>   commit atomically. It owns the transaction, the connection, and the lifecycle — and **no stores**.
>   No change to `MissionStorePort`, `PostgresMissionStore`, or the Mission Engine (ADR 0043 §8).
> - **Slice 4 — Transactional Outbox** (frozen): an **`OutboxSink`** (an `EventBus`
>   subscriber) writes each emitted domain event into an `outbox` table **on the same connection and
>   in the same transaction** as the mission `save` — so a mission's state change and its events
>   commit atomically. An **`OutboxRelay`** later drains the committed-but-unpublished rows onto a
>   Delivery Bus via an **`OutboxPublisher`**. No change to `MissionStorePort`, `UnitOfWork`, the
>   Mission Engine, or the `EventBus` protocol (ADR 0043-S4 Rev.3).
>
> All four slices are **frozen and Accepted** (ADR 0043). The store's payload later gained the
> optional `ApprovalRequest` column via **ADR 0044 Slice 1** (`payload_schema_version` 2 + migration
> `0003_approval.sql`) — see the note below.

> **Payload evolved by ADR 0044 (Human Approval, Slice 1).** The store now persists the mission's
> optional `ApprovalRequest`: `payload_schema_version` is **2**, the codec reads **both** v1 (no
> approval → `None`, no backfill) and v2, and a new **nullable `approval jsonb` column** is added by
> the additive migration [`0003_approval.sql`](migrations/0003_approval.sql) (`ADD COLUMN IF NOT
> EXISTS`; `0001` untouched). Backward-compatible by construction — existing rows read NULL → `None`.
> This is the `payload_schema_version` seam (below) doing exactly the job it was pre-built for.

## What Slice 1 does

`PostgresMissionStore` is a **drop-in replacement** for `InMemoryMissionStore`: the exact
`MissionStorePort` contract — `save` / `get` / `find_by_idempotency_key` — so the Mission Engine
runs unchanged and never learns that missions now live in PostgreSQL.

```python
from mission_engine import EchoExecutor, MissionEngine
from mission_store import PostgresMissionStore
from pipeline_contracts import TenantContext

store = PostgresMissionStore(dsn="postgresql://.../rasheed_v2")
engine = MissionEngine(store=store, executor=EchoExecutor())
tenant = TenantContext(tenant_id="org_acme", principal_id="u_owner", roles=("owner",))
mission = engine.run_simple("MFA lookup", tenant, "what does NCA ECC say about MFA?")
reloaded = store.get(mission.id, tenant)   # durably persisted, faithfully reconstructed
```

### In scope (Slice 1)

- The three port methods over a **state-snapshot** row (ADR 0043 §5): typed indexed columns for
  scoping/lifecycle, JSONB for nested collections (roles, current plan, full plan-version history,
  step results).
- **Tenant isolation in SQL** (`get`/`find` filter by `tenant_id`; a foreign tenant's mission is not
  found), and a **cross-tenant overwrite refusal** on `save` (defence in depth).
- **Faithful round-trip** of the aggregate incl. the plan-version history `Mission.to_dict()` omits.
- Schema carries **`revision`** (store-managed write counter) and **`payload_schema_version`** from
  the first migration — the seams a future concurrency / shape-evolution slice needs, so those land
  with no migration. Slice 1 writes both and enforces neither.
- Pure, driver-free **codec**; **lazy** psycopg import (package imports with or without the driver).

### Deferred to later slices (deliberately not built now)

- **Caller-managed transaction (unit of work)** — delivered in **Slice 3** (see below); Slice 1's
  injected connection was a *test/embedding affordance* only (ADR 0043 §8).
- **Enforced optimistic concurrency** — `revision` is present but not compared; today's
  single-writer-per-mission invariant (ADR 0042; ADR 0043 assumption 1) makes LWW safe. Enforcing
  OCC is a future ADR that extends the frozen port/aggregate (§10).
- **`payload_schema_version` forward-migration machinery** — only version 1 exists; an unknown
  version fails loud.
- **Generic migration runner + `schema_migrations` ledger**, and a **list/recovery read interface** —
  later concerns; not part of the frozen three-method port.

## What Slice 3 does — the `UnitOfWork`

`UnitOfWork` is the transaction boundary behind the frozen port. Slice 1/2 gave
`PostgresMissionStore` a constructor-injected connection but ran it in autocommit — each `save`/`get`
was its own durable statement, and no caller could group writes atomically. Slice 3 adds the object
that owns that group: **one flat transaction over one connection**, without adding a single method to
the store or the port.

```python
from mission_store import PostgresMissionStore, UnitOfWork

with UnitOfWork(dsn="postgresql://.../rasheed_v2") as uow:
    store = PostgresMissionStore(connection=uow.connection)
    store.save(mission)          # not yet durable — the UoW owns the commit
# clean exit commits; an exception rolls back — the store did neither
```

The division of labour is total: **the store** executes SQL, serializes, and deserializes and
**never** begins, commits, or rolls back; **the `UnitOfWork`** owns `BEGIN` / `COMMIT` / `ROLLBACK`
and the connection's lifecycle. It exposes **only** `begin`, `commit`, `rollback`, `connection`,
`close`, and the context-manager protocol — and **no stores** (no `mission_store`, `outbox_store`,
repositories, factories, or service-locator behaviour; no globals or contextvars). Stores are always
constructed outside the UoW and bound to `uow.connection`.

### In scope (Slice 3)

- **Two connection modes.** *Owned* (from `dsn=`) — opened lazily in `begin()` with `autocommit=False`
  and **closed** on disposal. *Injected* (`connection=`) — used as-is and **never** closed by the UoW.
- **Autocommit is fatal.** An injected `autocommit=True` connection is rejected **immediately** at
  construction — autocommit would silently defeat atomicity (ADR 0043 §8).
- **Single flat transaction, single-use.** No savepoints, no nesting, no re-entrant `begin`. A second
  `begin`/`commit`/`rollback`, a `commit` after `rollback` (or vice versa), or touching `connection`
  outside the active window each raise a clear `UnitOfWorkError`.
- **Fail-safe.** On any exception (including the store's `IdempotencyConflict`) the UoW rolls the whole
  unit back and disposes — proven end-to-end against Postgres (read-your-writes, invisibility before
  commit, visibility after commit, atomic rollback).
- **Future-ready by a shared connection.** Because every participant binds to the one `uow.connection`,
  a later Outbox / Lease / Approval write becomes atomic with the mission write **without changing this
  class or the store**.

### Still out of scope after Slice 3 (unchanged from the plan)

- **Outbox pattern**, **mission lease**, **human-approval writes**, **event publishing** — none are
  implemented; Slice 3 only makes them *possible* later via the shared connection.
- **Enforced optimistic concurrency (OCC)** — still deferred to a future ADR that extends the frozen
  port/aggregate (§10).
- **Savepoints / nested transactions** — deliberately not supported.
- **No change to `MissionStorePort`.** The port is still its three synchronous methods; `UnitOfWork` is
  an additive, separate interface (ADR 0043 §4), not a fourth port method.

## What Slice 4 does — the Transactional Outbox

The Mission Engine emits a domain event onto its `EventBus` immediately after every `save`. Slice 4
makes those emissions **transactional**: an **`OutboxSink`** — an `EventBus` *subscriber* — writes each
event into an `outbox` table on the **same connection** the store uses, inside the **same
`UnitOfWork` transaction** as the `save`. State change and events therefore commit atomically (no
dual-write). A separate **`OutboxRelay`** later drains the committed-but-unpublished rows onto a
**Delivery Bus** through an **`OutboxPublisher`**.

```python
from event_bus import ALL_EVENTS, InProcessEventBus, RecordingEventBus
from mission_engine import EchoExecutor, MissionEngine
from mission_store import (
    DeliveryBusPublisher, OutboxRelay, OutboxSink, PostgresMissionStore, UnitOfWork,
)

# --- capture: one transition, one transaction (per-transition only) ---
with UnitOfWork(connection=conn) as uow:                       # non-autocommit connection
    store = PostgresMissionStore(connection=uow.connection)
    capture_bus = InProcessEventBus()                          # any EventBus impl; synchronous
    capture_bus.subscribe(ALL_EVENTS, OutboxSink(connection=uow.connection).write)
    engine = MissionEngine(store, EchoExecutor(), events=capture_bus)
    engine.create("draft an access-control policy", tenant)    # save + event, same transaction
    uow.commit()                                               # both commit atomically

# --- deliver: drain committed rows onto the Delivery Bus (outside the transaction) ---
delivery_bus = RecordingEventBus()                             # the real consumers live here
OutboxRelay(dsn="postgresql://.../rasheed_v2").drain(DeliveryBusPublisher(delivery_bus))
```

### In scope (Slice 4)

- **`OutboxSink`** — an `EventHandler` (`(DomainEvent) -> None`) subscribed to the **Capture Bus**;
  writes the event to the outbox table on the injected connection. Like the store, it **never commits
  or rolls back** — the `UnitOfWork` owns the transaction; its failure must propagate to abort it.
- **`OutboxRelay`** — drains unpublished rows in insertion order, rehydrates each into a typed
  `DomainEvent` via a name→class registry, publishes via an `OutboxPublisher`, then marks the row
  published. **At-least-once** (a lost mark re-publishes). Single-worker.
- **`OutboxPublisher`** port + **`DeliveryBusPublisher`** adapter (forwards to any `EventBus`).
- **`UnsupportedEventType`** — an unregistered `event_name` fails loud; the relay **leaves the row
  unpublished** (never deleted, never marked). There is **no generic fallback event**.
- **`outbox` schema + migration `0002_outbox.sql`** (parity-tested), a **pure codec**, lazy psycopg.

### Still out of scope after Slice 4 (deferred in the ADR)

- **Retry / dead-letter / `attempts`**, **pruning / retention**, **scheduling**, and **multi-worker**
  (`FOR UPDATE SKIP LOCKED`) — none are implemented (ADR 0043-S4 Rev.3).
- **No change to `MissionStorePort`, `UnitOfWork`, the Mission Engine, or the `EventBus` protocol.**
  The outbox is entirely additive: a subscriber, a relay, and a publisher port.

## Idempotency: portable contract vs. durable-store guarantee

`PostgresMissionStore` raises `IdempotencyConflict` on a duplicate `(tenant_id, idempotency_key)`;
the reference `InMemoryMissionStore` (which ships in the *frozen* Mission Engine) does not. This
divergence is **intentional** (ADR 0043 §9):

- **Engine-level idempotency is the actual cross-adapter contract.** Correctness is guaranteed
  *above* the store by the engine's **find-before-create**: `create` calls
  `find_by_idempotency_key(tenant, key)` and returns the existing mission on a hit.
- **`find_by_idempotency_key()` + find-before-create are the portable semantics** — both adapters
  implement them identically, and both treat a keyed *same-id* re-save as a normal upsert (never a
  conflict). The shared contract suite exercises exactly this.
- **`IdempotencyConflict` is a durable-store defense-in-depth guarantee** for the *concurrent*
  database race (two different missions racing past the `find` with the same key). Only a real,
  concurrently-accessed database can experience that race; a single-process in-memory dict cannot.
- **So `IdempotencyConflict` is intentionally Postgres-specific and is *not* part of the
  adapter-independent `MissionStorePort` behavioural contract.** Its assertions live in the Postgres
  integration suite; the shared contract suite asserts only what every adapter honours.

> If the project ever decides *every* adapter must raise `IdempotencyConflict`, that is an
> **ADR-level change to the frozen `MissionStorePort` and Mission Engine** — a new ADR, not a Mission
> Store implementation change (see ADR 0043 → *Future ADRs*).

## Architecture & dependencies

```
mission-store ─→ mission-engine     (the Mission aggregate + the frozen MissionStorePort)
              ├─→ pipeline-contracts (TenantContext — pure)
              └─→ event-bus          (DomainEvent + the EventBus protocol — for the outbox, Slice 4)
```

- **`codec.py` is pure** (no driver, no I/O): the `Mission ⇄ row` translation, unit-testable without
  a database. Reuses each contract model's canonical `to_dict` out; reconstructs the aggregate
  directly in (restoring persisted state, not replaying the lifecycle).
- **`store.py` imports psycopg lazily**, inside the methods that touch the database.
- **`schema.py`** is the single source of truth for the table shape; the canonical migration
  [`migrations/0001_missions.sql`](migrations/0001_missions.sql) is kept in lock-step by a parity test.
- **Outbox (Slice 4):** `outbox_codec.py` / `outbox_schema.py` / `outbox_errors.py` /
  `outbox_publisher.py` are **pure**; only `outbox.py` (`OutboxSink`, `OutboxRelay`) touches psycopg,
  lazily. `outbox_schema.py` ⇄ [`migrations/0002_outbox.sql`](migrations/0002_outbox.sql) parity-tested.

## Configuration

DSN from `MISSION_STORE_DSN`, defaulting to the isolated V2 dev database `rasheed_v2` (its own
`missions` table; never V1's `aigrc`).

## Tests

```
uv run pytest
```

- **Shared port-contract suite** (`test_store_contract.py`) — the same behavioural assertions run
  against **both** `InMemoryMissionStore` and `PostgresMissionStore`, proving drop-in equivalence.
  The Postgres parametrization auto-skips without a database.
- **Pure suites** (run anywhere): codec round-trip incl. `payload_schema_version`; SQL construction
  via a recording connection (upsert shape, tenant guard, revision bump, JSONB wrapping); schema /
  migration parity; driver-laziness / purity.
- **Postgres-specific integration** (`test_postgres_integration.py`, DB-gated, auto-skip): DB-level
  unique-index enforcement, cross-tenant overwrite refusal, `revision` increments, engine-driven
  lifecycle upsert, and migration idempotency — on throwaway `missions_it_*` tables.
- **Unit of Work** (`test_unit_of_work.py`): the transaction lifecycle — commit/rollback, owned vs.
  injected connection ownership, autocommit rejection, the single-use state machine, and (DB-gated)
  read-your-writes / atomic rollback.
- **Outbox** (Slice 4): pure codec + registry (`test_outbox_codec.py`), recording-connection SQL
  (`test_outbox_sql.py`), schema/purity (`test_outbox_purity.py`), and **DB-gated integration**
  (`test_outbox_integration.py`, throwaway `*_s4_*` tables): atomic capture, whole-transition
  rollback on any event-write failure, end-to-end drain in order, at-least-once, and
  `UnsupportedEventType` leaving the row unpublished.
