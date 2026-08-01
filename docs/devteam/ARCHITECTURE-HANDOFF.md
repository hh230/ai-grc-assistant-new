# DevTeam Platform — Architecture Handoff (RC1)

> **Audience:** an engineer joining tomorrow who must understand the platform *before* reading code.
> **Status:** Release Candidate 1. The platform is frozen at v1.0 (see §12). Build the **product**
> on top of it — do not reopen these layers.
> **Companion docs:** ADRs [0061–0064](../adr), [DASHBOARD-ARCHITECTURE.md](DASHBOARD-ARCHITECTURE.md),
> [OBSERVABILITY-VALIDATION.md](OBSERVABILITY-VALIDATION.md), [DESIGN.md](DESIGN.md).

---

## Table of contents
1. What this platform is
2. The big picture (one diagram)
3. Runtime architecture
4. Observability architecture
5. Dashboard architecture
6. Public API contracts
7. DTO shapes (the frozen wire format)
8. Design principles
9. Extension points
10. Non-goals
11. Known limitations
12. Release & versioning (RC1 freeze)
13. Operating the platform

---

## 1. What this platform is

The **DevTeam Platform** is an autonomous, mission-centric engineering team that maintains this
codebase — it watches CI, diagnoses failures, proposes fixes behind a human approval gate, and is
observable end-to-end. It is **not** the product. It is the platform the **AI GRC Product** will be
built on top of.

Three layers, each frozen, each with a single job:

| Layer | Package(s) | Job | Frozen |
|---|---|---|---|
| **Runtime** | `v2/packages/*` (Core) + `devteam-*` runtime/agents | Execute governed missions | v1.0 |
| **Observability** | `devteam-observability` | Turn runtime activity into a read model | v1.0 |
| **Dashboard (DevTeam Ops)** | `devteam-dashboard` | Present the read model; drive the gate | v1.0 |

The golden rule that ties them together: **data flows one way — up.** Lower layers never depend on
higher ones. The Dashboard reads a projection; it never reaches into the Runtime to compute facts.

## 2. The big picture

```
   GitHub CI failure ─► Monitor (devteam-runtime) ─► Mission on the frozen v2 Core
                                    │                        │
                                    │                 emits runtime events
                                    ▼                        ▼
                           Human approval gate      devteam-observability
                           (approve / reject)                │
                                                     writes JSONL journal (a transport)
                                                             │
                                                     RuntimeStateView  ◄── the ONE read seam
                                                             │
                                        ┌────────────────────┼────────────────────┐
                                        ▼                    ▼                    ▼
                                   Mission View          Agent View        Executive View
                                  (pipeline_view)       (agents_view)      (executive_view)
                                        └────────────────────┴─────────► composed by ─┘
                                                             │
                                                     Dashboard SPA (read-only)
```

## 3. Runtime architecture

**The brain is the Mission Engine, not the LLM.** Work is modeled as a **Mission** with a lifecycle
(Created → Planned → Executing → Awaiting Approval → Completed / Failed / Cancelled). This is the
frozen **v2 Core** (ADR 0042/0045); the relevant packages:

- `v2/packages/mission-engine` — mission lifecycle, planning, human-approval gate, ports.
- `v2/packages/event-bus` — synchronous in-process bus + transactional outbox (no broker; ADR 0039/0043).
- `v2/packages/tool-registry` — the catalog; every capability is a registered, schema-validated Tool.
- `v2/packages/ai-orchestrator` + `pipeline-*` — the per-step grounded-answer pipeline (retrieve → prompt → validate).

**The DevTeam is a team of agents on that Core** (ADR 0061). Fifteen `devteam-*` packages compose it:

- `devteam-runtime` — composition root; the **Monitor** loop (poll CI → open a fix-it mission → gate).
- `devteam-agents` — the agents (realizations of the agent protocol): **Foreman, QA, Monitor, Security, Developer, Reviewer**.
- `devteam-protocol` — the collaboration protocol; **the boundary is the messages**, agents are realizations (ADR 0062).
- `devteam-intake` / `devteam-chain` — mission intake, correlation, and the fix-it chain model (ADR 0063/0064).
- `devteam-analysis` / `devteam-tools` / `devteam-github` / `devteam-ci` — failure analysis, dev tools, the GitHub connector, CI tooling.
- `devteam-contracts` — shared contracts. `devteam-observability` / `devteam-dashboard` — see §4/§5.
- `devteam-organization` — the **AI Organization** (CEO/CTO/CISO/GRC Expert/QA/DevTeam + Supervisor) and the **Mission Lifecycle** (ADR 0065). `devteam-approval` / `devteam-approval-api` — the generic resumable Approval domain + its API (S5, human-in-the-loop).

**Key runtime facts a new engineer needs:**
- The v2 mission/tool/event Core is **synchronous** (sync `psycopg3`, in-process bus). Do not add async to it.
- Agents act **only through Tools**; no agent self-authorizes a side effect. Consequential actions pass a **human gate**.
- The Monitor is **single-process, single-threaded**, with an in-memory mission store (this shapes the Dashboard — see §5).

## 4. Observability architecture

`devteam-observability` turns the runtime's activity into a clean, replayable **read model**. It is
**DevTeam-scoped** (product agents are out of scope for this milestone) and **roster-neutral** at its
core (a second agent system plugs in via an adapter, not a core change).

**Two halves:**

- **`core/`** — pure model, no runtime imports:
  - `events.py` — the runtime facts: `MissionObserved`, `AgentStarted`, `AgentCompleted`,
    `AgentDecisionRecorded`, `AgentHandoffOccurred`, `AgentAssigned`, `AgentStatusChanged`.
  - `ids.py` — `AgentId (subsystem, role)`, `AgentStatus`, `AgentSubsystem` (roster-neutral identity).
  - `session.py` — **`AgentSession`**: one immutable record of one agent executing one step
    (id, mission, step, start/end, duration, decision, artifacts, output, errors, parent/child links).
  - `registry.py` — **`AgentRuntimeRegistry`**: folds the event stream into live state
    (`AgentRuntimeState`, `MissionRuntimeState`) + an append-only session ledger.
  - `view.py` — **`RuntimeStateView`**: the read façade (agents, missions, sessions, ownership, feed).
  - `journal.py` — the JSONL journal: `JournalingObserver` (write), `JournalReader` /
    `build_view_from_journal` (read), `JOURNAL_SCHEMA_VERSION` (every record is versioned).
- **`adapter/`** — wires the roster-neutral core to the DevTeam runtime:
  - `observing_executor.py` — observes at the **`ExecutionPort`** seam (a `StepRequest` carries
    mission/step/tenant — the boundary where identity survives, unlike the agent boundary).
  - `wiring.py` — `DevTeamObservability`, `devteam_view_from_journal`. `roster.py` / `mission_bridge.py`
    / `capture.py` / `result_courier.py` — roster seeding, mission-event bridging, step capture.

**How to think about it:** events are ingress facts → the registry projects them into state → the
journal is a **swappable transport** (schema-versioned JSONL today; the reader could point at anything
tomorrow). The Dashboard consumes **only** `RuntimeStateView`, never the journal file.

## 5. Dashboard architecture

`devteam-dashboard` is a **presentation-only** operator tool: FastAPI serving JSON + one static SPA
(`static/{index.html,app.js,styles.css}` — no framework, no build step). Bound to `127.0.0.1:8787`,
no auth. Full detail in [DASHBOARD-ARCHITECTURE.md](DASHBOARD-ARCHITECTURE.md); the essentials:

- **One read seam.** The view modules import **only** `devteam_view_from_journal`. They never open
  or parse the journal, never import runtime internals.
- **Three experiences, one read model:**
  - **Mission Experience** (`pipeline_view.py`) — mission cards → timeline → session details; the
    timeline is **live via SSE** (`/api/pipeline/{id}/stream`), patching only changed nodes.
  - **Agent Experience** (`agents_view.py`) — roster → inspector (identity, live status, activity
    timeline, operational metrics). `agent_metrics(dto, sessions)` is the **additive** per-agent metric.
  - **Executive Experience** (`executive_view.py`) — command center: Overview + Organization View +
    Operations Intelligence. It **composes** the Mission/Agent outputs; it computes no new facts.
- **The one runtime *write* path** is separate: `runtime_gateway.py` re-derives a gated mission on
  demand and drives the existing `ApprovalGateway` (the "Open Missions" approve/reject feature). This
  exists because the Monitor keeps missions in-process — a separate process can't read them, so the
  Dashboard re-materializes the deterministic diagnosis and approves via the real gate.

## 6. Public API contracts

All read routes return additive `dict` DTOs. **Existing keys and their meaning are the frozen
contract** (§7); new keys may be added, keys are never removed or repurposed without a version bump.

| Method & route | Purpose | Read source |
|---|---|---|
| `GET /api/executive` | Command center (overview + organization + insights) | composition of the below |
| `GET /api/pipeline` | Observed mission cards | `RuntimeStateView.missions` + `session_summary` |
| `GET /api/pipeline/{id}` | One mission's timeline | `mission_flow` + `mission_sessions` |
| `GET /api/pipeline/{id}/stream` | **SSE** live timeline (emits on change; `event: done` at terminal) | re-reads the above |
| `GET /api/agents` | Live roster + recent sessions | `agents` + `recent_sessions` |
| `GET /api/agents/{key}` | Agent inspector (state + own timeline + metrics) | `agent_sessions` + `agent_metrics` |
| `GET /api/overview` | Monitor infra health (workers, last poll, open PRs) | log + plist + GitHub |
| `GET /api/missions` · `/{pr}` | Open PRs + on-demand diagnosis (the actionable set) | GitHub + re-derivation |
| `POST /api/missions/{id}/approve` · `/reject` | **The only writes** — drive the approval gate | `ApprovalGateway` |
| `GET /api/logs` · `/api/metrics` · `/api/settings` | Monitor log tail, daily counts, deployment config | log + plist |

## 7. DTO shapes (the frozen wire format)

The stable fields the SPA renders. (Illustrative, not exhaustive — see the view modules for the full
set; these are the contract.)

**Session** (everywhere a session appears): `session_id, agent{subsystem,role,key}, mission_id,
step_id, status(active|completed|failed), started_at, ended_at, duration_ms, decision{verdict,
rationale,confidence}|null, artifacts[{kind,title}], output_summary, errors[], parent_session_id,
child_session_ids[]`.

**`/api/agents/{key}`**: the agent DTO (`agent, display_name, status, current_mission_id,
current_step_id, last_activity_at, executions, completed_missions, average_duration_ms,
decision_history[], active_session|null`) + `sessions[]` + **`metrics`** (`session_count, active_ms,
idle_ms, avg_duration_ms, median_duration_ms|null, decision_distribution{}, missions_completed,
queue{participating,mission_id,status}, …`).

**`/api/executive`**: `missions{total,active,completed,awaiting_approval,active_list[]}`,
`agents{total,utilized,idle,blocked,waiting,engaged}`, `throughput{completed_missions}`,
`decision_distribution{}`, `queue{health,…}`, `utilization{ratio_now,ratio_window|null,…}`,
`organization{fleet,agent_performance[],mission_performance,operational_health}`,
`insights{attention_required,capacity_outlook,operational_summary[]}`.

**Contract invariant:** a figure that cannot be measured is `null` → the UI shows *"insufficient
data"*. Nulls are part of the contract; consumers must handle them.

## 8. Design principles

1. **One-way read model.** `RuntimeStateView` is the single read source. Views never parse the
   journal or import runtime internals.
2. **Executive owns composition, not facts.** The Executive layer sums *additive* metrics the
   Mission/Agent layers already produce; it computes no new runtime fact.
3. **Metrics are additive by design.** Per-agent `session_count/active_ms/idle_ms/decision counts`
   sum across the fleet; per-agent `avg/median` are display-only (fleet averages recompute from raw totals).
4. **Never infer.** No estimates, no predictions. Unmeasurable → `null` → "insufficient data".
5. **Presentation-only Dashboard.** The sole write path is the approve/reject gate.
6. **The journal is a transport.** Schema-versioned and swappable; consumers read the view, not the file.
7. **Roster-neutral observability.** A new agent system is a new adapter, not a core change (ADR 0062).
8. **Feature Freeze on lower layers.** Runtime and Observability do not change to add product features.

## 9. Extension points

Grow at the edges — you should rarely edit a frozen layer:

- **A new dashboard view / metric.** Add a `*_view.py` that reads `RuntimeStateView` (or composes
  existing views), a route in `app.py`, and a tab in the SPA. No runtime/observability change.
- **A second agent system** (e.g., the GRC product agents). Add an `AgentSubsystem` member and an
  **adapter** mapping its roles → `AgentId(subsystem, role)`; the projection and views are unchanged
  (that is the whole point of the roster-neutral core — ADR 0062).
- **A new agent in the DevTeam.** Register it in the roster + protocol; the registry folds its events
  with no code change to the fold.
- **A new Tool / capability.** Register it in the **Tool Registry** (v2 Core §10/§17). Agents discover it.
- **A new observability transport.** `JournalReader` / `JournalingObserver` are the seam; point the
  reader at a different store without touching the views.
- **A new mission trigger.** Intake normalizes triggers into `CreateMission | UpdateMission` (ADR 0063/0064).

## 10. Non-goals

- The Dashboard is **not** the AI GRC product — it is the platform's operator console.
- The DevTeam is **not** the product — it is the engineering platform the product runs on.
- Observability is **DevTeam-scoped** — the GRC product agents are out of scope for this milestone
  (they plug in later via §9's adapter).
- The Dashboard is **not** multi-tenant, authenticated, or internet-facing — it is a localhost operator tool.
- The Executive layer does **not** advise, recommend, or predict — it reports observed facts only.

## 11. Known limitations

- **Journal rotation** is not implemented — the JSONL grows unbounded (a future concern; today's
  volumes are tiny, and reconstruction of 400 missions is ~32 ms).
- **No incremental cache.** `RuntimeStateView` is rebuilt from the journal each request. Fine at
  current scale; revisit if the journal reaches many thousands of missions.
- **Single-process Monitor / in-memory mission store.** A separate process can't read live missions,
  which is exactly why the Dashboard re-derives gated missions on demand (§5).
- **"Completion time" is a session span**, not creation→completion — mission lifecycle timestamps are
  not exposed by the view, so avg completion is measured from completed missions' session spans.
- **Long-running elapsed is client-side** (wall clock vs `active_since`) so the backend stays deterministic.
- **Reserved agent states** (`THINKING`, `WAITING`, `OFFLINE`, `AgentAssigned`) are forward-compatible;
  today's single DevTeam adapter emits `WORKING`/`IDLE`/`BLOCKED` and parks to `WAITING` at gates.
- **Dashboard auth/TLS:** none by design (localhost operator tool). Do not expose it as-is.

## 12. Release & versioning (RC1 freeze)

As of RC1 these are **frozen**. Changing any of them is an architecturally significant decision
(raise it explicitly; do not drift into it):

| Component | Version | What is frozen |
|---|---|---|
| **Runtime** | v1.0 | The v2 Core (mission/tool/event) + the DevTeam runtime & agent roster |
| **Observability** | v1.0 | The event model, `AgentSession`, `RuntimeStateView`, the journal schema (`JOURNAL_SCHEMA_VERSION`) |
| **Dashboard API** | v1.0 | The read routes (§6) and the DTO field contract (§7) |
| **DevTeam Ops** | v1.0 | The Mission / Agent / Executive experiences |

Freeze discipline: additive changes (new optional keys, new views composing existing data) are fine;
removing/repurposing a key, changing the read seam, or editing a lower layer to serve a product
feature are **not** — they need an ADR.

## 13. Operating the platform

**Run the Monitor with Observability** (writes the journal the Dashboard reads):
```bash
uv run --directory devteam/packages/devteam-runtime python -m devteam_runtime.monitor \
  --repo <owner>/<name> --repo-root <checkout> --poll-seconds 60 --max-attempts 3
```
- Observability is **on by default**; it writes `~/Library/Logs/devteam-monitor/runtime.jsonl`.
  Override with `--journal <path>`, disable with `--no-journal`.
- In production the Monitor runs as a macOS **LaunchAgent** (`com.rasheed.devteam-monitor`).

**Run the Dashboard** (reads the same journal; presentation-only):
```bash
uv run --directory devteam/packages/devteam-dashboard python -m devteam_dashboard
```
- Opens `http://127.0.0.1:8787` (also a `.claude/launch.json` entry named `devteam-dashboard`).
- Landing tab is **Executive**. Navigation: Executive → Organization → Mission → Session → Agent
  (and back Agent → Mission). Approvals happen under **Open Missions** (the only write action).

**Verify the whole platform** (15 standalone package suites):
```bash
uv run --directory devteam/packages/devteam-ci python -m devteam_ci.test_runner --root devteam/packages
```

---

*This is a descriptive handoff of a frozen platform. The next work is the **AI GRC Product** —
Risk / Compliance / Policy / Report / Workflow experiences — built on top of these v1.0 layers, not
by extending them.*
