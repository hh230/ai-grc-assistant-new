# ADR 0017: Policy Intelligence AI runtime — real Tool Registry, roster extension, and an
apps/web-Postgres persistence bridge

- Status: Accepted
- Date: 2026-07-04
- Deciders: Product Owner (via direct working session), Architecture
- Related: CLAUDE.md §9, §10, §11, §20; ADR 0004, 0005, 0006, 0012, 0013; ADL-0007, ADL-0008

## Context

Two things were true before this change. First, `packages/tools` was a scaffold only — the
Tool contract and Registry described in ADR-0006 had never been implemented. Second, the
platform has two separate, disconnected persistence tracks: `packages/persistence` (a
SQLAlchemy/Postgres binding for the pure `packages/domain`/`packages/services` roadmap track,
gated on ADL-0008 and not selectable at runtime) and `apps/web` (a self-contained Next.js app
with its own live PostgreSQL+pgvector schema, real auth, and a working policy
authoring/approval workflow — the actual shipped product per its own README, though
ADL-0007 still labels it an out-of-roadmap prototype).

We are building a Policy Intelligence capability (Policy Hunter, Policy Analyst, Policy
Builder agents — regulatory-obligation discovery/classification plus internal coverage
analysis) that needs a real Tool Registry, a real database, and a real AI runtime process to
serve from. Building it inside `apps/web` would embed AI orchestration, Tool execution, and
scheduled regulatory polling into the Next.js app — exactly the coupling CLAUDE.md's layered
architecture (§5) is meant to prevent. Building it against `packages/persistence`'s schema
would target a database no real user's data lives in. Standing up a *third*, independent
database for Policy Intelligence would violate CLAUDE.md §20 (one source of truth per tenant)
and directly contradict the explicit instruction not to duplicate the database or create a
parallel product.

## Decision

We will:

1. Implement `packages/tools/grc_tools` for real: a `Tool` contract (typed Pydantic I/O, a
   `grc_domain.platform.ToolDescriptor` for governance metadata, an async `run` returning a
   `ToolOutcome` carrying confidence/citations/model/usage), a `ToolContext` naming the six
   CLAUDE.md §9 callers, and a `ToolRegistry` that authorizes, validates, executes, and
   unconditionally audits every invocation — including denied and failed ones.
2. Add a new outer package, `packages/persistence-web`, that implements read/write adapters
   **against apps/web's existing live PostgreSQL schema** (via asyncpg) — not a new database,
   and not `packages/persistence`'s separate SQLAlchemy schema. It provides the concrete
   `ToolInvocationRecorder` (writing to a new `ai_tool_invocations` audit table), a
   `PolicyRepository` (reads `policies`, and can insert AI-authored `draft` rows — never
   `in_review`/`published`, which stay behind apps/web's existing human-gated
   `publish` permission check), and a `PolicyMissionStore` (a lightweight Mission record —
   `policy_missions`/`policy_mission_steps` — scoped to Policy Intelligence runs, not the full
   generic Workflow Engine).
3. Stand up `apps/api` as the real AI runtime for this capability: it hosts the Tool Registry,
   the Orchestrator, and (in a later phase) the Policy Hunter/Analyst/Builder agents and
   scheduled regulatory-source polling (`apps/worker`). `apps/web` keeps UI, auth, dashboards,
   and its existing self-contained features; it does not gain new embedded AI logic. Because
   an asyncpg connection pool must be created inside the event loop that uses it (and
   `apps/api`'s composition root is built synchronously, before any loop-bound tests/lifespan
   run), the web-Postgres connection is created lazily on first use and memoized on
   `app.state`, independent of the existing `store_backend` selector (which continues to gate
   only the unrelated, still-`packages/persistence`-gated command/query bus routers).
4. Bridge dev authentication rather than build new auth: `apps/api`'s existing
   `StaticTokenAuthenticator` now recognizes all seven of `apps/web`'s seeded dev bearer
   tokens (not just `owner`'s), configured via `API_AUTH_TOKENS`, so every dev role can call
   the AI runtime under the same `Principal` shape both sides already agree on
   (`grc_domain.tenancy.enums.UserRole`).
5. New database migrations for this capability (`ai_tool_invocations`, policy AI-provenance
   columns, `policy_missions`/`policy_mission_steps`) are authored and applied exclusively
   through `apps/web/lib/db/migrations/` — the one migration path for the one database.

## Consequences

**Positive**
- One database, one migration path, no parallel product — `apps/api`/`apps/worker` become
  real, working consumers of the data that already exists, rather than a disconnected demo.
- The Tool Registry is now load-bearing infrastructure, not aspirational documentation —
  every future Tool (Policy Intelligence or otherwise) has a real contract to implement
  against, with audit logging free by construction.
- `packages/persistence`'s gated ADL-0008 schema is untouched — this work does not reopen
  that decision or inherit its debt (the Application/Services layer's 0-test, contract-hole
  status per PROJECT_STATE.md §5).

**Negative / costs**
- A second, narrower persistence adapter now exists alongside `packages/persistence`
  (`packages/persistence-web`), each targeting a different schema for different subsystems —
  a reader of the codebase must know which one a given feature uses. This is the accepted
  first step of reconciling the ADL-0007/ADL-0008 fork, not the end state.
- The lazy, per-process-memoized asyncpg pool (rather than eager lifespan-managed startup) is
  a direct consequence of the existing test harness building `app.state` synchronously and
  bypassing `lifespan` (documented in `apps/api/src/grc_api/app.py`). If that harness
  constraint is ever lifted, this wiring should move to `lifespan` for conventional
  startup/shutdown symmetry.
- Static per-user dev bearer tokens are not real production authentication. Production still
  requires `apps/web` to mint (and `apps/api` to verify) a real per-request credential
  (e.g. a short-lived signed token), tracked as follow-up, not solved here.

## Alternatives considered

- **Build Policy Intelligence inside `apps/web`.** Rejected per explicit direction: it would
  embed Tool execution, multi-agent orchestration, and regulatory connectors/scheduled jobs
  into the Next.js app, coupling AI runtime concerns to the UI/auth/dashboard layer.
- **Target `packages/persistence`'s schema instead of apps/web's.** Rejected: no real tenant
  data lives there; doing so would build Policy Intelligence against a database nothing else
  uses, and would implicitly force resolving ADL-0008 as a side effect of an unrelated
  feature.
- **Stand up a third, Policy-Intelligence-only database.** Rejected explicitly: duplicates
  the database and creates a parallel product, the two things this ADR is instructed to avoid.
- **Route Policy Builder's writes through `grc_services.policies`' existing CQRS command
  handlers.** Rejected for now: those handlers require the full `UnitOfWork` contract (16+
  repositories, with a known, tracked contract hole — ADL-0006 — and zero tests per
  PROJECT_STATE.md §5). Reusing them would import that debt into a new feature; `PolicyRepository`
  in `packages/persistence-web` instead writes directly to the same `policies` table apps/web's
  own `lib/policies/service.ts` already serves from, with an identical `status='draft'` +
  existing-human-gate invariant.
