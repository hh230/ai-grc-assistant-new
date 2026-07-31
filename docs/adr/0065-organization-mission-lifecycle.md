# ADR 0065: The Organization Mission Lifecycle — drive a mission from evidence to closure, verified by the connector, escalated on exhaustion

- Status: **Implemented & live-validated (2026-07-31); Core FROZEN.** The daemon hosts the lifecycle as
  the single operational path (the old `Jobs → MissionGate → run_mission` scheduler is removed); proven
  live end-to-end (detect → own → open → verify → close, recovery across restart, escalation, MTTC,
  dashboard). Per the owner, the Core (Lifecycle, Coordinator, Correlation, Strategy & Resolution
  frameworks) is now **frozen** — bug fixes and performance only; new capability goes *on top* (S5
  Approval Experience, S6 Dashboard & Operations). Originally **Accepted** (2026-07-30) — owner-approved
  before implementation. Resolved decisions:
  **D1** mission durability = **re-derivation** for v1 (no shared store/DB; the Connector is the source
  of truth); **D2** Safe Class = **empty** (every consequential action human-gated until the platform
  proves stable); **D3** = **3 attempts**, then escalate to the **Supervisor**, then to the **CEO** if
  it persists/becomes critical. Owner refinement folded in: verification = **evidence-cleared +
  execution-evidence** (decision 3). Continues the escalation path **deliberately deferred by ADR 0064**
  ("re-planning or reopening on new evidence is a deliberate later escalation, never an automatic
  in-flight mutation").
- Date: 2026-07-30
- Deciders: **Product Owner**, Architecture
- Related: ADR 0064 (Mission Correlation) · 0061 (autonomous dev team / `ChainDriver`,
  `ContinuousMonitor`) · 0044 (human approval gate) · 0048 (`PlanStep`/per-step tool) · 0042
  (mission lifecycle, `AWAITING_APPROVAL`) · 0043 (Mission Store) · CLAUDE.md §7, §8, §9, §11, §19.
  Design detail: `docs/devteam/MISSION-LIFECYCLE.md`.

## Context

The AI Organization detects real problems (Connectors) and opens real Missions (Jobs), but a mission
runs **advisory-only, straight to `COMPLETED`**, and is then forgotten. Verified in code: the
`OrganizationPlanner` never sets `PlanStep.consequential=True`, so the frozen engine's `AWAITING_APPROVAL`
gate never fires; the DELIVERY stage plans but never lands; the jobs `MissionGate` is in-memory and keeps
no durable link to the mission it opened or whether the problem was resolved; and **no verification of
remediation exists anywhere** (the squad's only signal is CI turning green). The organization therefore
behaves as a monitor, not an operating organization. The missing capability is the **lifecycle around a
mission** — analyze → assign → (gated) execute → **verify** → approve → close — with **escalation** and
**traceability**. The frozen `MissionEngine` already supports the full 9-state lifecycle including the
human gate; the squad already runs a continue-until-resolved loop (`ContinuousMonitor` → `ChainDriver` →
verify-by-CI). Both are unused by the organization.

## Decision

1. **A general lifecycle for every mission type; mirror the squad's operating loop, do not build a new
   one.** Add an org-side **`LifecycleDriver`** (a sibling of `ChainDriver`) that runs **inside the
   existing `OrganizationMonitor.tick`** — no new runtime, scheduler, or dashboard. Per open problem it
   `advance`s: re-observe → **resolved?** close : **under attempt cap?** ensure a gated remediation
   mission exists / open the next attempt : **escalate**. The driver and its verdicts are
   **domain-agnostic** (owner principle, 2026-07-30): the lifecycle drives *any* mission type — a
   compliance gap, a policy contradiction, a risk item, an ops problem — not only a code fix. Code
   remediation is one *strategy* plugged into the remediation seam; the core imports nothing code- or
   connector-specific.

2. **One problem, one durable lineage — correlated by (Mission Type + Asset + Evidence Signature).**
   A detected condition is a **`ProblemSignal`** whose identity is
   `correlation_ref = {mission_type}:{asset}:{evidence_signature}` (owner principle, 2026-07-30) — so the
   same condition on different assets is tracked separately (TLS expiry on host-A ≠ host-B), the same
   condition recurring on one asset dedups to one lineage, and problems stay distinct across domains. An
   org-local **`ProblemLedger`** (the ADR-0064 pattern — register / find_active / deactivate,
   tenant-scoped) replaces the in-memory `MissionGate`; it holds the active-problem set the driver
   advances and **deactivates on verified resolution** (not merely mission-terminal — resolution is the
   two-part verification of decision 3), so a recurrence after closure is a new problem, never a
   resurrection. This is a third correlation store, distinct from intake's and the chain's (ADR 0064).

3. **Verification is evidence-cleared + execution-evidence — closure means the originating evidence
   disappeared, not that execution finished.** A problem closes only when **both** hold: (a)
   *evidence-cleared* — a fresh, **OK** re-observation (`ConnectorRegistry.fetch(id, use_cache=False)`,
   never `UNAVAILABLE`/`ERROR`) in which the originating signature is absent; and (b) *execution-evidence*
   where a remediation ran — the change's tests/CI green (reuse `ChainDriver` GREEN) for code, the CVE
   absent from a **regenerated** report for dependencies, a re-measurement within threshold for
   performance (for security headers the two coincide; for human-ops Class B, execution-evidence is N/A).
   Verification is a **plugin, one `ResolutionCheck` per strategy/domain** (a registry lookup — never an
   `if mission_type ==` in the driver; a new domain registers a new check, owner principle 2026-07-30),
   and it is **multi-evidence**: each check closes only on the combination its policy demands (Execution
   + Connector + optional Human), never one assumed source — a red CI keeps a connector-cleared problem
   open; an unavailable source never closes. Verification is an over-time (Layer-2) concern, never a
   synchronous in-mission step. This guards against false-closure (a transient blip, an unavailable
   source mistaken for "fixed," or a remediation that ran but did not resolve the signal).

8. **The coordinator: one tagged entry, idempotent, generic-events, reason-logged (owner rules,
   2026-07-30).** A `LifecycleCoordinator` fronts the driver with four load-bearing rules: (a) **one
   entry** `advance(problem, trigger)` — both `tick()` (polling, `Trigger.POLL`) and `notify(event)`
   (the event's trigger: CONNECTOR/GITHUB/RUNTIME/HUMAN/TIMER) flow through it, so we record *why* a
   state changed, not just that it did; (b) **idempotent events** — a re-delivered event (same
   `event_id`) is ignored, changing no state and opening no attempt; (c) **generic events only** —
   `EvidenceChanged / ExecutionFinished / ApprovalGranted / ApprovalRejected / RuntimeRecovered`; the
   GitHub/connector translation lives in an adapter, never in the lifecycle; (d) **every transition
   records its reason** — a problem walks `NEW → IN_PROGRESS → VERIFIED → CLOSED` (or `ESCALATED`) with
   each move carrying its cause (`approval granted`; `connector cleared + ci green`; `resolution policy
   satisfied`) for the §19 audit trail. The event path is an optimization over the tick, never a second
   brain — both call the same per-problem `LifecycleDriver.advance`.

4. **Remediation is a Strategy, not a fixed workflow; approval binds to the Strategy + severity, not
   the mission type (owner principles, 2026-07-30).** Mission type is not wired to an execution method:
   `Mission → Strategy → Approval → Execution`. A `RemediationStrategy` (plugin, CLAUDE.md §17) declares
   `applies_to` (so one mission type can be served by several — Security via `code_remediation` *or*
   `infrastructure_change`; Compliance via `evidence_collection` *or* `policy_update`) and an
   `ApprovalPolicy` derived from **the strategy + the problem's severity** — read-only evidence needs
   `none`, a policy update needs the `policy_owner`, a production merge needs a human (`standard`), a
   risk acceptance needs the `risk_owner`/`ceo` (`executive`). The chosen step's `consequential` flag is
   exactly `approval.requires_gate`, so the frozen engine pauses at `AWAITING_APPROVAL` iff the policy
   demands it — a human then decides through the **existing** `ApprovalGateway`. No Core change; a
   read-only strategy simply never gates.

5. **Cross-process approval by re-derivation, not a shared database.** The dashboard **re-derives** an
   org problem's gated remediation from the connector's evidence into its own store and approves it —
   exactly as `RuntimeGateway.materialize` re-derives a fix-it mission from CI today. A problem that can
   no longer be re-derived has already resolved (self-verifying). A shared `PostgresMissionStore` for
   live cross-restart continuity is an available durability upgrade, **not** required (the journal is the
   durable audit; the correlation entry re-derives an unresolved problem after a restart).

6. **Autonomy = lifecycle management; consequential execution stays human-gated except an opt-in Safe
   Class.** The org autonomously analyzes, assigns, tracks, verifies, escalates, and closes. Consequential
   *action* is either dispatched to the squad's human-gated fix-it flow (code-remediable), surfaced as a
   human-ops task (not org-actionable), or — only for an **explicitly configured** allowlist of
   low-risk, reversible remediations — auto-approved by the driver. **For v1 that allowlist is empty**
   (owner, D2): every consequential action is human-gated until the platform proves stable; the
   mechanism ships closed so it can be opened later by config alone, and a Safe-Class remediation that
   fails verification twice **falls back to the human gate**.

7. **Escalation is a real mission, not a log line — a two-tier ladder.** Exhausting the attempt cap
   (**3**, matching the squad) raises a `ChainAlert`-shaped escalation to the **Supervisor**; if the
   problem **persists or becomes critical**, the Supervisor escalates to the **CEO**. Both tiers are
   real, dashboard-visible missions.

9. **Adapters translate; the coordinator owns state — five integration rules (owner, 2026-07-30).**
   Before daemon wiring, five rules keep the API stable for a distributed, webhook-driven future: (a)
   **hot-swappable adapters** via an `AdapterRegistry` (GitHub/GitLab/Jenkins/local — a new execution
   source is a registration, not an `if/else`); (b) **out-of-order tolerance** — every event resolves
   against *current state + a legal-transition table*; an out-of-order or stale move is ignored, never
   corrupting state, and a late event after close finds nothing to advance; (c) **never depend on
   delivery** — `notify()` is the fast path, `tick()` is reconciliation that re-discovers any missed
   change, so the system is eventually consistent even if every webhook is lost; (d) **provenance** —
   each event/transition records its concrete `source` (`github-actions`, `website-connector`,
   `dashboard-approval`), not just the trigger class; (e) **adapters never mutate state** — their whole
   job is `External → Generic Event`; the `LifecycleCoordinator` is the single source of truth. A
   failing adapter is contained (the tick still reconciles).

10. **Operational maturity: recoverable, tick-independent, measurable (owner, 2026-07-31).** Three
    rules make the lifecycle production-grade: (a) **recoverable** — on daemon restart the coordinator
    rebuilds its state from the durable ledger/records (`export`/`recover`), continuing in-flight
    problems instead of restarting from zero; (b) **execution is not tied to the tick** — `notify()`
    advances a problem immediately; `tick()` is *reconciliation only*, not the execution driver (proven:
    a problem progresses on `notify` with no tick); (c) **measurable** — a `LifecycleMetrics` observer
    (wired as `on_transition` + `on_advance`, zero change to decision logic) exposes active problems,
    mean-time-to-verify, mean-time-to-close, retry/escalation/verification-failure counts, and event
    latency, so the organization can be improved, not just operated.

11. **The lifecycle is the spine: detection ≠ ownership, stateless jobs, one source of truth, one-way
    flow (owner, 2026-07-31).** Four rules keep the platform unconstrained as it grows: (a) **detection
    ≠ ownership** — a job emits a `ProblemSignal` and ownership passes to the Lifecycle; the strategy,
    not the detecting job, decides who executes; (b) **stateless jobs** — a job's whole job is
    `observe → emit`, keeping no memory of open/attempts/closed (all of which live in the ProblemLedger /
    Coordinator / AttemptStore), so any job restarts with zero lost context; (c) **single source of
    truth** — no duplicate problem state in a connector, job, adapter, or dashboard; everyone reads the
    Ledger + lifecycle state, and the dashboard is a *viewer*, never a decider; (d) **one-way flow** —
    `External → Adapter → Generic Event → Coordinator → State → Dashboard/Metrics/Audit`, never
    `Dashboard → Lifecycle` or `Adapter → State` except *through* the `LifecycleCoordinator`, so no
    integration can create a feedback loop. The stateless emitters (`emission.py`) realize (a)+(b);
    `AttemptStore.forget` frees a resolved chain so a recurrence starts fresh.

12. **One Composition Root; dependency injection; the daemon is a host (owner, 2026-07-31).** A single
    `build_lifecycle` factory (`composition.py`) is the only place that creates and wires every part —
    ledger, metrics, attempt store, driver, resolver, coordinator, registries, emitters, adapters (rule
    1). The coordinator news-up nothing of its own; every collaborator is injected (rule 2). The leaf
    primitives — how a connector is read, how evidence is observed, how a mission is opened/checked/
    escalated — are injected callables, so the whole engine runs end-to-end under test with fakes and in
    production with the real connectors + `OrganizationRuntime`. The result is a plain
    `LifecycleComposition` the daemon **hosts** and calls (`sync()` = emit→observe, drain→notify,
    reconcile); the lifecycle package imports nothing from the daemon (rule 3) — `Daemon → Lifecycle`,
    never the reverse.

## Consequences

**Positive**
- End-to-end operational autonomy — evidence → analysis → gated execution → verification → closure —
  with governance and traceability intact, reusing the engine, correlation, approval, continue-until-
  resolved, and code-remediation machinery already in the repo.
- The first real **verification** capability on the platform (connector re-observation), closing the loop
  the squad leaves open.
- No new runtime/scheduler/dashboard and **no frozen-Core change**; the org merely sets an existing flag.
- No-fabrication is strengthened: "verified" and "resolved" are real re-observations.

**Negative / costs**
- A new `LifecycleDriver` plus the correlation-opener, gated-remediation, Safe-Class, and dashboard-lens
  slices — more moving parts than today's fire-and-forget mission.
- Re-derivation requires connector evidence to be deterministic and still present at approval time
  (true for state-based problems; transient problems self-resolve, which is correct).
- The Safe Class is a real (bounded, opt-in) autonomy surface that must be governed carefully.

## Alternatives considered

- **Shared `PostgresMissionStore` as the primary approval path.** Deferred to a durability upgrade
  (D1) — makes a database a hot-path dependency of the daemon and dashboard and diverges from the squad's
  proven re-derivation pattern, for continuity that the correlation store + journal already provide.
- **In-mission verification step.** Rejected — real resolution takes time; a synchronous re-check right
  after the action would falsely fail. Verification belongs to the over-time driver, as with CI.
- **Full auto-remediation (no gate).** Rejected — violates §9 human-in-the-loop. The opt-in Safe Class
  is the bounded exception the owner chose.
- **A new orchestration engine coordinating the agents.** Rejected — the agents are already coordinated
  by the mission plan; what was missing is the lifecycle *around* the mission, which the engine + a
  `ChainDriver`-shaped driver already express.
