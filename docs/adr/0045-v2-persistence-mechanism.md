# ADR 0045: V2 persistence mechanism — reconciling ADR 0012 (sync psycopg3 + raw parameterized SQL for V2)

- Status: **Accepted**
- Date: 2026-07-17
- Deciders: Architecture, Product Owner
- Related: CLAUDE.md §4 (tech stack), §12 (RAG/pgvector), §14 (services/repository), §20 (security);
  **ADR 0012 (PostgreSQL + pgvector — amended in scope by this ADR)**, 0008 (knowledge & RAG),
  0038 (pipeline-contracts), 0042 (Mission Engine — the frozen synchronous ports), 0043 (Mission
  Store — where this reconciliation was promised, §0)

---

## Context

The project carries a **formal contradiction** between what an ADR mandates and what V2 actually
builds — the kind of drift that misleads a team returning to the project or receiving a handoff.

- **[ADR 0012](./0012-postgres-pgvector.md) (Accepted)** chose PostgreSQL + pgvector as the primary
  store, and — in the same decision — mandated the **access mechanism**: "Access is via **SQLAlchemy
  (async)** with **Alembic** migrations … no raw SQL string interpolation; repositories isolate data
  access."
- **V2, in production, does the opposite mechanism.** The Retrieval Engine's pgvector adapter
  (Phase 9B) and the Mission Store ([ADR 0043](./0043-v2-mission-store.md), Slices 1–4, frozen) both
  run **synchronous psycopg3 + raw, fully parameterized SQL behind Ports & Adapters**, with
  hand-written ordered `.sql` migrations and a `schema_migrations` ledger — **not** async SQLAlchemy,
  **not** Alembic.

[ADR 0043 §0](./0043-v2-mission-store.md) adopted the V2 mechanism and **explicitly deferred the
reconciliation to "a separate ADR amendment to ADR 0012"** so the project would end with a single,
coherent persistence policy. **This is that ADR.** It writes no code; it records the decision that
V2 has already been built on, and removes the contradiction.

> **What is *not* in question.** ADR 0012's *primary decision* — PostgreSQL + pgvector as the single
> source of truth, hybrid retrieval, `tenant_id` filtering next to the vectors, the vector store
> behind an interface — **stands unchanged and reaffirmed.** This ADR narrows only the **access /
> migration mechanism** clause of ADR 0012, and only for V2.

---

## Decision

1. **ADR 0012's store choice stands, unchanged.** PostgreSQL is the primary relational store and
   pgvector holds embeddings, co-located, with tenant-scoped hybrid retrieval. This ADR does not
   touch that.

2. **ADR 0012's *access-mechanism* clause (async SQLAlchemy + Alembic + "no raw SQL") is recorded as
   V1-scoped.** It remains the guidance for V1 (`apps/api` and the V1 `aigrc` database) where it is
   already in use; it is **not** the V2 mechanism.

3. **V2 standardizes on: synchronous psycopg3 + raw, fully parameterized SQL, behind Ports &
   Adapters, with hand-written ordered `.sql` migrations + a `schema_migrations` ledger.** Every V2
   persistence adapter follows this one mechanism (the Retrieval Engine and the Mission Store already
   do). There is **one** V2 persistence idiom, not two.

Why this is the correct — not merely convenient — mechanism for V2 (condensed from ADR 0043 §0):

- **The frozen ports are synchronous.** `MissionStorePort` (ADR 0042) and every V2 core seam are
  `def`, not `async def`. An async ORM behind a sync port needs per-call event-loop bridging
  (`asyncio.run` / `run_in_executor`) — an anti-pattern — and cannot be adopted without superseding
  the frozen ADR 0042. Async SQLAlchemy is off the table **by construction**, not preference.
- **V2's concurrency boundary is process/worker-level, above the core.** The pure, framework-free V2
  computation core is synchronous; the async boundary (FastAPI) sits *above* it and invokes it off
  the event loop. Pushing `asyncio` into the core would invert that boundary and couple pure domain
  packages to an event loop — exactly what Ports & Adapters and domain purity (CLAUDE.md §15) exist
  to prevent.
- **Ports & Adapters already deliver ADR 0012's *repository intent*.** ADR 0012 wanted "repositories
  isolate data access." The **Port is that boundary**: domain/engine code depends only on the
  `Protocol`; all SQL lives in one swappable adapter. Same goal, lighter mechanism.
- **Parameterized SQL already delivers ADR 0012's *anti-injection intent*.** "No raw SQL string
  interpolation" exists to eliminate injection. V2 binds **every value** through driver placeholders
  (`%(name)s`); the only interpolated tokens are static identifiers (table names) from **code
  constants, never input**. The injection surface is zero — the rule's purpose is met, the mechanism
  differs.
- **Precedent, uniformity, and dependency minimalism.** The Retrieval Engine already runs this idiom
  in production; standardizing on it keeps V2 coherent and avoids adding SQLAlchemy Core + Alembic (a
  heavy dependency and a second migration runtime) for no benefit a synchronous port can use.

4. **ADR 0012 gains an "Amended-by" pointer** to this ADR (a cross-reference in its header/Related —
   its Decision text is left immutable, per the ADR process). Anyone reading ADR 0012 is routed here
   for the V2 mechanism.

---

## Consequences

**Positive**
- The formal contradiction is **resolved**: one persistence policy, scoped per major version (V1:
  async SQLAlchemy + Alembic; V2: sync psycopg3 + raw parameterized SQL + `.sql` migrations).
- A returning or receiving team reads a coherent story instead of an ADR that contradicts the code.
- No code changes — V2 already conforms; this ADR ratifies reality.

**Negative / costs**
- Two persistence idioms **coexist across major versions** (V1 vs V2). This is deliberate and
  bounded: V1 is not being rewritten, and V2 will not adopt the V1 idiom. The split is by version,
  not within a version.
- The anti-injection guarantee now rests on the discipline "**values are always parameterized;
  interpolated identifiers come only from code constants**" — enforced by the store SQL-construction
  tests, not by an ORM. Recorded so the guarantee is explicit, not assumed.

## Alternatives considered

- **Keep ADR 0012 verbatim for V2 (async SQLAlchemy + Alembic).** Rejected: impossible behind the
  frozen synchronous `MissionStorePort` without superseding ADR 0042; would invert V2's async
  boundary and break domain purity.
- **Rewrite ADR 0012's Decision in place.** Rejected: ADRs are immutable once Accepted (repo
  process); the correct move is a new ADR that amends scope + a pointer, which this is.
- **Sync SQLAlchemy Core + Alembic (keep the ORM, drop only async).** Rejected as the V2 standard:
  it would fracture V2 into two persistence idioms *within one version* (the Retrieval Engine already
  runs raw psycopg3), add a heavy dependency and a second migration runtime, and buy nothing the
  synchronous ports can use.
- **A brand-new store ADR superseding 0012 entirely.** Rejected as heavier than needed: 0012's
  *store* decision is correct and unchanged; only its *mechanism* clause needed version-scoping.
