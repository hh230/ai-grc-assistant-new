# ADR 0043: Rasheed V2 — the Mission Store (durable persistence behind the frozen MissionStorePort)

- Status: **Accepted — implemented** (Slices 1–4 built, tested against real PostgreSQL, and frozen;
  see *Implementation Status* at the end). *(Header updated 2026-07-17: the original "Proposed /
  writes no code" wording predated implementation.)*
- Date: 2026-07-16
- Deciders: Product Owner (review pending), Architecture
- Related: CLAUDE.md §3 (mission-centric), §8 (mission lifecycle), §14 (services/repository),
  §15 (DDD), §16 (EDA), §19 (audit), §20 (tenancy); ADR 0012 (Postgres + SQLAlchemy/Alembic),
  0015 (audit & traceability), 0038 (pipeline-contracts), 0039 (platform hardening / event bus),
  0040 (tenancy model), **0042 (Mission Engine — defines and freezes `MissionStorePort`)**

---

## Context

Phase 15 built the **Mission Engine** (ADR 0042) with two ports. One of them,
`MissionStorePort`, is the single persistence seam; Phase 15 shipped it with a reference
`InMemoryMissionStore` (a per-tenant dict, non-durable). ADR 0042 §9/§12.3 names the **Postgres
Mission Store** as *step 4* — "the store implementation (Postgres, per ADR 0012) lands later
behind that port." This ADR is that step's design, produced **before** any implementation.

**The port is a frozen input, not a decision of this ADR.** From `mission_engine.ports`:

```python
class MissionStorePort(Protocol):
    def save(self, mission: Mission) -> None: ...
    def get(self, mission_id: str, tenant: TenantContext) -> Mission | None: ...
    def find_by_idempotency_key(self, tenant: TenantContext, key: str) -> Mission | None: ...
```

Three properties of this signature **constrain everything below** and cannot be changed here
(changing them supersedes ADR 0042):

1. **It is synchronous.** `def`, not `async def`. A store behind it must be sync, or bridge.
2. **`save` returns `None` and takes only the aggregate.** No expected-version, no returned
   revision, no returned mission. The store cannot hand back a reconciled winner or an assigned
   version through this method.
3. **Reads are tenant-scoped by argument.** Every read carries a `TenantContext`; the store
   must filter by it and never return another tenant's mission (ADR 0040 §5).

What this ADR *does* decide, firmly: to **adopt the existing V2 persistence direction** (§0), the
package, the persistence and serialization strategy, the schema, migrations, and the transaction /
idempotency / concurrency / failure / recovery models that live **behind** that fixed port. Reconciling
that direction with ADR 0012 is left to a **separate ADR amendment** (§0) — this ADR does not redefine
another ADR. Two small, non-structural points remain for the final review (§"Open decisions"), each
with a stated default; the structural direction is settled here, not deferred.

The frozen platform (Mission Engine, Tool Registry, Pipeline Tool, Tenant Activation / ADR 0040)
is not modified by anything here. If a design point below appears to require touching one of
them, that is a signal to stop and raise a new ADR — noted where it arises.

---

## Architectural assumptions

These are the load-bearing assumptions the design rests on. Each is stated with the **trigger**
that would invalidate it and the localized change it would force, so no assumption is silent and
none hides a future redesign.

1. **Single writer per mission (today) — and therefore Last-Writer-Wins is *not* an architectural
   goal.** ADR 0042's execution model drives each mission synchronously through one engine owned by
   its creator; there is **no durable multi-worker mission execution yet**. So at any instant exactly
   one writer saves a given mission, and no write-write conflict on a mission is *reachable*. The
   store's Last-Writer-Wins behaviour (§10) is therefore **not a chosen concurrency strategy — it is a
   consequence we tolerate only because ADR 0042 guarantees a single writer per mission today.** We
   are not selecting LWW over optimistic concurrency; we are recording that concurrency control is not
   yet *needed*, while refusing to bake in anything that blocks adding it later.
   - **Trigger:** the day durable multi-worker execution (Workflow / Agent Runtime, a later phase)
     can drive one mission from two processes, this assumption breaks. That layer **must** preserve
     single-writer-per-mission (a mission lease) — or enforced optimistic concurrency must be switched
     on (assumption 2).
2. **The schema already carries the metadata a future optimistic-concurrency upgrade needs — so that
   upgrade is not a redesign.** Every mission row carries a store-managed monotonic `revision` (and the
   domain `updated_at`) from the *first* migration. Turning on optimistic concurrency later is then a
   **localized change** — a `WHERE revision = :expected` guard on the update plus surfacing the
   expected value across the boundary — with **no schema migration and no data backfill.** The design
   deliberately pre-pays the *schema* cost of OCC now, while **not enabling OCC today** (the frozen
   `MissionStorePort` carries no expected-version, and the frozen aggregate no version field; enabling
   enforced OCC is a future ADR that extends ADR 0042 — §10).
3. **The event log, not the store, is the history of record.** Audit reconstruction and replay come
   from the Event Bus + audit sink (ADR 0039). The store is the **current-state projection** only. Any
   future need for historical/temporal queries is met by a derived read-model, never by turning the
   store into a second event log (§5).
4. **`TenantContext` is trustworthy and minted upstream.** The store binds and filters by the tenant it
   is handed (ADR 0040); it assumes the auth boundary already verified it. The store is the *last* line
   of tenant defence (SQL-level scoping + cross-tenant-write refusal), not the first.
5. **`payload_schema_version` governs shape evolution.** Stored JSON is read back only through the
   codec, which honours `payload_schema_version`. The design assumes every change to a persisted shape
   (`Plan`, `PlanStep`, `StepResult`, `TenantContext`) bumps that version and ships a forward-migration
   path, so indefinitely-retained missions stay reconstructable for audit (ADR 0042 §7).

---

## Decision

### 0. Data-access direction — **adopting the existing V2 persistence direction** (decided, not deferred)

**ADR 0043 adopts the existing V2 persistence direction: synchronous psycopg3 + raw, fully
parameterized SQL behind Ports & Adapters.** This direction is not invented here — it is already
established in V2, where the Retrieval Engine's pgvector adapter runs it in production (Phase 9B). The
Mission Store follows it, as every V2 persistence adapter does.

**This ADR does not itself redefine ADR 0012.** ADR 0012 currently mandates async SQLAlchemy + Alembic;
reconciling that with the direction V2 already follows is the job of a **separate ADR amendment to
ADR 0012**, so the project ends with a single, coherent persistence policy. That amendment is out of
scope for the Mission Store ADR — ADR 0043 *adopts* the V2 direction and *points to* the amendment; it
does not perform it. There is one direction, not two.

Why this is the single correct direction for V2 (not merely the convenient one):

1. **The frozen contract forces synchronous.** `MissionStorePort` (ADR 0042) — and every V2 platform
   seam beneath it — is synchronous by design. An async ORM behind a sync port requires per-call
   event-loop bridging (`asyncio.run` / `run_in_executor`), which either blocks the loop or spawns
   loops per query — an anti-pattern. Making the port async is impossible without superseding the
   frozen ADR 0042. So async SQLAlchemy is off the table *by construction*, not by preference.
2. **V2's concurrency model is process/worker-level, not async-in-request.** The V2 core is a pure,
   framework-free, synchronous computation core; the async boundary (FastAPI, `apps/api`) sits **above**
   V2 and invokes it off the event loop (threadpool / background worker). Pushing `asyncio` into the
   core would invert that boundary and couple pure domain packages to an event loop — exactly what the
   ports design (and CLAUDE.md §15 domain purity) exists to prevent.
3. **Ports & Adapters already delivers ADR 0012's *intent*.** ADR 0012 wanted "repositories isolate
   data access." The **Port is that repository boundary**: domain and engine code depend only on the
   `Protocol`; all SQL lives in one swappable adapter. We honour the *goal* — isolated, swappable,
   testable data access — through a lighter mechanism.
4. **Parameterized SQL honours ADR 0012's *security* rule.** "No raw SQL string interpolation" exists to
   eliminate injection. V2 binds **every value** through driver placeholders (`%(name)s`); the only
   interpolated tokens are static identifiers (table names) taken from **code constants, never input**.
   The injection surface is zero — the rule's purpose is met, only its mechanism differs.
5. **Precedent and uniformity.** The Retrieval Engine (Phase 9B) already established sync psycopg3 + raw
   parameterized SQL + hand-written `.sql` migrations in V2, in production. Adopting SQLAlchemy/Alembic
   *only* for the Mission Store would fracture V2 into two persistence idioms — the opposite of "a
   single direction." Standardizing on the existing one keeps V2 coherent.
6. **Dependency minimalism.** V2 packages are small and dependency-light (pure contracts + one driver
   behind an optional extra). SQLAlchemy Core + Alembic is a heavy dependency and a second migration
   runtime the rest of V2 does not carry.

**Consequences of §0:** (a) a **separate ADR amendment to ADR 0012** will record the single
project-wide persistence policy — ADR 0012's async-SQLAlchemy + Alembic guidance read as V1-scoped, and
V2's sync psycopg3 + raw parameterized SQL behind Ports & Adapters recorded alongside it. That
amendment is out of scope here; ADR 0043 only *adopts* the direction V2 already follows and names the
amendment as the follow-up that keeps one policy. (b) Migrations follow that existing V2 direction —
forward-only ordered `.sql` + a `schema_migrations` ledger runner (§14) — not Alembic. This is a
*decision*, closing what was previously an open item.

### 1. Responsibilities

The Mission Store is the **durable, tenant-scoped current-state projection of the Mission
aggregate**. Its responsibilities, and only these:

1. **Persist the aggregate on every `save`** — a full-aggregate upsert reflecting the mission's
   current lifecycle state, called by the engine after each transition. Every mission is stored,
   `simple` and `composite` alike, no exception (ADR 0042 §11).
2. **Reconstruct the aggregate on `get`** — faithfully, including its versioned plan, its **full
   plan-version history** (ADR 0042 §12.6), its step records, its lifecycle status, and its bound
   `TenantContext`.
3. **Resolve idempotency reads** — return the tenant's existing mission for a non-empty key so
   the engine's create is idempotent (ADR 0042 §12.7).
4. **Enforce tenant isolation at the storage boundary** — scope every read by `tenant_id` in the
   query; refuse any write that would move an existing mission to a different tenant.
5. **Own its schema and migrations** — the engine holds no schema, SQL, or driver (ADR 0042 §9).
6. **Fail loud and fail safe** — surface storage errors explicitly; never leave a partial or
   corrupt mission record.

### 2. Non-goals

- **It does not drive the lifecycle.** Legal transitions are the aggregate's invariants; the
  store persists whatever state the aggregate presents. It never advances or validates a
  transition.
- **It does not decide retention, deletion, or archival.** Those are policies *above* the store
  in a later phase (ADR 0042 §11). The store offers no delete in this phase.
- **It is not the audit log or the event store.** The event history is owned by the Event Bus +
  audit sink (ADR 0039). The store persists the **current-state snapshot**, not an event stream
  (see §5, and the event-sourcing alternative).
- **It does not emit events.** The engine emits; the store writes rows.
- **It does not resolve tenancy.** `TenantContext` is minted at the auth boundary (ADR 0040) and
  carried in; the store binds and filters, never derives or widens.
- **It does not orchestrate recovery.** Finding resumable missions to re-drive is a later
  worker/recovery concern (see §12); the store's recovery duty is faithful load-by-id.
- **It does not expose list/search/reporting queries.** The frozen port has three methods; any
  read-model for the workspace is a separate, additive read interface, not this port (§"Open").

### 3. Package boundaries

A **new standalone package `v2/packages/mission-store`**, depending on `mission-engine` (for the
`Mission` aggregate and the `MissionStorePort` it implements) and `pipeline-contracts` (for
`TenantContext`).

- **Why not inside `mission-engine`.** The engine is enforced-pure (`tests/test_purity.py`
  forbids `psycopg`, `os`, sockets, etc.). A database adapter cannot live there. This is the
  ports-and-adapters split ADR 0042 §12.3 designed for.
- **Why a per-aggregate store, not a shared `v2-persistence` package.** V2 keeps each subsystem's
  adapter with its subsystem (the Retrieval Engine owns its `pg/` adapter). One durable aggregate
  exists today; a shared persistence package is premature abstraction. If a second durable
  aggregate appears, extract shared plumbing then, not now.
- **Internal boundary.** A **pure codec** module (aggregate ⇄ row, no driver, no I/O) is separated
  from the **driver-facing store** module (all psycopg/SQL). The codec is unit-testable without a
  database; the store imports the driver lazily so the package imports with or without it.

### 4. Port ownership

- **The port is owned by `mission-engine` (ADR 0042) and is frozen.** This package *implements*
  it; it does not define, extend, or alter it.
- **`PostgresMissionStore` is a drop-in for `InMemoryMissionStore`** — identical observable
  semantics under the same contract suite (§13). The engine and aggregate are untouched.
- **Any capability beyond the three port methods** (a transactional unit-of-work handle, a
  resumable-missions query) is exposed as a **separate, additive interface** the store may also
  implement — never as a change to `MissionStorePort`. This keeps ADR 0042 intact.

### 5. Aggregate persistence strategy — **state snapshot, not event log, not normalized children**

We persist each mission as **one row: a current-state snapshot**, with the aggregate's nested
collections (roles, current plan, plan-version history, step results) stored as **JSONB** and the
scoping/lifecycle fields (tenant_id, status, idempotency_key, execution_profile, plan_version) as
**typed, indexed columns**.

- **Snapshot over event-sourcing.** The port's semantic is "save the current aggregate," and the
  aggregate is small and always fully in hand at save time. The *event* history is already a
  first-class asset elsewhere (Event Bus + audit, ADR 0039); event-sourcing the store would build
  a second history and force replay-to-read. The store is the **read-optimized current-state
  projection**; the event log is the append-only narrative. Keeping them separate is the CQRS-lite
  split ADR 0039/0042 already imply.
- **Snapshot over normalized child tables** (`missions` + `plan_versions` + `step_results` rows).
  Normalization buys SQL-queryable steps/plans, but the frozen port never queries into them — it
  loads whole aggregates by id and by key. Normalization would turn every `save` into a
  multi-statement, ordering-sensitive transaction for zero benefit the port can use. JSONB keeps
  `save` a single atomic statement (§8) while preserving the whole aggregate. If a future
  read-model needs to query across steps, it is built as a **projection derived from** these rows,
  not by normalizing the write model.
- **Consequence to accept:** the JSONB columns are opaque to SQL analytics. That is fine — analytics
  is a later read-model concern, explicitly out of scope (§2).

### 6. Serialization strategy

- **Write** reuses each contract model's canonical `to_dict` (the platform's one serialization
  convention, `pipeline_contracts.dataclass_dict`), so the persisted JSON matches what the rest of
  V2 already produces. The store adds nothing bespoke.
- **Read** reconstructs the aggregate **directly via its constructor**, including the private
  `_plan_versions` init field that `Mission.to_dict()` omits. This is restoration of persisted
  state, not a lifecycle mutation — no transition guard is invoked or bypassed. (This is the one
  place the store reaches a non-public-looking field; it is an init parameter of the frozen
  aggregate and is the designated reconstruction path. Flagged as a coupling to watch: if a future
  Mission Engine version changes its constructor, the codec breaks loudly — caught by the contract
  suite, §13.)
- **Payload versioning (new — my earlier spike lacked this).** A `payload_schema_version` integer is
  stored with every row. Missions are meant to be "reconstructable for audit indefinitely"
  (ADR 0042 §7); the shape of `Plan`/`StepResult` will evolve. Versioning the stored payload lets a
  future reader migrate old JSON forward (lazily on read, or in a backfill migration) instead of
  guessing. Version starts at 1.
- **No secrets, no chain-of-thought, source IDs not corpora** (ADR 0042 §8) — enforced by the
  aggregate's own `to_dict`, which already carries only grounded, minimized fields; the store adds
  no new data.

### 7. Postgres schema (proposed)

```sql
CREATE TABLE missions (
    id                     text             PRIMARY KEY,          -- 'mis_...' (platform-minted)
    tenant_id              text             NOT NULL,             -- scoping; indexed
    principal_id           text             NOT NULL DEFAULT '',
    region                 text             NOT NULL DEFAULT '',
    roles                  jsonb            NOT NULL DEFAULT '[]'::jsonb,
    goal                   text             NOT NULL,
    trace_id               text             NOT NULL,
    status                 text             NOT NULL,             -- lifecycle state value
    execution_profile      text,                                 -- 'simple' | 'composite' | NULL
    plan_version           integer          NOT NULL DEFAULT 0,
    idempotency_key        text             NOT NULL DEFAULT '',
    plan                   jsonb,                                 -- current plan (NULL pre-plan)
    plan_versions          jsonb            NOT NULL DEFAULT '[]'::jsonb,  -- full history
    step_results           jsonb            NOT NULL DEFAULT '[]'::jsonb,
    payload_schema_version integer          NOT NULL DEFAULT 1,   -- serialization version (§6)
    revision               bigint           NOT NULL DEFAULT 0,   -- store-managed write counter (§9)
    created_at             double precision NOT NULL,             -- domain clock (epoch seconds)
    updated_at             double precision NOT NULL,             -- domain clock
    stored_at              timestamptz      NOT NULL DEFAULT now(),  -- first-persist (ops)
    row_updated_at         timestamptz      NOT NULL DEFAULT now()   -- last-write (ops)
);

CREATE INDEX missions_tenant_idx ON missions (tenant_id);

-- Idempotency is unique PER TENANT and only for a non-empty key (ADR 0040 §5). A PARTIAL unique
-- index both enforces the invariant at the DB and backs find_by_idempotency_key.
CREATE UNIQUE INDEX missions_idem_idx
    ON missions (tenant_id, idempotency_key) WHERE idempotency_key <> '';

-- For a later per-tenant "resumable missions" read (§12) and workspace listing.
CREATE INDEX missions_tenant_status_idx ON missions (tenant_id, status);
```

Two schema sub-choices, decided:

- **Tenant as columns, not a single `tenant` JSONB.** `tenant_id` *must* be a real indexed column
  (scoping, the unique index). Keeping `principal_id`/`region`/`roles` as siblings (roles as JSONB)
  is uniform and matches ADR 0042 §8's stored-fields table. A single opaque `tenant` JSONB would
  hide `tenant_id` from the constraints that depend on it.
- **`created_at`/`updated_at` are `double precision`** because the aggregate's clock is
  `time.time()` (epoch float). `stored_at`/`row_updated_at` are DB-managed `timestamptz` for ops.
  The domain clock and the ops clock are deliberately distinct.

### 8. Transaction model

- **One `save` = one atomic statement = one transaction.** Because the snapshot is a single-row
  upsert, each `save` is atomic without an explicit `BEGIN/COMMIT`. There is **no multi-`save`
  transaction** spanning create→plan→execute: the lifecycle is a sequence of **durable
  checkpoints**, each independently committed. This is what makes a mission resumable from its last
  persisted state after a crash (§12).
- **Connection modes.** The store supports two:
  1. **Owned connection (default):** the store opens its own connection in **autocommit**; each
     `save`/`get` is self-contained and durable on return — the mode the engine needs.
  2. **Injected connection (unit-of-work):** a caller (a Services-layer coordinator) may inject a
     connection and manage the transaction itself. This is required so a future **transactional
     outbox** (ADR 0039 EDA) can write the mission row and an outbox event **atomically** in one
     transaction. The store must not *force* autocommit on an injected connection — it issues its
     statement and lets the caller commit. (Designing for this now costs nothing and avoids a
     rewrite when the outbox lands; it is not built in this phase.)
- **No cross-aggregate transactions in this phase.** Only the mission row is written.

### 9. Idempotency model

- **Per-tenant idempotency key**, exactly as the port and ADR 0040 §5 require. The engine's
  `create` calls `find_by_idempotency_key(tenant, key)` first and returns the existing mission on a
  hit.
- **Defence in depth at the DB:** the partial unique index `(tenant_id, idempotency_key) WHERE key
  <> ''` makes a duplicate physically impossible even under a race, and two tenants may reuse the
  same key.
- **The TOCTOU race, stated honestly.** Two concurrent creates with the same `(tenant, key)` both
  pass the `find` (miss), then both `save`. The unique index lets exactly one win; the other's
  `INSERT` raises a unique violation. **The frozen `save` returns `None`, so the store cannot hand
  the loser the winning mission.** Behaviour: the store raises a specific `IdempotencyConflict`; the
  losing create fails safe, and the caller re-invokes create, which now *finds* the winner. This
  window is narrow, self-healing on retry, and cannot produce two missions. Making it fully silent
  would require the port to return a mission from `save` — an ADR-0042 change, out of scope. (Called
  out in §"Open decisions" as a known, accepted limitation.)
- **Empty key is not a key.** The engine uses `""` for "no idempotency"; `find_by_idempotency_key`
  short-circuits on empty and never matches, and the partial index excludes empty keys so unkeyed
  missions never collide.

**Cross-adapter contract — what is portable vs. adapter-specific (Slice 2 review, 2026-07-16).**
`PostgresMissionStore` raises `IdempotencyConflict`; the reference `InMemoryMissionStore` (which
ships in the *frozen* Mission Engine) does not. This divergence is **intentional**, and the line is
drawn deliberately:

- **Engine-level idempotency is the actual cross-adapter contract.** Idempotency correctness is
  guaranteed *above* the store, by the engine's **find-before-create**: `create` calls
  `find_by_idempotency_key(tenant, key)` and returns the existing mission on a hit. This is the
  behaviour every adapter shares and that the shared port-contract suite exercises.
- **`find_by_idempotency_key()` + find-before-create are the portable semantics.** Both adapters
  implement `find_by_idempotency_key` identically, and both treat a keyed *same-id* re-save as a
  normal upsert (never a conflict) — locked by the shared contract suite.
- **`IdempotencyConflict` is a durable-store defense-in-depth guarantee** for the *concurrent*
  database race (two different missions racing past the `find` with the same key). Only a real,
  concurrently-accessed database can experience that race; the single-process in-memory dict cannot,
  so it has nothing to back-stop.
- **Therefore `IdempotencyConflict` is intentionally Postgres-specific and is *not* part of the
  adapter-independent `MissionStorePort` behavioural contract.** Requiring the in-memory adapter to
  simulate a conflict it can never encounter would add contract surface with no portable meaning.
  The conflict-raise assertions live in the Postgres integration suite; the shared contract suite
  asserts only what all adapters honour.

### 10. Concurrency model

This is the sharpest constraint, and I will not paper over it. It rests on *Architectural
assumption 1* (single writer per mission today) and *assumption 2* (schema carries the OCC hook).

- **The frozen port cannot express optimistic concurrency.** `save(mission) -> None` carries no
  expected-version, and the **frozen aggregate has no version/revision field** the store could
  compare against. So the store *cannot* implement enforced OCC (load-rev, `UPDATE ... WHERE
  revision = :expected`) without changing the Mission Engine — which is frozen.
- **The operative model is last-writer-wins snapshot — tolerated, not chosen (assumption 1).** It is
  *not* selected as a concurrency strategy; it is simply the behaviour when no write-write conflict on
  a mission is reachable. Within one process the engine drives a mission sequentially, so its saves are
  ordered. Across processes, correctness relies on **one owner driving a given mission at a time** — an
  invariant owned by the layer that *dispatches* missions (the Workflow / Agent Runtime / a mission
  lease), not by the store. Today missions are driven synchronously by their creator, so the invariant
  holds trivially; when durable multi-worker execution lands, that layer **must** provide the lease
  (assumption 1's trigger) or enforced OCC is switched on (next bullet).
- **Store-managed `revision` column, incremented on every write** (`revision = revision + 1`). It is
  **not enforced** today (no caller supplies an expected value) but is written from day one because:
  (a) it is a cheap, precise write-ordering/debug signal in the audit trail, and (b) it is the exact
  hook a future OCC needs, so adding enforced OCC later is a port+aggregate ADR plus a `WHERE
  revision =` clause — no schema migration.
- **`get` uses `READ COMMITTED`** (Postgres default); a single-row read needs nothing stronger.
- **Explicitly deferred:** true multi-writer safety (enforced OCC or pessimistic `SELECT ... FOR
  UPDATE` lease). It requires extending the frozen port/aggregate → a **new ADR**, not this one.
  This ADR's job is to make that future change *cheap* (the `revision` column), not to smuggle it in.

### 11. Failure model

Every failure **fails loud in the store and safe in the mission** (the mission's durable state is
whatever last committed; nothing partial):

| Failure | Store behaviour |
|---|---|
| Connection unreachable / dropped mid-call | Raise a wrapped `MissionStoreError`; the caller's transition is not durable, so the mission stays at its last committed checkpoint. No partial row (single-statement upsert). |
| Unique violation on idempotency (§9 race) | Raise `IdempotencyConflict` (a `MissionStoreError`); loser fails safe; retry finds the winner. |
| Cross-tenant overwrite attempt | The upsert's `WHERE tenant_id = EXCLUDED.tenant_id` guard matches 0 rows → raise `MissionStoreError`. The original row is untouched. (Defence in depth; the aggregate already forbids tenant change.) |
| Serialization/`to_dict` error before the write | Raise before touching the DB; nothing persisted. |
| Row present but payload unreadable (corrupt/old JSON) | Raise on `get` with the mission id and `payload_schema_version` in the message; never return a half-built aggregate. Old-but-known versions are migrated (§6), not failed. |
| Driver missing (`postgres` extra not installed) | `ImportError` with the install hint, at first DB touch — the pure codec still imports. |

Rule: the store **never swallows** an error to return a plausible-looking mission. In a regulated
domain a wrong-but-silent read is worse than a loud failure (CLAUDE.md §22, §"fail safe").

### 12. Recovery model

- **The store is the recovery checkpoint.** Because every transition is a committed snapshot (§8), a
  crash loses at most the in-flight, not-yet-saved step; on restart the engine `get`s the mission and
  resumes from its persisted lifecycle state. `AWAITING_APPROVAL`, `PLANNED`, `EXECUTING` all reload
  exactly.
- **Idempotent re-drive.** A resumed step must not double-apply side effects (ADR 0042 §7). The store
  supports this by faithfully restoring `step_results` (what already ran) and the plan; whether a
  step re-runs is the engine/executor's idempotency concern, but the store gives it the truth to
  decide.
- **Finding *what* to resume is out of scope for the frozen port.** "List this tenant's non-terminal
  missions" is a read the three port methods don't offer. It is provided later by an **additive
  read interface** (backed by `missions_tenant_status_idx`) consumed by a recovery worker — not by
  changing `MissionStorePort`. Named here so the seam is deliberate, not discovered.
- **No point-in-time rewind in the store.** History/replay for audit is the event log's job
  (ADR 0039). The store restores *current* state only.

### 13. Testing strategy

- **One shared port-contract suite, run against BOTH stores.** A single parametrized behavioural
  suite (save/get round-trip, tenant-scoped reads, per-tenant idempotency, cross-tenant refusal,
  lifecycle upsert) runs against `InMemoryMissionStore` **and** `PostgresMissionStore`. This is the
  real proof of "drop-in equivalence" — my earlier spike tested them separately and could have
  drifted. The Postgres parametrization auto-skips without a DB.
- **Pure codec suite (no DB):** full aggregate round-trip incl. multi-version plan history, `simple`
  and `composite`, the pre-plan (no-plan) case, tenant fields, and `payload_schema_version`.
- **SQL-construction suite (no DB):** a recording fake connection asserts the upsert shape + tenant
  guard, JSONB wrapping, tenant-scoped read predicates, and the empty-key short-circuit — so the SQL
  path is covered even where no Postgres exists (e.g. CI without a DB service).
- **Schema/migration parity (no DB):** `schema.py` ⇄ migration `.sql` stay in lock-step.
- **Purity (no DB):** codec/config/schema carry no runtime driver import; importing the package loads
  no driver (subprocess-checked).
- **Integration suite (DB-gated, auto-skip):** against the isolated `rasheed_v2` dev DB on throwaway
  `missions_it_*` tables — round-trip, tenant isolation, the **DB-level unique index** under a
  simulated race, lifecycle upsert driven end-to-end by the engine, cross-tenant refusal, and a
  migration-applies-cleanly test.
- **Concurrency test (DB-gated):** two writers against one mission id assert last-writer-wins is
  *consistent* (no corrupt/partial row, `revision` strictly increases), documenting the model of §10.
- **Type + lint:** mypy strict + ruff, matching the sibling V2 packages.

### 14. Migration strategy

Forward-only, ordered, idempotent SQL migrations (`migrations/0001_missions.sql`, `IF NOT EXISTS`),
applied by a small runner that records applied files in a `schema_migrations` ledger table —
**the V2 standard set in §0** (hand-written `.sql`, not Alembic), matching the Retrieval Engine
precedent. Reversibility is provided by paired down-migrations where practical.

This follows directly from the data-access direction **adopted in §0** (the direction V2 already
follows; reconciling ADR 0012 is left to a separate amendment). It is a settled decision, not an open
choice.

---

## Design challenge (I am challenging this before accepting it)

The reviewer asked for the design to be challenged. The five hardest objections, and where each
lands:

1. **"This violates ADR 0012 (async SQLAlchemy + Alembic + no raw SQL)."** *Valid and material —
   now resolved with a single direction (§0), not left open.* The frozen `MissionStorePort` is
   **synchronous**, so async SQLAlchemy behind it would need `asyncio`-to-sync bridges (an anti-pattern
   that blocks or spawns loops per call) — impossible without superseding the frozen ADR 0042. We
   therefore standardize **all of V2** on sync psycopg3 + raw *parameterized* SQL behind Ports &
   Adapters (§0), honouring ADR 0012's isolation and anti-injection *intent* through a lighter
   mechanism. This ADR does not redefine ADR 0012; **a separate amendment will update ADR 0012** so the
   project keeps a single persistence policy. The considered rejected alternative — sync SQLAlchemy Core
   + Alembic — would fracture V2 into two persistence idioms for no benefit the sync port can use; see
   *Alternatives*. The architecture has one direction.

2. **"Last-writer-wins is unsafe for a regulated, auditable system."** *Partly.* It is unsafe *only*
   under concurrent multi-writer drive of the same mission, which does not exist today (missions are
   driven synchronously by their creator). The honest constraint is that the **frozen port/aggregate
   cannot express enforced OCC**, so real multi-writer safety is a *future ADR*, not a thing I can add
   here without unfreezing ADR 0042. I mitigate by writing the `revision` column now so that future
   ADR is cheap. **Residual risk accepted and documented (§10), not hidden.**

3. **"Snapshot loses history — but ADR 0042 §8 stresses the event log."** *Answered.* The event log
   *is* preserved — by the Event Bus + audit sink (ADR 0039), which is where ADR 0042 §8 puts it. The
   store is the current-state projection; plan-version *history* (which §12.6 requires) is still fully
   kept in `plan_versions`. We are not dropping history; we are declining to build a *second* event
   store inside the snapshot table.

4. **"JSONB blobs make the data un-queryable and can rot."** *True and accepted.* The port never
   queries into the blobs, so there is no queryability lost that the system uses. Rot is mitigated by
   `payload_schema_version` (§6) enabling forward-migration. If analytics later needs queryable steps,
   it is a derived read-model, not a reshape of the write model.

5. **"Why a whole new package for one adapter — isn't that ceremony?"** *No.* The engine's enforced
   purity makes co-location impossible, and the port was designed for exactly this adapter to land
   behind it. The package is the intended shape, not ceremony. A *shared* persistence package would be
   the premature abstraction — correctly deferred until a second durable aggregate exists.

Two smaller challenges worth recording: the codec's use of the aggregate's `_plan_versions` init
field is a coupling to the frozen constructor (caught loudly by the contract suite if it changes);
and the injected-connection/unit-of-work seam (§8) adds surface for a future outbox that this phase
does not build — I judge the near-zero cost worth the avoided rewrite, but it could be cut if the
reviewer wants the smallest possible first cut.

---

## Open decisions (need the reviewer's ruling before build)

The two structural decisions that were open in the prior draft — the **driver/ORM direction** and the
**migration runner** — are now **resolved in §0** (sync psycopg3 + raw parameterized SQL; hand-written
`.sql` + ledger), so V2 has one direction. Two smaller, non-structural points remain for the final
review; each has a default I will take unless overruled, and neither blocks the shape of the schema:

1. **Idempotency-race UX.** Accept the self-healing `IdempotencyConflict`-then-retry (§9), or judge the
   race material enough to justify a future ADR-0042 change letting `save` return the winner. *Default:
   accept-and-document* — the race is narrow, cannot create two missions, and self-heals on retry.
2. **Unit-of-work seam now or later.** Build the injected-connection path in this phase (cheap
   future-proofing for the transactional outbox, §8) or defer for the smallest first cut. *Default:
   build the seam* — near-zero cost, avoids a later rewrite; trivial to cut if you prefer the minimal
   first slice.

---

## Consequences

**Positive**
- The durable store lands **behind the frozen port with zero change** to the Mission Engine,
  aggregate, Tool Registry, Pipeline Tool, or Tenancy — the payoff ADR 0042 §12.3 designed for.
- Every mission becomes a durable, reconstructable, tenant-isolated object (ADR 0042 §11) with a
  faithful plan-version history and per-tenant idempotency enforced at the database.
- A single contract suite proves the Postgres and in-memory stores are true drop-ins.
- The design is honest about what the frozen port *cannot* do (enforced OCC, silent idempotency
  reconciliation, list-resumable) and routes each to a future ADR/interface instead of smuggling a
  contract change in as an "implementation detail."

**Negative / costs**
- A store write on the path of every interaction (universal persistence, ADR 0042 §11) — accepted
  there, inherited here.
- Last-writer-wins is the ceiling until a future ADR unfreezes the port/aggregate for OCC.
- JSONB payloads are opaque to SQL analytics until a derived read-model exists.
- The project's single persistence policy is completed by a **separate ADR amendment to ADR 0012**
  (recording ADR 0012's async/Alembic guidance as V1-scoped and V2's sync psycopg3 + raw parameterized
  SQL alongside it). ADR 0043 only *adopts* the direction V2 already follows (§0); it does not redefine
  ADR 0012. The outstanding item is that amendment, not an unresolved architectural choice.

## Alternatives considered

- **Event-sourced store (events are the source of truth; state is a replay).** Rejected: duplicates
  the Event-Bus/audit history (ADR 0039), forces replay-to-read, and is far heavier than a small
  always-in-hand aggregate needs. The store is a projection, not a second log.
- **Normalized child tables (`missions`/`plan_versions`/`step_results`).** Rejected for this phase: the
  frozen port loads whole aggregates and never queries into children, so normalization adds
  multi-statement transactional writes for no benefit the port can use. Revisit only when a read-model
  demands cross-step SQL — as a projection, not a write-model reshape.
- **Async SQLAlchemy + Alembic strictly per ADR 0012.** Rejected: the frozen `MissionStorePort` is
  synchronous, so an async ORM behind it demands loop-bridging anti-patterns and cannot be adopted
  without superseding ADR 0042 (§0).
- **Sync SQLAlchemy Core + Alembic (the ADR-0012-fidelity compromise).** Considered as the way to keep
  "SQLAlchemy + Alembic + no raw SQL" while dropping only "async." Rejected as the V2 standard: it
  would fracture V2 into two persistence idioms (the Retrieval Engine already runs sync psycopg3 + raw
  parameterized SQL in production), add a heavy dependency and a second migration runtime the rest of
  V2 does not carry, and buy nothing the frozen sync port can use. §0 adopts the single direction V2
  already follows instead; ADR 0012 is reconciled by a separate amendment, not redefined by this ADR.
- **Extend `MissionStorePort` (add versioned save / list / delete) to do this "properly."** Rejected
  here by definition: the port is frozen (ADR 0042). Such changes are future ADRs that supersede 0042,
  not implementation details of this one.
- **Put the adapter inside `mission-engine` behind an extra.** Rejected: the engine's purity test
  forbids a driver anywhere in its tree; the standalone package is the intended split.
- **A shared `v2-persistence` package now.** Rejected: premature abstraction with a single durable
  aggregate; extract when a second one appears.

---

## Future ADRs

- **Uniform `IdempotencyConflict` across all adapters.** If the project ever decides that *every*
  `MissionStorePort` adapter (including the in-memory reference adapter) must raise
  `IdempotencyConflict` on a duplicate `(tenant_id, idempotency_key)`, that is an **ADR-level change
  to the frozen `MissionStorePort` contract (ADR 0042) and to the frozen Mission Engine** — not a
  Mission Store implementation change. It would require: a new ADR amending the port's behavioural
  contract; a new home for `IdempotencyConflict` that `mission-engine` can import without a cycle
  (which changes its current `MissionStoreError` parentage); and a modification to the frozen
  `InMemoryMissionStore`. Until such an ADR exists, `IdempotencyConflict` remains a durable-store
  defense-in-depth guarantee (§9), and the portable cross-adapter contract is engine-level
  find-before-create.

---

## Implementation Status

The Mission Store is delivered as vertical slices — each built end-to-end, tested, reviewed, and
frozen before the next. Status as of 2026-07-17:

- **Slice 1 — persistence round-trip — ✅ Frozen.** `PostgresMissionStore` implementing the three
  frozen `MissionStorePort` methods (`save` / `get` / `find_by_idempotency_key`) over a state-snapshot
  row (§5–§7): typed indexed scoping/lifecycle columns + JSONB nested collections, tenant isolation in
  SQL, cross-tenant overwrite refusal, faithful aggregate round-trip (incl. plan-version history),
  store-managed `revision` and `payload_schema_version` written from the first migration, a pure
  driver-free codec, and lazy psycopg import.
- **Slice 2 — idempotency completion — ✅ Frozen.** A `save` colliding on `(tenant_id,
  idempotency_key)` from a *different* mission is wrapped from the raw driver uniqueness violation into
  a typed `IdempotencyConflict` (§9, §11). Portable semantics stay engine-level find-before-create;
  `IdempotencyConflict` is the Postgres-specific defence-in-depth guarantee.
- **Slice 3 — Unit of Work — ✅ Frozen.** A caller-owned `UnitOfWork` that owns a single flat
  transaction over one connection — `BEGIN` / `COMMIT` / `ROLLBACK` and the connection lifecycle
  (owned vs. injected; injected `autocommit=True` rejected immediately) — so several store operations
  commit atomically (§8). It owns **no stores** (exposes only `begin`/`commit`/`rollback`/`connection`/
  `close` + context manager); the store still never commits or rolls back. Verified end-to-end against
  PostgreSQL (read-your-writes, invisibility before commit, visibility after commit, atomic rollback
  incl. an `IdempotencyConflict` inside the transaction). **No change to `MissionStorePort`, the
  Mission Engine, or the `PostgresMissionStore` contract.**
- **Slice 4 — Transactional Outbox — ✅ Frozen.** Governed by the approved design **ADR 0043-S4
  Rev.3** (an inline design revision recorded in this ADR, not a separate file). An **`OutboxSink`** (an `EventBus` *subscriber*, not the bus)
  writes each emitted `DomainEvent` into an `outbox` table on the **same connection and same
  `UnitOfWork` transaction** as the mission `save`, so a mission's state change and its events commit
  atomically (Invariants I1/I2). An **`OutboxRelay`** drains committed-but-unpublished rows in
  insertion order onto a **Delivery Bus** via an **`OutboxPublisher`** — at-least-once (I6); an
  unregistered event raises **`UnsupportedEventType`** and the row is left unpublished (I8), with no
  generic fallback. Per-transition only (no whole-run); `attempts`/retry/DLQ/pruning/scheduling/
  multi-worker are deferred. Verified end-to-end against PostgreSQL (atomic capture, whole-transition
  rollback on any event-write failure, in-order drain, at-least-once, `UnsupportedEventType`). **No
  change to `MissionStorePort`, `UnitOfWork`, the Mission Engine, or the `EventBus` protocol.** All
  eleven invariants (I1–I11) hold.

## Next Planned Slice

- **None planned.** Slices 1–4 complete the durable Mission Store behind the frozen `MissionStorePort`.
  Any further work (retry/dead-letter, pruning, multi-worker relay, enforced OCC) is a future ADR, not
  designed or decided here.
