# ADR 0064: Mission Correlation — relate a trigger to an existing mission; Intake receives CreateMission | UpdateMission

- Status: **Accepted** (2026-07-26) — owner-approved after a Design-on-Reality pass, before
  implementation. **Refines ADR 0063**: Mission Intake's input becomes an `IntakeCommand`
  (`CreateMission | UpdateMission`), produced by a correlation step — never a raw external event.
  **Amended 2026-07-26** (owner-approved): correlation persistence is an internal `CorrelationRepository`,
  not a Port — `MissionCorrelator` remains the sole boundary (see the amended decision 2).
- Date: 2026-07-26
- Deciders: **Product Owner**, Architecture
- Related: ADR 0063 (Mission Intake — refined) · 0061 · 0062 · 0042 (idempotency §12.7:
  `find_by_idempotency_key` — the closest existing concept) · 0043 (Mission Store) · 0053 (read
  models & projection) · 0040 (tenancy) · 0009 / 0039 (events + audit) · CLAUDE.md §8, §16.

## Context

Mission Intake must **not** mint a new mission per trigger. Duplicate webhooks, GitHub issue
updates/comments, CI reruns, and repeated Sentry alerts must relate to an **existing** Dev Mission and
update it — not spawn duplicates. Design-on-Reality found the Core's closest concept is **idempotency**
(create-dedup by key: `create(..., idempotency_key)` + `find_by_idempotency_key`), but that is
exact-command dedup, not trigger↔mission correlation; and `CommandContext.correlation_id` is
*"audit: ties related actions together"* — observability, not intake. **No Mission Correlation concept
exists.** The owner chose a **separate correlation store** (an internal repository, not overloading
`idempotency_key`) and **record-only** updates for the first cut.

## Decision

1. **Intake receives a command, not a raw event.**
   `TriggerSource.normalize(raw) → IntakeSignal` (adds a stable `correlation_ref`) →
   `MissionCorrelator.correlate(signal, tenant) → IntakeCommand` →
   `MissionIntake.admit(command)`, where **`IntakeCommand = CreateMission(signal) |
   UpdateMission(mission_id, signal)`**.

2. **Correlation persistence is an internal repository, not a platform Port.** `MissionCorrelator`
   remains the architectural boundary Mission Intake depends on. Behind it, correlation state — a
   `correlation_ref → active mission` mapping, tenant-scoped — lives in a small in-package
   **`CorrelationRepository`** (an implementation detail: `register` / `find_active` / `deactivate`).
   This is a separate store from the Core's `idempotency_key`, which is kept for exact-event dedup —
   a distinct concern. Per the Port-Worthiness rule, correlation storage is **not** elevated to a Port
   (one production form). If future requirements introduce multiple genuinely different correlation
   strategies, we revisit the boundary in a new ADR.

3. **The Correlator decides create-vs-update.** `find_active(ref)` → `None` → `CreateMission`; a
   mission id → `UpdateMission`. On `CreateMission`, Intake **registers** `ref → mission_id`; when the
   mission reaches a terminal state, a subscriber **deactivates** the entry — so a recurrence *after*
   closure is a **new** mission (a regression), never a resurrection of a terminal one.

4. **UpdateMission is record-only (first cut).** It emits a **`MissionSignalReceived`** domain event
   (tenant- and mission-stamped, carrying the new `AgentFinding`) onto the event bus + audit — **no
   lifecycle mutation**. This absorbs duplicate webhooks, issue comments, CI reruns, and repeated
   alerts as audited provenance against the live mission. Re-planning or reopening on new evidence is
   a deliberate later escalation, never an automatic in-flight mutation.

5. **The TriggerSource sets the `correlation_ref` granularity — and that granularity *is* the
   correlation policy.** Per-entity for issues/CI/Sentry (`github:issue:123`, `ci:pipeline:api`,
   `sentry:fingerprint:abc` → updates correlate); per-occurrence for schedules
   (`schedule:nightly:2026-07-27` → each run is new). The `TriggerSource` is the only origin-aware
   layer; the Foreman never sees the origin (ADR 0063).

## Consequences

**Positive**
- Intake is idempotent by construction: one active mission per correlation ref; every later related
  trigger is absorbed as a recorded signal, not a duplicate mission.
- `idempotency_key` (command-dedup) and `correlation_ref` (entity-correlation) stay cleanly separated.
- Correlation persistence is a small internal repository behind the `MissionCorrelator` boundary; the
  create path and events are all reused.
- Record-only updates never mutate a running mission by surprise; escalation stays explicit.

**Negative / costs**
- A small correlation repository plus a lifecycle-event subscriber to deactivate on terminal — more
  moving parts than reusing `idempotency_key`.
- "Record-only" means new evidence on a live mission is visible but not yet acted on until the
  escalation path is designed.

## Alternatives considered

- **Reuse `idempotency_key` as the correlation ref.** Rejected by the owner — conflates command-dedup
  with entity-correlation, and can't cleanly model a regression after closure (the terminal mission
  would keep absorbing the key).
- **Blind create per trigger.** Rejected — duplicate missions, the exact bug this prevents.
- **Auto re-plan/reopen on update.** Deferred — automatically mutating in-flight missions is riskier;
  record-only first, escalation later.
