# ADR 0029: AI Worker Control Center (KI-P5) — durable admin control, activity timeline, and reporting over the Autonomous Knowledge Worker

- Status: Accepted
- Date: 2026-07-06
- Deciders: Product Owner (via direct working session), Architecture
- Related: CLAUDE.md §1, §5, §7, §9, §16, §18, §19, §20, §22, §23; ADR 0022, 0025, 0026, 0027,
  0028

## Context

KI-P4 (ADR-0028) built the first real, always-on Knowledge Worker process
(`apps/worker/src/grc_worker/knowledge_learning_loop.py`): a scheduler-driven loop that
periodically detects knowledge gaps and researches them, unattended. That ADR named three
things explicitly as future work: "no durable `last_run_at`" (a restart forgets cadence
state), "no consumer wiring, no API endpoint, no UI," and no way to change the cadence, pause
the worker, or trigger a cycle early without editing environment variables and restarting the
process.

This phase (Knowledge Intelligence KI-P5) is that future work: an Admin-only "AI Worker
Control Center" — a dashboard showing the worker's status, an activity timeline of what it is
doing, admin-configurable scheduling (default every 12 hours), a manual "Run Learning Now"
trigger, and learning reports over the shared knowledge base — all with an audit trail and
strict RBAC, and without exposing raw model reasoning (CLAUDE.md §19).

Architecture exploration before writing code confirmed: the worker's state
(`knowledge_items`, and now `worker_control`/`worker_run_history`/`worker_events`) is
platform-scope, not tenant-scope (the same posture ADR-0025 already established) — the
Control Center is therefore gated on a role, not a tenant-scoped resource ownership check.

## Decision

Bottom-up, matching this repo's established layering (pure packages → adapters →
persistence/API → UI):

**1. Pure package (`packages/knowledge-worker`) — two new optional seams, zero behavior
change for existing callers.**
- `events.py`: `WorkerEventType` (12 values: `cycle_started`, `questions_loaded`,
  `gap_detected`, `source_searched`, `knowledge_discovered`, `item_saved`, `error`,
  `cycle_completed`, plus four admin-action types added in the persistence layer), a frozen
  `WorkerEvent` (event_type/message/occurred_at/question_id/metadata), and a structural
  `WorkerEventSink` Protocol (`async def record(event) -> None`). Every `message` is an
  operational fact (a count, a status, a source name) — never a model's raw reasoning
  (CLAUDE.md §19).
- `control.py`: `WorkerControlSettings` (enabled/interval/manual_trigger_requested) and a
  structural `WorkerControlPort` Protocol (`get_settings()`, `clear_manual_trigger()`).
- `worker.py`: `AutonomousKnowledgeWorker.__init__` gained optional `control`/`event_sink`
  parameters (default `None`, fully backward compatible — all 17 pre-existing tests pass
  unmodified). `tick()` now: (a) asks the control port for current settings on *every* call
  rather than trusting the fixed `LearningCycleScheduler` it was constructed with, so an
  admin's enable/disable/interval change takes effect on the next poll, no restart required;
  (b) returns a new `reason="disabled"` when paused, and `reason="manual"` when a pending
  manual trigger runs the cycle early (bypassing the interval, but never bypassing
  `disabled`); (c) emits `cycle_started`/`cycle_completed`/`error` around the runner call. A
  new `questions_count` property exposes the combined catalog size (for "questions
  considered" reporting, distinct from `CycleOutcome.outcomes`, which holds only the
  *actionable* gaps one cycle actually researched). `GapResearchOutcomeLike` gained one
  additive property, `error: str | None`, mirroring the real `GapResearchOutcome`'s existing
  field — needed so a composition root can count cycle errors without importing the concrete
  adapter type.

**2. Adapter (`packages/knowledge-research-adapters`) — richer timeline events, one new
dependency edge.** `KnowledgeGapResearchRunner` gained an optional `event_sink` parameter and
now emits `questions_loaded` (once), `gap_detected` (per actionable gap), and, per question,
`source_searched`/`knowledge_discovered`/`item_saved`/`error` — using data the runner already
computes (`ResearchResult.attempts`, `GapResearchOutcome`), no new I/O. This package now
depends on `grc-knowledge-worker` for the `WorkerEvent`/`WorkerEventType`/`WorkerEventSink`
vocabulary — a deliberate, acyclic, one-way edge (`grc_knowledge_worker` never imports
`grc_knowledge_research_adapters`), chosen over duplicating the event schema in a second
package.

**3. Persistence (`packages/persistence-web` + `apps/web/lib/db/migrations/0019_worker_
control.sql`) — three new tables, platform-scope like `knowledge_items`.**
- `worker_control`: a **singleton** row (`id = 'default'`) — `enabled`, `interval_hours`
  (default `12`, satisfying "default run every 12 hours"), `manual_trigger_requested_at`,
  `updated_at`/`updated_by`. One worker process exists platform-wide, so one row, not a table
  keyed by tenant.
- `worker_run_history`: one row per cycle that actually ran (`reason`
  `'due'`/`'manual'`, timestamps, `questions_considered`/`gaps_detected`/`items_saved`/
  `error_count`) — the durable `last_run_at`/"next run" state and Learning Reports trend data
  ADR-0028 deferred, delivered as a genuinely additive migration, not a redesign (exactly the
  alternative ADR-0028 named and declined "for now").
- `worker_events`: the single append-only table serving **both** the activity timeline and
  the admin-action audit trail (CLAUDE.md §19/§23) — the same 8 worker-emitted event types
  above, plus four admin-action types (`worker_enabled`, `worker_disabled`,
  `interval_changed`, `manual_trigger_requested`) carrying `actor_user_id`/`actor_tenant_id`.
  One unified table was chosen over two (a separate "audit log") because every admin control
  action is exactly as much an operational event as a worker-emitted one, and a
  reviewer/auditor wants one chronological feed, not two to reconcile.

  `grc_persistence_web.worker_control` implements `WorkerControlRepository` (satisfies
  `WorkerControlPort` by directly returning the pure `WorkerControlSettings` type — not just
  structurally, but by reuse), `WorkerRunHistoryRepository`, and `WorkerEventRepository`
  (satisfies `WorkerEventSink`, plus `record_admin_action` for admin-initiated writes).

**4. Composition root (`apps/worker/knowledge_learning_loop.py`).** `build_worker` now wires
`WorkerControlRepository`/`WorkerEventRepository` into both `AutonomousKnowledgeWorker` and
`KnowledgeGapResearchRunner` (the same `Database` connection — no new pool). `run_forever`
gained an optional `run_history` parameter (a structural `RunHistoryPort`, so tests can fake
it without a real database); when a cycle ran, it records history best-effort — a recording
failure is logged, never allowed to break the loop that already did the real work, the same
fail-safe posture (CLAUDE.md §16) `run_forever` already held for tick failures.

**5. RBAC (`grc_services.shared.authorization`).** A new `ResourceType.KNOWLEDGE_WORKER`,
deliberately **not** added to the `_OPERATIONAL`/`_CATALOG` grant sets any other role draws
from. `OWNER`/`ADMIN` hold every action on it via their existing `_ALL_RESOURCES` grant;
`AUDITOR` inherits its existing platform-wide *read-only* grant (the same rule that already
covers the audit trail) — reading status/timeline is consistent with "auditors read
everything," but every consequential action (reschedule, enable/disable, manual trigger)
stays `OWNER`/`ADMIN`-only, matching "Admin users only" where it actually matters. Every other
role (Compliance Manager, Risk Manager, Analyst, Viewer) gets a 403 on every route. Mirrored
in `apps/web/lib/auth/permissions.ts`.

**6. API (`apps/api/routers/knowledge_worker.py`).** Six endpoints under
`/api/v1/knowledge-worker`: `GET /status` (enabled/running, current cycle + task — derived
by scanning the timeline backwards for the nearest `cycle_started` vs. terminal event, no
separate "is running" heartbeat table to avoid drift — last run, next run), `GET /events`,
`GET /runs`, `GET /reports` (knowledge-base counts by verification status, `updated` as items
with `version > 1`, `added_this_cycle` from the latest run's `items_saved`), `POST /schedule`
(enable/disable and/or interval, each change independently audited), `POST /trigger`. Modeled
on Policy Intelligence's router (PI-P5, ADR-0022): talks to `grc_persistence_web`
repositories directly rather than the tenant-scoped command/query bus, since this state is
platform-scope, not a tenant-owned aggregate.

**7. Frontend.** `/ai-worker` — a real, workspace-first page (not the placeholder pattern
`/settings` still uses), gated `requireRoles("owner", "admin")` server-side (stricter than
the API's own Auditor-can-read allowance — a deliberate UI/API asymmetry: the surface is
admin-only in the sense the ticket asked for, while the API still honors the platform's
"auditors read everything" invariant for any future consumer). Status card, schedule toggle +
interval control, "Run Learning Now" button, an activity timeline (icon+tone per event type,
CLAUDE.md §19-safe — operational facts only), and a learning-reports stat grid. A Next.js
proxy under `/api/knowledge-worker/*` (admin-gated again, defense in depth) forwards to
`apps/api` with the actor's bearer token, mirroring Policy Intelligence's proxy exactly. Nav
entry added to `FOOTER_NAV`, admin-gated; bilingual (en/ar) message keys added.

## Consequences

**Positive**
- Delivers exactly the three things ADR-0028 named as deferred: durable run history/cadence
  state, an API/UI, and (new） a genuine "why is nothing happening" activity trail —
  additively, via one new migration and two new optional pure-package seams, not a redesign.
- Zero behavior change for any existing caller: `AutonomousKnowledgeWorker` and
  `KnowledgeGapResearchRunner` both work identically when `control`/`event_sink` are omitted;
  all 26 pre-existing `knowledge-worker` tests and all 22 pre-existing
  `knowledge-research-adapters` tests pass unmodified.
- One unified, append-only `worker_events` table serves both the human-facing timeline and
  the admin-action audit trail — no second audit subsystem invented.
- RBAC stays declarative and default-deny: adding one `ResourceType` and leaving it out of
  the shared grant sets is the whole enforcement mechanism; no per-route role checks to keep
  in sync.
- New tests: 8 pure `knowledge-worker` (control/event seams), 2 `knowledge-research-adapters`
  (timeline emission), 5 `persistence-web` (control/run-history/event repositories against
  the real schema), 1 `apps/worker` (run-history recording), 9 `apps/api` (status/events/
  reports/schedule/trigger, RBAC differentiation including the Auditor read-only case) — 25
  new tests, all green against the real dev Postgres; `pnpm typecheck`/`pnpm lint` clean.
- Verified live in the browser end-to-end (not just against tests): logged in as `owner`,
  loaded `/ai-worker`, toggled the schedule off, and clicked "Run Learning Now" — each action
  round-tripped through the Next.js proxy → `apps/api` → Postgres and the UI reflected the
  new state (badge, next-run text, timeline entry) without a manual refresh.

**Negative / costs**
- **Two small pieces of pre-existing repo debt surfaced and were fixed as unblocking, not
  as scope creep:** `httpx` was used throughout `apps/api/tests` but never declared as a
  dependency anywhere (the entire `apps/api` test suite, including every pre-existing test
  file, failed to collect before this ADR's session); added to the root dev dependency
  group. `packages/services` still lacks a `py.typed` marker (same class of gap ADR-0028 §7
  fixed for `packages/llm`) — this ADR's new router hits the same `mypy --strict`
  "Skipping analyzing... missing library stubs" note every other `apps/api` router importing
  `grc_services` already does; left unfixed here since it is repo-wide debt unrelated to this
  feature, not something this phase introduced.
- **Current-cycle detection is a heuristic, not a dedicated state machine.** "A cycle is in
  progress" is inferred by scanning the most recent 50 timeline events backwards for a
  `cycle_started` not yet followed by a terminal event, rather than a dedicated
  `is_running` flag. Chosen to avoid a second source of truth that could drift from the
  timeline; acceptable because real cycles are short relative to the 50-event window, but
  worth revisiting if cycles grow to produce more than ~50 events each.
- **`added_this_cycle`/`updated` in Learning Reports are proxies, not exact provenance.**
  `knowledge_items` has no per-cycle "was this row touched this cycle" column;
  `added_this_cycle` reports the latest run's `items_saved` count (new-or-updated,
  undifferentiated) and `updated` reports items with `version > 1` (re-discovered at least
  once, ever — not scoped to "this cycle"). Named explicitly rather than silently
  approximated; an exact per-cycle attribution would need a `knowledge_items.last_run_id`
  column, deferred as unnecessary for this phase's reporting granularity.
- **No container/deployment wiring**, consistent with ADR-0028's own precedent — this phase
  is application code, not ops/deployment.

## Alternatives considered

- **A separate `worker_admin_audit` table distinct from the operational `worker_events`
  timeline.** Rejected: an admin's enable/disable/reschedule/trigger action is exactly as
  much a fact about "what happened to the worker" as a `cycle_started` event — one
  chronological, append-only feed is simpler to reason about and to review than reconciling
  two.
- **A dedicated `is_running` boolean, flipped by the composition root at cycle start/end.**
  Rejected for this phase: it is a second source of truth that must be kept exactly in sync
  with the timeline, and a crash mid-cycle would leave it stuck `true` forever without an
  additional recovery mechanism. Deriving current-cycle state from the timeline itself has
  no such stale-flag failure mode (a crash simply leaves the last real event as
  `cycle_started`, which is actually correct: the cycle never finished).
- **Auditor gets a 403 everywhere on `/knowledge-worker/*`, matching "Admin users only"
  literally.** Rejected: `RbacAuthorizationService`'s `AUDITOR` role already holds a
  deliberate, blanket, platform-wide READ grant (`_grant(_ALL_RESOURCES, _READ)`) that exists
  specifically so an auditor can review anything, including future resource types, without
  this file being revisited every time one is added. Carving out an exception for this one
  resource would special-case the matrix and quietly weaken CLAUDE.md's own auditability
  mandate ("every AI action... traceable... reviewable") for no real security benefit, since
  Auditor already cannot mutate anything. The frontend page still gates on `owner`/`admin`
  only, satisfying the literal "Admin users only" ask for the *surface* while the API
  underneath stays consistent with the rest of the platform.
- **Thread `run_id` through every `WorkerEvent` so the timeline can be grouped by cycle.**
  Rejected for this phase: it would require creating the `worker_run_history` row *before*
  the cycle runs (to have an id to attach) rather than after (once real counts are known),
  complicating the otherwise simple "record once, after the fact" write path for a grouping
  feature the current spec does not ask for. The timeline already reads correctly ordered by
  `occurred_at` without it.
