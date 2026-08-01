# The Organization Mission Lifecycle

> **Status: IMPLEMENTED & live-validated 2026-07-31 — the single operational path; Core FROZEN.** The
> daemon hosts the lifecycle; the old jobs→gate→run_mission path is removed; proven live end-to-end
> (§9a scenarios + a live daemon run). The autonomy boundary is an **opt-in
> Safe Class, empty for v1** (every consequential action is human-gated until the platform proves
> stable). Open decisions D1–D3 are resolved (§10). Verification is **evidence-cleared + execution-
> evidence** (§3.3), per the owner's refinement. The decision record is
> [ADR 0065](../adr/0065-organization-mission-lifecycle.md).
>
> **Owner principles, baked in from the start (2026-07-30):**
> 1. **The lifecycle is general for every mission type** — a compliance gap, a policy contradiction,
>    a risk item, an ops problem — **not** just code fixes. The `LifecycleDriver` and its verdicts are
>    domain-agnostic; code remediation is one *strategy* plugged into the remediation seam. The pure
>    core imports nothing code- or connector-specific.
> 2. **Correlation identity is `(Mission Type + Asset + Evidence Signature)`** — so a problem is tracked
>    correctly across all domains: the same condition on different assets is a different lineage, the
>    same condition recurring on one asset dedups, and domains never collide.
> 3. **Remediation is a Strategy, not a fixed workflow** — `Mission → Strategy → Approval → Execution`;
>    one mission type resolves several ways by context, and **approval binds to the strategy + severity,
>    not the mission type**.
> 4. **Verification is a plugin per strategy/domain (`ResolutionCheck`), never `if mission_type ==`** —
>    a new domain registers a new check.
> 5. **Multi-evidence**: a check closes only on the combination its policy demands — Execution +
>    Connector + optional Human — never one assumed source.
> 6. **Event-driven-ready**: the lifecycle exposes `notify(event)` for real triggers (a CI run
>    finished, a connector changed); the tick is fallback polling.
>
> The coordinator (S4b-1) and adapter (S4b-2a) layers add nine operational rules — one tagged entry,
> idempotent + out-of-order-tolerant events, generic-events-only, per-transition reasons, source
> provenance, reconciliation-not-delivery, hot-swappable adapters, and adapters-never-mutate-state —
> recorded in [ADR 0065](../adr/0065-organization-mission-lifecycle.md) decisions 8–9.

## 1. The gap, stated precisely

The AI Organization now **detects** real problems (Connectors) and **opens** real Missions (Jobs).
But a mission, once opened, is driven **synchronously straight to `COMPLETED` at the advisory
level** and then forgotten. Verified against the code:

- `OrganizationRuntime.run_mission` calls `create → plan → execute` inline and returns a terminal
  mission (`devteam-organization/.../runtime.py:143`). There is no pause, no follow-up.
- `OrganizationPlanner.plan` builds every `PlanStep` **without `consequential=True`**
  (`planner.py:52`), so the frozen engine's human gate (`AWAITING_APPROVAL`) **never fires** — even
  though the engine fully supports it (`v2/.../mission_engine/engine.py:150`).
- The `DevTeamAgent` DELIVERY stage writes a *delivery plan* and explicitly **defers landing**
  (`agents/devteam.py`) — it never executes.
- The jobs `MissionGate` is **in-memory and per-process** (`jobs/framework.py:150`): it edge-triggers
  one mission per problem episode but keeps no durable link to that mission and has no notion of
  whether the problem was ever *resolved*.
- There is **no verification anywhere** that a remediation actually fixed the problem (confirmed:
  the squad has none either — its only "did it work?" signal is CI going green).

So today's organization is a **monitoring system that files reports**, not an operating organization
that drives a problem to closure. The missing capability is the **lifecycle around a mission**:
analyze → assign → (gated) execute → **verify** → approve → close, with **escalation** and full
**traceability**.

## 2. The insight: this is the squad's loop, with the Connector as CI

The engineering squad *already* runs a continuous, close-the-loop operating cycle. We do not invent a
new one — we hold the org's problems in the **same** proven shape, swapping the source of truth:

| Squad (exists today) | Organization (this design) |
|---|---|
| `ContinuousMonitor.tick()` polls open PRs | `OrganizationMonitor.tick()` (already runs every poll) |
| `ChainDriver.advance(correlation_ref, branch)` | **`LifecycleDriver.advance(correlation_ref)`** (new, sibling) |
| Source of truth = **GitHub CI** | Source of truth = **a Connector** |
| Remediation = `FixItRuntime` (diagnose → gate → land code) | Class-A reuses `FixItRuntime`; Class-B is a human task; Class-C is Safe |
| **Verification = CI goes GREEN** (next ticks) | **Verification = originating evidence gone _+_ execution evidence** (§3.3) |
| Escalation = `ChainAlert` at attempt cap | Escalation ladder: cap → Supervisor → (if it persists/critical) → CEO |
| Dedup = chain `correlation_ref` | Dedup = ADR-0064 pattern, keyed `{mission_type}:{asset}:{evidence_signature}` |

The connector re-fetch as the **verification oracle** is the one genuinely new idea — and it is the
honest one: *the same connector that detected the problem confirms the fix*, and if the problem can
no longer be observed, it is resolved. It also strengthens the no-fabrication contract: "verified"
is a real re-observation, never an assertion.

## 3. The lifecycle state model — two layers

The user's stages (analyzed, assigned, executed, verified, approved, closed, escalated) live across
**two layers**, each realized by machinery that already exists.

### Layer 1 — the attempt mission (the frozen engine's 9 states, reused unchanged)

```
CREATED → PLANNED → EXECUTING → AWAITING_APPROVAL → RESUMED → EXECUTING → COMPLETED
                                      │(reject)                                 (or FAILED, fail-safe)
                                      ▼
                                  CANCELLED
```

- **Analyzed / Assigned** = `EXECUTING` the CEO→…→DevTeam plan (capability routing *is* assignment).
- **Approved** = the engine pauses at `AWAITING_APPROVAL` on the `consequential=True` remediation
  step; a human decides via the existing `ApprovalGateway` → `RESUMED`.
- **Executed** = the resumed remediation step runs → `COMPLETED`.

This layer is **entirely the frozen `MissionEngine`**. The only change that unlocks it is org-side:
the planner must mark the remediation step `consequential=True`. No Core change (§2 of the ADR).

### Layer 2 — the problem (per `correlation_ref`, across attempts)

```
OPEN ──▶ REMEDIATING ──▶ VERIFYING ──▶ RESOLVED        (connector cleared → deactivate correlation)
  ▲                          │
  └──────── next attempt ◀───┴──▶ ESCALATED            (attempt cap reached → escalation mission)
```

- **Verified / Closed** = Layer 2: after an attempt completes, the driver confirms resolution over
  subsequent ticks via the two-part verification contract (§3.3); **resolved ⇒ RESOLVED** and the
  correlation entry is deactivated (ADR-0064's `CorrelationDeactivator` already frees it on
  mission-terminal).
- **Escalated** = Layer 2: attempts exhausted (cap 3) ⇒ escalate to the **Supervisor** as a real
  mission; if the problem **persists or is critical**, the Supervisor escalates to the **CEO** — a
  two-tier ladder, never a silent log.

Verification is deliberately a **Layer-2 (over-time)** concern, not an in-mission step: real
resolution takes time (a cert renews, a deploy propagates), exactly as the squad confirms a fix by
polling CI across ticks — never synchronously inside the fixing mission.

### 3.3 The verification contract — evidence-cleared **+** execution-evidence

A problem is closed only when **the evidence that created it has disappeared** — never merely because
"execution finished." Verification is the **conjunction** of two checks:

1. **Evidence-cleared (always required).** A *fresh, successful* re-observation
   (`ConnectorRegistry.fetch(id, use_cache=False)`, status **OK** — not `UNAVAILABLE`/`ERROR`) in which
   the **originating signature is absent**. The same signature that opened the problem (the correlation
   key, §4) is what must be gone. An unavailable source is **not** a clear — it cannot close a problem.
2. **Execution-evidence (required wherever a remediation executed).** Positive proof the remediation's
   own success criterion is met, by class:
   - **Code fix** → the change's **tests/CI are green** (reuse the squad's `ChainDriver` GREEN signal)
     *and* the flagging connector clears.
   - **Security header** → the header is present in the fresh connector fetch (the two checks coincide
     — one observation proves both).
   - **Dependency / CVE** → the CVE is **absent from a newly regenerated** vulnerability report (not a
     cached one) — which is exactly why `use_cache=False` and report freshness matter.
   - **Performance** → a **re-measurement** meets the threshold.
   - **Human-ops (Class B, no org execution)** → execution-evidence is N/A; the human's action is
     verified purely by the symptom disappearing (check 1 alone).

Closure requires **check 1 AND (check 2 _or_ check-2-not-applicable)**. This guards against
false-closure — a transient healthy blip, an unavailable source mistaken for "fixed," or a remediation
that ran but did not actually resolve the signal. It also unifies the two cohorts: the squad's existing
CI-green verification **is** the execution-evidence half for code remediations. Each problem type
declares a small `ResolutionCheck` (`evidence_cleared` + optional `execution_verified`); the
`LifecycleDriver` closes only when both hold.

## 4. What gets reused vs. what is new

**Reused, unchanged:**

| Concern | Component (verified) |
|---|---|
| Lifecycle + human gate | frozen `MissionEngine` (`AWAITING_APPROVAL`, `approve`/`reject`/`resume`) |
| One-problem-one-lineage | `CorrelationRepository` + `MissionCorrelator` + `CorrelationDeactivator` (ADR 0064, `devteam-intake`) |
| Continue-until-resolved | `ChainDriver`/`AttemptStore` shape (`devteam-runtime`, `devteam-chain`) |
| Human decision (cross-process) | `ApprovalGateway` + the dashboard's `RuntimeGateway.materialize/approve/reject` |
| Code remediation | `FixItRuntime` (diagnose → gate → apply/commit/push/PR) |
| Verification oracle | `ConnectorRegistry.fetch(id, use_cache=False)` (live re-observation) + CI-green (`ChainDriver`) as execution-evidence for code fixes |
| The tick, the journal, the dashboard | `OrganizationMonitor.tick`, the runtime journal, the SPA |

**New (small, all org-side, no Core change):**

1. **`LifecycleDriver`** — the sibling of `ChainDriver`. `advance(correlation_ref)` per open problem,
   inside the existing `OrganizationMonitor.tick`. Decides: re-fetch → cleared? (RESOLVE) :
   under-cap? (ensure a gated remediation mission exists / open next attempt) : (ESCALATE).
2. **A `ProblemSignal` + `ProblemLedger`** replacing the in-memory `MissionGate`: a detected condition
   is a domain-agnostic `ProblemSignal(mission_type, asset, evidence_signature, …)` whose
   `correlation_ref = {mission_type}:{asset}:{evidence_signature}`; the ledger (ADR-0064 pattern) holds
   the active-problem set the driver advances and deactivates on **verified resolution**, so lineage is
   durable, per-asset, cross-domain, and self-closing.
3. **Remediation as a Strategy** (`Mission → Strategy → Approval → Execution`) — a
   `RemediationStrategy` (plugin) declares `applies_to` (one mission type, several strategies by
   context) and an `ApprovalPolicy` from the **strategy + severity, not the mission type**; the step's
   `consequential` flag = `approval.requires_gate`, so a read-only strategy never gates while a policy
   update / prod merge / risk acceptance does (to the policy owner / a human / the CEO respectively).
4. **Cross-process approval by re-derivation** (§5).
5. **The Safe Class** (§6).
6. **A dashboard lifecycle lens** — extend the existing Open-Missions/approval surface to org
   problems (data-driven; no new dashboard).

## 5. The human gate across processes — re-derive, don't share a database

The daemon's `OrganizationRuntime` holds missions in an `InMemoryMissionStore` (`runtime.py:113`),
and the dashboard runs in a **different process**. The squad already solved this without a shared DB:
`RuntimeGateway.materialize()` **re-derives** the gated mission deterministically from the external
source of truth (CI) into its own store, then approves (`runtime_gateway.py:14`). We follow it
exactly, with the **connector** as the source of truth:

- The dashboard **re-derives** an org problem's gated remediation from `registry.fetch(connector_id)`
  — the same evidence yields the same proposal (deterministic, LLM-free).
- If the problem **can't be re-derived** (the connector now reads healthy), there is nothing to
  approve — it already resolved. Re-derivation is **self-verifying**.
- Approve → the dashboard process lands the remediation (Class A via `FixItRuntime`); the daemon
  observes resolution on its next connector re-fetch and closes the problem.

This keeps Postgres **out of the hot path**, stays identical to the squad, and reinforces
no-fabrication. Durable mission aggregates across restarts (a `PostgresMissionStore` for both
processes) remain available as a later durability upgrade — **Open Decision D1** — but are not
required: the correlation entry re-opens (re-derives) an unresolved problem after a restart, so
nothing is lost, and the **journal already persists the full audit trail** the dashboard reads.

## 6. The autonomy boundary — an opt-in Safe Class

Owner's decision (2026-07-30): **human gate by default, with an opt-in Safe Class that is _empty for
v1_** — every consequential action goes through Human Approval until the platform proves stable. The
mechanism below exists so the allowlist can be opened later by config alone, but ships closed.

Every consequential remediation pauses at `AWAITING_APPROVAL` **unless** its problem type is on an
explicitly configured allowlist of **low-risk, reversible, org-actionable** remediations, which the
driver may auto-approve (drive `engine.approve` itself) and execute. **The allowlist is empty by
default and stays empty for v1.**

Remediation taxonomy (honest about what the org can actually do):

- **Class A — code-remediable** (e.g. a missing security header, a dependency bump): remediation is a
  **squad `FixItRuntime` mission**, landed behind its existing `apply_patch` gate. The org dispatches
  and tracks; it does not write code itself.
- **Class B — human-ops** (e.g. TLS renewal, a down website, secret rotation): the org **cannot** act;
  it surfaces an evidence-backed, owned task and escalates. "Approval" is human acknowledgement; the
  connector re-fetch still verifies and closes.
- **Class C — Safe Class** (narrow, reversible, org-actionable — e.g. re-run a transient check):
  auto-approved **only** if configured; otherwise it too waits for a human.

Safe-Class rules (all enforced structurally): allowlist is **explicit config**, empty by default;
members must be reversible and idempotent; every auto-approval is journaled as an `AgentDecision`
with the evidence; and a Safe-Class remediation that fails verification twice **falls back to the
human gate** (no infinite silent retry). **Open Decision D2**: the initial Safe-Class membership.

## 7. Traceability, governance, no-fabrication

- **Traceability** is free: every attempt mission, decision, gate, and escalation already flows
  through the `MissionEngine` audit + the observability journal + the dashboard timeline.
- **Governance** holds: consequential action is gated by default; §9 human-in-the-loop is honored;
  the Safe Class is a *bounded, opt-in* exception, journaled.
- **No-fabrication** holds end to end: an `UNAVAILABLE` connector opens nothing; "verified" is a real
  re-observation; a problem that can't be re-derived is resolved, not asserted.

## 8. What does NOT change (the validation contract)

- **No new runtime** — the frozen `MissionEngine` drives every attempt.
- **No new scheduler** — the `LifecycleDriver` advances inside the existing `OrganizationMonitor.tick`.
- **No new dashboard** — a data-driven lens over the existing SPA and `RuntimeGateway`.
- **No frozen-Core change** — the gate primitive already exists; the org merely sets
  `consequential=True`.
- **No duplicated machinery** — correlation, the gate, the approval seam, continue-until-resolved,
  and code remediation are all reused.

## 9. Build plan (thin vertical slices, each shippable + tested)

1. **S1 — Lifecycle core ✅ (done, green).** The pure, domain-agnostic `LifecycleDriver` + two-part
   `Resolution` (evidence-cleared + execution-evidence; a failed execution never closes) + the two-tier
   `EscalationLedger` (Supervisor → CEO, critical goes straight to CEO). Reuses `devteam-chain`'s
   `AttemptStore`; imports nothing from the Mission Engine. (13 tests: full truth table, attempt
   lineage, every ladder rung.)
2. **S2 — Correlation opener.** `ProblemSignal(mission_type, asset, evidence_signature, …)` +
   `ProblemLedger` (ADR-0064 pattern) keyed `{mission_type}:{asset}:{evidence_signature}`, replacing the
   in-memory `MissionGate`; per-asset, cross-domain, self-closing on verified resolution. (Tests: dedup
   per asset, distinct across domains, re-arm after resolve.)
3. **S3 — Remediation Strategy + Approval Policy ✅ (done, green).** `Mission → Strategy → Approval →
   Execution`: a `RemediationStrategy` plugin layer (7 strategies — code/infra/evidence/policy/docs/
   risk-acceptance/runbook) with `applies_to` (several strategies per mission type, context-selected)
   and an `ApprovalPolicy` from **strategy + severity, not mission type**; `RemediationPlan.consequential`
   = `approval.requires_gate` → the engine gate. (12 tests: context selection, approval-by-strategy,
   severity scaling.)
4. **S4a — `ResolutionCheck` plugin + multi-evidence ✅ (done, green).** A `ResolutionCheck` plugin per
   strategy (registry lookup, no if/else) combining multiple `EvidenceSource`s (connector + CI + runtime
   + human) per policy into the two-part `Resolution`; a red CI keeps a connector-cleared problem open;
   an unavailable source never closes. (10 tests.)
5. **S4b-1 — Event-driven coordinator core ✅ (done, green).** A `LifecycleCoordinator` with the four
   owner rules: one entry `advance(problem, trigger)` behind `tick()` (POLL) and `notify(event)`;
   idempotent events (`ProcessedEventLog`); generic events only (`EvidenceChanged`/`ExecutionFinished`/
   `ApprovalGranted`/`ApprovalRejected`/`RuntimeRecovered`); a `ProblemState` machine (NEW → IN_PROGRESS
   → VERIFIED → CLOSED / ESCALATED) recording every `Transition` with its reason. (7 tests.)
6. **S4b-2a — Coordinator hardening + adapter registry ✅ (done, green).** The five integration rules:
   event `source` provenance on events + transitions; a legal-transition guard (out-of-order/late events
   ignored, never corrupting state); `tick()` documented + tested as reconciliation (converges with zero
   events); a hot-swappable `AdapterRegistry` (`drain_all`, failing adapter contained); adapters only
   produce generic events, never mutate state. (6 tests.)
7. **S4b-2b-1 — Operational maturity (recoverable, tick-independent, measurable) ✅ (done, green).**
   `ProblemRecord` + coordinator `export`/`recover` (rebuild state from persistence on restart);
   `notify()` proven to advance without a tick (tick = reconciliation only); `LifecycleMetrics`
   (active / MTTV / MTTC / retries / escalations / verification-failures / event-latency) wired as
   `on_transition` + `on_advance`. (6 tests.)
8. **S4b-2b-2a — Stateless emission + `AttemptStore.forget` ✅ (done, green).** Pure per-domain emitters
   (`emission.py`: website/tls/http-security/vulnerability/secrets/runtime) mapping connector evidence →
   per-asset `ProblemSignal`s with no state of their own (detection ≠ ownership; jobs stateless); the
   signals route straight into the strategy layer. `AttemptStore.forget` frees a resolved chain so a
   recurrence starts fresh. (7 emitter + 1 chain tests.)
9. **S4b-2b-2b-1 — Composition Root ✅ (done, green).** One `build_lifecycle` factory creates + wires
   every part (ledger/metrics/attempt-store/driver/resolver/coordinator/registries/emitters/adapters)
   from injected leaf primitives (connector-read, evidence, open/check/escalate-mission); the daemon
   merely hosts the returned `LifecycleComposition.sync()`. Proven end-to-end with fakes: detect → open
   gated remediation → verify → close, and detect → escalate-at-cap. (2 tests.)
10. **S4b-2b-2b-2 — Real primitives + daemon hosting + live ✅ (done, live-validated).** `lifecycle_host`
    supplies the real leaf primitives (connector re-fetch `use_cache=False` + re-emit for the clearing
    evidence, runtime-view for execution evidence, `OrganizationRuntime.run_mission` / `engine.get`);
    `OrganizationMonitor.tick` **hosts `composition.sync()` and the old `Jobs → MissionGate → run_mission`
    scheduler is removed** — one operational path; ledger + metrics persisted to `lifecycle.json` and
    recovered on startup; a dashboard **Lifecycle** tab reads it (viewer-only). Proven live on the running
    daemon: detect a down site → NEW → IN_PROGRESS → (restart) recover → VERIFIED → CLOSED, with MTTC
    computed across the restart, a recurrence as a fresh lineage, escalation at the cap, and the dashboard
    showing the same state as the ledger + logs.

**Core is now FROZEN** (owner, 2026-07-31): Lifecycle, Coordinator, Correlation, Strategy & Resolution
frameworks change only for bug fixes / performance; new capability (S5 Approval Experience, S6 Dashboard
& Operations) builds *on top* of this stable base.
5. **S5 — Cross-process approval.** Extend `RuntimeGateway` to materialize + approve/reject an org
   problem by re-derivation from the connector. (Tests: re-derive determinism, self-verify on clear.)
6. **S6 — Dashboard lifecycle lens + live validation.** Surface problem state (open / awaiting /
   remediating / verifying / resolved / escalated) and the approve action; the Safe-Class mechanism
   present but empty (v1). Redeploy; verify live.

## 9a. Acceptance scenarios (green)

`tests/test_lifecycle_scenarios.py` proves the assembled engine end-to-end on the owner's seven real
flows (fakes only for the host's connectors + mission seams): **① Website Down** (detect → own →
strategy → hold at the approval gate → approve → verify → close, with the audit trail
`NEW→IN_PROGRESS→VERIFIED→CLOSED` and metrics updated); **② TLS Expiry** (infrastructure strategy,
runtime verification, close on evidence gone); **③ Compliance Gap** (policy-update strategy, policy-owner
approval, verify, close); **④ Recurrence** (close → recur next day → fresh lineage, the spent one not
revived); **⑤ Lost Webhook** (zero events, the tick alone reconciles to the correct state); **⑥ Daemon
Restart** (export → recover → continue to closure without losing state); **⑦ Duplicate Events** (same
`event_id` twice → ignored, no duplicate transition / attempt / mission).

## 10. Resolved decisions (owner, 2026-07-30)

- **D1 — Mission durability → Re-derivation for v1.** No shared store/database now; the Connector is
  the source of truth and the mission is re-derived from it. A `PostgresMissionStore` remains a later
  upgrade if cross-restart live continuity is ever needed.
- **D2 — Safe Class → empty.** Every consequential action goes through Human Approval until the
  platform proves stable. The mechanism ships closed.
- **D3 — Attempts & escalation → cap 3, then Supervisor, then CEO.** Three attempts maximum; exhaustion
  escalates to the Supervisor; if the problem persists or becomes critical, the Supervisor escalates to
  the CEO.
