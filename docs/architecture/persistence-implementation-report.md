# Persistence Layer — Implementation Report

> **Scope.** This report documents the implementation of the Infrastructure / Persistence
> layer (`packages/persistence/grc_persistence/`) — the outermost adapter that turns the
> Domain repository interfaces and the Application's `UnitOfWork` port into concrete,
> PostgreSQL-backed behaviour. It is a companion to
> [`PROJECT_STATE.md`](../../PROJECT_STATE.md), [`CLAUDE.md`](../../CLAUDE.md), and
> [`PROJECT_SKELETON.md`](./PROJECT_SKELETON.md).
>
> **Status:** complete and verified. **Date:** 2026-06-26.
>
> **Constraint honoured:** the Domain (`grc_domain`) and Application (`grc_services`) layers
> were **not modified**. All work is additive, inside `packages/persistence`, plus two
> tooling/doc edits noted in §5.

---

## 1. Goals and constraints

The task was to implement the complete persistence layer to the project's Definition of
Done (CLAUDE.md §24), satisfying these hard requirements:

- Do not modify the Domain or Application layers.
- Keep **all** Domain↔ORM translation exclusively inside a `mappers` package.
- Repositories perform only: query construction, persistence orchestration, optimistic
  concurrency, aggregate tracking, child synchronization, and cache hooks.
- Use SQLAlchemy 2.x Async, asyncpg, Alembic, PostgreSQL.
- Implement every repository interface and `SqlAlchemyUnitOfWork`.
- Implement the transactional outbox as the single source of integration events.
- Implement the `RepositoryCache` abstraction with `NullRepositoryCache`.
- Implement diff-based child synchronization using stable identifiers.
- Implement the `contracts` package as designed.
- Add the complete initial Alembic migration.
- Add integration tests for repository round-trip, tenant isolation, optimistic-concurrency
  conflicts, diff-based child synchronization, and the transactional outbox.
- Run formatting, linting, import verification, and all tests until green.

---

## 2. Architecture and key decisions

### 2.1 Layering and dependency direction

The persistence layer sits at the bottom of the inward-pointing dependency graph
(CLAUDE.md §6). It **implements** the ports declared by inner layers and therefore depends
on them: it imports the domain repository ABCs and entities from `grc_domain`, and the
`UnitOfWork` ABC, ports, and exceptions from `grc_services`. Nothing in domain or
application imports the persistence layer; it is injected at a (future) composition root.

### 2.2 The `contracts` package — the layer's seams

`grc_persistence/contracts/` defines the stable abstractions the rest of the layer depends
on, so each moving part can evolve independently:

| Contract | Purpose |
|---|---|
| `AggregateMapper[DOMAIN, ORM]` | The Domain↔ORM translation contract: `to_orm` (insert), `update_orm` (root scalars only), `to_domain` (rebuild). |
| `ChildMapper[CHILD, CHILD_ORM]` | Per-child translation + a **stable identity** used as the diff key, with `position` for ordering. |
| `RepositoryCache` / `NullRepositoryCache` / `CacheKey` | Optional read-through cache; the null object is the default. Keys are `entity:tenant:identity` so a cache can never cross tenants. |
| `Outbox` / `IntegrationEvent` | The transactional-outbox seam and the immutable integration-event envelope. |
| `AggregateTracker` (Protocol) | How repositories register touched aggregates so the UoW can collect their recorded domain events. |

### 2.3 Mappers — the single home of translation

Every Domain↔ORM and Domain→integration-event conversion lives in `mappers/`. Repositories
delegate all field-level work to a mapper and never read a domain field to write an ORM
column (or vice versa) themselves. `mappers/_common.py` holds reusable value-object codecs
(citations, framework-control refs, semantic versions, risk scores, coverage summaries,
proposed actions, audit actor/trace/AI-call, …). Aggregates are reconstructed with the
plain dataclass constructor (not the domain factory methods), so **loading never re-emits
domain events**. `mappers/events.py` serializes a recorded domain event into a JSON-safe
payload and wraps it in an `IntegrationEvent`, attributing it to the owning tenant (the
`Organization` aggregate is recognised as its own tenant).

### 2.4 ORM models

20 tables: 13 bounded-context aggregate tables, the two Mission child tables
(`mission_steps`, `mission_approval_gates`), and `outbox_messages`. Design choices:

- **Enums and typed identifiers are stored as strings**; the mapper converts on the
  boundary. This avoids brittle DB enum types and keeps migrations stable when enum values
  evolve.
- **Structured value-object collections are stored as JSON** via a portable `JSONColumn`
  type that renders as `JSONB` on PostgreSQL and the generic `JSON` type elsewhere. Only the
  Mission aggregate uses child tables (it is the one aggregate with separately-addressable,
  ordered, mutable children); other nested collections are immutable-ish value objects best
  kept inline as JSON.
- **Optimistic concurrency** is a `version` integer column on every aggregate root, wired as
  SQLAlchemy's `version_id_col` via an `AggregateRootMixin` (the frameworks table names it
  `row_version` to avoid colliding with its domain `version_label`).
- A deterministic constraint-naming convention keeps Alembic diffs stable.

### 2.5 Repositories

A generic `SqlAlchemyAggregateRepository[D, M]` base centralizes the mechanics so each
concrete repository contains essentially only its queries:

- query construction (`_fetch_one`, `_fetch_all`, `_get_by`, `_list_by`);
- persistence orchestration (`_insert`, `_update`);
- optimistic concurrency (loads the managed row via `session.get` so the version pinned at
  read time is authoritative, then lets `version_id_col` guard the UPDATE);
- aggregate tracking (registers every loaded/added/saved aggregate root with the UoW);
- child synchronization (delegated to `repositories/_sync.py`);
- cache hooks (consult on read, invalidate on write).

All 17 repositories are implemented: the 16 declared on the application `UnitOfWork` ABC
plus `MissionRepository`. The append-only `AuditRecordRepository` is implemented directly
(no update path, no event tracking), matching the domain's no-setter design.

### 2.6 Diff-based child synchronization

`repositories/_sync.py::sync_children` reconciles an ORM child collection to match the
desired domain children, keyed on each child's **stable id**: children present only in the
domain are inserted, those present in both are updated in place, and those present only in
the ORM are removed (delete-orphan cascade). Order is preserved via a `position` column.
The Mission repository applies this to both `steps` and `approval_gates` on `save`.

### 2.7 Unit of Work

`SqlAlchemyUnitOfWork` realizes the application's `UnitOfWork` port:

- one `AsyncSession` per activation, every repository exposed lazily and bound to it;
- **aggregate tracking** — repositories register touched roots; `collect_new_events()`
  pulls and flattens their recorded domain events (and remembers them for the outbox);
- **transactional outbox** — on `commit()` the collected events are translated into
  `IntegrationEvent`s and written to `outbox_messages` **in the same transaction** as the
  state change, then the session commits;
- **error translation** — `StaleDataError` → `ConcurrencyError`, `IntegrityError` →
  `ConflictError`;
- **session hygiene** — `__aexit__` is overridden so the read-only query-handler path
  (which never calls `commit()`) still rolls back and closes its session.

It also exposes a `missions` property even though the abstract port omits it (see §7), since
the concrete UoW may provide more than the port's minimum.

### 2.8 Transactional outbox as the single source of integration events

`SqlAlchemyOutbox.enqueue` stages `outbox_messages` rows on the current session; the UoW
flushes and commits them with the aggregate change, so an event is persisted **iff** its
state change was. A rejected commit (e.g. an optimistic-concurrency conflict) leaves no
outbox row. Publication to a bus is deliberately **out of scope** here — a downstream relay
(roadmap #2) reads unpublished rows (`published_at IS NULL`) and forwards them, giving
at-least-once delivery with exactly-once capture and a single source of truth.

### 2.9 Test engine strategy

Production targets PostgreSQL + asyncpg; the Alembic migration emits `JSONB`. The
integration suite runs against an async **SQLite** engine (aiosqlite) built from the same
`Base.metadata`, which is hermetic and needs no external services. The same tests run
against PostgreSQL by setting `TEST_DATABASE_URL`. The portable `JSONColumn` type and the
string-based enums/ids make the models dialect-portable; the migration is likewise portable
and is exercised on SQLite by the migration test.

---

## 3. Files created

### Package configuration
- `packages/persistence/pyproject.toml` *(modified — see §5)*
- `packages/persistence/alembic.ini`

### `grc_persistence/` root
- `__init__.py` *(modified — lazy `SqlAlchemyUnitOfWork` export)*
- `unit_of_work.py`
- `outbox.py`

### `contracts/`
- `__init__.py`, `mapper.py`, `cache.py`, `outbox.py`, `tracking.py`

### `db/`
- `__init__.py`, `base.py`, `types.py`, `engine.py`

### `models/` (20 tables)
- `__init__.py`, `tenancy.py`, `workspace.py`, `frameworks.py`, `controls.py`,
  `policies.py`, `risks.py`, `assessments.py`, `evidence.py`, `knowledge.py`,
  `reporting.py`, `platform.py`, `missions.py`, `audit.py`, `outbox.py`

### `mappers/`
- `__init__.py`, `_common.py`, `events.py`, `tenancy.py`, `workspace.py`, `frameworks.py`,
  `controls.py`, `policies.py`, `risks.py`, `assessments.py`, `evidence.py`, `knowledge.py`,
  `reporting.py`, `platform.py`, `missions.py`, `audit.py`

### `repositories/` (17 repositories)
- `__init__.py`, `base.py`, `_sync.py`, `tenancy.py`, `workspace.py`, `frameworks.py`,
  `controls.py`, `policies.py`, `risks.py`, `assessments.py`, `evidence.py`, `knowledge.py`,
  `reporting.py`, `platform.py`, `missions.py`, `audit.py`

### `migrations/`
- `__init__.py`, `env.py`, `script.py.mako`, `versions/0001_initial_schema.py`

### `tests/`
- `__init__.py`, `conftest.py`, `_builders.py`, `test_repository_round_trip.py`,
  `test_tenant_isolation.py`, `test_optimistic_concurrency.py`,
  `test_child_synchronization.py`, `test_transactional_outbox.py`, `test_migration.py`

---

## 4. Files modified (outside the new package)

- **`packages/persistence/pyproject.toml`** — added dependencies (`grc-domain`,
  `grc-services`, `SQLAlchemy>=2.0`, `alembic>=1.13`), a `postgres` extra (`asyncpg`,
  `greenlet`), a dev group (`aiosqlite`, `pytest`, `pytest-asyncio`, `greenlet`), and uv
  workspace sources.
- **`pyproject.toml` (repo root)** — added a `[tool.ruff.lint.per-file-ignores]` entry so
  the generated Alembic migration is exempt from `E501` (its verbatim `create_table`/index
  calls are kept diff-able against future autogenerated revisions). No other tooling change.
- **`packages/persistence/grc_persistence/__init__.py`** — replaced the eager top-level
  import with a lazy `__getattr__` export of `SqlAlchemyUnitOfWork` (importing the package
  no longer forces the whole ORM/engine stack).
- **`packages/persistence/tests/.gitkeep`** — removed (the directory now has real content).

> **Not modified:** `packages/domain/**` and `packages/services/**` are byte-for-byte
> unchanged.

---

## 5. Migration

`versions/0001_initial_schema.py` (revision `0001_initial_schema`, down-revision `None`)
creates all 20 tables with their foreign keys, indexes, the composite primary key for
`frameworks (id, version_label)`, and the optimistic-concurrency columns. It was produced
by Alembic autogenerate against `Base.metadata` (guaranteeing fidelity) and then refined to
use the shared `JSONColumn` type for every JSON column — which (a) renders `JSONB` on
PostgreSQL and `JSON` on SQLite, (b) removed an autogen `NameError` (`astext_type=Text()`
emitted without an import), and (c) de-duplicated the column type into one reference.

`migrations/env.py` reads the database URL from `ALEMBIC_DATABASE_URL` / `DATABASE_URL`
(never from code or the ini), supports offline SQL rendering for CI validation, and uses
`Base.metadata` as the autogenerate target.

**Verified:** `alembic upgrade head` on SQLite produces a schema whose tables and columns
exactly match `Base.metadata` (20/20 tables); `downgrade base` drops everything; offline
`upgrade head --sql` against the `postgresql+asyncpg` dialect renders `JSONB` columns.

---

## 6. Tests and results

All tests run in an isolated Python 3.12 virtual environment with SQLAlchemy 2.0.51,
aiosqlite, and Alembic, against a per-test file-backed async SQLite database.

| File | Cases | What it proves |
|---|---|---|
| `test_repository_round_trip.py` | 5 | Persist→reload preserves state for a tenant root, a JSON-collection root, a value-object root, the composite-key Framework, and the child-bearing Mission; plus a load→mutate→save update path. |
| `test_tenant_isolation.py` | 3 | Cross-tenant `get` returns `None`, cross-tenant list is empty, and outbox rows carry the owning tenant. |
| `test_optimistic_concurrency.py` | 3 | Two units of work that load the same aggregate and both write — the later commit raises `ConcurrencyError`; the winner's state survives; works for both a childless aggregate and Mission. |
| `test_child_synchronization.py` | 3 | Add/update/remove of Mission children by stable id, order preservation on reorder, and idempotent re-save. |
| `test_transactional_outbox.py` | 4 | Events become outbox rows with correct type/tenant/payload, rows start unpublished, a rejected commit writes **no** outbox row, and the row count matches the collected events. |
| `test_migration.py` | 1 | `upgrade head` builds exactly the model schema and `downgrade base` removes it (drift guard). |

**Result:** **19 passed.** `ruff check` clean, `black --check` clean, **59 modules import**
cleanly.

---

## 7. Bugs found and fixed

### 7.1 Optimistic concurrency silently defeated by the weak identity map *(critical)*

SQLAlchemy's session identity map holds objects **weakly**. The repository mapped each
loaded ORM row to a domain object and dropped its reference to the ORM row, so the row could
be garbage-collected; a later `save()` would then re-read the **current** version from the
database and the `version_id_col` guard would match — silently allowing a lost update. This
was caught while making the concurrency test deterministic. **Fix:** the repository now
pins every loaded ORM row for the unit of work's lifetime and retrieves the managed row for
updates via `session.get` (identity-map-first, no refreshing SELECT), so the version read at
load time stays authoritative. Conflict detection is now deterministic (verified across many
trials on both SQLite and the production access pattern).

### 7.2 Session leak on the read-only path *(correctness)*

Query handlers open the UoW as a context manager but never call `commit()`; the abstract
`__aexit__` only rolled back on exception, so a successful read left the session open.
**Fix:** `SqlAlchemyUnitOfWork.__aexit__` rolls back and closes any still-open session.

### 7.3 Autogenerated migration `NameError` *(correctness)*

Alembic autogenerate emitted `postgresql.JSONB(astext_type=Text())` with `Text` unqualified
and unimported. **Fix:** replaced every JSON column in the migration with the shared
`JSONColumn` type (also DRYs the migration and makes it dialect-portable).

---

## 8. Compliance check

- **CLAUDE.md §6 (dependencies inward):** persistence depends only on domain + services;
  nothing depends back on it. ✓
- **§9/§14 (Tools call Services; Services operate the Domain; repository pattern):** the
  persistence layer implements the repository interfaces and the transaction boundary; no
  ORM leaks above it. ✓
- **§16 (EDA / outbox):** transactional outbox is the single source of integration events. ✓
- **§19 (audit):** `AuditRecord` persistence is append-only, no update/delete. ✓
- **§20 (multi-tenancy):** every read/list/save is tenant-scoped, default deny. ✓
- **§22 (standards):** fully type-hinted, validated at boundaries, no secrets in code (DB URL
  from env), no raw SQL string interpolation. ✓
- **ADR 0011 (DDD boundaries) / 0012 (Postgres+pgvector) / 0014 (security & multitenancy):**
  honoured; pgvector deferred to the RAG layer (no embeddings in these aggregates). ✓
- **PROJECT_SKELETON §5 (`persistence/` = repositories + migrations, no ORM leaks upward):**
  matched, expanded with `contracts/`, `db/`, `models/`, `mappers/`. ✓

---

## 9. Technical debt and known limitations

1. **Application `UnitOfWork` ABC omits `missions`.** The mission use cases call
   `uow.missions`, and the concrete UoW provides it, but the abstract port (in
   `grc_services`) does not declare it. Fixing this requires an application-layer change
   (and ideally an ADR note) and was out of scope here. Tracked for the composition-root
   work.
2. **`Evidence.list_for_control` filters in memory.** The control linkage is a JSON id-set;
   the query scopes by tenant in SQL and filters membership in Python. Future: a JSONB GIN
   index or a dedicated link table.
3. **Optimistic concurrency is unit-of-work-scoped.** It detects conflicts between
   concurrent transactions, not the stateless read-in-request-A / write-in-request-B
   pattern. A stateless API should carry the aggregate `version`/etag in its DTOs and pass it
   back on write.
4. **`mypy --strict` not yet verified** on the package (the run was interrupted). The code is
   fully type-hinted; a strict pass against the SQLAlchemy plugin should be added to CI.
5. **pgvector tables not created.** None of these aggregates store embeddings; the RAG layer
   will add the vector tables and extension in its own migration.
6. **Tests default to SQLite.** Faithful for round-trip, tenancy, child-sync, outbox, and
   the now-deterministic OCC case; CI should also run them against PostgreSQL via
   `TEST_DATABASE_URL` to exercise `JSONB` and Postgres isolation semantics.
7. **Tenant column naming.** `organization_id` is used as the tenant-scoping column (the
   tenant aggregate is `Organization`), a deliberate realization of CLAUDE.md §21's generic
   `tenant_id`. Worth an explicit note in the naming conventions if a reviewer expects
   `tenant_id`.

---

## 10. Future improvements

- **Outbox relay + `EventDispatcher`** (`packages/events`): poll/stream unpublished rows to
  the bus, mark `published_at`, with idempotent at-least-once delivery; wire the injected
  dispatcher so it does not double-publish.
- **Composition root**: engine/session-factory construction, dependency injection of the
  UoW + dispatcher + authz into the application services, and Alembic migration execution in
  CI/CD against PostgreSQL.
- **Read-side optimizations**: a concrete `RepositoryCache` (e.g. Redis) for hot, slow-moving
  aggregates (framework definitions) returning disconnected copies; JSONB GIN indexes for
  id-set membership queries; pagination on list methods.
- **Connection & resilience**: pool tuning, statement timeouts, and retry/backoff around
  transient transaction errors.
- **Stronger concurrency UX**: surface the conflicting version in `ConcurrencyError` and
  thread an etag through DTOs for stateless OCC.
- **mypy strict in CI** for the persistence package, and a Postgres service in the test
  matrix.

---

*Companion to PROJECT_STATE.md and CLAUDE.md. Propose architectural changes via ADR + PR.*
