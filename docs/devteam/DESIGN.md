# Autonomous Platform Dev Team — Architecture & Roadmap

> **Status:** IMPLEMENTED & FROZEN (2026-07-31) — Stage 1 design; the three forks in §9 are
> **resolved** (see ADR [0061](../adr/0061-autonomous-platform-dev-team.md)). All phases have been
> built, tested, and frozen — see [ARCHITECTURE-HANDOFF](./ARCHITECTURE-HANDOFF.md),
> [CORE-FREEZE-REVIEW](./CORE-FREEZE-REVIEW.md), and
> [ARCHITECTURE-CERTIFICATION](./ARCHITECTURE-CERTIFICATION.md) (PASS). The package layout proposed
> below is the original Stage-1 sketch; some shipped names differ (see the handoff for the built set).
> **Author:** Lead AI Architect (Claude).
> **Date:** 2026-07-26.
> **Owner decisions (§9):** autonomy = **Safe-Class auto-land** · runtime = **Claude Code
> scheduling → graduate** · first build = **read-only spine**.
> **Scope of this doc:** modular architecture · mission (task) lifecycle · event system ·
> safety model · extensibility · phased roadmap.

---

## 0. Thesis (read this first)

We are building an **internal AI engineering team** — not a chatbot, not a pile of CI
scripts — that continuously **improves, tests, monitors, and secures** the Rasheed GRC
platform, with a human approving anything consequential.

The decisive design move: **the dev team is itself a Mission-Centric platform, built on the
frozen v2 Core.** Every unit of engineering work (triage a CI failure, propose a fix, run a
security sweep) becomes a governed **Mission** with a lifecycle, approval gates, an audit
trail, and events — reusing `mission-engine`, `tool-registry`, `event-bus`, and the audit
outbox that already exist. We *eat our own dog food*: the AI team obeys the same eight
architectural pillars (CLAUDE.md §3) as the product it maintains.

This is the difference between an **engineering platform** and **scattered scripts**:
every capability is a typed, versioned, side-effect-tagged **Tool** in a registry; every
worker is a governed **Agent**; every wake-up is a typed **Event**; every action is
**audited**; nothing consequential lands without a **human gate**.

---

## 1. Reality Gate — what exists, what's missing

Grounded in a full read of the repo (not assumptions):

**Already built (reuse, do not rebuild):**
- **Mission lifecycle** — `v2/packages/mission-engine/mission_engine/lifecycle.py`
  (`MissionStatus`: `CREATED, PLANNED, EXECUTING, AWAITING_APPROVAL, RESUMED, COMPLETED,
  FAILED, CANCELLED, ARCHIVED`; closed legal-transition table; fail-safe terminals).
- **Mission engine + aggregate** — `.../mission_engine/engine.py`, `mission.py`
  (`create/plan/execute/_drive/approve/reject/resume/cancel`).
- **Human approval gate** — `.../mission_engine/approval.py` + the `_drive` gate: a
  `CONSEQUENTIAL` step pauses the mission (`await_approval`), emits
  `MissionAwaitingApproval`, and resumes only on an explicit decision (ADR 0044).
- **Tool contract + registry** — `v2/packages/tool-registry/` (`Tool` protocol, `ToolSpec`
  with `SideEffectProfile = READ_ONLY | CONSEQUENTIAL`, versioning, catalog).
- **Execution seam** — `ExecutionPort` (`.../mission_engine/ports.py`) realized by
  `RegistryExecutor` (`v2/packages/pipeline-tool/pipeline_tool/executor.py`); per-step tool
  selection via `PlanStep.tool` (ADR 0048).
- **Event bus + domain events + audit** — `v2/packages/event-bus/` (`InProcessEventBus`,
  `DomainEvent` carrying `trace_id/tenant_id/mission_id`, `AuditRecord`, `AuditSink`).
- **Durable mission store + transactional outbox** — `v2/packages/mission-store/`,
  composed end-to-end in `v2/packages/mission-integration/`.
- **Ports/adapters discipline** — every seam is a `Protocol` with a reference + a real
  realization; purity enforced by per-package `test_architecture.py`.

**Missing / gaps this team should also close (real findings):**
- **CI covers only the root uv workspace + `apps/web`.** `.github/workflows/ci.yml` never
  runs the **1,000+ tests in `v2/` and `v3/`** (they are standalone packages with their own
  locks/venvs, invisible to `uv sync --all-packages`). *First high-value mission.*
- **No security scanning, no dependency audit, no coverage gate** anywhere in CI.
- **CLAUDE.md §11's six-agent roster is not implemented** — today "agents" are capabilities
  resolving to plans of tools. The dev team is the first true multi-agent implementation.
- **`packages/observability` is a stub;** real logging lives in
  `apps/api/.../observability/logging.py` (JSON, secret-redacting) + Sentry in `apps/web` +
  `v2/.../pipeline-tracing`. The Monitor agent consumes these.

---

## 2. Layered architecture

Two clean layers. **Governance is reused; Execution is new.**

- **Governance layer (reuse v2 Core, unchanged):** Mission Engine, Tool Registry, Event
  Bus, Approval gate, Audit Sink + outbox. Gives us lifecycle, gating, resume, idempotency,
  events, and a tamper-evident audit trail *for free*.
- **Execution layer (new):** the **Foreman** (dev orchestrator) + six specialist **Agents**,
  each an isolated worker (Claude Agent SDK / sub-agent) invoked **only through registered
  Dev Tools**. Agents never mutate state directly — they act through tools, and consequential
  tools are gated.

```
 TRIGGERS (events in)                         HUMAN (approve · reject · steer)
 ┌────────────────────────┐                   ┌───────────────────────────────┐
 │ cron heartbeat (24/7)  │                   │  approval surface + notify     │
 │ CI run failed          │                   └───────────────▲───────────────┘
 │ error / log spike      │                                   │ gate (CONSEQUENTIAL steps)
 │ perf regression        │                   ┌───────────────┴───────────────┐
 │ vulnerability found    │──────────────────▶│           FOREMAN              │
 │ dependency outdated    │                   │  plan · route · follow-up ·    │
 │ pull request opened    │                   │  escalate   (dev orchestrator) │
 │ scheduled sweep due    │                   └───────────────┬───────────────┘
 └────────────────────────┘                                   │ opens & drives Dev Missions
                                                              ▼
   ┌──────────────────────────────────────────────────────────────────────────┐
   │                    v2 CORE  —  REUSED, FROZEN, UNCHANGED                    │
   │  Mission Engine · Tool Registry · Event Bus · Approval · Audit · Outbox     │
   │  (lifecycle · gating · resume · idempotency · events · tamper-evident log)  │
   └───────────────┬───────────────────────────────────────┬───────────────────┘
                   │ ExecutionPort (per step → PlanStep.tool)│ events + audit (every step)
        ┌──────────▼───────────┐                  ┌──────────▼───────────┐
        │   SPECIALIST AGENTS   │                  │    OBSERVABILITY      │
        │   (behind tools)      │                  │  every decision logged │
        │   QA · Monitor ·      │                  │  + reproducible        │
        │   Security ·          │                  └────────────────────────┘
        │   Developer · Reviewer│  each agent = an isolated worker,
        └──────────┬───────────┘  invoked as a registered Tool
                   │ act ONLY through registered Dev Tools
        ┌──────────▼────────────────────────────────────────────────────────┐
        │  DEV TOOLS  (typed I/O · versioned · side-effect-tagged · audited)  │
        │  run_tests · run_lint · typecheck · scan_deps · scan_secrets ·      │
        │  read_logs · read_ci · read_metrics · code_review · run_app_smoke · │
        │  propose_patch  ·  apply_patch* · open_pr* · comment_pr* · merge**  │
        │            (* = CONSEQUENTIAL → human gate;  ** = never without owner)│
        └────────────────────────────────────────────────────────────────────┘
```

### Code layout (proposed)

A new standalone package tree, sibling to `v2/` and `v3/`, consuming v2 Core via editable
path deps (the same pattern `v2/apps/grc-api` already uses). Names adjustable.

```
devteam/
  docs/                         # this design, ADRs live in docs/adr/
  packages/
    devteam-contracts/          # DevTrigger events, DevFinding, Patch/Diff, ReviewResult (pure)
    devteam-tools/              # the Dev Tools above (implement Tool contract, register)
    devteam-agents/             # Foreman + 6 specialists as ExecutionPort-backed workers
    devteam-triggers/           # trigger sources → DevTrigger events (CI, cron, logs, PRs)
    devteam-runtime/            # composition root: wires v2 Core + agents + tools + triggers
  apps/
    foreman-worker/             # the 24/7 loop host (substrate per §9-B)
```

**Tenancy:** the platform maintains itself under a single reserved internal tenant
(`tenant:platform`), so every existing tenant-scoped guarantee (audit isolation, event
scoping) applies unchanged. No new tenancy model needed.

---

## 3. The agent roster

Maps 1:1 to the six agents requested. Each is *specialized, composable, governed, least-
privilege* (CLAUDE.md §11). Each acts only through Dev Tools.

| Agent | (requested) | Responsibility | Primary tools | Default side-effect |
|---|---|---|---|---|
| **Foreman** — dev orchestrator | وكيل يوزّع ويتابع | Turn a finding/trigger into a Dev Mission; plan steps; route each step to a specialist; follow up; escalate to human at gates | *plans; composes the others* | Orchestration only (no direct writes) |
| **QA** | وكيل جودة | Run test/lint/type suites; author missing tests; smoke-test the **running app** (via browser preview tools); verify a proposed fix actually passes | `run_tests`, `run_lint`, `typecheck`, `run_app_smoke` | Read-only (authoring tests → gated) |
| **Monitor** | وكيل مراقبة | Watch logs, errors (Sentry + JSON logs), CI status, performance; detect anomalies; emit findings that open missions | `read_logs`, `read_ci`, `read_metrics` | Read-only |
| **Security** | وكيل أمن | Dependency + secret scanning, SAST-lite, tenant-isolation / authz diff review; feeds `/security-review` discipline | `scan_deps`, `scan_secrets`, `security_review` | Read-only |
| **Developer** | وكيل مطور | Diagnose a bug/failing test; produce a **patch (diff) as an artifact** with rationale; never lands it itself | `propose_patch`, `apply_patch*` | Proposes (apply → gated) |
| **Reviewer** | وكيل مراجعة كود | Review a diff against CLAUDE.md pillars, tests, naming, security; approve/request-changes with reasons | `code_review`, `comment_pr*` | Read-only (PR comment → gated) |

`*` = a `CONSEQUENTIAL` tool: the Mission Engine pauses at `AWAITING_APPROVAL` before it runs.

---

## 4. The dev-mission lifecycle (task lifecycle)

We **reuse `MissionStatus` verbatim** — no new state machine. Read-only work runs
autonomously; the first consequential step trips the existing gate. The canonical
**"Fix-It" mission**:

```
 [trigger: Monitor detects a failing CI job]
        │
   CREATED ─▶ PLANNED           Foreman plans steps; each step declares a tool + consequential flag
        │
   EXECUTING                    (all read-only, autonomous, run in an isolated git worktree)
     ├─ Developer.propose_patch → produces a Diff artifact (no write to disk yet)
     ├─ Reviewer.code_review    → ReviewResult vs pillars/tests/security
     ├─ QA.run_tests            → runs the suite against the diff in the worktree
     └─ Security.security_review→ scans the diff
        │
   AWAITING_APPROVAL            step "apply_patch / open_pr" is CONSEQUENTIAL →
        │                       engine pauses, emits MissionAwaitingApproval, surfaces to human:
        │                       { diff · review · test results · scan · audit trail }
        │
   RESUMED ─▶ COMPLETED         on approve: apply on a branch / open PR → FixLanded event
        │
   FAILED / CANCELLED           fail-safe: worktree discarded, no partial consequential change,
                                everything logged and reconstructable
```

Every transition emits an event, is idempotent/resumable, and writes an `AuditRecord`
(reuse the outbox). An auditor can replay exactly what was found, what was proposed, who
approved it, and why — the same reproducibility guarantee the GRC product gives customers.

---

## 5. Event & trigger system + the 24/7 loop

Reuse the `event-bus`; add typed **DevTrigger** events (in `devteam-contracts`).

- **Inbound triggers (open/advance missions):** `CIRunFailed`, `TestFailureDetected`,
  `ErrorSpikeDetected`, `PerfRegressionDetected`, `VulnerabilityFound`,
  `DependencyOutdated`, `PullRequestOpened`, `ScheduledSweepDue`.
- **Mission events (reused):** `MissionCreated/Planned/StepCompleted/AwaitingApproval/
  Resumed/Completed/Failed`.
- **Outbound / notifications:** `HumanApprovalRequested` (→ push/Slack/email),
  `PatchProposed`, `ReviewCompleted`, `FixLanded`, `HeartbeatRecorded`.

**24/7 operation = a Foreman heartbeat + event wake-ups:**
- A scheduled **tick** (substrate per §9-B) that: drains the trigger queue → opens/advances
  missions → dispatches agents within a **concurrency + budget cap** → pushes anything at a
  gate to the human → writes a heartbeat status record.
- **Event-driven wake-ups** between ticks (e.g. a CI-failure webhook opens a triage mission
  immediately, not at the next tick).
- **Scheduled sweeps:** nightly full test/type run; weekly dependency + security audit;
  weekly architecture-drift / doc-sync check.

---

## 6. Safety & governance model (non-negotiable)

This system modifies its own codebase — so guardrails are first-class, not an afterthought.

- **Default-deny on consequential actions.** Never, without a human: push to `main`,
  force-push, deploy to prod, install/add a dependency, read a secret, or edit CI/security
  config, `.env`, auth/tenancy code, or the approval machinery itself.
- **Isolation.** Every code-writing mission runs in a **dedicated git worktree**; discarded
  on fail/cancel. No agent edits the working tree in place.
- **Blast-radius / path allowlist.** Each mission declares the paths it may touch. Protected
  paths (secrets, CI, auth, tenancy, migrations) require *elevated* human approval.
- **Budgets.** Per-mission token/cost/time ceilings; global concurrency cap; a mission that
  exceeds budget stops fail-safe and escalates.
- **Idempotency.** Consequential tools take idempotency keys (reuse the mission-store
  pattern) — a retried step never double-applies.
- **Least-privilege credentials.** The bot's git/CI token can open PRs and comment, **not**
  merge or administer. Merge stays a human action (or a §9-A opt-in class).
- **Full audit + kill switch.** Every step → `AuditRecord`; a single env flag halts all
  dispatch and in-flight missions stop fail-safe.
- **LLM output is untrusted input.** Diffs are validated/type-checked/tested before they can
  reach a gate; retrieved logs/PR text can't inject instructions (CLAUDE.md §19).

---

## 7. Extensibility (the anti-"scattered-scripts" guarantee)

- **New agent** = a new `ExecutionPort`-backed worker + declared tool scope, registered.
  The Foreman composes it into plans. *No core change.*
- **New tool** = implement the `Tool` contract, tag its `SideEffectProfile`, register it
  (versioned). *No core change.*
- **New trigger** = a new `DevTrigger` event + a subscriber that opens a mission. *No core
  change.*

If extending the team ever requires editing the Mission Engine, that's a design smell
(CLAUDE.md §17). Growth happens at the edges, through registries — the same rule the
product lives by.

---

## 8. How this honors the pillars (CLAUDE.md §3)

Mission-centric ✓ · Orchestrator-is-the-brain (Foreman plans; the LLM only reasons) ✓ ·
Tools as first-class units ✓ · Tool Registry ✓ · Multi-agent under an orchestrator ✓ ·
Event-driven ✓ · Human approval gates ✓ · Transparency & auditability ✓ · Extensible via
registries ✓ · Multi-tenant by construction (`tenant:platform`) ✓.

---

## 9. Decisions (RESOLVED by the owner, 2026-07-26 — see ADR 0061)

**A. Autonomy posture → Safe-Class auto-land.** Read-only work is autonomous. Consequential
  work is gated *except* a closed **Safe Class** that may auto-land without a human. A change
  is Safe-Class **iff all** hold: (1) it is formatting, lint autofix, a dependency *patch*-bump,
  or a generated-code refresh; (2) full CI is green incl. the newly-wired v2/v3 tests + security
  scan; (3) it touches **no protected path** (secrets, CI/CD, auth, tenancy, migrations, the
  approval machinery, this policy); (4) diff under a size threshold; (5) Reviewer **and** Security
  both pass; (6) it is auto-revertible. Fail any → human gate. **Safe Class ships in Phase 4; the
  read-only spine writes no code.**

**B. Runtime substrate → Claude Code scheduling, then graduate.** The Foreman heartbeat + event
  wake-ups bootstrap on Claude Code scheduled tasks/routines, then graduate to GitHub Actions
  (cron + CI events), then a dedicated worker service as scale/trust grow.

**C. First build → the read-only spine.** Foreman + Monitor + QA + Reviewer, all read-only, on
  the Phase 0 foundation. No agent touches code until Phase 3.

---

## 10. Roadmap (crawl → walk → run)

- **Phase 0 — Foundation (backbone, zero risk).** `devteam/` tree + `devteam-contracts`;
  `DevMissionRuntime` on v2 Core; event/trigger plumbing; one trivial read-only tool
  (`run_tests`); audit + heartbeat wired. **First win:** close CI gap #1 — run the 1,000+
  `v2/`+`v3/` tests in CI. No agents yet.
- **Phase 1 — Read-only spine.** Foreman + Monitor + QA + Reviewer, all read-only. Nightly
  test/lint/type sweep; CI-failure triage; daily error/log digest; PR-review comments
  (gated). Output = reports + opened missions. *No code changes.*
- **Phase 2 — Security + supply chain.** Security agent tools (dep/secret scan, SAST-lite) +
  a scheduled security mission. **Win:** close CI gap #2 — add security + dependency
  scanning to CI.
- **Phase 3 — Developer agent (propose-only).** The full closed Fix-It loop, human-gated:
  detect → propose patch → review → verify in a worktree → human approves → PR. First
  code-writing capability, fully gated.
- **Phase 4 — Selective autonomy.** Auto-land the pre-agreed safe class (formatting, lint
  autofix, dependency patch bumps green on full CI) without a human; everything else stays
  gated. Unlocked only after trust is earned in P1–P3.
- **Phase 5 — Scale & self-healing.** Graduate the substrate; add weekly architecture-drift
  + doc-sync agent; dashboards; flake quarantine; auto-revert on post-merge regression.

Each phase ends at a review gate. Nothing in a later phase starts without the owner's
trigger.
