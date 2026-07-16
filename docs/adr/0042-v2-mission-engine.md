# ADR 0042: Rasheed V2 — the Mission Engine (the governed unit of work, decided before it is built)

- Status: **Accepted** — architecture only (this ADR writes no code); the first Phase 15
  package (the Mission Engine) is built directly against it. Amended and accepted 2026-07-16
  (see *Amendment* at the end).
- Date: 2026-07-16
- Deciders: Product Owner (accepted 2026-07-16), Architecture
- Related: CLAUDE.md §3 (mission-centric), §7 (the Orchestrator is the brain), §8 (mission
  lifecycle), §9/§10 (tools & registry), §11 (agents), §14/§15 (services & DDD), §16
  (events), §19 (audit & transparency), §20 (tenancy); ADR 0003 (mission-centric design),
  0004 (AI Orchestrator), 0005 (multi-agent), 0006 (tools & registry), 0009 (EDA), 0011
  (DDD boundaries), 0015 (audit & traceability), 0038 (pipeline-contracts + ai-orchestrator
  composition root), 0039 (platform hardening), 0040 (tenancy model — contract only)

---

## Context

V2 has a stable **Platform** layer (Phases 1–14.8): Decision Engine, Retrieval Engine,
Context Builder, Prompt Orchestrator, Generation Engine, Answer Validation, AI Orchestrator
(the pipeline composition root, ADR 0038), Event Bus, Pipeline Tracing, and the Knowledge
Importer. All of it does one thing: it turns a single `UserRequest` into a single grounded,
validated, audited `Answer`. It is a **one-shot reasoning pipeline**.

The **Product** layer does not exist yet: Mission Engine, Tool Registry, Mission Store,
Human Approval, Agent Runtime, Framework Engine. CLAUDE.md has asserted since day one (§3,
§8; ADR 0003) that the system is *mission-centric, not chat-centric* — but nothing named
"Mission" has ever been built. The pipeline is the whole product today.

Phase 15 begins the Product layer, and the Mission Engine is its foundation. Every later
subsystem (Tools, Agents, Human Approval) is something a Mission *uses*. If the Mission
model is wrong, or its boundaries with the coming layers are vague, we will redesign Phases
15, 16, and 17 in sequence. ADR 0040 already made this argument for tenancy and fixed that
contract ahead of the build; this ADR does the same for the Mission itself.

**This ADR deliberately writes no code.** No package, class, interface, or dataclass is
proposed. It fixes: (1) *whether* Mission is even the right top-level unit, (2) what a
Mission is and is not, (3) the boundaries between Mission and the Platform below it and the
Product layers beside it, and (4) the small set of decisions that must be locked now to
avoid a redesign in Phase 16/17.

### The question the sponsor asked: is "Mission" actually right?

Before accepting the mission-centric pillar as a foregone conclusion, we re-opened it and
weighed five candidate top-level units of work: **Chat-first, Workflow-first, Tool-first,
Agent-first, Mission-first.** The analysis is in *Alternatives considered* below and is the
real substance of this ADR. Its conclusion is stated up front so the rest of the document
can build on it:

> **The five options are not rivals at the same altitude — treating them as mutually
> exclusive is a category error.** A **Tool** is a unit of *capability* (a verb). An
> **Agent** is a unit of *reasoning* (a worker). A **Workflow** is a unit of *durable
> execution* (a substrate). **Chat** is one *interface* (an input modality). Only a
> **Mission** is a unit of *governed work toward an outcome* (the envelope). Mission is the
> only candidate operating at the governance altitude a regulated, auditable, consequential,
> multi-tenant, human-gated domain demands — and the other four are best understood as its
> collaborators nesting inside it, not as alternatives to it.

So the decision is **Mission-first**, but not as a rubber stamp of §3. It is chosen because
it is the *only* option at the right altitude, and because elevating any of the other four
to the top produces a concrete, nameable failure (each is named below). It is adopted in its
strongest form — **Everything is a Mission** (*Decision §11*): there is no Query, Workflow,
Session, or Job as an independent executable unit, and no "promotion" into a mission. The
only thing that varies between a trivial read and a large engagement is the mission's
**`execution_profile`** — never its model, its store, or its execution path.

---

## Decision

### 1. What a Mission is

**A Mission is the platform's single top-level unit of governed work: a tenant-owned,
goal-directed, auditable, resumable envelope that carries a goal, a versioned plan, an
ordered set of steps, the agents and tools each step used, its inputs and outputs, their
citations and confidence, its human-approval gates, its status, and its complete event
history — from creation to archival.**

A Mission is the **noun** the whole system is organized around. It does not reason (agents
do), it does not execute capability (tools do), it does not persist itself (the Mission
Store does), and it does not run durably by itself (the Workflow substrate does). It
*owns the outcome* and *governs the path to it*: the plan, the lifecycle, the gates, and
the audit narrative that an external auditor replays. Everything else is something the
Mission composes.

A Mission is a **first-class domain aggregate** (DDD, §15; ADR 0011) in a new **Missions**
bounded context. Its aggregate root enforces its own invariants — a step cannot complete
before it starts, a consequential step cannot execute before its gate is approved, a
mission cannot change tenant, a completed mission is immutable. State changes go through the
root, never around it.

**Why a Mission is not each of the neighbouring concepts** (the distinction is load-bearing;
conflating any of them collapses the governance model):

| A Mission is **not** a… | Because… |
|---|---|
| **Chat** | Chat is an *interface/modality* that can *open* or *steer* a mission. A chat has a transcript; a mission has a goal, a plan, a lifecycle, gates, and a reconstructable audit trail. Messages scroll away; a mission is a durable object. (§18) |
| **Request** | A Request (`UserRequest`, §5/ADR 0038) is a single stateless input→output at the API boundary, alive for one round-trip. A Mission is stateful, multi-step, resumable, and outlives any request. One request may *create* a mission or *advance* it; it is never the mission. |
| **Workflow** | A Workflow is a *durable execution mechanism* — the substrate that provides retries, timers, and replayable state. It answers *how* work runs reliably. A Mission is a *domain and governance* concept — it answers *what* outcome is pursued, *why*, with *what grounding*, and under *whose* approval. A mission is *executed via* a workflow; it is not one. (§8 vs the Workflow Engine in §5) |
| **Task / Job** | A Task or Job is a unit of *execution* — a step, a queued background job — with no goal-level governance, no grounding, no human-gate narrative, and no standing before an auditor. A Mission *contains* steps and may *schedule* jobs, but a job is not accountable for an *outcome*; a mission is. |
| **Session** | A Session is an *authentication / interaction context* tied to a login and a time window. A Mission is tied to a *goal*, not a login: it outlives any session and can be resumed later, in a different session, by a different authorized principal of the same tenant. |

### 2. Responsibilities of the Mission Engine

The **Mission Engine** is the subsystem that creates missions and drives them through their
lifecycle. Its responsibilities, and *only* these:

1. **Mission creation & identity.** Open a mission from a goal and a context, binding
   `tenant_id`, owner/principal, and an immutable identity at birth (tenancy per ADR 0040).
2. **Planning custody — not planning itself.** Hold the mission's **plan** as a persisted,
   versioned, inspectable artifact. The *plan is produced by the Orchestrator's planning
   step* (which may consult the LLM as a suggester, §7); the Mission Engine owns *storing,
   versioning, and exposing* it, and owns re-planning as a new plan version on the same
   mission. The plan is data, never the model's hidden reasoning (§19).
3. **Lifecycle custody.** Own the state machine (§7 below): advance a mission through its
   states, enforce legal transitions, and reject illegal ones at the aggregate boundary.
4. **Step sequencing & dispatch — via a port, not by executing.** Decide which step runs
   next and hand it to an **execution port** for running. The Mission Engine does *not*
   itself call tools, run agents, or invoke the pipeline; it dispatches a "step to execute"
   and records the result. (Boundary in §5 and §9.)
5. **Human-gate custody.** When a step is consequential, pause the mission in *Awaiting
   Approval* **before** the step executes, surface the proposed action and its grounded
   evidence, and resume only on an explicit, tenant-verified human decision (§4, §9;
   fail-safe per §16 of CLAUDE.md).
6. **State, resume, replay, idempotency.** Persist mission state (through the Mission Store
   *port*) so a mission can be paused, resumed, retried, cancelled, or replayed
   deterministically, and so a retried step never double-applies a side effect.
7. **Event emission.** Emit a domain event on every meaningful transition (§8 below), each
   **`mission_id`-stamped and `tenant_id`-stamped** (§12.2; ADR 0040 §6), onto the existing
   Event Bus (ADR 0039) — the Mission Engine publishes; it does not run the bus.
8. **Audit & trace composition — not reimplementation.** Assemble each step's existing
   `PipelineResult` / `AuditRecord` / trace (ADR 0038/0039) into the mission's narrative so
   an auditor can replay the whole mission. It *composes* the platform's audit; it does not
   build a second one (§4).

### 3. Non-Goals — what the Mission Engine does not do

Stated as hard exclusions so reviewers can reject scope creep:

- **It does not reason.** No planning heuristics, no GRC judgement, no prompt content live
  in the Mission Engine. Reasoning is the Orchestrator's planning step and the Agents (§6).
- **It does not execute capability.** It never calls a Tool, never talks to the Tool
  Registry, never touches a vector store, an LLM SDK, or a provider. It dispatches to an
  execution port and records the outcome (§5, §9).
- **It does not re-implement the Platform.** It reuses the AI Orchestrator/pipeline, Event
  Bus, Audit, Tracing, and Answer Validation as they are (§4). It adds *no* second pipeline,
  *no* second event bus, *no* second validator.
- **It does not resolve tenancy.** Tenant context is minted at the auth boundary and carried
  in (ADR 0040). The Mission Engine *binds and preserves* it; it never derives, widens, or
  infers it.
- **It does not persist itself.** Durable storage is the **Mission Store** (a later phase),
  reached through a port. The Mission Engine holds no schema and no DB knowledge.
- **It does not decide approvals.** *Human Approval* (a later phase) resolves gates; the
  Mission Engine owns only the *pause/resume authority* and the lifecycle state.
- **It does not define frameworks or GRC domain rules.** Those live in the Framework Engine,
  the Agents, and the domain Services (§13, §11, §14).
- **It is not a chat runtime.** Conversation is an interface onto missions, handled above,
  not a responsibility of the engine.

### 4. Relationship to the existing Platform — reuse, never reimplement

The Mission Engine sits **above** the existing AI Orchestrator and consumes the Platform
through its existing seams. It writes none of these afresh:

- **AI Orchestrator / pipeline (ADR 0038).** A mission step that needs a grounded answer
  invokes the existing pipeline (`UserRequest → Decision → Retrieval → Context → Prompt →
  Generation → Answer`) through the execution port. The pipeline stays the *per-step
  reasoning substrate*; the Mission Engine is the *multi-step governance layer* above it.
  (See the naming clarification in *Decision §12* — there are effectively two orchestration
  altitudes, and this ADR names them.)
- **Answer Validation (ADR 0039).** Runs *inside* the pipeline exactly as today, per step.
  The Mission Engine adds *gate* evaluation on top (a governance check), not a second answer
  validator. Low confidence or thin evidence in a step surfaces as a reason to gate, not a
  new validation engine.
- **Event Bus (ADR 0039).** The Mission Engine *publishes* mission lifecycle events onto the
  existing in-process bus; subscribers (audit sink, tracer, workspace stream) consume them.
  No new transport.
- **Audit (ADR 0015/0040).** Each step already produces an `AuditRecord`. The Mission
  Engine *links* those records under the mission and adds mission-level audit facts (plan
  versions, gate decisions with who/when). The `AuditRecord` shape is already tenant-stamped
  (ADR 0040 §6); the Mission Engine relies on that, it does not redefine it.
- **Pipeline Tracing (ADR 0039).** Step traces nest under a mission trace id; the mission
  becomes the top of the existing trace tree, not a parallel tracing system.

**Rule:** if implementing the Mission Engine requires editing the pipeline, the Event Bus,
the validator, the audit record, or the tracer, that is a design smell — the Mission Engine
consumes them through their ports and adds a layer, it does not reach inside them.

### 5. Relationship to Tools — where a Mission ends and a Tool begins

- **A Mission owns *what* and *why*; a Tool performs *one capability*.** The boundary: the
  Mission holds the goal, plan, lifecycle, gates, and audit narrative; a Tool is a single
  schema-validated capability with a declared side-effect profile (§9; ADR 0006).
- **A Mission never calls a Tool directly, and never imports the Tool Registry.** This is a
  deliberate decoupling. The Mission Engine dispatches a *step* to the **execution port**;
  the executor on the other side of that port (the Orchestrator / Agent Runtime, later
  phases) is what resolves the step to Tools via the **Tool Registry** and invokes them.
  Keeping the Registry out of the Mission entity keeps the Missions domain pure (§15) and
  lets the Tool Registry land in a later phase without touching the Mission model.
- **`TenantContext` flows Mission → step → Tool unchanged** (ADR 0040 §5). Every Tool
  invocation inside a mission carries the mission's tenant; a tool cannot widen it.
- **Consequential Tools are gated by the Mission, not by themselves.** A Tool *declares* it
  is consequential; the Mission Engine *enforces* the human gate before dispatching that
  step. The Tool never self-authorizes (§9; ADR 0006).

### 6. Relationship to Agents — who owns whom

- **A Mission owns an Agent; an Agent never owns a Mission.** This direction is fixed now
  and is non-negotiable. An Agent (Compliance, Risk, Audit, Policy, …; §11) is a *worker* a
  mission step is routed to. It executes *inside* a mission step, borrows the mission's
  `TenantContext`, acts *only through Tools*, and returns a result. It does not create,
  own, plan, or govern a mission.
- **Agents do not spawn missions; the Orchestrator does.** If work needs to branch into a
  sub-mission, the *plan* (Orchestrator custody) creates a sub-mission in the *same tenant*
  (ADR 0040 §5) — an agent cannot mint one out of band. This keeps the seat of control in
  the Orchestrator, never in an LLM-driven agent loop (§3, §7).
- **The Agent Runtime is a later phase and sits behind the execution port.** The Mission
  Engine does not know how agents are hosted, looped, or scoped; it hands a step to the
  executor and the Agent Runtime (Phase 16/17) is one implementation behind that port.

The inversion this forbids — *Mission running inside an Agent* — is exactly the failure mode
of "Agent-first" (see *Alternatives*): it would make an autonomous LLM loop the top-level
owner of tenant scope, side effects, and audit, which §3/§7 prohibit.

### 7. Mission lifecycle

The Mission Engine owns the state machine below. It refines the canonical lifecycle in
CLAUDE.md §8 / ADR 0003 without contradicting it; any state added here that is not already
in §8 is flagged in *Decision §12* as requiring a CLAUDE.md update on acceptance.

```
                         ┌─────────────┐
                         │   CREATED   │  tenant + owner + goal bound (immutable identity)
                         └──────┬──────┘
                                │ plan produced (Orchestrator) & stored (versioned)
                         ┌──────▼──────┐
                         │   PLANNED   │  plan is inspectable before any execution
                         └──────┬──────┘
                                │ begin execution
                         ┌──────▼──────┐   step is consequential →
                         │  EXECUTING  ├───────────────┐
                         └──┬───────┬──┘               │
             step ok, more │       │ all steps done    │
                  steps ───┘       │            ┌──────▼───────────┐
                                   │            │ AWAITING APPROVAL│  paused BEFORE the
                                   │            │   (human gate)   │  side effect; evidence
                                   │            └──┬───────────┬───┘  surfaced
                                   │      approved │           │ rejected / edited
                                   │        ┌──────▼─────┐     │
                                   │        │  RESUMED / │◄────┘  re-plan → new plan version,
                                   │        │  RE-PLANNED│        back to PLANNED/EXECUTING
                                   │        └──────┬─────┘
                                   │               │
                         ┌─────────▼───────────────▼──┐
                         │         COMPLETED          │  outputs + citations + decision
                         └────────────┬───────────────┘  trail finalized (immutable)
                                      │
       unrecoverable error / cancel   │           ┌──────────────────────┐
       ──────────────────────────────┼──────────►│  FAILED / CANCELLED   │  fail-safe: no
                                      │           └───────────┬──────────┘  partial
                                      │                       │             consequential
                                      │                       │             change left applied
                                      └───────────┬───────────┘
                                          ┌───────▼────────┐
                                          │    ARCHIVED    │  reconstructable for audit
                                          └────────────────┘  (retention/residency by tenant)
```

Each transition **emits a tenant-stamped domain event** (§8, next) and is **recorded for
audit**. Missions are **resumable, replayable, and idempotent**: a retried step must not
double-apply side effects, and a resumed/re-planned mission re-enters with the same
`TenantContext` it started with (ADR 0040 §5). Resumption after a gate **re-verifies the
approver belongs to the mission's tenant** — a gate approved by an outsider is not a gate.

### 8. Mission Context — what is stored, what is not

"Mission Context" is the durable, tenant-scoped state the mission carries (persisted via the
Mission Store port). The line between *store the fact* and *store a reference* is where audit
integrity and data-minimisation meet. **Persistence is universal (§11): the record below is
stored for every mission without exception — the `simple` one-step read included.**

| **Stored** (the mission's durable record) | **Never stored** (referenced, derived, or forbidden) |
|---|---|
| Mission identity, `tenant_id`, owner/principal, `region` | The tenant's secrets, credentials, API keys, provider keys |
| Goal, and the **versioned plan** (each re-plan a new version) | Raw LLM chain-of-thought / hidden reasoning (§19) — only the grounded plan and outputs |
| Ordered **step records**: which agent/tool, inputs (or **hashes** for sensitive data), outputs, latency/cost | Full copies of source documents — store **source IDs + sections** (RAG provenance, §12), not the corpus |
| **Citations, confidence**, and the retrieved **source IDs** per step | Any cross-tenant data — impossible by construction (ADR 0040) |
| **Gate decisions**: proposal, evidence reference, approver, timestamp, outcome | The model/provider internals beyond the logged version + prompt version |
| **Status**, lifecycle history, and the **event log** | Anything the auth boundary owns (raw identity tokens) — carry the resolved `TenantContext`, not the token |
| Model + **prompt version** references per step (reproducibility, §19) | Ephemeral working memory once a step is finalized (see below) |

**Working vs. durable memory (§7).** The Mission Engine distinguishes short-term *working
memory* (scratch state within a step) from durable *mission memory* (the record above).
Working memory is not part of the audit record and may be discarded once a step finalizes;
durable mission memory is tenant-scoped, append-oriented, and reconstructable. Both are
tenant-isolated; neither ever crosses a tenant.

### 9. Boundaries with the coming Product layers (none implemented yet)

All five are explicitly **not built**. This ADR fixes the *seam* to each so they can land in
later phases without reshaping the Mission model:

- **Tool Registry (coming).** Reached by the *executor* behind the execution port, **never
  by the Mission entity**. The Mission dispatches a step; the executor resolves it to Tools
  via the Registry. Fixing this now means the Registry can arrive in Phase 16 with zero
  change to the Mission aggregate.
- **Mission Store (coming).** The Mission Engine talks to a **Mission Store port** — a
  persistence seam mirroring the provider-port pattern of ADR 0038. The engine holds no
  schema, no SQL, no DB driver. The store implementation (Postgres, per ADR 0012) lands
  later behind that port.
- **Human Approval (coming).** Resolves the *Awaiting Approval* gate. The Mission Engine
  owns the **pause/resume authority and the lifecycle state**; Human Approval owns the
  *decision surface and routing*. The gate is evaluated **before** a consequential step, and
  resumption re-verifies the approver's tenant (§7; ADR 0040 §5).
- **Agent Runtime (coming).** One implementation behind the execution port. It hosts, loops,
  and scopes agents; the Mission Engine does not know how. An agent it runs borrows the
  mission's `TenantContext` and acts only through Tools (§6).
- **Framework Engine (coming).** Not called by the Mission Engine at all. Frameworks are
  data (§13; ADR 0007) consumed by Agents and Tools *inside* steps. The Mission Engine is
  framework-blind — no framework name ever appears in it (§13 hard rule).

### 10. Dependency graph (proposed)

Arrows = "depends on". The Mission Engine depends **downward** on the shared contracts, the
Mission Store port, the Event Bus, and the execution port — and on **nothing** in the
not-yet-built Product layers directly. Those arrive *behind ports*, so the graph does not
change shape when they do.

```
   ┌──────────────────────────────────────────────────────────────────────┐
   │                          INTERFACES (UI · API · Chat)                  │
   │                     open / steer / inspect missions                    │
   └───────────────────────────────────┬────────────────────────────────────┘
                                        │
                              ┌─────────▼──────────┐
                              │   MISSION ENGINE   │  goal · plan (versioned) · lifecycle ·
                              │  (Phase 15, this)  │  gates · idempotency · event emission
                              └───┬───────┬────┬───┘
             depends on           │       │    │            depends on (ports only)
        ┌──────────────────┐      │       │    │      ┌───────────────────────────────┐
        │ pipeline-        │◄─────┘       │    └─────►│  execution port               │
        │ contracts        │              │          │  (Orchestrator / Agent Runtime │
        │ (pure, ADR 0038) │              │          │   resolve → Tool Registry)     │
        └──────────────────┘              │          └───────────────┬───────────────┘
        ┌──────────────────┐              │                          │  (coming: Phase 16/17)
        │ Event Bus (0039) │◄─────────────┤                          ▼
        └──────────────────┘              │          ┌───────────────────────────────┐
        ┌──────────────────┐              │          │ AI ORCHESTRATOR / PIPELINE     │
        │ Mission Store    │◄─────────────┘          │ (existing, ADR 0038/0039):     │
        │ PORT (coming)    │                         │ Decision→Retrieval→Context→    │
        └──────────────────┘                         │ Prompt→Generation→Validation   │
                                                      └───────────────┬───────────────┘
                                                                      ▼
                                              Answer + PipelineResult + AuditRecord + trace
                                                   (composed into the mission's narrative)
```

Two invariants the graph encodes: (1) **the Mission Engine never imports the Tool Registry,
the Agent Runtime, or a Mission Store implementation** — only ports and pure contracts; (2)
**the arrow to the pipeline goes through the execution port**, so the mission layer and the
per-step pipeline stay independently testable and swappable.

### 11. The decision that must be locked now — **Everything is a Mission** (one aggregate, one execution profile)

Making *every* interaction a full Mission raises an honest objection: wrapping a trivial
grounded question ("what does NCA ECC say about MFA?") in planning, lifecycle, gates, and
persistence it does not need. An earlier draft answered this with a **two-lane model** — a
Query lane beside a Mission lane, with *promotion* between them. **That answer is withdrawn.**
Two lanes invite two code paths, two mental models, and a "a query is not really a mission"
drift — precisely what the mission-centric pillar forbids. It is replaced by a single,
stricter rule.

**Decision — there is one executable unit, and one only: the Mission.**

- **There is no Query, Workflow, Session, or Job as an independent executable behaviour.**
  Even the simplest question is a Mission from birth. It is never *promoted* into one, because
  it was never anything else — there is no `Query → Mission` transition and no promotion event
  anywhere in the system.
- **`simple` and `composite` are not types, not tables, not stores, not execution paths.**
  They are the *same* Aggregate. The only thing that differs is the **plan** and the
  **`execution_profile`** — an attribute of the mission, never a fork in the model.

`execution_profile ∈ {simple, composite}`:

| | `simple` | `composite` |
|---|---|---|
| Plan | exactly one step | many steps |
| Steps | one Pipeline-Tool step | several tools / agents |
| Human gates | none | as the plan requires |
| Lifecycle driven | `CREATED → PLANNED → EXECUTING → COMPLETED` | full lifecycle incl. `AWAITING APPROVAL` |
| `TenantContext` | bound at creation | identical |
| Audit / events | same shape: `mission_id` + `tenant_id` | identical |
| Persistence | **stored — no exception** | **stored — no exception** |

**What replaces "promotion".** If a `simple` mission discovers mid-flight that it needs a
second step or a human gate, it does not change type — it **re-plans** (RESUMED / RE-PLANNED,
§7): a new plan version adds steps to the *same* aggregate, and `execution_profile` is
re-derived from the new plan. The rise in ceremony is a re-plan, never a type change and never
a migration between stores.

**Persistence is universal (locked).** Every Mission is stored — from the one-step read to the
largest composite engagement. There is **no "skip persistence for trivial reads" exception**
in the Mission Engine. Display, retention, deletion, and archival are **policies applied above
the store in a later phase**, never conditional branches inside the engine. The engine's rule
is unconditional: *a mission exists ⇒ a mission is stored.*

**The cost, accepted with eyes open.** Universal persistence means a store write on the path of
every interaction, trivial reads included — the very tax the withdrawn two-lane model tried to
avoid. We take it deliberately: in a regulated domain, "every mission is a durable, auditable
object" is worth more than a saved write on a read, and conditional persistence is exactly the
special case that rots. `execution_profile=simple` keeps the *ceremony* cheap (no planning LLM
call, no gate, a single step); it buys **no** escape from persistence, tenancy, or audit.

### 12. Other decisions to lock now (to avoid a Phase 16/17 redesign)

Beyond *Everything is a Mission* (§11), these calls are locked now; deferring any one forces a
redesign later. They are the acceptance decisions of this ADR (see *Amendment*).

1. **`TenantContext` is bound at mission creation — in the very first package.** Per ADR 0040
   §5, a mission binds `tenant_id` from the `TenantContext` handed to it at birth, immutable for
   life. This is not a later-phase feature: the smallest Mission Engine already requires a
   `TenantContext` and refuses to create a tenant-less mission. The engine *binds and preserves*
   it; it never derives, widens, or infers it (§3 Non-Goals; ADR 0040 §3).
2. **`mission_id` enters the shared contracts alongside `tenant_id`, in the same change.**
   `AuditRecord` and every `DomainEvent` gain a required `mission_id` from their first
   tenant-aware version — not retrofitted after the Mission Store lands. The argument is
   ADR 0040's own: a record retrofitted with its owner later cannot vouch for the runs written
   before it. Because *everything is a mission* (§11), every audit record and every event is
   produced inside a mission, so a `mission_id` is always available to stamp. From the moment
   the Pipeline Tool lands (Phase 15, step 3), every run carries one.
3. **Two ports are defined in the first package: `ExecutionPort` and `MissionStorePort`.** The
   Mission Engine reaches *all* step execution through the `ExecutionPort` and *all* persistence
   through the `MissionStorePort`, from day one. The first package ships trivial adapters behind
   both — an in-memory store and a no-op / echo executor — and later phases swap the adapters
   (the Pipeline-Tool executor at step 3; the Postgres store at step 4, ADR 0012) with **zero
   change to the Mission aggregate**. Letting the engine call a tool, an agent, or a database
   "directly, just for now" is forbidden: it couples the Missions domain to infrastructure and
   is paid for three phases running.
4. **The full lifecycle is implemented; only the happy path is exercised first.** The state
   machine of §7 is built complete — every state and legal transition, including `AWAITING
   APPROVAL` and the pause/resume authority — in the first package. That package only *drives*
   the happy path `CREATED → PLANNED → EXECUTING → COMPLETED`; the gate stays un-triggered until
   Human Approval (a later phase) supplies the decision surface. We do **not** ship a reduced
   three-state machine and grow it later.
5. **Human gate is a lifecycle state, not a tool call.** Durable pause/resume with fail-safe
   semantics must live in the Mission lifecycle. If approval were "just another tool," we would
   lose durable pause and the fail-safe guarantee the moment side-effectful Tools land. Lock it
   as a state now (built per §12.4, resolved by Human Approval later).
6. **The plan is a persisted, versioned, first-class artifact — not LLM text.** Even a `simple`
   mission has a plan of exactly one step. Re-planning creates a new plan version on the same
   mission. Fixing this now shapes the Mission Store schema; discovering it later means migrating
   stored missions.
7. **Idempotency and stable ids are part of the Mission Store contract.** Stable mission id,
   stable step id, per-tenant idempotency key (ADR 0040 §5). These shape persistence; decide
   before the store exists.
8. **Two orchestration altitudes, one vocabulary fix.** The existing `ai-orchestrator`
   (ADR 0038) is really the **pipeline runner** (one grounded run). The §7 "Orchestrator is the
   brain" role — planning, routing, lifecycle, gates — is realized by the **Mission Engine above
   it**. Calling both "orchestrator" will confuse every future reader. **Recommendation:** keep
   the package names, but adopt the vocabulary "**Mission Orchestration** (mission layer) over
   **Pipeline Execution** (per-step)" in CLAUDE.md, and record that §7's "brain" spans the
   planning step + Mission Engine, not the pipeline runner. A CLAUDE.md clarification, not a
   rename.

If review disagrees with any of these, that is the moment to change them — the entire reason
this ADR is written before the first package.

---

## Consequences

**Positive**

- The top-level unit of work is settled *before* Tools, Agents, Human Approval, and the
  Mission Store exist to retrofit it into — the cheapest moment, and the last cheap one
  (the same argument ADR 0040 made for tenancy).
- Mission-centricity is adopted with eyes open: chosen because it is the only concept at the
  governance altitude, not because §3 said so — and adopted in its strongest form (*Everything
  is a Mission*, §11), with a cheap `simple` execution profile keeping trivial reads light on
  ceremony while every mission still carries one uniform tenancy, audit, and persistence shape.
- The boundaries are drawn so each coming layer (Tool Registry, Mission Store, Human
  Approval, Agent Runtime, Framework Engine) arrives **behind a port** with no change to the
  Mission model. Phases 16 and 17 extend; they do not redesign.
- The Platform is reused, not reimplemented: one pipeline, one event bus, one validator, one
  audit shape, one tracer — the Mission Engine is a governance layer above them.
- Reviewers get a concrete boundary to reject scope creep against (the Non-Goals in §3 and
  the "never imports the Registry / never persists itself" rules).

**Negative / costs**

- More upfront modeling than a chat loop or a bare pipeline: a lifecycle, versioned plans,
  gate custody, resume/replay semantics, and a Mission Store port — before any of it runs.
- Universal persistence has a real cost: a store write on the path of every interaction,
  trivial reads included — the tax the withdrawn two-lane model tried to dodge. Accepted
  deliberately (§11): one uniform "every mission is a durable, auditable object" beats a
  conditional-persistence special case that would rot. `execution_profile` keeps ceremony, not
  persistence, cheap.
- Two orchestration altitudes are a real cognitive cost; the §12.1 vocabulary fix mitigates
  but does not erase it.
- The Mission model is fixed here while the layers it depends on (execution port, Mission
  Store, Human Approval) are still just ports — if a coming phase discovers a port is the
  wrong shape, this ADR is superseded, not amended (ADR process, README).

---

## Alternatives considered

The heart of this ADR. Each option is weighed as a candidate for the **top-level unit of
work**, with the concrete failure that elevating it produces.

- **Chat-first** (the unit is a conversation turn; state is ephemeral). *Pros:* simplest,
  lowest latency to first token, familiar, cheap. *Cons / failure:* no durable plan, no
  lifecycle, no human gates as a first-class concept, and an audit trail that cannot be
  reconstructed across steps — a transcript is not a decision record. In a regulated domain a
  consequential action taken "in a chat" has no envelope an auditor can replay. **Rejected**
  — already rejected in ADR 0003 and CLAUDE.md §3/§18; re-confirmed here. Chat survives as an
  *interface onto missions*, not as the unit of work.

- **Workflow-first** (the unit is a durable, authored workflow graph; e.g. Temporal). *Pros:*
  excellent durability, retries, deterministic replay; mature engines; strong for
  long-running side-effectful processes. *Cons / failure:* a workflow is an *authored,
  largely predefined* structure, while GRC missions are frequently *emergent* — the plan is
  decided at runtime by the Orchestrator (with LLM suggestion), and re-planning is the norm,
  not the exception. Forcing every mission into a predefined graph makes adaptivity and
  re-planning awkward, and a raw workflow has no native notion of goal, grounding, citations,
  confidence, or judgement-gates — only steps and human *tasks*. **Rejected as the top-level
  unit** — but *retained as the substrate*: a Mission is *executed via* a durable
  workflow/job engine (§5 of CLAUDE.md). Workflow is the *how*, Mission is the *what*.
  Elevating the substrate to the concept would bury governance under execution mechanics.

- **Tool-first** (everything composes from Tool invocations; the system is a tool-calling
  loop). *Pros:* real, and a genuine pillar (§9/§10; ADR 0006) — composability, testability,
  the six-callers property, clean capability boundaries. *Cons / failure:* a Tool is
  stateless and single-shot. It has no goal, no memory across calls, no lifecycle, and no
  approval *spanning* steps. Tool-first gives capabilities but no *envelope*: nothing owns
  the plan across three tool calls, nothing holds a gate that spans them, and there is no
  single object an auditor replays as an *outcome*. A Tool is the *verb*; you still need a
  *noun* that owns a sequence of verbs toward a goal. **Rejected as the top-level unit** —
  Tools stay the universal unit of *capability* *inside* missions.

- **Agent-first** (everything is an autonomous agent; agents talk to agents). *Pros:*
  flexible, emergent, powerful for open-ended tasks. *Cons / failure:* making *the agent* the
  top-level governed unit puts the seat of control inside a non-deterministic LLM loop — a
  direct violation of CLAUDE.md §3/§7 ("the Orchestrator is the brain, not the LLM"). An
  agent-first system is hard to audit (the plan lives in the model's head, not as data), hard
  to gate (where do you pause a loop?), and hard to make idempotent/replayable. In a
  multi-tenant, regulated setting you cannot let an autonomous agent be the top-level owner of
  tenant scope and side effects. **Rejected as the top-level unit** — Agents are *workers
  inside* mission steps, governed by the Orchestrator, acting only through Tools (§6, §11).
  This is the inversion §6 explicitly forbids.

- **Mission-first** (the unit is a governed, goal-directed, auditable, resumable envelope
  that *uses* agents and tools, *executes via* the workflow substrate, and *is* the audit
  object). *Pros:* it is the only concept at the *governance* altitude — it owns goal + plan
  + lifecycle + human gates + audit narrative + tenant scope while delegating reasoning to
  agents, capability to tools, and durability to the workflow engine. It matches the domain:
  GRC work *is* mission-shaped — bounded, goal-directed, consequential, needing sign-off and
  a reconstructable record. *Cons:* heavier upfront modeling; a real risk of over-ceremony on
  trivial reads (answered by the cheap `simple` execution profile, §11); and the burden of drawing the
  Mission/Workflow, Mission/Agent, Mission/Tool boundaries precisely (this ADR §5, §6, §10).
  **Accepted** — not as a rubber stamp of §3, but because the other four each fail at the top
  when named concretely, and because Mission is the only one that *composes* them rather than
  *competing* with them.

- **Hybrid "no top-level unit" (Query-only, add missions ad hoc later).** Considered because
  today's platform is Query-only and works. *Rejected:* deferring the mission model is the
  retrofit path ADR 0040 warned against — Tools, Agents, and Human Approval each assume an
  envelope; building them against an undecided one guarantees inconsistent answers and a later
  migration. *Everything is a Mission* (§11) keeps the simple path cheap in ceremony *and*
  fixes the envelope now.

---

## Amendment — 2026-07-16: acceptance decisions (Product Owner)

This ADR is **Accepted** with the following six decisions locked, which this revision
incorporates in place. They are the binding contract the first Phase 15 package is built
against; changing any one requires a new ADR that supersedes this.

1. **Everything is a Mission — one aggregate, one `execution_profile`.** The concepts *Query
   Lane*, *Mission Lane*, and *promotion* are **removed** (they were in an earlier draft of
   §11). There is no Query, Workflow, Session, or Job as an independent executable unit. A
   `simple` and a `composite` mission are the *same* aggregate differing only in plan and
   `execution_profile`; a mission never changes type — added scope is a **re-plan** (§11).
2. **A Mission binds `TenantContext` at creation, from the first package** — never tenant-less,
   never derived, immutable for life (§12.1; ADR 0040 §5).
3. **`mission_id` is a required field on `AuditRecord` and every `DomainEvent` from their first
   version**, added in the same change as `tenant_id` — not retrofitted after the Mission Store
   (§12.2).
4. **`ExecutionPort` and `MissionStorePort` are defined in the first package**, behind trivial
   adapters (in-memory store, no-op executor); later phases swap adapters with zero change to
   the Mission aggregate (§12.3).
5. **The full lifecycle (§7) is implemented; only the happy path
   `CREATED → PLANNED → EXECUTING → COMPLETED` is exercised first.** `AWAITING APPROVAL` and the
   pause/resume authority exist from day one but stay un-triggered until Human Approval lands
   (§12.4–12.5). No reduced three-state machine.
6. **Every Mission is persisted — no exception.** Display, retention, deletion, and archival are
   policies applied *above* the store in a later phase, never conditional branches inside the
   Mission Engine. *A mission exists ⇒ a mission is stored* (§11).

**Next action (locked):** build the first Phase 15 package — the **Mission Engine** — and
nothing else. The Tool Registry, Agent Runtime, and Human Approval are built *on top of* it in
later steps and are explicitly out of scope for the first package.
