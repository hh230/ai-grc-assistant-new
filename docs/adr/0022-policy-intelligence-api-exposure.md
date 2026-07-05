# ADR 0022: Policy Intelligence API exposure — a thin, read-only `apps/api` router

- Status: Accepted
- Date: 2026-07-06
- Deciders: Product Owner (via direct working session), Architecture
- Related: CLAUDE.md §5, §6, §9, §10, §11, §19, §20; ADR 0006, 0013, 0014, 0017, 0020, 0021

## Context

PI-P3 (ADR-0020, Policy Hunter) and PI-P4 (ADR-0021, Policy Analyst) each shipped as a
tested library with two Tools and one Tool respectively, invoked directly through a
`ToolRegistry` in tests — deliberately with "no `apps/api` HTTP endpoint yet," each ADR
naming that composition as "a later, separate decision." PI-P5 is that decision: the
workspace UI (and any other HTTP caller) needs to reach `list_applicable_obligations`,
`scan_policy_coverage_gaps`, and `review_policy_quality` the same way every other
capability in `apps/api` is reached — authenticated, tenant-scoped, authorized, and
audited — without inventing a second way to call a Tool.

`apps/api` already has a real Tool Registry and a live-Postgres wiring for Policy
Intelligence (ADR-0017's `web_runtime.py`), but that registry has never had a tool
registered on it — `web_runtime.py` only builds an empty `ToolRegistry`. Separately,
`apps/api`'s existing routers (`policies.py`, `platform.py`, `orchestrator.py`) all follow
one of two patterns: CQRS command/query dispatch through `Commands`/`Queries` (the
`store_backend`-gated in-memory bus), or a direct call into a governed capability
(`orchestrator.py`'s `POST /orchestrator/runs`, which calls `authz.ensure_can` explicitly
before invoking the Orchestrator, because that capability sits outside the command/query
bus). Policy Hunter and Policy Analyst are Tools invoked via their Agents, not commands or
queries, and they run against `web_runtime.py`'s Postgres binding, not the `store_backend`
bus — so they need the same "explicit `authz.ensure_can`, then call the capability
directly" shape `orchestrator.py` already established, not a new pattern.

The one open design question was permissions: both Tools declare
`required_permissions={Permission("policy_hunter")}` /
`{Permission("policy_analyst")}`, checked by the Tool Registry against
`ToolContext.roles` — a `frozenset[str]` of capability names, deliberately distinct from
`Principal.roles` (`grc_domain.tenancy.enums.UserRole`, the RBAC roles `apps/api`
authenticates callers into). Nothing before this phase ever bridged the two.

## Decision

We will:

1. Add `packages/policy-hunter` and `packages/policy-analyst` as dependencies of
   `apps/api`, and extend `web_runtime.py`'s `get_tool_registry` to register all three
   Tools — `ListApplicableObligationsTool`, `ScanPolicyCoverageGapsTool`,
   `ReviewPolicyQualityTool` — against `grc_persistence_web`'s existing
   `RegulatoryObligationRepository`/`RegulatoryRawDocumentRepository`/`PolicyRepository`,
   in `_register_policy_intelligence_tools`, called exactly once per process (the same
   lazy-singleton point `get_tool_registry` already memoizes on `app.state`). No new
   persistence code or migration: every repository this needs already exists.
2. Add `security/dependencies.py` dependencies `get_policy_hunter_agent`/
   `get_policy_analyst_agent` that construct `PolicyHunterAgent(registry)`/
   `PolicyAnalystAgent(registry)` from the existing `WebToolRegistry` dependency — thin
   wrappers, not new state — and expose them as `PolicyHunterAgentDep`/
   `PolicyAnalystAgentDep` aliases, matching every other dependency in that module.
3. Add `routers/policy_intelligence.py` with three `GET` endpoints (idempotent, read-only
   operations — `GET` matches CLAUDE.md §21's REST conventions better than the `POST
   .../runs` shape `orchestrator.py` uses for a stateful agent run):
   `GET /policy-intelligence/obligations`, `GET /policy-intelligence/coverage-gaps`
   (both optionally filtered by `control_domain`), and
   `GET /policy-intelligence/policies/{policy_id}/quality-review`. Each handler calls
   `authz.ensure_can(context, Action.READ, ResourceType.POLICY)` first — the identical
   gate `/policies`' own read endpoints are authorized under via the command/query bus —
   then calls the agent, which calls the Tool Registry, which authorizes (its own
   permission check), validates, executes, and unconditionally audits, exactly like any
   other Tool invocation (CLAUDE.md §19). `PolicyNotFoundError` (an unknown
   `(tenant_id, policy_id)`) is translated to `ResourceNotFoundError` (HTTP 404), matching
   this codebase's existing application-error-to-problem+json mapping.
4. Bridge `ToolContext.roles` from the RBAC gate rather than from `Principal.roles`
   directly: once `authz.ensure_can(READ, POLICY)` has passed, the router grants the
   caller both `"policy_hunter"` and `"policy_analyst"` Tool permissions
   unconditionally. This is deliberate, not an oversight — every `UserRole` this platform
   defines already has `POLICY` read access under `RbacAuthorizationService`'s existing
   matrix (`OWNER`, `ADMIN`, `COMPLIANCE_MANAGER`, `RISK_MANAGER`, `ANALYST`, `AUDITOR`,
   `VIEWER` all do), so translating the RBAC decision that already exists is equivalent to
   — and far less risky than — hand-maintaining a second, independent
   `UserRole → {"policy_hunter", "policy_analyst"}` table in `apps/api` that could drift
   out of sync with `RbacAuthorizationService`'s matrix as new roles are added. The Tool
   Registry's own permission check remains real defense-in-depth for every *other* caller
   of these Tools (a future scheduled job, a future Workflow step, or a test) that does
   not go through this RBAC gate at all.
5. Neither endpoint needs a human-approval gate: both Tools are
   `ToolSideEffect.READ_ONLY` (`requires_approval=False` structurally), matching every
   other read endpoint in this API (`GET /policies`, `GET /tools`, ...).

## Consequences

**Positive**
- Policy Hunter and Policy Analyst are now reachable exactly the way CLAUDE.md §9 requires
  — the same Tool Registry, the same audit trail, the same Agent objects already tested in
  PI-P3/PI-P4 — with zero new execution path invented for HTTP.
- The permission bridge is derived from, not duplicated against, the existing RBAC matrix:
  a future role addition to `RbacAuthorizationService` automatically extends (or doesn't)
  who can call these endpoints without a second file to remember to update.
- Every invocation is still fully audited via `PostgresToolInvocationRecorder`
  (`ai_tool_invocations`), including denials — unchanged from PI-P0's guarantee.

**Negative / costs**
- The `authz.ensure_can(READ, POLICY)` gate is currently unconditionally satisfied by every
  defined `UserRole` — there is no role today that is authenticated but denied. It is kept
  anyway as the correct, forward-compatible shape (CLAUDE.md §20's default-deny posture)
  for the day a narrower role is introduced, and it is exactly the same authorization the
  existing `/policies` read endpoints already rely on, not a new, weaker check invented for
  this router.
- `_register_policy_intelligence_tools` runs on the *first* call to `get_tool_registry` in
  a process. Under concurrent first requests, `get_web_database`'s own lock prevents a
  double-built Postgres pool, but two racing requests could each build and register a
  distinct `ToolRegistry` before one wins the `app.state` assignment — harmless (the loser
  is simply discarded, and `ToolRegistry.register`'s duplicate-registration guard only
  matters *within* one registry instance), but worth naming: this is the same class of
  race `web_runtime.py`'s own module docstring already documents and accepts for the
  lazily-created pool.

## Alternatives considered

- **Route Policy Hunter/Analyst through the existing CQRS command/query bus
  (`Commands`/`Queries`), like `policies.py`.** Rejected: that bus is bound to the
  `store_backend`-gated (in-memory / ADL-0008-blocked SQLAlchemy) persistence track, not
  `web_runtime.py`'s Postgres binding these Tools actually read from — forcing that
  mismatch would either require a second command/query bus or would fight the existing
  `ADR-0017` boundary between the two persistence tracks.
- **Maintain an explicit `UserRole → tool permission` mapping table in `apps/api`.**
  Rejected in favor of deriving the grant from the `authz.ensure_can(READ, POLICY)` result
  already computed — see Decision §4. A future capability with a genuinely narrower
  audience (e.g. a *consequential* Policy Builder tool once ADR-0017's Policy Builder
  ships) should introduce its own, deliberately distinct authorization gate rather than
  reuse this one.
- **`POST /policy-intelligence/...` actions (mirroring `orchestrator.py`'s
  `POST /orchestrator/runs`).** Rejected: those endpoints are idempotent reads over
  already-stored data with no mission/run state created — `GET` is the more accurate REST
  verb (CLAUDE.md §21), and nothing here needs `orchestrator.py`'s "propose, await
  approval" shape since there is no consequential output to gate.
