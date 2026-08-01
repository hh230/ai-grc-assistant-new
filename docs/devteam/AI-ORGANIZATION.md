# The AI Organization

The **AI Organization** is the platform's permanent, mission-governing organization — **CEO, CTO,
CISO, GRC Expert, QA, DevTeam**, watched by a **Supervisor**. It is built **on** the frozen v2 Core
and the existing observability + Operations Dashboard. It is **not** a new Runtime, Orchestrator,
Dashboard, or state model — it is a composition (`devteam/packages/devteam-organization`) that reuses
what already exists.

> Realizes CLAUDE.md §11 (multi-agent architecture) as a second cohort alongside the engineering
> squad (Foreman/QA/Monitor/Security/Developer/Reviewer, ADR 0061). Both cohorts are the `PLATFORM`
> subsystem, run on the frozen `MissionEngine`, and are observed the same way. **QA is shared** — the
> organization's quality member *is* the squad's `QaAgent`, reused, never duplicated.

## What was reused (not rebuilt)

| Concern | Reused component |
|---|---|
| Runtime / lifecycle | frozen `mission-engine` (`MissionEngine`, `ExecutionPort`, `MissionStatus`) |
| Step execution | `DevToolExecutor` + `AgentTool` + `build_agent_registry` (one Tool path) |
| Live state model | `RuntimeStateView` / `AgentStatus` (Idle/Thinking/Working/Waiting/Blocked/Offline) — unchanged |
| Observability | `DevTeamObservability` → `ObservingExecutor` → journal (`devteam_view_from_journal`) |
| Dashboard | the existing SPA — Mission Cards, Timeline, Live Pipeline (SSE), Agent Inspector, Executive |
| QA member | the engineering squad's `QaAgent` |

The **only** change to a frozen-listed package was **additive**: the org roles/capabilities were
added to the `AgentRole`/`AgentCapability` enums (the §17 extension point) and to the observability
**adapter** roster (`ORG_ROSTER`, `CAPABILITY_ROLES`, `seed_roster`). Because the Dashboard renders
whatever `/api/agents` returns, the organization appears **automatically** — zero Dashboard change.

## Mission flow

A mission is planned by the CEO (`OrganizationPlanner`) and driven by the frozen Mission Engine
through capability-routed steps:

```
STRATEGY(CEO) → ARCHITECTURE(CTO) → SECURITY_REVIEW(CISO) → GRC(GRC Expert) → TESTING(QA) → DELIVERY(DevTeam)
```

**Dynamic skipping** (the Orchestrator routes): the CEO always leads and the DevTeam always closes;
the middle stages run only when the goal is relevant to them (a pure policy mission skips the CTO; a
code change skips the GRC stage). An unscoped goal keeps the full pipeline — fail toward *more*
governance. Each stage records a real `AgentDecision` (Mission Approved / Architecture Approved /
Security Approved / Risk Accepted / Evidence Requested / Delivery Approved) into the existing decision
history, and hands off to the next — the handoff chain the Timeline shows. Consequential code changes
are **not** made here: the DevTeam stage plans delivery and defers landing to the squad's existing
human-gated fix-it flow (ADR 0044).

## The Supervisor

One controller above all agents. It **supervises; it never replaces the Runtime**: it reads the
frozen `RuntimeStateView`, computes health, detects stalled agents/missions, escalates them, and
recovers via the Mission Engine's **public API** (`cancel`) only. Its observable **heartbeat** is a
real `SUPERVISION` mission (a live health check), so it appears in the Dashboard doing real work.

## Running it

Continuous Worker (writes the same journal the Dashboard reads):

```bash
uv run --directory devteam/packages/devteam-organization python -m devteam_organization \
  --repo-root "$(git rev-parse --show-toplevel)"
```

One pass with a mission, no daemon:

```bash
uv run --directory devteam/packages/devteam-organization python -m devteam_organization \
  --once --goal "Map ISO 27001 access controls for the export service" \
  --repo-root "$(git rev-parse --show-toplevel)"
```

The Dashboard (already deployed) shows the organization the moment the journal has activity.

## Extending it

- **A new organization role** → add to `AgentRole` + `AgentCapability`, map it in the observability
  adapter (`CAPABILITY_ROLES` + `ORG_ROSTER`), write the agent, and add it to
  `build_organization_agents`. No Core/executor/registry/dashboard change (§17).
- **Real reasoning** → each agent's seam (CISO `ThreatReview`, GRC `FrameworkKnowledge`, QA
  `SuiteRunner`) is injected; swap the deterministic default for an LLM- or tool-backed source
  behind the same boundary, exactly as the Developer's `PatchProposer` will gain an LLM.

## The Mission Lifecycle — continuous detection to closure

The organization does not only wait for a submitted mission: it **continuously detects real problems
and drives each one to closure**. This is the **Organization Mission Lifecycle**
([ADR 0065](../adr/0065-organization-mission-lifecycle.md) · [MISSION-LIFECYCLE.md](./MISSION-LIFECYCLE.md))
— the **single operational path**, hosted by the daemon and **frozen (2026-07-31)**. It runs inside the
existing service — **no new runtime, scheduler, or dashboard.**

**Detection is stateless.** Each tick, the daemon reads the read-only **Connectors** (below) and
per-domain **emitters** (`lifecycle/emission.py`: website, TLS, HTTP-security, vulnerability, secrets,
runtime) map that evidence into per-asset `ProblemSignal`s — detection has no state of its own
(detection ≠ ownership). A problem's identity is
`correlation_ref = {mission_type}:{asset}:{evidence_signature}`, so the same condition on different
assets is a distinct lineage and a recurrence on one asset dedups.

**The `LifecycleCoordinator` is the single owner of every problem's state**, driving each one
`NEW → IN_PROGRESS → VERIFIED → CLOSED / ESCALATED`:

- **Remediation is a Strategy** (`Mission → Strategy → Approval → Execution`). The strategy's
  `ApprovalPolicy` — keyed on **strategy + severity, not mission type** — sets the step's
  `consequential` flag, so the frozen Mission Engine's human gate (`AWAITING_APPROVAL`) fires for
  anything consequential. The **Safe Class is empty (v1)**: every consequential action is human-gated.
- **Verification is two-part** (a `ResolutionCheck` per strategy): **evidence-cleared** (a fresh
  connector re-fetch in which the originating signature is gone) **and** **execution-evidence** (a code
  fix's CI is green; a header is present; a CVE is absent from a freshly regenerated report). A problem
  closes only when both hold — "verified" is a real re-observation, never an assertion.
- **Escalation** ladders on exhaustion: **3 attempts → the Supervisor → the CEO** (immediately if the
  problem is critical).

The daemon's single operational step per tick is `lifecycle.sync()`; the coordinator advances each open
problem, opens gated remediation missions through the existing runtime, and persists the ledger +
metrics to `lifecycle.json` (recovered on restart). The earlier `Jobs → MissionGate → JobScheduler`
scheduler was **superseded by this lifecycle** (ADR 0065) and is no longer on the operational path.

**Departmental responsibilities.** Each role still owns the continuous inspection of its domain, now
expressed as **read-only connectors** feeding the lifecycle: CISO (website / security headers / TLS /
dependency & secret reports / runtime health), CTO (GitHub builds & PRs), QA (test & regression
reports), GRC Expert (policy / evidence / controls), and the Supervisor (agents + workers + runtime
health). The connector roster is in the next section; wiring a new domain into the lifecycle is a
registration (a new emitter + strategy + `ResolutionCheck`), never a Core edit.

**The no-fabrication contract** holds end to end: an `UNAVAILABLE` connector opens nothing, an empty
source is a healthy idle, and a problem that can no longer be observed is *resolved*, not asserted.

## Connectors — the read-only integration layer

A job never talks to an external system directly. It requests a **connector** from the registry and
`fetch()`es evidence:

```
Job → Connector → External System → Evidence → Mission
```

This is `devteam_organization.connectors`, running inside the existing service — **no new runtime,
scheduler, or dashboard.**

**The framework.** A `Connector` declares `id / name / type / owner / enabled` and turns nothing into
a `ConnectorResult` (status + data + latency). The `ConnectorRegistry` is the **only** fetch path — it
owns the **TTL cache** (`ConnectorCache`), timing, `ConnectorMetrics` (fetches / failures / cache
hits / avg latency), the per-connector `ConnectorState` (health / last_check / latency / status), and
the **fail-safe guard**: even if a connector's `fetch` raised, the registry returns an `ERROR` result
rather than propagating. Jobs call `registry.fetch(connector_id)`; they never instantiate a connector.

**The connectors** (each wraps an existing integration — no duplication — and fails safe to
`UNAVAILABLE`):

| Connector | Owner | Wraps / reads |
|---|---|---|
| Website | CISO | HTTP probe — availability, status, response time |
| HTTP Security | CISO | HTTP headers — HSTS/CSP/X-Frame/X-Content-Type/Referrer/Permissions-Policy |
| TLS | CISO | `ssl` — expiry, hostname validity, issuer |
| Vulnerability | CISO | a SARIF/JSON/CSV report the project produces |
| Secrets | CISO | a secret-scan report the project produces |
| Runtime | Supervisor | `RuntimeStateView` + LaunchAgent worker status |
| GitHub | CTO | the existing `GitHubActions` — failed builds + open PRs |
| Test Reports | QA | JUnit/pytest/coverage/regression reports |
| Compliance | GRC Expert | a policy/evidence/controls report |
| Filesystem | GRC Expert | read-only folder listing |
| Playwright | QA | read-only Playwright results (live run is the injectable seam) |

**Jobs are orchestration only.** Every job was refactored to remove direct probing: it fetches its
connector, interprets `ConnectorResult.data`, and opens a Mission only on real evidence. An
`UNAVAILABLE` connector ⇒ the job records "unavailable" and opens nothing.

**Config.** One file (YAML, JSON also accepted) with `${ENV_VAR}` overrides holds every connector
source, cadence, and threshold — empty sources ⇒ Unavailable connectors, idle jobs.

**Dashboard.** A **Connectors** tab reads `/api/connectors` → the `connectors.json` snapshot and shows
Name / Owner / Health / Latency / Last Sync / Owner Jobs / Status. No new dashboard.

**The no-fabrication contract, restated at the connector layer:** connectors are read-only, fail safe,
and never invent results; a source that cannot be reached is Unavailable, and Unavailable never becomes
a Mission.
