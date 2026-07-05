# ADR 0023: Policy Intelligence frontend — a server-side proxy to `apps/api`, not a second implementation

- Status: Accepted
- Date: 2026-07-06
- Deciders: Product Owner (via direct working session), Architecture
- Related: CLAUDE.md §5, §6, §18, §20, §22; ADR 0013, 0017, 0022

## Context

PI-P5 (ADR-0022) exposed Policy Hunter's and Policy Analyst's Tools over HTTP from
`apps/api`. PI-P6 needs a workspace UI for them in `apps/web` — obligations, coverage gaps,
and per-policy quality review. `apps/web` is a separate, self-contained Next.js application
with its own Postgres access layer (`lib/<feature>/repository.ts`) for its own features
(policies, risks, evidence, ...); it has never called `apps/api` for anything. Two paths
existed: reimplement the coverage-gap/quality-review logic in TypeScript against the same
Postgres tables, or call the FastAPI endpoints PI-P5 already built and audits.

The reimplementation path was never seriously on the table — it would duplicate
`grc_policy_hunter`/`grc_policy_analyst`'s deterministic matching engines in a second
language, immediately risking drift between the two, and would bypass the Tool Registry's
unconditional audit trail (CLAUDE.md §19) entirely for every call made from the UI. The real
question was *how* to reach `apps/api` from `apps/web` without breaking either app's existing
security model: `apps/web` authenticates its own users with its own session JWT and never
exposed `apps/api`'s bearer-token scheme to the browser, and `apps/api` only accepts its own
`API_AUTH_TOKENS` bearer tokens, not `apps/web`'s session cookie.

The answer already existed in the code, unused: `apps/web`'s session payload
(`lib/auth/session.ts`) and `ActorContext` (`lib/auth/actor.ts`) both carry an `apiToken`
field, documented since PI-P0/ADR-0017 as "used when proxying to the FastAPI API," and every
seeded dev user's `apiToken` is literally one of `apps/api`'s configured `API_AUTH_TOKENS`
entries (same tenant, same role). No route had ever actually read it.

## Decision

We will:

1. Add `lib/policyIntelligence/service.ts`, a Node-only module (server components and route
   handlers only) that calls `apps/api`'s `/api/v1/policy-intelligence/*` endpoints using
   `ActorContext.apiToken` as the `Authorization: Bearer` credential, and translates the
   snake_case Pydantic response shapes into this app's camelCase domain types
   (`lib/policyIntelligence/types.ts`) — the anti-corruption boundary (CLAUDE.md §15). This
   is the first real consumer of the `apiToken` bridge.
2. Expose that service through three thin Next.js Route Handlers under
   `app/api/policy-intelligence/*`, following the exact shape every other apps/web feature
   route already uses (`getActor()` → 401 if none → call the service → `errorResponse()`).
   The browser never receives or sends the `apps/api` bearer token; it only ever talks to
   `apps/web`'s own same-origin routes, exactly like every other feature.
3. Map `apps/api`'s RFC 9457 problem+json statuses to this app's existing `AppError` family
   (`ForbiddenError` for 403, `NotFoundError` for 404, `ValidationError` for 422) and add one
   new class, `UpstreamError` (502), for anything else — a failed or unreachable downstream
   call is a distinct failure mode from *this* app rejecting the request outright, and
   deserves its own code or a future retry/circuit-breaker policy could hang off of it.
4. Keep `apps/api` as the sole authorization source of truth: the UI's own
   `lib/auth/permissions.ts` mirror (already used to hide/show the nav item) is advisory only,
   and every proxied call still passes through `apps/api`'s own `authz.ensure_can` gate and
   the Tool Registry's permission check, unconditionally audited (ADR-0022) — a denial there
   surfaces to the user as a real `ForbiddenError`, not silently reinterpreted.
5. Build the three views (Obligations, Coverage Gaps, Quality Review) as tabs within one page
   (`/policy-intelligence`), reusing the existing `Card`/`Badge`/tone-system components and
   the loading/error/empty three-state idiom already established by `DocumentList`,
   `PoliciesWorkspace`, and `ReportsWorkspace` — no new UI primitives, no new state-management
   pattern, no new test framework (the one integration check added,
   `tests/eval/policyIntelligence.eval.ts`, follows the existing `tests/eval/*.eval.ts`
   convention: exercise the real proxy against a real `apps/api` + Postgres, skip cleanly
   when unreachable).

## Consequences

**Positive**
- Zero duplicated business logic: every finding the UI shows was computed once, by the same
  deterministic engines PI-P3/PI-P4 already test, through the same audited Tool Registry path
  PI-P5 established.
- The `apiToken` bridge documented since PI-P0 finally has a real caller, validating that
  design rather than leaving it speculative.
- Establishes the pattern any future `apps/web` feature needing a real AI/backend capability
  from `apps/api` will follow — a Node-only service module translating `ActorContext.apiToken`
  into a proxied call, never touching the browser.

**Negative / costs**
- `apps/web` now depends on `apps/api` being reachable for this one feature; if it's down,
  Policy Intelligence's three views degrade to an `UpstreamError` state while the rest of the
  app (which never called `apps/api`) is unaffected. Acceptable: this is a genuinely different
  failure domain than a Postgres outage, and the UI surfaces it honestly rather than masking
  it.
- Two independent RBAC mirrors now exist for the same "policy" resource — `apps/web`'s
  `lib/auth/permissions.ts` and `apps/api`'s `RbacAuthorizationService` — with no automated
  check that they stay in sync. This risk already existed before this ADR (every other
  `apps/web` feature has the same UI-only mirror); Policy Intelligence does not introduce a
  new instance of it, it inherits the existing one.

## Alternatives considered

- **Reimplement coverage-gap/quality-review matching in TypeScript against Postgres
  directly.** Rejected: duplicates `grc_policy_hunter`/`grc_policy_analyst`'s tested,
  deterministic engines in a second language, risks silent drift between the two
  implementations, and bypasses the Tool Registry's audit trail entirely for UI-originated
  calls.
- **Expose `apps/api` directly to the browser (CORS + a client-visible token).** Rejected:
  would leak a backend bearer-token scheme into client-side JavaScript and require `apps/api`
  to accept cross-origin browser requests it was never designed for; the existing
  same-origin-proxy pattern every other `apps/web` feature already uses required no such
  change.
- **A shared `UserRole → tool permission` sync check between the two RBAC mirrors.** Deferred:
  real, but pre-existing across every `apps/web` feature, not specific to Policy Intelligence;
  addressing it is a separate, cross-cutting decision, not one this phase should bundle in.
