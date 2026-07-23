# ADR 0044: Rasheed V2 — the Human Approval Lifecycle (approval as a Mission-owned value object)

- Status: **Accepted — implemented** (Slices 1–3 built, tested against real PostgreSQL, and frozen;
  Slice 4 "Advanced Approval" deferred — see *Implementation Status* at the end). *(Header updated
  2026-07-17: the original "Proposed / architecture only" wording predated implementation.)*
- Date: 2026-07-17
- Deciders: Product Owner (review pending), Architecture
- Related: CLAUDE.md §3 (mission-centric), §7 (orchestrator / human gates), §8 (mission lifecycle —
  *Awaiting Approval*, *Resumed*), §15 (DDD aggregates & consistency boundaries), §16 (EDA), §19
  (audit — "every human approval/rejection with who and when"), §20 (tenancy);
  **ADR 0042 (Mission Engine — defines and freezes the Mission aggregate, the lifecycle, and the
  event vocabulary; this ADR amends it)**, ADR 0043 + 0043-S4 (Mission Store / Unit of Work /
  Transactional Outbox — the durable + delivery seam approval rides on), ADR 0040 (tenancy),
  0039 (event bus / audit), 0015 (audit & traceability)

---

## Context

Human-in-the-loop approval is a Rasheed pillar: "any agent or tool action with side effects passes
through an explicit approval step" (CLAUDE.md §7, §9), and "no consequential action executes without
a human gate" (§24 Definition of Done). Phase 15 built the **Mission Engine** (ADR 0042) with the
*pause* half of that gate already present, then the **Mission Store** (ADR 0043, Slices 1–4) made
missions durable, atomic, and event-delivering, and the **Integration phase** proved the whole path
runs end-to-end and that a paused mission survives a restart and resumes.

What does **not** yet exist is the *resolution* half: a way for a human to **approve** or **reject**
the paused action, a place to record **what** is awaiting approval and **who** decided it, and the
**resume** that continues (or the termination that stops) the mission afterwards. This ADR decides
that architecture — **before any code**, by the same method ADR 0043 used: ADR → review → very small
slice → tests → review → freeze.

### What is already frozen (and therefore an input, not a decision, here)

Reading the frozen code precisely matters, because it changes what this ADR must invent versus what
it merely *drives*:

1. **The lifecycle already contains the approval states, and the transition table is already
   complete.** From `mission_engine.lifecycle` (frozen, ADR 0042 §7): `AWAITING_APPROVAL` and
   `RESUMED` exist, and the closed legal table **already** permits every transition this feature
   needs:

   ```
   EXECUTING          → AWAITING_APPROVAL          (request approval — already legal)
   AWAITING_APPROVAL  → RESUMED | CANCELLED | FAILED
   RESUMED            → PLANNED | EXECUTING | CANCELLED | FAILED
   ```

   **So this ADR adds no lifecycle state and no transition.** The state machine ADR 0042 shipped
   "full from day one, driven incrementally" was built for exactly this moment.

   **`RESUMED` is treated as a *compatibility* state, not a new long-lived business state.** It
   already exists in the frozen lifecycle as the momentary hand-off between "the gate was resolved"
   and "the engine continues (or re-plans)". ADR 0044 **does not expand its semantics and introduces
   no new logic around it**: approve drives `AWAITING_APPROVAL → RESUMED` purely to reuse the frozen,
   already-legal transition, and the engine then immediately moves on to `EXECUTING` (Slice 3) or
   `PLANNED` (a re-plan). A mission is not meant to *rest* in `RESUMED`; it is the transient bridge
   the frozen machine already provides. `MissionResumed` remains the domain event that marks crossing
   that bridge — unchanged, already registered in the outbox.

2. **The aggregate already has the pause/resume/replan methods.** `Mission.await_approval()`,
   `Mission.resume()`, and `Mission.replan()` exist and enforce the transitions above. The aggregate
   is **pure** — "holds no ports and performs no I/O."

3. **The engine already drives the pause.** `MissionEngine.execute()`, on reaching a `consequential`
   step, calls `await_approval()`, `save`s the mission (a durable checkpoint, ADR 0043 §8), emits
   **`MissionAwaitingApproval`**, and **stops fail-safe** — "the resolution surface is a later phase,
   so the mission remains paused" (comment in the frozen engine). That later phase is this ADR.

4. **The events and the delivery path already exist.** `MissionAwaitingApproval` and `MissionResumed`
   are defined in `mission_engine.events` **and already registered** in the Mission Store's outbox
   `EVENT_REGISTRY` (ADR 0043-S4). The capture → outbox → relay → Delivery Bus → audit path carries
   them today with no mechanism change.

### The load-bearing honesty of this ADR (stated up front)

ADR 0043 fit **entirely behind a frozen port** and changed nothing in the aggregate; the Integration
phase was **pure wiring** outside every frozen package. **Human Approval is neither.** The
resolution — the `approve`/`reject` decision, and the record of *what/who/why* — is **intrinsic to
the mission's own state and invariants** (a consequential step must not run without an approved
gate). It cannot live as pure external wiring or purely behind the store port. Therefore:

> **This ADR consciously *amends* ADR 0042.** It extends the frozen Mission aggregate (a new
> optional `ApprovalRequest` value object + `approve`/`reject` methods), extends the frozen event
> vocabulary (two new events), and — as a consequence — evolves the frozen Mission Store codec (a
> `payload_schema_version` bump, the seam ADR 0043 §6 pre-built for exactly this). These are **not
> smuggled as "implementation details"**; they are the substance of the decision, called out
> wherever they arise, exactly as ADR 0043 promised ("if a design point requires touching a frozen
> component, that is a signal to stop and raise a new ADR — this is that ADR").

Nothing in the *mechanism* of the Store, the Unit of Work, the Outbox, or the Event Bus changes.
`MissionStorePort` keeps its three synchronous methods. The lifecycle table is untouched.

---

## Architectural assumptions

Each is stated with the trigger that would invalidate it, in the ADR 0043 style.

1. **Invariant — at most one active `ApprovalRequest` per Mission at any time.** This is a hard
   aggregate invariant, not merely an observation. At any instant a mission has **either**:
   - **no active approval request** (its normal condition — before any gate, and after every gate is
     resolved), **or**
   - **exactly one active approval request** (while paused in `AWAITING_APPROVAL`),

   and **never multiple concurrent requests.** The engine pauses at the *first* consequential step and
   stops, so a plan with several consequential steps gates them strictly one at a time (pause →
   resolve → resume → next pause); a new request can only be created when there is no active one, and
   resolving a request (approve/reject) clears the active slot. A single optional `approval` field
   (0-or-1) on the aggregate is therefore both sufficient *and* the structural enforcement of this
   invariant — there is nowhere to put a second concurrent request.
   - **Trigger:** parallel/branching plans that could hold several gates open at once (multi-approver,
     Slice 4 / a later planning ADR) would relax this invariant to "at most one active request *per
     open branch*" and replace the single field with a keyed *collection* — a localized change, not a
     redesign, because the field already isolates approval state in one place.
2. **Single required approver, single decision.** One human's approve/reject resolves the gate.
   Multiple approvers, quorum, SLA, timeout, escalation, and expiry are **Slice 4 — deferred**
   (below). The `ApprovalRequest` shape is designed with room for them (a `decisions` list could
   replace a single decision) but Slices 1–3 populate exactly one.
3. **The approver's authority is verified at the engine boundary, not invented by the aggregate.**
   Per ADR 0040 §5 the aggregate re-checks the approver's *tenant* (`assert_tenant`), but *whether a
   principal may approve* (role/permission) is an authorization decision owned by the
   engine/orchestrator above the pure aggregate. The aggregate records the decision; it does not run
   RBAC.
4. **Resume is an explicit re-drive, never a callback inside `approve()`.** The aggregate is pure and
   performs no I/O, so `approve()` cannot dispatch execution. Resumption is a separate step the
   engine/runtime performs on the reloaded mission — the same "external re-drives a durable
   checkpoint" model the Integration phase already proved (ADR 0043 §12).
5. **Approval state is durable *with the mission*, atomically.** Because the `ApprovalRequest` lives
   inside the aggregate, it is written in the *same* row, in the *same* Unit-of-Work transaction, as
   the mission's state change and its outbox event (ADR 0043 §8, 0043-S4 I1/I2). No second store, no
   dual write, no cross-aggregate transaction.

---

## Decision

The seven architectural questions the review posed, each decided.

### 1. What *is* an Approval? — a **value object owned by the Mission aggregate**, not a separate aggregate

An **`ApprovalRequest`** is a value object **inside the Mission aggregate's consistency boundary** —
not an aggregate, not an entity with independent identity, not a separate `Approval` root.

```
Mission
 ├── identity (id, tenant, trace_id)   [frozen]
 ├── status  (lifecycle)               [frozen]
 ├── plan + plan-version history       [frozen]
 ├── step_results                      [frozen]
 └── approval: ApprovalRequest | None  [NEW — this ADR]     ← 0-or-1, the active request (invariant, above)
      └── decision: ApprovalDecision | None                ← None until a human decides
```

Approval is modelled as **two value objects**, deliberately split so the *request* (a fact created
when the mission pauses) is separate from the *decision* (a fact created only when a human acts). The
request exists from the moment of the pause; the decision is **absent until a decision exists** and is
then set exactly once:

**Why a value object inside Mission, and not a separate `Approval` aggregate** (endorsing the
reviewer's steer, with the DDD reasoning made explicit, CLAUDE.md §15):

- **No independent lifecycle.** An approval exists only because a *specific mission* paused at a
  *specific gated step*. It is meaningless without that mission; it is never queried, owned, or
  reasoned about on its own. That is the definition of "belongs inside the aggregate," not "is its
  own aggregate."
- **The consistency boundary is the mission.** Approving must change the mission's lifecycle
  (`AWAITING_APPROVAL → RESUMED`) **and** record the decision **atomically** — a half-applied state
  where the mission resumed but the decision was not recorded (or vice-versa) is a correctness bug in
  a regulated, auditable domain. An aggregate is precisely the transactional consistency boundary
  that makes that atomicity an invariant rather than a hope. A separate aggregate would reintroduce
  the dual-write the Outbox exists to eliminate.
- **Resume stays natural.** Because approval state is part of the mission, it reloads *with* the
  mission (Q7) — the Integration phase's `load()` already returns it for free. A separate Approval
  Store would require a second load, a second tenancy scoping, and a join to answer "what is this
  mission waiting for?"

**`ApprovalRequest`** — the request fact, created by the engine's pause path (Q3):

| field | meaning | populated in |
|---|---|---|
| `id` | identity of *this* request (a minted `apr_…`), so a decision and its events reference an exact request — and the audit trail distinguishes successive gates on one mission | Slice 1 |
| `reason` | why approval is needed (what the gated step will do) — a summary, not the step output | Slice 1 |
| `requested_at` | domain clock at pause | Slice 1 |
| `requested_by` | the request **origin**, not the deciding human (that is `ApprovalDecision.approver`). An engine-raised gate has no human requester, so it records the platform **system principal** (`"system"`) — never the mission id, never a subject. RBAC and the human are out of the aggregate (assumption 3). *(The field name is kept for Slice-1 compatibility; a clearer name — `request_origin` / `requested_by_principal` — is a tracked future ADR, below.)* | Slice 1 |

**`ApprovalDecision`** — the decision fact, **optional until a decision exists** (`None` while
`PENDING`), set exactly once by `approve()`/`reject()` (Q4/Q5):

| field | meaning | populated in |
|---|---|---|
| `approved` | the outcome — `True` = approved, `False` = rejected | Slice 2 |
| `approver` | the deciding `principal_id` (recorded as data; the aggregate does not authorize it, assumption 3) | Slice 2 |
| `comment` | free-text justification (especially for a rejection) | Slice 2 |
| `decided_at` | domain clock at the decision | Slice 2 |

**Both are frozen dataclass value objects** (immutable; consistent with `Plan`/`PlanStep`/
`StepResult`). The *state* of an approval is derived, not stored as an enum: `approval is None` → no
gate; `approval.decision is None` → **pending**; `approval.decision.approved` → **approved**;
`not approval.decision.approved` → **rejected**. Recording a decision produces a *new*
`ApprovalRequest` carrying its `ApprovalDecision`, never a mutation — so "requested" and "decided"
remain two distinct, append-only facts, which is what an audit reconstruction needs.

### 2. Where does it live? — **inside the Mission, persisted through the frozen `MissionStorePort`; no Approval Store, no new port**

- It is a field on the aggregate (Q1), so it is persisted by the **existing** `save(mission)` — **no
  new port method, no `MissionStorePort` change.**
- It is stored **with the mission**, versioned by the frozen store's `payload_schema_version` seam
  (ADR 0043 §6, built precisely because "the shape of `Plan`/`StepResult` will evolve"): **bump
  `payload_schema_version` 1 → 2**, teach the codec that a version-1 row has `approval = None`, and
  read version-2 rows with the field. Old rows keep loading with **no backfill** (absent/NULL → None).
- **Correction discovered at build time (Slice 1):** the real missions schema does **not** use a
  single opaque payload blob — it stores each nested collection in its **own** JSONB column (`roles`,
  `plan`, `plan_versions`, `step_results`). So the faithful realization of "its own nested JSONB" is a
  **new nullable `approval jsonb` column**, added by a small **additive migration
  (`0003_approval.sql`, `ADD COLUMN IF NOT EXISTS`)** — not the "no schema migration" the pre-build
  draft claimed. The migration is backward-compatible by construction (nullable, no default → every
  existing row is NULL → `approval = None`); `0001` stays frozen and untouched.
- **No `Approval Store`, no `ApprovalPort`.** Introducing either would be the separate-aggregate
  design Q1 rejected, and would add a persistence seam ADR 0043 deliberately avoided.

> **Honest frozen-package touch:** this edits the Mission Store's codec and schema (frozen Slice-1
> files), bumps the payload version 1 → 2, and adds the additive `0003` migration. The version bump is
> the *designed* evolution path (ADR 0043 §6), guarded by the codec's version check, the schema parity
> test, and the round-trip contract suite — but it is a change to a frozen package, recorded here, not
> hidden.

### 3. What happens when approval is requested? — **it already pauses, commits, and emits; this ADR only attaches the request**

This is **mostly already frozen behaviour** (Context §3). When `execute()` reaches a consequential
step, the engine:

- **Stops (pauses).** `EXECUTING → AWAITING_APPROVAL` — *already happens.*
- **Commits.** `save(mission)` writes a durable checkpoint (ADR 0043 §8) — *already happens.*
- **Emits an event.** `MissionAwaitingApproval`, captured atomically into the outbox (0043-S4) —
  *already happens.*

**The only addition (Slice 1):** at the moment of pausing, the engine **builds and attaches an
`ApprovalRequest`** (`id`, `reason`, `requested_at`, `requested_by`) to the mission *before* the
`save`, with **no `ApprovalDecision` yet** (`decision = None` → pending). The paused checkpoint
therefore carries **why** it paused, not just the bare status; the request and the
`AWAITING_APPROVAL` state commit together in one transaction (assumption 5). Creating the request is
also where the one-active-request invariant (assumption 1) is enforced: a request is only ever
created into an empty `approval` slot. No new event is needed for "requested" —
`MissionAwaitingApproval` (which already carries the gated `step_id`) already is that fact.

### 4. What happens on Approve? — **a pure state transition + decision record; resumption is a *separate* explicit re-drive, not auto-resume**

`Mission.approve(principal, ...)` (Slice 2):

1. `assert_tenant(principal)` — an approval by a foreign tenant is not an approval (ADR 0040 §5).
2. Set the active request's `ApprovalDecision` (`approved=True`, `approver`, `comment`, `decided_at`)
   — the request's first and only decision; a mission with no active pending request cannot be
   approved.
3. Drive the **already-legal** transition `AWAITING_APPROVAL → RESUMED` (the transient compatibility
   state — Context §1; the engine continues from there, it does not rest in it).
4. Emit **`MissionApproved`** (new event, §6).

**`approve()` does *not* execute the pending step and does *not* auto-resume** (assumption 4):

- The aggregate is pure — it *cannot* dispatch execution.
- Keeping approve a pure decision preserves human-in-the-loop and fail-safe semantics.
- What happens *after* RESUMED is an orchestrator choice the state machine already offers: continue
  (`RESUMED → EXECUTING`) or re-plan (`RESUMED → PLANNED`). Baking auto-continue into `approve()`
  would steal that choice and couple the aggregate to execution.

**Resumption (Slice 3)** is therefore a separate, explicit engine step on the (possibly reloaded)
mission: from `RESUMED`, re-enter execution and run the now-approved step (and the rest of the plan).
This is the same external-re-drive model the Integration phase proved — `load()` then `run_transition()`.

### 5. What happens on Reject? — **fail-safe termination (`CANCELLED`), with the rejection recorded; not an automatic rewind**

`Mission.reject(principal, comment)` (Slice 2):

1. `assert_tenant(principal)`.
2. Set the active request's `ApprovalDecision` (`approved=False`, `approver`, `comment`, `decided_at`).
3. Drive the **already-legal** transition `AWAITING_APPROVAL → CANCELLED`.
4. Emit **`MissionRejected`** (new event, §6).

**Reject terminates the mission fail-safe** — it does **not** roll back to a previous stage and does
**not** execute the rejected action (executing it would defeat the entire gate):

- The gated action is exactly the thing the human declined; the fail-safe outcome is "the
  consequential change was never applied" (ADR 0042 §7), which a terminal `CANCELLED` with a recorded
  rejection delivers cleanly.
- **`CANCELLED`, not `FAILED` or a new `REJECTED` state.** `CANCELLED` already means "a human stopped
  it, fail-safe" and is **already reachable** from `AWAITING_APPROVAL` — so reject **adds no state and
  no transition**. A rejection is a human decision, not an error (`FAILED`); a bespoke `REJECTED`
  terminal would enlarge the frozen state machine for no behaviour `CANCELLED` doesn't already give.
  The rejection is distinguished from a plain cancel by the recorded `ApprovalDecision`
  (`approved=False`, with its `approver` and `comment`) and the `MissionRejected` event — the audit
  fact lives in the data, not in a new status.
- **"Reject-and-replan"** (drop the consequential step, try another path) is *structurally* possible
  (the table allows `AWAITING_APPROVAL → RESUMED → PLANNED`), but conflating "reject this action" with
  "re-plan the mission" is an orchestrator/human decision, **not an automatic consequence of reject.**
  Default reject = terminate fail-safe; a deliberate rework is a separate, higher-level action —
  **deferred** (Slice 4 / a planning concern), not decided here.

### 6. Integration with the Outbox and events — **the mechanism is untouched; the vocabulary gains two members**

- **The outbox/relay/delivery mechanism does not change at all.** Approval events are ordinary
  `MissionEvent`s: mission- and tenant-stamped, captured on the Capture Bus into the outbox in the
  *same* transaction as the `save` (0043-S4 I1/I2), drained in order onto the Delivery Bus, recorded
  by the audit sink. No new sink, no new bus, no relay change.
- **Reused, already-registered:** `MissionAwaitingApproval` (request), `MissionResumed` (resume,
  Slice 3).
- **New (this ADR): `MissionApproved`, `MissionRejected`** — past-tense facts carrying the resolved
  request's `id`, the `approver`, and (for reject) the `comment`, so the audit trail records "every
  human approval/rejection with who and when" (CLAUDE.md §19). They must be **registered in the frozen
  Mission Store `EVENT_REGISTRY`** — which is the *designed* extension point (the codec even ships a
  registry-completeness test that will *fail* until they are added, ADR 0043-S4). Adding two entries
  there is additive and guarded, but is a change to frozen Slice-4 code — recorded here, not hidden.

> **Honest frozen-package touch:** ADR 0042 §12 froze the event vocabulary "so the audit sink,
> tracer, and workspace stream are built once against a stable event set." Adding two events extends
> that set. That is an amendment to ADR 0042's frozen vocabulary, made consciously.

### 7. Preserving the Resume property we built — **for free, *because* approval lives in the aggregate**

The Integration phase proved: pause → `load()` from the store → continue on the reloaded aggregate,
with every event committed and delivered. Human Approval preserves this **by construction**:

- The `ApprovalRequest` is part of the mission payload (Q1/Q2), so `MissionRuntime.load(id, tenant)`
  returns a paused mission **with its pending approval intact** — no second load, no join.
- `approve()`/`reject()` operate on that reloaded aggregate; the decision + state change + event
  commit **atomically** in one Unit-of-Work transaction (assumption 5), exactly as every other
  transition does.
- Resume (Slice 3) is the same `load()` → `run_transition(execute)` the Integration phase already
  ships. **No change to the resume mechanism, the Unit of Work, or the Outbox.**

This is the payoff of the Q1 decision: making approval a value object *inside* the aggregate is what
keeps resume trivial. The separate-aggregate alternative would have broken this.

---

## Slice plan (very small, end-to-end, frozen before the next — the ADR 0043 method)

| Slice | Scope | Adds | Explicitly NOT in it |
|---|---|---|---|
| **1 — Approval State** ⭐ | The mission can *carry* a pending approval and reload it. | `ApprovalRequest` value object (`ApprovalDecision` type defined but always `None` here); optional `approval` field on `Mission` enforcing the one-active-request invariant; engine attaches the request when pausing; codec serializes it (`payload_schema_version` 1→2); round-trips through the store; reloads after restart. | No `approve`/`reject`; no `ApprovalDecision` ever set; no new events beyond the existing `MissionAwaitingApproval`; no UI; no API. |
| **2 — Approve / Reject** | Resolve the gate as a pure decision. | `Mission.approve()` / `Mission.reject()` (tenant re-check + set the request's `ApprovalDecision` + the already-legal `→RESUMED` / `→CANCELLED` transition); `MissionApproved` / `MissionRejected` events + registry entries. | No auto-resume; no execution continuation; no UI/API. |
| **3 — Resume** | Continue execution after approval. | Engine drives `RESUMED → EXECUTING` on the reloaded mission and runs the approved step (and the remaining plan); reuses `MissionResumed`. End-to-end approval→resume→complete test. | No re-plan-after-reject; no multi-approver. |
| **4 — Advanced Approval** | *Deferred.* | Multiple approvers / quorum, timeout, escalation, expiry, SLA, reject-and-replan. | Everything — not designed here; a future ADR. |

Slice 1 is the smallest thing that proves the system can *stop carrying a reason to pause and get it
back after a restart* — the direct analogue of Mission Store Slice 1's "persistence round-trip."

---

## Design challenge (challenged before acceptance, ADR 0043 style)

1. **"This isn't 'behind a frozen port' like the Store — you're editing the frozen aggregate. Isn't
   that exactly what we said we'd never do?"** *The objection is correct about the fact and wrong
   about the rule.* We said we would never *silently* change a frozen component, and that a needed
   change is "a signal to stop and raise a **new ADR**." This **is** that ADR. Human Approval is
   intrinsic to mission state; it *cannot* be pure external wiring without inventing a second
   aggregate (Q1) that reintroduces dual-write. The change is scoped as tightly as possible (one
   optional field + two methods + two events; **zero** lifecycle-table changes) and every frozen-file
   touch is named. This is disciplined amendment, not drift.

2. **"Reject → CANCELLED overloads 'human cancellation'; you're losing the fact that it was a
   rejection."** *Answered.* The *status* is deliberately coarse (the state machine stays frozen and
   minimal); the *fact* that it was a rejection — with who, when, and why — is preserved precisely,
   in the request's `ApprovalDecision` (`approved=False`, `approver`, `comment`, `decided_at`) and the
   `MissionRejected` event. An auditor reconstructs "rejected by whom and why" from the data, which is
   where §19 says that fact belongs, not from a proliferation of terminal states.

3. **"Approve without auto-resume is a worse UX — the user clicks approve and nothing runs."** *A UX
   concern, correctly resolved at the orchestrator, not the aggregate.* The aggregate is pure and must
   stay so; auto-dispatch from a domain method would couple it to execution and I/O. The
   engine/runtime can absolutely chain approve→resume in one caller-level action for a smooth UX —
   that is composition above the aggregate (Slice 3), and it keeps approve independently testable and
   the human-gate semantics clean.

4. **"Why not a separate Approval microservice/aggregate for future flexibility (multi-approver,
   SLA)?"** *Premature, and it breaks atomicity + resume today.* Multi-approver/SLA (Slice 4) can be
   modelled *inside* the aggregate (a `decisions` collection, a deadline field) when it is actually
   built; nothing here blocks that. Splitting approval out now would trade a real, present property
   (atomic state+decision, free resume) for a speculative future one — the exact premature-abstraction
   trap ADR 0043 §3 rejected for the store.

5. **"Bumping `payload_schema_version` and adding a column touches the frozen Store — you're
   unfreezing Slice 1."** *This is the seam working as designed, not a breach — with one honest
   correction.* ADR 0043 §6 introduced `payload_schema_version` **specifically** so aggregate shape
   could evolve in a guarded, versioned way; using it is the intended path (version check + schema
   parity + round-trip contract suite). The pre-build draft claimed this needed *no* schema migration;
   at build time we found the real schema uses per-field JSONB columns, so `approval` is added as its
   own **nullable** column via an **additive** migration (`0003`). That is still cheap and
   backward-compatible (old rows read NULL → None; `0001` untouched), but it is a schema change — named
   here, not hidden. A frozen-file edit, guarded and additive, not a redesign.

---

## Open decisions (need the reviewer's ruling before build)

Each has a default that will be taken unless overruled; none blocks the slice shape.

1. **Reject terminal state.** Reuse `CANCELLED` (no new state; recorded rejection distinguishes it)
   vs. add a dedicated `REJECTED` terminal state to the frozen machine. *Default: reuse `CANCELLED`*
   — adds nothing to the state machine and loses no audit fact.
2. **Where the pause path attaches the `ApprovalRequest`.** Extend the engine's existing pause path to
   build+attach it (keeps the aggregate method count minimal) vs. add a parameter to
   `Mission.await_approval(request=...)` (keeps the aggregate self-describing). *Default: attach in
   the engine's pause path, passing the built request into `await_approval`* — smallest aggregate
   surface, approval data still lives on the aggregate.
3. **`MissionApproved`/`MissionRejected` vs. reuse existing events.** Add the two new events (faithful
   "who/when/why" for §19) vs. reuse `MissionResumed`/`MissionCancelled` (zero new events, weaker
   audit). *Default: add the two events* — audit fidelity is the point of the feature; the registry
   extension point exists for exactly this.
4. **Approver authorization.** Confirm that *whether a principal may approve* (role/permission) is the
   engine/orchestrator's decision (aggregate only re-checks tenant), consistent with assumption 3.
   *Default: yes* — the pure aggregate does not run RBAC.

---

## Consequences

**Positive**
- The human gate becomes **complete** (pause → decide → resume/terminate) while the **lifecycle state
  machine stays frozen and unchanged** — no new state, no new transition.
- Approval state is **durable, atomic, and tenant-isolated for free**, riding the Store + Unit of Work
  + Outbox exactly as every other transition does; **resume keeps working unchanged** (Q7).
- Every approval/rejection is an **auditable event with who/when/why** (CLAUDE.md §19), delivered
  through the existing path.
- Scope is minimal and honest: the frozen-component amendments (aggregate field + method extension,
  the two events + registry entries later, the `payload_schema_version` 1 → 2 bump, and the additive
  `0003` column migration) are each named and each guarded by an existing test seam.

**Negative / costs**
- This ADR **amends the frozen ADR 0042** (aggregate shape + event vocabulary) and evolves the frozen
  ADR 0043 store (codec version bump **plus an additive `approval` column migration** — the pre-build
  "no schema migration" claim was corrected at build time; see §2). Accepted, deliberate, and scoped —
  but real, and it means Mission Engine + Mission Store are no longer "never touched again."
- On acceptance, **CLAUDE.md §8** (which already names *Awaiting Approval* and *Resumed*) gets a small
  clarification that approve/reject are the resolution, and the index/status here move to Accepted.
- Advanced approval (multi-approver, SLA, timeout, escalation, expiry, reject-and-replan) is **not
  designed here** — Slice 4, a future ADR.

## Alternatives considered

- **Approval as a separate `Approval` aggregate + `ApprovalStore`/`ApprovalPort`.** Rejected (Q1): no
  independent lifecycle, reintroduces the dual-write the Outbox exists to remove, breaks free resume,
  and adds a persistence seam ADR 0043 avoided. Multi-approver later is modelled *inside* the mission,
  not by splitting it out.
- **A dedicated `REJECTED` terminal state.** Rejected: enlarges the frozen state machine for no
  behaviour `CANCELLED` (already reachable, already fail-safe) doesn't provide; the rejection fact
  lives in the `ApprovalDecision` + the `MissionRejected` event.
- **Auto-resume inside `approve()`.** Rejected (assumption 4): the pure aggregate cannot perform I/O;
  it would couple the domain to execution and steal the RESUMED→(EXECUTING|PLANNED) choice from the
  orchestrator. UX chaining is done above the aggregate (Slice 3).
- **Store approval data in a side column outside the aggregate.** Rejected: it would not reload with
  the mission (breaking Q7's free resume) and would split the mission's consistency boundary.
- **Do it all in one release (no slices).** Rejected: contradicts the method that made Mission Store
  safe. Slice 1 (carry + reload a pending approval) is the smallest provable increment.

---

## Future ADRs

- **Advanced Approval (Slice 4).** Multiple approvers / quorum, timeout, escalation, expiry, SLA, and
  reject-and-replan. These extend the `ApprovalRequest` (e.g. a `decisions` collection, a deadline)
  and may add orchestration (a scheduler for timeouts) — designed when built, not here.
- **Approver authorization model.** If role/permission-based approval authority becomes a
  first-class, configurable policy (beyond "the engine checks it"), that is its own ADR touching the
  orchestrator's policy layer (CLAUDE.md §7), not the aggregate.
- **`requested_by` naming + a real service principal.** `ApprovalRequest.requested_by` is the request
  *origin*; today an engine-raised gate records the sentinel `"system"`. When a **Human Approval
  service** and real **service-principal identities** land, this should carry that principal, and the
  field is a candidate to **rename** to an unambiguous name (`request_origin` /
  `requested_by_principal`). Because the field is persisted (payload v2), a rename is a payload-shape
  change → a `payload_schema_version` bump + forward-migration, i.e. a tracked ADR-level change, not a
  silent edit. Recorded here so the current `"system"` sentinel is a **documented interim**, not
  hidden technical debt.

---

## Implementation Status

Delivered as slices, each built end-to-end, tested, and frozen before the next — the Mission Store
method. Status as of 2026-07-17:

- **Slice 1 — Approval State — ✅ Implemented (green; pending freeze review).** The Mission aggregate
  can now *carry* a pending approval and round-trip it durably.
  - **Aggregate (`mission-engine`, extends ADR 0042):** two frozen value objects `ApprovalRequest`
    (`id` / `reason` / `requested_at` / `requested_by`, + minted `apr_…` id) and `ApprovalDecision`
    (`approved` / `approver` / `comment` / `decided_at`), in `approval.py`; an optional
    `Mission.approval` field; `await_approval(request=None)` extended to attach the request
    (backward-compatible — the no-arg call is unchanged); the `has_active_approval` view; and a new
    `ApprovalError`. The **one-active-request invariant** is enforced in `await_approval` (a second
    active request is refused). **No approve/reject, no `ApprovalDecision` ever set, no events** — the
    decision half is always `None` in Slice 1.
  - **Persistence (`mission-store`, evolves ADR 0043):** `payload_schema_version` **1 → 2**; codec
    reads **both** versions (v1 → `approval = None`, no backfill) and writes the optional approval; a
    new nullable `approval jsonb` column via the **additive** migration `0003_approval.sql`
    (`ADD COLUMN IF NOT EXISTS`; `0001` untouched); schema parity updated.
  - **Verified:** aggregate + value-object unit tests (incl. the invariant), pure codec round-trip and
    **v1/v2 back-compat**, and a **real-PostgreSQL** save → reload proving a paused mission's
    `ApprovalRequest` survives unchanged (the "resume returns it as-is" evidence — *data* round-trip
    only; no new resume logic). Full suites green: event-bus 35, mission-engine 60, mission-store 85,
    mission-integration 9 (= 189); `ruff` + `mypy --strict` clean on all source.
  - **Deliberately NOT in Slice 1:** `approve()`/`reject()`, `MissionApproved`/`MissionRejected`, RBAC,
    API, UI, notifications, any Outbox/Integration change, and any new resume logic.
- **Slice 2 — Approve / Reject — ✅ Implemented (green; pending freeze review).** The aggregate can
  now *resolve* a pending gate.
  - **Aggregate (`mission-engine`):** `Mission.approve(approver, comment=…, now=…)` drives
    AWAITING_APPROVAL → RESUMED; `Mission.reject(…)` drives AWAITING_APPROVAL → CANCELLED (fail-safe,
    reusing the frozen terminal — no `REJECTED` state). Both re-check the approver's **tenant**
    (`assert_tenant`, ADR 0040 §5), require an active pending request, and record the decision as a
    **new** `ApprovalRequest` carrying its `ApprovalDecision` (`approved` true/false, `approver`,
    `comment`, `decided_at`) — never a mutation. The transition is validated **before** the decision
    is written, so an illegal call leaves the request undecided. A resolved request is no longer
    active, so a gate is decided exactly once.
  - **Events (`mission-engine` + `mission-store`):** `MissionApproved` (`approval_id` / `approver`)
    and `MissionRejected` (`approval_id` / `approver` / `comment`), registered in the outbox
    `EVENT_REGISTRY` (the completeness test enforces it) so the delivery path can carry them.
  - **Verified:** approve/reject lifecycle unit tests (transition, decision recording, foreign-tenant
    refusal → `TenantMismatch`, no-pending-request → `ApprovalError`, decide-once, illegal-state
    leaves the request undecided) and outbox round-trip for both new events. Full suites green:
    event-bus 35, mission-engine 70, mission-store 86, mission-integration 9 (= 200); `ruff` +
    `mypy --strict` clean on all source.
  - **Deliberately NOT in Slice 2 (per the slice brief):** no resume orchestration / execution
    continuation, no engine *emission* wiring for the two events, no RBAC, and no Human service / API /
    REST / UI / Email / Slack / notifications / Integration Runtime / audit projection / lease / OCC /
    retry / scheduler.
- **Slice 3 — Resume (orchestration) — ✅ Implemented (green; pending freeze review).** The first
  time the **Integration Runtime** enters ADR 0044: an approved mission is detected, reloaded, and
  re-entered into the engine to continue from the pause point.
  - **Engine (`mission-engine`):** the pause path now **attaches** the `ApprovalRequest` it was
    always meant to (`_build_request`, `requested_by = "system"` — the request origin, not a human;
    see the naming note in §1 and Future ADRs), wiring what Slice 1 deferred;
    `execute` and the new `resume` share one resume-aware driver (`_drive`) — a single approval
    authorizes exactly the gated step at the resume point (`_gate_is_approved`), any later
    consequential step still pauses. `engine.approve` / `engine.reject` apply the aggregate decision,
    persist it, and **emit** `MissionApproved` / `MissionRejected`; `engine.resume` emits
    `MissionResumed`, re-enters `RESUMED → EXECUTING`, and drives to completion or the next gate.
  - **Runtime (`mission-integration`):** `MissionRuntime.approve` / `reject` / `resume_if_approved`
    — the orchestration seam. `resume_if_approved` **detects** the approval (persisted status
    `RESUMED`), **reloads** from the store, and **re-enters** the engine, each in its own
    transaction so every event (`MissionResumed`, the gated step, `MissionCompleted`) is captured to
    the outbox exactly like any other transition. No scheduler/queue/polling — the caller names the
    mission; a non-`RESUMED` mission is a deliberate no-op.
  - **Verified:** engine-level approve/resume/reject unit tests (attach-at-pause, resume-from-point,
    single-approval-authorizes-single-step, guards) and **real-PostgreSQL E2E**: pause → approve →
    `resume_if_approved` → COMPLETED with the full outbox narrative (`created, planned,
    step_completed, awaiting_approval, approved, resumed, step_completed, completed`) delivered to the
    Audit Sink in order; plus the reject and no-op variants. Full suites green: event-bus 35,
    mission-engine 76, mission-store 86, mission-integration 12 (= 209); `ruff` + `mypy --strict`
    clean on all source.
  - **Deliberately NOT in Slice 3 (per the slice brief):** no REST API, Human UI, Email, Slack,
    notifications, RBAC, scheduler, retry, lease, OCC, multi-worker, or approval queue.
- **Slice 4 — Advanced Approval — ⏳ Not started** (multi-approver, timeout, escalation, expiry, SLA,
  reject-and-replan).
