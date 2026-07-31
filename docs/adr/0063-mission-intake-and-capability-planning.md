# ADR 0063: Mission Intake & capability-based planning — normalize triggers into missions; plan in capabilities, resolve separately

- Status: **Accepted** (2026-07-26) — owner-approved after the boundary design was reviewed, before
  implementation. **Amends ADR 0062 rule 6** (role→agent resolution becomes capability→agent via a
  separate resolver). Mission Intake is Accepted-architecture; implemented per phase. Mission Intake's
  input is **refined by ADR 0064**: it receives an `IntakeCommand` (`CreateMission | UpdateMission`)
  from a Mission Correlation step, never a raw event or a bare `IntakeSignal`.
- Date: 2026-07-26
- Deciders: **Product Owner**, Architecture
- Related: ADR 0046 (assistant-runtime — the generic "input → capability → Mission" mechanism, **reused
  wholesale**) · 0061 (the dev team) · 0062 (agent protocol — amended) · 0042 (Mission Engine) · 0048
  (per-step tool routing, `PlanStep.tool`) · 0040 (tenancy: identity at the boundary, never the payload)
  · 0056 / 0059 (one Port, many realizations) · CLAUDE.md §5, §9, §11, §17.

## Context

The dev team must convert heterogeneous external triggers — GitHub Issue, CI failure, Sentry alert,
scheduled maintenance, a manual owner request — into governed Dev Missions, and the **Foreman must
never know where a mission came from**. Separately, the Foreman must **plan in capabilities**
(testing, implementation, review, security, monitoring), not in concrete agent classes, with
capability resolution as a **separate concern**.

Crucially, the Core already solves the first problem generically: `assistant-runtime` (ADR 0046) is
*"mechanism only — no GRC capabilities, no LLM, no tools; depends only on mission-engine +
pipeline-contracts"* and implements exactly `input → intent → capability → (goal, Plan) → Mission`.
The owner's ruling: reuse it; do not reinvent capability/catalog/selector/mission-type abstractions.

## Decision

### 1. Mission Intake is a boundary; everything behind it is reused

- **`TriggerSource` (Port — one, many realizations)** is the *only* origin-aware layer:
  `normalize(raw_event) -> IntakeSignal`. Realizations: `GitHubIssueSource`, `CIFailureSource`,
  `SentryAlertSource`, `ScheduledMaintenanceSource`, `ManualRequestSource`.
- **`IntakeSignal`** is the single normalized shape — a thin envelope of **reused** parts:
  `tenant: TenantContext` (entered here from verified identity, never the payload — ADR 0040),
  `intent: CapabilityIntent` (a structured source sets it directly; no LLM), `findings:
  tuple[AgentFinding, ...]`, and `origin: str` (audit label only).
- **`MissionIntake`** turns an `IntakeSignal` into a Dev Mission by **reusing the assistant-runtime
  machinery unchanged**: `CapabilitySelector.select(intent) → Capability → MissionCatalog.build(...) →
  (goal, Plan) → MissionDriver.run_transition(create → plan → execute)`.
- **The Foreman stays origin-blind:** its planning methods *are* the `PlanFactory`s registered as dev
  `MissionType`s; the catalog hands the Foreman only `(inputs, tenant)`. "GitHub vs Sentry" lives
  solely in the `TriggerSource`. New here: **`TriggerSource` + `IntakeSignal`** — nothing else.

### 2. The Foreman plans in capabilities

A new vocabulary **`AgentCapability` = {TESTING, IMPLEMENTATION, REVIEW, SECURITY, MONITORING}** — what
a *step needs*, distinct from `AgentRole` (*who* an agent is) and from the mission-level `Capability`
(*what a trigger wants*). The Foreman writes an `AgentCapability` into **`PlanStep.tool`** (reusing the
ADR 0048 routing field) and **imports no agent class**.

### 3. Capability resolution is a separate concern (amends ADR 0062 rule 6)

A **`CapabilityResolver`** maps `AgentCapability → Agent`, configured at the composition root
(`{TESTING: QA, REVIEW: Reviewer, SECURITY: Security, MONITORING: Monitor, IMPLEMENTATION: Developer}`)
— the same existence-check shape as the reused `CapabilitySelector`, one granularity down. An
**`AgentTool`** per capability resolves each step via the `CapabilityResolver` (not
`AgentRole(step.tool)`), run by the Mission Engine's existing tool-execution path — no dedicated agent
executor. `AgentRole` is **demoted to the agent's identity** (finding `source`, decision `by_role`,
audit) — it is no longer the routing key. **This supersedes ADR 0062 rule 6** ("role→agent map in the
executor").

## Consequences

**Positive**
- The dev team reuses ADR 0046's generic intake wholesale; only the `TriggerSource` normalization and
  a thin `IntakeSignal` are new. No new selection/catalog abstractions.
- The Foreman is doubly decoupled: it never sees the trigger origin, and it plans in capabilities, not
  agents. Agents can be swapped, added, or reassigned to capabilities without touching a plan.
- Capability resolution is one small, testable component; `AgentRole` cleanly means "identity."

**Negative / costs**
- Two capability granularities now coexist (mission-level `Capability`, step-level `AgentCapability`);
  the naming must stay crisp to avoid confusion.
- The dev team gains a dependency on `assistant-runtime` (acceptable — it is generic mechanism, deps:
  only mission-engine + pipeline-contracts).

## Alternatives considered

- **Replicate the intake pattern inside the dev tree.** Rejected — reinvents the abstractions ADR 0046
  already provides generically; the owner ruled for reuse.
- **Keep role-based routing (`PlanStep.tool = AgentRole`).** Rejected — couples every plan to concrete
  agents; the decoupling is the whole point.
- **LLM intent recognition for triggers.** Unnecessary — structured sources set the `CapabilityIntent`
  directly; the `IntentRecognizer` port remains available for the free-text manual path if wanted.
