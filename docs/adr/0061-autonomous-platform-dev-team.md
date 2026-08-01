# ADR 0061: The Autonomous Platform Dev Team — a mission-centric engineering team on the frozen v2 Core

- Status: **Accepted — implemented** (design 2026-07-26; all phases landed & frozen 2026-07-31) —
  Stage-1 design accepted in principle; the owner fixed the three forks below (autonomy =
  **Safe-Class auto-land**; runtime = **Claude Code scheduling → graduate**; first build = **read-only
  spine**). Every phase landed behind its review gate; the dev team + AI Organization are built,
  tested, and deployed — see the [Architecture Certification](../devteam/ARCHITECTURE-CERTIFICATION.md)
  (PASS) and the [Core Freeze Review](../devteam/CORE-FREEZE-REVIEW.md).
- Date: 2026-07-26
- Deciders: **Product Owner**, Architecture
- Related: [docs/devteam/DESIGN.md](../devteam/DESIGN.md) (full architecture & roadmap) · CLAUDE.md §3
  (pillars), §7 (Orchestrator-is-the-brain), §8 (Mission lifecycle), §9–10 (Tools & Registry), §11
  (agent roster), §16 (EDA), §17 (plugin extensibility), §19 (transparency/audit), §20 (multi-tenancy) ·
  ADR 0003 (mission-centric) · 0004 (Orchestrator is the brain) · 0005 (multi-agent) · 0006 (Tools &
  Registry) · 0009 (EDA) · 0010 (plugin architecture) · 0042 (Mission Engine) · 0044 (Human Approval
  Lifecycle) · 0048 (per-step tool selection) · 0055 (execution lifecycle ownership).

## Context

The platform needs to be **continuously improved, tested, monitored, secured, and maintained** with as
little manual work as possible — while a human keeps control of anything consequential. The owner's
requirement is explicit: an **internal AI engineering team** (a Foreman that distributes and follows up,
a QA agent that continuously exercises the platform, a Monitor for errors/logs/performance, a Security
agent, a Developer that proposes fixes, and a Code-Reviewer) — delivered as a **modular architecture
with a task lifecycle, an event system, and an extensible roadmap — not scattered scripts.**

Three forces make the decision non-trivial:

1. **The hard parts already exist and are frozen.** `v2/` ships a Mission Engine with a closed lifecycle
   and a human-approval gate (ADR 0042/0044), a Tool Registry with a `SideEffectProfile`-tagged Tool
   contract (ADR 0006/0049), an Event Bus with tenant-scoped domain events, and a durable
   audit/outbox (ADR 0043). Rebuilding any of this for a "dev bot" would duplicate the Core and violate
   dog-fooding.
2. **CLAUDE.md §11's six-agent roster is still unimplemented** — today "agents" are capabilities that
   resolve to plans of tools. This is the first true multi-agent implementation, so by the ADR process
   (§23) it *requires* an ADR.
3. **CI has real gaps this team must also close.** `.github/workflows/ci.yml` runs only the root uv
   workspace + `apps/web`; the **1,000+ tests under `v2/` and `v3/` never run in CI**, and there is no
   security scan, dependency audit, or coverage gate. The lazy path is a pile of one-off scripts; the
   right path is an engineering *system*.

## Decision

**We will build the dev team as a Mission-Centric application on the frozen v2 Core, governed by six
binding rules.**

1. **The dev team is a mission-centric application, not scripts.** Every unit of engineering work
   (triage a CI failure, run a security sweep, propose a fix) is a governed **Mission** that reuses
   `mission-engine`, `tool-registry`, `event-bus`, the approval gate, and the audit outbox. **We reuse
   `MissionStatus` verbatim** — no new lifecycle. The team lives in a new standalone package tree
   (`devteam/`) that consumes v2 Core via editable path deps, exactly as `v2/apps/grc-api` does. It runs
   under a reserved internal tenant `tenant:platform`, so every existing tenant-scoped guarantee applies
   unchanged.

2. **The Foreman is the brain; agents act only through registered Dev Tools.** Six specialists —
   **Foreman** (وكيل يوزّع ويتابع), **QA** (وكيل جودة), **Monitor** (وكيل مراقبة), **Security**
   (وكيل أمن), **Developer** (وكيل مطور), **Reviewer** (وكيل مراجعة كود) — realize CLAUDE.md §11. Each is
   an `ExecutionPort`-backed worker; the LLM only reasons, the Foreman decides and routes. Every
   capability is a typed, versioned, `SideEffectProfile`-tagged **Tool** in the registry. A new
   agent/tool/trigger is added at a **registry edge, never by editing the Core** (§17) — this is the
   anti-"scattered-scripts" guarantee.

3. **Consequential actions are gated; read-only work is autonomous.** `apply_patch`, `open_pr`, `merge`,
   and any config/dependency change are `CONSEQUENTIAL` and pass through the existing `AWAITING_APPROVAL`
   gate (ADR 0044). **Default-deny:** the team will *never*, without a human, push to `main`,
   force-push, deploy to production, install/add a dependency, read a secret, or edit CI/CD, auth,
   tenancy, migrations, or the approval machinery itself.

4. **Auto-land is permitted only for a defined Safe Class** *(owner decision A)*. A change may land
   **without** a human **iff all** hold: (a) it falls in a declared safe category —
   **formatting, lint autofix, dependency *patch*-version bump, or generated-code refresh**; (b) full CI
   is green, *including the newly-wired v2/v3 tests and the security scan*; (c) the diff touches **no
   protected path** (secrets, CI/CD, auth, tenancy, migrations, the approval machinery, or this
   safe-class policy); (d) the diff is under a size threshold; (e) both the Reviewer and Security agents
   pass; (f) it is **auto-revertible** — a post-merge regression triggers an automatic revert. Failing
   *any* criterion routes the change to a human gate. **The Safe Class ships in Phase 4, not before** —
   the read-only spine writes no code at all.

5. **Isolation, budgets, audit, kill switch are first-class.** Every code-writing mission runs in a
   **dedicated git worktree**, discarded on fail/cancel — no agent edits the working tree in place. Each
   mission carries token/cost/time budgets and a path allowlist; a global concurrency cap bounds the
   fleet. Every step writes an `AuditRecord` through the outbox (reproducible, tamper-evident). A single
   **kill switch** halts all dispatch, and in-flight missions stop fail-safe. The bot's git/CI
   credential is least-privilege: it may open PRs and comment, **not** merge or administer.

6. **24/7 = a Foreman heartbeat + event wake-ups; the substrate graduates** *(owner decision B)*. Typed
   `DevTrigger` events (`CIRunFailed`, `TestFailureDetected`, `ErrorSpikeDetected`,
   `PerfRegressionDetected`, `VulnerabilityFound`, `DependencyOutdated`, `PullRequestOpened`,
   `ScheduledSweepDue`) open/advance missions. The loop **bootstraps on Claude Code scheduling**, then
   graduates to GitHub Actions (cron + CI events), then a dedicated worker service as trust and scale
   grow.

**Build ordering** *(owner decision C — read-only spine first)*: **Phase 0** foundation + close CI gap
#1 (run the v2/v3 tests in CI) → **Phase 1** read-only spine (Foreman + Monitor + QA + Reviewer, no code
writing) → **Phase 2** Security agent + CI gap #2 (security/dependency scanning) → **Phase 3** Developer
agent (propose-only, fully gated) → **Phase 4** Safe-Class auto-land → **Phase 5** scale & self-healing.
Each phase ends at an owner review gate; no later phase starts without the owner's trigger.

## Consequences

**Positive**
- The team is a *platform*, not scripts: every capability is a discoverable, versioned, audited Tool;
  every worker a governed Agent; every wake-up a typed Event — the same discipline it enforces on the
  product.
- Lifecycle, gating, resume, idempotency, events, and a tamper-evident audit trail come **for free** by
  reusing the frozen Core; the v2 Core stays unchanged (new consumer, not a modification).
- Human control is structural, not procedural — consequential steps *cannot* proceed past the engine's
  gate; the Safe Class is a closed, auditable whitelist.
- The first missions deliver immediate value by closing real CI gaps (v2/v3 tests, security scanning).
- Extensible by construction: new agents/tools/triggers are registry edges (§17).

**Negative / costs**
- The Safe-Class policy (Rule 4) is safety-critical and must be reviewed like auth code; a mistake there
  is how an auto-lander causes harm. It is itself a protected path.
- Running LLM-backed agents 24/7 has real token/cost/time budget implications that must be capped and
  monitored (the Monitor watches the team too).
- Reusing the GRC Mission Engine for engineering work means dev missions share the product's persistence
  and event infrastructure; the `tenant:platform` boundary must be honored so dev activity never mixes
  with customer tenants.

## Alternatives considered

- **A pile of CI scripts / GitHub Actions jobs.** Rejected — the owner's explicit non-goal ("مو سكربتات
  متفرقة"). Not governed, not auditable as missions, not extensible, no shared lifecycle or human gate.
- **A separate bespoke agent framework for the dev team.** Rejected — duplicates the frozen Core, breaks
  dog-fooding, and creates a second lifecycle/audit/approval implementation to maintain.
- **Full autonomy from day one.** Rejected — violates the GRC human-in-the-loop posture (CLAUDE.md §1);
  trust must be *earned* across phases before any auto-land, and even then only for the Safe Class.
- **A new task-state machine for dev work.** Rejected — `MissionStatus` (CREATED→…→ARCHIVED) already
  models exactly what a dev task needs, including the approval pause; a parallel state machine would be
  redundant and would fork the audit story.
