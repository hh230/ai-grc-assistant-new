# Core Freeze Review — the Mission Lifecycle

> **Purpose.** This is the auditable record behind freezing the Mission Lifecycle Core (ADR 0065). It
> is evidence, not description: an architecture diff, an evidence pack captured from the running daemon,
> the freeze manifest, and the extension points. A reviewer should be able to check each claim.
>
> **Date:** 2026-07-31 · **Decision:** [ADR 0065](../adr/0065-organization-mission-lifecycle.md) —
> Implemented & live-validated; Core frozen.

---

## 1. Architecture diff

### Before — two ways to open a mission

```
Connector ─▶ Job (stateful: MissionGate, failure counters)
                 │  edge-triggers, opens directly
                 ▼
           OrganizationRuntime.run_mission ─▶ Mission
                 (no ownership after creation; no verify; no close; no metrics)
```

### After — one operational path, the Coordinator owns every problem

```
Connector ──▶ Emitter (stateless: observe → emit ProblemSignal)
                                │
Adapter ─▶ Generic Event ──▶ LifecycleCoordinator  ◀── the single owner of state
                                │  NEW → IN_PROGRESS → VERIFIED → CLOSED / ESCALATED
                                ├─▶ Strategy → Approval → open_mission → run_mission
                                ├─▶ Resolution (connector re-fetch + runtime/CI/human)
                                └─▶ Ledger + Metrics  ──▶  lifecycle.json (read-only projection)
                                                              │
                                       Dashboard / Metrics / Audit  ◀── viewer only
```

### What was removed / what became the single entry (checkable)

| Change | Evidence |
|---|---|
| The old `Jobs → MissionGate → run_mission` scheduler is **deleted** from the daemon | `grep -c "MissionGate\|build_scheduler\|JobScheduler\|scheduler.tick\|job_runs" monitor.py` → **0** |
| The tick's single operational step is the hosted lifecycle | `grep -c "self._lifecycle.sync()" monitor.py` → **1** |
| `build_scheduler_from_config` → **`build_connector_registry`** (connectors are a read-only evidence source; no scheduler) | `monitor.py` |
| The daemon is a *host*: the `lifecycle/` package imports **nothing** from the daemon | `grep -rn "lifecycle_host\|import monitor" lifecycle/` → **none** |
| Jobs became stateless emitters (`observe → emit`); the `MissionGate` state is gone | `lifecycle/emission.py` |

---

## 2. Evidence pack — captured from the running daemon

A controllable real problem: the website connector pointed at a dead `http://localhost:8123`. Each
pass is a **separate `python -m devteam_organization --once` process**, so the multi-pass run also
exercises restart + recovery.

### 2.1 Logs — the state transitions (real daemon output)

**Pass 1** (site down → detect → own → open):
```
lifecycle on — 11 connector(s), 0 problem(s) recovered
lifecycle: operations:http_//localhost_8123:endpoint_down  — → new  (detected: endpoint_down; connector/emission)
lifecycle: opened mission mis_151e3e2ef4714be6a8e4b119173c83b4 for operations:http_//localhost_8123:endpoint_down
lifecycle: operations:http_//localhost_8123:endpoint_down  new → in_progress  (remediation attempt 1 opened; poll/reconciliation)
```

**Pass 2** — a *new process*; the site is now up (`curl → HTTP 200`):
```
lifecycle on — 11 connector(s), 1 problem(s) recovered
lifecycle: operations:http_//localhost_8123:endpoint_down  in_progress → verified  (connector:satisfied; runtime:satisfied; poll/reconciliation)
lifecycle: operations:http_//localhost_8123:endpoint_down  verified → closed  (resolution policy satisfied; poll/reconciliation)
```

### 2.2 Ledger snapshot (`lifecycle.json`) — after pass 1

```json
{
  "problems": [{
    "correlation_ref": "operations:http_//localhost_8123:endpoint_down",
    "mission_type": "operations", "asset": "http://localhost:8123",
    "evidence_signature": "endpoint_down", "connector_id": "website",
    "severity": "high", "state": "in_progress",
    "first_seen": 1785450315.038074, "last_seen": 1785450315.038074
  }],
  "metrics": { "active_problems": 1, "mean_time_to_close": null, ... }
}
```

### 2.3 Metrics snapshot — after pass 2 (MTTC across the restart)

```
active_problems      = 0     (the endpoint_down problem closed)
mean_time_to_close   = 158.88810396194458 s   ← computed across the restart
                                                (close time in pass-2 process − detect time persisted from pass 1)
```
`active_problems` is derived from the open-timestamps map, so the metrics **always agree with the
ledger**; the map + durations are persisted and restored, so MTTC survives a restart.

### 2.4 Dashboard — the same state (viewer-only Lifecycle tab)

`/api/lifecycle` → the tab rendered (no console errors):
```
The single operational path. Every problem is owned by the LifecycleCoordinator …
1 active ·  MTTV 159s  ·  MTTC 159s  ·  0 escalations  ·  0 retries  ·  0 verify-failures
PROBLEM                                          TYPE      SEVERITY  STATE
http://localhost:8123  missing_header:CSP+HSTS…  security  medium    in_progress
```
The dashboard state == the ledger state == the logs (single source of truth). Screenshot captured in
the session; the tab reads the snapshot the coordinator writes and never mutates it.

### 2.5 Recovery after restart

Pass 2 (a separate process) logged **`1 problem(s) recovered`** and drove that recovered problem to
`verified → closed` — resumed without losing context. Verified again on the deployed LaunchAgent: it
kickstarted onto the new code, recovered a stale snapshot, and (after removing it) restarted with
`0 problem(s) recovered`, `active_problems = 0` — idle, no fabrication.

### 2.6 Correlation — a recurrence is a fresh lineage

During pass 2, the now-up site exposed missing security headers — a **different** problem on the same
asset, opened as its own lineage (different `mission_type`/`evidence`):
```
lifecycle: security:http_//localhost_8123:missing_header:CSP+HSTS+…  — → new  (detected: …)
```
`operations:…:endpoint_down` (closed) was **not** revived; `security:…:missing_header` is a distinct
`correlation_ref`. This is `(mission_type + asset + evidence_signature)` correlation, live.

### 2.7 Duplicate-event idempotency

`tests/test_lifecycle_scenarios.py::test_scenario_7_duplicate_events_are_idempotent`: the same
`event_id` delivered twice → the second `notify` returns `None`; **no duplicate transition, attempt, or
mission**. Backed by the `ProcessedEventLog` (coordinator rule 2).

### 2.8 Gate

`devteam-chain` 5 · `devteam-organization` 153 · `devteam-dashboard` 71 — ruff + mypy clean, as of the
freeze gate (final v2.0.0 counts: `devteam-organization` **165** · `devteam-dashboard` **73**). (A
pre-existing `_fakes` / unused-`type: ignore` mypy nuance in `devteam-dashboard`'s **test** files is
non-gating — the suites pass and the source is mypy-clean.)

---

## 3. Core Freeze Manifest

The following modules are **stable**. They change only for **bug fixes and performance** — never for
new capability. New capability is added at the extension points (§4), not by editing these.

| Frozen unit | Module | Responsibility (unchanged) |
|---|---|---|
| **LifecycleCoordinator** | `lifecycle/coordinator.py` | The single owner of problem state; `advance`/`tick`/`notify`; the ProblemState machine + transition rules |
| **ProblemLedger** | `lifecycle/correlation.py` | The active-problem set; register / find_active / deactivate |
| **Correlation** | `lifecycle/correlation.py` | `ProblemSignal` identity = `(mission_type, asset, evidence_signature)` |
| **Strategy Framework** | `lifecycle/strategy.py` | `RemediationStrategy`, `ApprovalPolicy`, `RemediationPlanner`, `StrategyRegistry` |
| **Resolution Framework** | `lifecycle/resolution.py` | `ResolutionCheck`, multi-evidence `EvidenceResolutionCheck`, the registry |
| **Event Model** | `lifecycle/coordinator.py`, `lifecycle/adapters.py` | `LifecycleEvent` (generic kinds), `Trigger`, `Adapter`, idempotency |
| **Composition Root** | `lifecycle/composition.py` | `build_lifecycle` — the one place that assembles + injects everything |
| **Driver / Metrics** | `lifecycle/driver.py`, `lifecycle/metrics.py` | The advance policy + escalation ladder; the metric definitions |

**Rule:** a PR that changes the *behavior* of any unit above is rejected unless it is a bug fix (with a
failing test first) or a measured performance change (no behavior delta). The ~90 lifecycle tests + the
7 acceptance scenarios are the regression guard.

---

## 4. Extension points — where new capability goes

A new developer adds features **here**, without touching the Core:

| To add… | Do this | No change to |
|---|---|---|
| **A connector** (new evidence source) | Implement the connector; register it in the `ConnectorRegistry` (config) | Core |
| **An adapter** (new event source: GitLab, Jenkins, a webhook) | Implement the `Adapter` protocol (`drain`); register in the `AdapterRegistry` | Coordinator |
| **A strategy** (new remediation approach) | Implement `RemediationStrategy`; register in the `StrategyRegistry` | Resolution, Coordinator |
| **A ResolutionCheck** (new verification) | Implement `ResolutionCheck` (or compose an `EvidenceResolutionCheck`); register per strategy | Coordinator |
| **An EvidenceSource** (new signal: CI, human, a data store) | Inject a callable into `build_evidence_sources` | Checks, Coordinator |
| **A dashboard view** | Add a read-only `*_view.py` + route + tab; read a snapshot | Lifecycle (viewer-only, one-way) |
| **An approval policy** | Add an `ApprovalRequirement`/`ApprovalPolicy` mapping in a strategy | Coordinator, gate mechanics |
| **A mission type / domain** | A new `mission_type` string + an emitter + a strategy + a check | Correlation identity, Core |

Every one of these is a *registration* or an *injected primitive* — the plugin pattern (CLAUDE.md §17).
The daemon (`lifecycle_host.py`, `monitor.py`) is the host that wires them; it holds no lifecycle logic.
