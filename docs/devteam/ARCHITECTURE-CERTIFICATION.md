# AI Organization — Architecture Certification Review

**Date:** 2026-07-31 · **Scope:** the AI Organization platform (Lifecycle Core, Correlation,
Strategy Engine, Resolution Checks, Connectors, Approval Domain, Approval API, Operations Projection,
Dashboard Viewer). **Method:** evidence-based — every claim below is backed by a command that anyone
can re-run. This is **not** an ADR; it is a certificate of architectural integrity. It certifies that
the Core is frozen, the seams are honored, and future work can be built as plugins/domains rather than
Core edits.

> **Verdict: PASS — Production Ready.** All six certification lines are clean. The one operational
> recommendation raised in review — the activity timeline surviving a restart (**AR-1**) — has been
> **applied and live-proven** (host-only fix; no Core, contract, state, or dependency change). One
> observation (**OBS-1**) records a pre-existing legacy subsystem in the dashboard that shares no state
> with the org lifecycle; it is not debt and does not block reliance. **The Core is hereby declared
> definitively frozen** (§ Freeze Declaration): no Core changes except bug fixes or performance work.

---

## D1 — Single Source of Truth

**Question:** Is `operations.json` fully derived? Is any state stored in two places that can drift?
Does any View recompute instead of reading the projection?

- **The projection is derived, not stored.** `build_operations_snapshot(...)` folds the live objects
  (coordinator `export()`, `approvals.pending()`, `runtime.view.missions()`, `metrics_snapshot()`,
  `activity.events()`) each tick. The projection holds no independent state; `write_operations_snapshot`
  only serializes.
- **The Viewer reads verbatim.** `operations_view.read_operations` parses `operations.json` and returns
  it; it computes nothing.
- **No drift.** The `LifecycleCoordinator` is the sole owner of *problem state*; the `ApprovalService`
  is the sole owner of *decision state*; they are linked by `correlation_ref == target_ref` and joined
  **one-way** (decisions flow into the coordinator via `notify`, never the reverse). Each snapshot file
  (`operations.json`, `lifecycle.json`, `connectors.json`) has exactly **one writer** — the daemon.

**Verdict: ✓** One derived projection; one writer; no recompute; no dual-write.

---

## D2 — Backdoors

**Question:** Does anything bypass `External → Adapter → Lifecycle → Projection → Viewer`?

```
$ grep -rn "lifecycle|coordinator|devteam_organization" devteam-approval-api/   → only docstrings
$ grep -rn "ProblemLedger|MissionEngine|LifecycleCoordinator" dashboard/operations_view.py → NONE
$ grep -rn "run_mission|open_mission" connectors/               → only "open_missions" (a COUNT metric)
# ApprovalDecisionAdapter.drain() returns list[LifecycleEvent] — it never calls notify/advance.
```

- **API → Approval only.** The Approval API talks to `ApprovalService` over `FileApprovalStore` and
  nothing else — never the coordinator.
- **Adapter → events only.** `ApprovalDecisionAdapter.drain()` produces events; the frozen `sync()`
  feeds them to `notify()`. The adapter never mutates state (rule 5).
- **Connectors → read-only.** They fetch and return a `ConnectorResult`; they never open a mission
  (`open_missions` is a metric they *count*, not an action).
- **Operations Viewer → the projection only.**

**Verdict: ✓ for the org lifecycle.** See **OBS-1** for the dashboard's separate squad flow.

---

## D3 — Is the Freeze real?

**Question:** Does adding a Strategy / Connector / Mission Type / Resolution Check require editing any
Core file?

- **The Core is generic.** `driver.py`, `coordinator.py`, `correlation.py` name **no** concrete
  strategy, mission type, or connector (grep returns only a docstring example). Control flow is over
  abstractions (`RemediationStrategy`, `ResolutionCheck`, `Adapter`, `ProblemEmitter`).
- **Every extension point is constructor-injectable** at `build_lifecycle(..., strategies=None,
  resolution_checks=None, emitters=None, adapters=None)`. A new strategy/check/emitter/adapter is added
  by passing a registry — **no edit to `driver`/`coordinator`/the Protocols**.
- **Mission types are strings**; **connectors** are added via `connectors/wiring.py` + config; **frameworks**
  are data. None of these touch the lifecycle Core.
- **Proven for the two most recent domains:** `grep -rn devteam_approval lifecycle/` → **NONE**. S5
  (Approval) and S6 (Projection) were built entirely on host + extension surfaces; the frozen
  `lifecycle/` tree was not edited.

**Verdict: ✓** The freeze is real: extensions register; the Core does not change.

---

## D4 — Dependency Direction

**Question:** Do dependencies flow one way, with no cycles?

```
$ grep -rn "devteam_organization" devteam-approval/    → NONE  (approval is a pure leaf)
$ grep -rn "lifecycle_host|monitor|devteam_approval" lifecycle/  → NONE  (lifecycle is a pure leaf)
```

```
        lifecycle/  (pure Core — depends on nothing above it)
             ▲
   devteam-approval  (pure domain — depends on nothing)
             ▲                         ▲
   devteam-organization host  ─────────┘   (composes lifecycle + approval + runtime)
             ▲
        the daemon (monitor)  →  writes snapshots
                                      ▲
        dashboard Viewer  (reads snapshots; imports no live store for the Operations path)
```

**Verdict: ✓** `lifecycle` and `approval` are pure leaves; the org host composes them; the Viewer
reads files. No cycles.

---

## D5 — Failure Modes

**Question:** Does the system continue if a part fails?

| If this fails… | Behavior | Evidence |
|---|---|---|
| **Approval API** disappears | Daemon runs; gates wait at NEW; the tick reconciles; a self-resolving problem still closes. The daemon imports nothing from the API. | separate process; file-store + reconcile |
| **Dashboard** disappears | No effect — it is a pure read-only Viewer. | daemon has no dashboard dependency |
| **Projection** write throws | `after_tick` is wrapped; the tick logs and continues; `sync()` already ran (before the write), so lifecycle state is unaffected. | `monitor.tick` try/except around `after_tick` |
| **A Connector** stops | Returns `UNAVAILABLE` with empty data — never an exception, never fabricated. No mission opens. | `connectors/framework.py` |
| **An Adapter** drain throws | Contained per-adapter; the tick reconciles regardless. | `AdapterRegistry.drain_all` try/except |

**Verdict: ✓** Every part fails safe; the lifecycle tick is the resilient spine.

---

## D6 — Recovery after restart

**Question:** After a restart, do approvals, ledger, metrics, activity, and the projection all return
with no intervention?

| State | Recovers? | How |
|---|---|---|
| **Approval requests** | ✓ | durable `FileApprovalStore` (`approvals.json`) — read on start |
| **Ledger (problems + states)** | ✓ | `recover_lifecycle` → `coordinator.recover(records)` from `lifecycle.json` |
| **Metrics (active, MTTV, MTTC…)** | ✓ | `recover_lifecycle` → `metrics.restore(metrics_state)` |
| **Projection** | ✓ | derived — the first `after_tick` regenerates `operations.json` from recovered state |
| **Activity timeline** | ✓ | **AR-1 applied** — `recover_activity` rebuilds the `ActivityLog` from the last `operations.json` before the first tick |

**Verdict: ✓** All five recover automatically with no intervention. **Live-proven:** a daemon restart
with two seeded activity events (`detected`, `closed`) re-emitted both into the fresh snapshot — the
timeline survived the restart.

---

## D7 — Performance

| Concern | Bound | Evidence |
|---|---|---|
| **Connector fan-out** | one fetch per connector per tick, TTL-cached | `ConnectorRegistry` cache |
| **Snapshot generation** | `O(problems + approvals + missions + activity)` — small | `build_operations_snapshot` |
| **Tick latency** | `O(active problems)` per pass; 60s poll | `sync()` + `after_tick` |
| **Memory — activity log** | **bounded** (`deque(maxlen=50)`) | `ActivityLog` |
| **Memory — event dedup** | **bounded** (`ProcessedEventLog`, `capacity=10_000`, evicts oldest) | `coordinator.py` |
| **Memory — metrics** | bounded (fixed counters + `_open_at` map = active problems) | `LifecycleMetrics` |

**Verdict: ✓** No unbounded growth; costs scale with the (small) active set, not with history.

---

## Findings

### AR-1 — The activity timeline should survive a restart (D6) · *RESOLVED*
**Applied 2026-07-31.** `recover_activity(activity, operations_path)` rebuilds the `ActivityLog` from
the last `operations.json`'s `recent_activity` on startup, before the first `after_tick`, via the
existing `ActivityLog.restore(...)`. Host-only — no Core, contract, state, or dependency change. Unit
tests: `test_recover_activity_restores_the_timeline`, `test_recover_activity_missing_or_empty_is_safe`.
Live-proven by a daemon restart that retained the seeded timeline. This was an operational enhancement,
not an architectural risk — its resolution turns *Operational Recovery* green.

### OBS-1 — The dashboard carries a second, pre-existing paradigm (D2) · *observation, non-blocking*
`dashboard/runtime_gateway.py` (the "Open Missions" tab, ADR 0061) **re-derives** the *engineering
squad's* CI fix-it missions into its own in-memory store and drives the squad's `ApprovalGateway`
directly — because those missions live in the squad daemon's process memory (cross-process
unreachable). This is a **separate subsystem** from the org lifecycle: it does **not** read the org
ledger/coordinator, and the org's Operations path stays a pure projection. It predates S5/S6. It means
the dashboard is not *uniformly* a projection reader — it has one compute path for the squad. **Future
unification (optional):** give the squad the same projection treatment (a `squad-operations.json`), so
every dashboard surface reads a projection. Not required for the org platform to be stable.

---

## Certification Scorecard

| Line | Status | Basis |
|---|---|---|
| **Core Frozen** | ✅ | D3 (Core generic + injectable registries); S5/S6 edited no `lifecycle/` file |
| **Extension Points Verified** | ✅ | D3 (strategies/checks/emitters/adapters injectable; connectors/frameworks as data) |
| **Dependency Rules Verified** | ✅ | D4 (pure leaves, one-way, no cycles) |
| **Operational Recovery Verified** | ✅ | D6 — approvals/ledger/metrics/projection recover; **activity too (AR-1 applied)** |
| **Production Topology Verified** | ✅ | D5 + live: 3 LaunchAgents, each failure-isolated; daemon independent of API/dashboard |
| **No Architectural Debt Blocking Future Work** | ✅ | AR-1 resolved; OBS-1 is a non-blocking legacy subsystem |

## Overall

The AI Organization is architecturally a **platform**: one source of truth per concern, one-way
dependencies, a genuinely frozen Core behind injectable extension points, fail-safe parts, and bounded
memory. **All six lines certify clean.** The one operational recommendation (**AR-1**) has been applied
and live-proven; **OBS-1** is a legacy subsystem sharing no state with the org lifecycle — optional
future unification, not debt.

**Architecture Certification: PASS.** From here, treat all new work — GRC domains, connectors, agents,
integrations — as **plugins/domains on a stable base**, never Core edits.

## Freeze Declaration

The **Core is declared definitively frozen** as of 2026-07-31. The frozen units are:
`lifecycle/driver.py`, `lifecycle/coordinator.py`, `lifecycle/correlation.py`, the `RemediationStrategy`
and `ResolutionCheck` Protocols (`lifecycle/strategy.py`, `lifecycle/resolution.py`), the event model
(`LifecycleEvent`/`Adapter`), and the composition root (`lifecycle/composition.py`).

**Change policy:** no functional change to these units. Permitted only: (a) bug fixes with a failing
test that proves the defect, and (b) performance work that preserves behavior. Everything else —
strategies, resolution checks, connectors, mission types, adapters, emitters, new domains, new
integrations — is added at the **extension surface** (injectable registries / config / host), never by
editing the Core. A change that cannot be expressed as an extension is a design smell to redesign, not
a Core edit.
