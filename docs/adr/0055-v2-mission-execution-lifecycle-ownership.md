# ADR 0055: Who owns the mission execution lifecycle — the transaction boundary for the Product API

- Status: **Accepted** (2026-07-23) — **Gate A** of the V1 → Platform migration is **closed**; Wave 1
  may open. (While this was `Proposed`, no code was permitted to change `create_app()`, wire
  `mission-store`, or replace `EchoExecutor`.)
- Date: 2026-07-23
- Deciders: **Product Owner** (this is a lifecycle decision, reserved to the owner like ADR 0052–0054),
  Architecture
- Related: ADR 0042 (Mission Engine) · ADR 0043 (Mission Store, Unit of Work, Transactional Outbox) ·
  ADR 0044 (human approval + resume orchestration) · ADR 0052 (`grc-api` is a Composition Root) ·
  ADR 0053 (read models & Application-layer projection) · ADR 0054 (the Application-layer contract) ·
  [MIGRATION_ASSESSMENT.md](../../v2/docs/MIGRATION_ASSESSMENT.md) (F11, Gate A, Wave 1)

---

## Context

Fact **F11** of the Migration Assessment, stated without interpretation:

> `MissionRuntime.run_transition` builds a connection, a `UnitOfWork`, a `PostgresMissionStore`, a
> capture `EventBus`, an `OutboxSink`, and a `MissionEngine` **per transition**.
> `grc-api`'s `create_app` builds **one** `MissionEngine` and **one** store, stores them on
> `app.state`, and hands them to every request for the lifetime of the process.

Today this costs nothing: `app.state` holds an `InMemoryMissionStore` and an `EchoExecutor`, so there
is no connection and no transaction to get wrong. The moment Wave 1 wires the durable path, the two
models meet — and they cannot both be right.

The decision this ADR must settle is therefore **not** "how do we swap `EchoExecutor`". It is:
**who owns a mission's execution lifecycle, and where does its transaction begin and end?**

### What the investigation found

Three findings, established by reading the frozen code before writing this ADR.

**C1 — `MissionEngine` is stateless.** It holds only its injected collaborators (`store`, `executor`,
`events`, `clock`) and no mission state, session, or connection. So a "long-lived engine" is not a
state hazard. The hazard is **binding**: an engine is constructed *with* a store, and
`PostgresMissionStore` is constructed *with* a connection — so an engine's lifetime is transitively
a **connection's** lifetime. A process-lifetime engine over Postgres means one connection shared by
every request, with no per-use-case transaction boundary.

**C2 — one `execute()` is many writes, and `run_transition` wraps all of them in one transaction.**
`MissionEngine._drive` calls `store.save(mission)` and emits an event **after every step**
(`engine.py` contains 11 `_store.save` calls). `mission-integration`'s own tests drive a whole plan
as a single transition — `runtime.run_transition(lambda e: e.execute(mission))`. With `EchoExecutor`
that transaction lasts microseconds. With `RegistryExecutor` it spans **every tool call and every LLM
call in the plan**: a Gap Assessment holds a Postgres transaction open across a framework lookup, a
tenant-scoped search, and a generation call.

**This is the discovery that makes Gate A non-trivial.** The proven `MissionRuntime` pattern was
validated against an instant executor. It has never met a slow one. Wiring it unchanged would put
minutes-long LLM latency inside a database transaction, holding a connection and its locks for the
duration.

**C3 — a command has three transactional participants, not one.** `MissionCommand.execute` runs
`authorize → load → validate → invoke → project`. In `grc-api` those are three separate objects over
three independently-constructed collaborators: `StoreMissionAccess` (a store), `EngineWorkflow` (an
engine), and `ReadModelProjection` (a read model). With in-memory adapters, atomicity between them
was moot. With Postgres, the mission write, the outbox rows, **and the read-model projection** must
share one transaction — or ADR 0053's synchronous projection becomes a second dual write, alongside
the one the outbox exists to prevent.

`UnitOfWork` constrains the answer: it is **single-use, a single flat transaction, no nesting**, and
it rejects an injected autocommit connection outright.

## Forces

1. **Atomicity of state and events.** A mission's `save` and its domain events must commit together,
   or the audit trail lies. This is the whole reason the outbox exists (ADR 0043-S4).
2. **Transaction duration.** A transaction must not span an LLM call. This force did not exist before
   Wave 1 and is invisible in the current tests (C2).
3. **The use case is the natural boundary.** CLAUDE.md §14 and ADR 0054 both place the transaction at
   the Application service / command — one use case, one unit of work — which C3 requires anyway.
4. **One proven capture path.** `MissionRuntime` already encodes the correct capture wiring, green
   against real PostgreSQL. Re-encoding it elsewhere invites divergence.
5. **Synchronous V1 is locked.** ADR 0053 §3: "V1 is synchronous; no async infra before need."
   Forces 2 and 5 pull in opposite directions — that tension is the substance of this decision.
6. **The frozen Core must not change.** `MissionEngine`, `MissionStorePort`, and `UnitOfWork` are
   frozen. Any option requiring an engine change is disqualified without a superseding ADR.
7. **`grc-api` is a Composition Root only** (ADR 0052). Whatever owns the transaction, no business
   logic may move into the host.

## Non-goals

This ADR does **not** decide:

- Whether mission execution remains **synchronous** or moves to background processing.
- Which `ExecutionPort` implementation is used — `EchoExecutor`, `RegistryExecutor`, or any future one.
- HTTP request/response semantics, or any queue / background-job architecture.
- Whether read-model projection later becomes event-driven; ADR 0053 keeps that open, and C3 pulling
  projection into the transaction does not close it.

It decides **only** the ownership and lifetime of the transaction boundary for command execution.

This section exists because C2 is easy to over-read. Discovering that slow execution inside a
transaction is a problem invites the conclusion "then move execution to a queue" — a reasonable
thought, and a different decision. Keeping it out is what lets this one be settled.

## Options

*Each option is named by its **principle**, not by its letter — the letters are cross-reference
handles only. A year from now nobody will remember what "B" was; "who owns the transaction" stays
readable.*

### Option A — Runtime-owned transaction boundary (the transaction wraps execution) — **rejected**

`grc-api` drops `app.state.mission_engine` / `app.state.mission_store`; every command drives the Core
through `MissionRuntime.run_transition`.

- **For:** one proven path; capture-half correctness by construction; `mission-integration` stays the
  only place that knows the wiring (force 4).
- **Against:** violates force 2 head-on — `execute` inside `run_transition` spans every LLM call
  (C2). Also unresolved: `MissionCommand`'s `load` happens *outside* the transition, and the
  read-model projection has no seat in it (C3).

### Option B — Request-owned transaction boundary

The host opens one `UnitOfWork` per request as a dependency, binds the store, the outbox sink **and
the read model** to `uow.connection`, constructs the engine there, and injects it into the command.
`MissionRuntime` remains the composition root for workers and batch, not for HTTP.

- **For:** matches force 3 exactly — one use case, one transaction, with all three C3 participants
  inside it; load, invoke, and project become atomic; no Core change.
- **Against:** re-encodes capture wiring that `MissionRuntime` already owns (force 4 — mitigable by
  extracting the capture assembly into a shared factory rather than copying it). Does **not** by
  itself solve force 2: a synchronous `start` still runs the plan in-request.

### Option C — Transition-owned transaction boundary (execution outside the transaction)

Create · plan · approve · reject · start-of-run are short transitions, each its own transaction. The
step loop (`_drive`) runs **outside** any transaction, persisting per step through the store's
autocommit (owned) mode, with each step's events captured in their own short transaction.

- **For:** resolves force 2 properly — no transaction ever spans a tool or LLM call.
- **Against:** a mission's steps are no longer atomic with each other (they already are not
  semantically — each step is separately recorded), and per-step capture needs a defined boundary.
  Closest to the ROADMAP's deferred "durable/concurrent mission execution", so it risks pulling that
  scope forward against force 5.

### Option D — **Command-owned transaction boundary; execution outside the transaction**

Short commands own their transaction (the boundary of Option B, placed at the command rather than
the request). The step loop runs outside it (Option C), each step's state and events committed in
their own short transaction.

**Its real shape: this is not one answer, it is the separation of two questions that have been
conflated.**

| Question | Answer |
|---|---|
| Who owns the **transaction**? | **The command.** |
| Who owns the **execution**? | **Not this ADR.** |

That separation is the point. Options A and B answer both questions at once — and therefore answer
the second one by accident.

- **For:** satisfies forces 1, 2, 3, 6 and 7 simultaneously; keeps V1 synchronous (a `start` request
  still returns when the plan finishes — the *transaction* is short, not the *request*), so force 5
  holds without introducing a queue; and it leaves the execution-ownership question open to be
  decided on its own merits rather than settled as a side effect of a persistence choice.
- **Against:** two boundaries to explain instead of one; requires naming exactly which engine calls
  are "short transitions". Highest conceptual cost, lowest operational risk.

## Decision

**Option D — *Command-owned transaction boundary; execution outside the transaction*.**

The transaction is owned by the **command** — the Application-layer use case of ADR 0054. One command,
one `UnitOfWork`, with the mission store, the outbox sink, **and** the read-model projection all bound
to its connection, so load · invoke · project commit together or not at all (C3). The step loop runs
**outside** that transaction, each step's state and events committed in their own short transaction,
so no transaction ever spans a tool or an LLM call (C2).

### The principle

> **A transaction boundary is defined by the use case, not by where the work runs.**

This is the rule to apply when a future question looks like this one. It is why the decision holds
under either execution model, and why it deliberately settles only the first of the two questions
that were being conflated:

| Question | Answer |
|---|---|
| Who owns the **transaction**? | **The command.** |
| Who owns the **execution**? | **Deferred** — see *Deferred decision*. |

Every rejected option answers both questions at once, and therefore settles mission execution's
lifecycle as a side effect of choosing where a `COMMIT` goes.

## Consequences

**If Option D — *Command-owned transaction boundary; execution outside the transaction* — is accepted:**

- **Changes.** `grc-api` gains a per-command Unit of Work; `StoreMissionAccess`, `EngineWorkflow`,
  and `ReadModelProjection` are constructed against one shared connection instead of three
  independent ones; the read model's projection joins the mission's transaction (the **Consistency**
  model). Execution is taken out of that transaction (the **Temporal** model) — see *Implementation
  notes* for why these are two changes, not one.
- **Does not change.** `MissionEngine`, `MissionStorePort`, `UnitOfWork`, the aggregate, the event
  set, ADR 0053's "projection is a synchronous Application-layer act", ADR 0054's command contract,
  or any route signature. `MissionRuntime` keeps its role for workers and batch and stays frozen.
- **Wave 1 becomes wiring.** With the boundary named, replacing `EchoExecutor`, wiring
  `PostgresMissionStore`, and wiring both Postgres read models are composition changes behind
  existing seams — which is the outcome this methodology is aiming at.
- **Opens later.** Moving execution off the request entirely (a queue or worker) remains available
  and is *not* decided here; Option D deliberately keeps that door open without walking through it.

**Regardless of the option chosen**, two things must be true before Wave 1 closes: no production path
retains a Development Composition adapter, and the durable path has its own tests — today's suites
prove the in-memory path only.

### Deferred decision

Whether mission execution should remain synchronous or move to background processing is
**intentionally deferred to a future ADR**. The decision made here remains valid under either
execution model: a command-owned transaction boundary is correct whether the step loop runs
in-request or in a worker, because the boundary is defined by the *use case*, not by *where the work
runs*. Today's decision constrains nothing about tomorrow's.

## Implementation notes (added 2026-07-23, during Wave 1)

Building this decision surfaced two things worth recording on the ADR itself — one a sharpening of
what the decision *is*, one a constraint the frozen Core imposes on *how* it is reached. Neither
changes the decision.

### Two models, not two mechanisms

"Command owns the transaction; execution sits outside it" is not one property — it is **two
independently observable ones**, and conflating them is what a first implementation got wrong (it
made the transaction atomic and left execution inside it; the atomicity test passed and the
visibility test failed, on the same code). Named at the level the system observes them:

| Property | Model it changes | Observable as | Does **not** speak of |
|---|---|---|---|
| Every logical effect of a command (state · events · projection) is atomic | **Consistency** | a failed command leaves nothing; its event is in the outbox | time, execution, tools |
| Execution progress becomes visible as it happens | **Temporal** | step *n* is visible to another session before the mission finishes; no transaction spans a tool/LLM call | atomicity, which store |

`Store` and `Execution` are *mechanisms*; **Consistency** and **Temporal visibility** are the
*properties*. Scoping the work by the properties (per rule 7 of the migration protocol) is what keeps
the boundary stable when the mechanism later changes.

### The separation is achieved outside the frozen engine — a constraint, not a defect

`MissionEngine.execute()` (and `resume()`) **couple** the state transition into `EXECUTING` with the
`_drive` step loop, in one call. This is a **constraint of the frozen Core**, recorded as such — not
a bug to fix and not a reason to touch the engine (ADR 0042 §3 keeps infrastructure out of it). The
consequence is stated precisely:

> Given this Core, the separation is achieved **from outside it**: execution becomes not-part-of the
> command transaction. *Today* that is realised by running the drive on an autocommit connection
> while decision transitions run inside a `UnitOfWork`; *tomorrow* it could be a worker, a queue, an
> actor, or a saga. The autocommit connection is the **first implementation** of the temporal model,
> not the model itself.

This is the same discipline the whole project follows: **wire above the Core, do not change the
Core.**

### The resulting split

Because the two properties can succeed or fail independently, they are two commits, each named for
its property, not its mechanism:

- **`replace(wave1): introduce command-scoped durability`** — the Consistency model. (The Wave 1
  Commit-3 work already written realises exactly this and only this; it is re-scoped to it, not
  discarded.)
- **`replace(wave1): run execution outside the command transaction`** — the Temporal model.

## Rejected alternatives

- **Option A — Runtime-owned transaction boundary** (`MissionRuntime` as the single entry point).
  Rejected at acceptance, in the owner's words: *it builds the transaction around execution* — exactly
  what C2 disqualifies. Note what is **not** rejected: `MissionRuntime`'s capture wiring stays correct
  and stays in use for workers and batch. It is the **placement of the boundary** that is rejected,
  not the runtime.
- **Option B — Request-owned transaction boundary**, on its own. It resolves atomicity (C3) but not
  transaction duration (C2): a synchronous `start` still runs the whole plan inside the transaction.
  Its boundary survives *inside* the accepted decision, moved from the request to the command.
- **Keep one process-lifetime engine over a Postgres store.** One shared connection for all requests,
  no per-use-case boundary, and concurrent requests interleaving on one transaction (C1). Unsafe.
- **Per-step autocommit with no outbox capture.** Restores the exact dual write the Transactional
  Outbox was built to eliminate (force 1) — mission state durable, events lost on failure.
- **Change `MissionEngine` to own its transaction.** Violates force 6, and would put infrastructure
  concern inside the frozen Core, which ADR 0042 §3 explicitly excludes.
- **Nested or re-entrant units of work** (a transaction per command *and* per transition). `UnitOfWork`
  is single-use and non-nesting by design (ADR 0043 §8); working around it means changing frozen code.
- **Defer the whole question and wire the in-memory adapters "for now".** That is the status quo, and
  it is precisely what produced a convincing product standing on `dev.py`.

## Open question carried to the owner

Option D keeps V1 synchronous: a `start` request still returns only when the plan finishes, so a slow
mission means a slow HTTP response even though no transaction is held open. **Is that acceptable for
V1?**

Either answer leaves this ADR intact — see *Deferred decision*. A "no" does not call for a different
transaction boundary; it calls for moving execution off the request, which is the deferred decision
and its own ADR. The question is asked here only so that acceptance is informed, not so that it is
settled here.
