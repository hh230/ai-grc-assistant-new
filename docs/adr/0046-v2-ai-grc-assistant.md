# ADR 0046: Rasheed V2 — the AI GRC Assistant (the application/product layer; the gateway that turns requests into Missions)

- Status: **Accepted — architecture** (the four open decisions were ruled and the **Capability
  Catalog** added on 2026-07-17; implementation begins at Slice 2. This ADR itself writes no code.)
- Date: 2026-07-17
- Deciders: Product Owner (review pending), Architecture
- Related: CLAUDE.md §3 (mission-centric), §5 (architecture overview — the Interfaces layer), §7 (the
  Orchestrator decides, the LLM suggests), §8 (mission lifecycle), §18 (Workspace-first UX), §19
  (transparency/audit), §20 (tenancy); **ADR 0042 (Mission Engine — *everything is a Mission*)**,
  0043 (Mission Store), 0044 (Human Approval), 0039 (Event Bus + audit), 0040 (tenancy); the frozen
  `mission-integration` **`MissionRuntime`** facade; [V2 Roadmap](../../v2/docs/ROADMAP.md)

---

## Context

The **V2 Core is frozen** (Platform pipeline + Mission Engine + Mission Store Slices 1–4 +
Integration Runtime + Human Approval Slices 1–3; see the [Roadmap](../../v2/docs/ROADMAP.md)). The
next step is **not** to add features *inside* the Core, but to build **applications that consume it
exactly as any client would** — through the frozen `MissionRuntime` facade.

The **AI GRC Assistant** is the first such application, and it is special: it is the **primary
human-facing gateway** through which a user's request becomes the *right* Mission. Its strategic
value is that, once it exists, **the other GRC "applications" are not separate stacks — they are
Mission types in its catalog**:

```
"assess this vendor"    → Assistant → MissionRuntime → VendorRiskAssessmentMission
"run an ISO 27001 gap"  → Assistant → MissionRuntime → ISOGapAnalysisMission
"draft a password policy" → Assistant → MissionRuntime → PolicyGenerationMission
```

This ADR designs that application's architecture **before any code**, by the same method the Core
used (ADR → review → very small slices → tests → review → freeze). It decides the Assistant's
boundaries, its relationship to `MissionRuntime`, and its core models (Capability Catalog, Mission Catalog, Session,
Conversation, `AssistantRuntime`). It writes no code.

### What is a frozen input (not decided here)

The Assistant is a **consumer** of the frozen Core. From `mission-integration`, the
**`MissionRuntime`** facade is fixed and this ADR builds strictly on it:

```python
run_transition(apply)   # drive one engine transition (create / plan / execute / …) in one txn
relay(limit=…)          # drain the outbox onto the Delivery Bus → Audit Sink
load(mission_id, tenant) # reload a mission from the durable store
approve(mission_id, approver, comment=…)      # human gate: approve  → RESUMED
reject(mission_id, approver, comment=…)        # human gate: reject   → CANCELLED
resume_if_approved(mission_id, tenant)         # detect+reload+re-enter → continue
.audit                  # the delivered mission-event stream
.delivery_bus           # the EventBus the relay publishes onto
```

The Assistant **does not change** any of this, nor the Mission Engine, Store, Event Bus, or the
lifecycle. If a design point below appears to require touching the frozen Core, that is a signal to
stop and raise a Core ADR — noted where it arises.

---

## Architectural assumptions

1. **The Assistant is the *product* layer, not the AI.** The reasoning/RAG/generation pipeline is the
   frozen Platform, reached **behind the `ExecutionPort`** as a mission step runs. The Assistant never
   calls an LLM or a tool directly; it turns requests into Missions and lets the Core execute them.
2. **Everything a user asks for becomes a Mission** (ADR 0042 §11). Even a trivial question is a
   `simple` mission (`run_simple`); a complex request is a `composite` mission with a gated plan. The
   Assistant never has a "chat path" that bypasses Missions — chat is *an interface onto Missions*.
3. **The Mission is the durable, auditable unit; the Session/Conversation are the interaction layer.**
   Missions live in the Mission Store with full audit (ADR 0043/0039). The Assistant's own
   Session/Conversation state is UX bookkeeping that *references* missions — it is never a second,
   parallel record of what happened.
4. **`TenantContext` is minted upstream (auth) and threaded through** every Assistant call into every
   Mission (ADR 0040). The Assistant binds and preserves tenant; it never derives or widens it.
5. **The Assistant is executor-agnostic.** Which `ExecutionPort` backs the missions (today the
   reference `EchoExecutor`; later the Pipeline-Tool executor + Tool Registry) is injected. Building
   that real executor is a **Core/Platform** concern (its own ADR), **not** part of the Assistant.

---

## Decision

### 1. What the AI GRC Assistant *is* — and is not

The Assistant is a **product-layer application that sits above the frozen Core as its client**, in
the **Interfaces** position of CLAUDE.md §5. Its responsibilities, and only these:

1. **Be the gateway.** Accept a user's natural-language request (within a tenant/session) and turn it
   into the *right* Mission.
2. **Own the Capability & Mission Catalogs.** Know which *capabilities* the product offers (the
   user's terms) and how each resolves to Mission *types* and their plans (§4).
3. **Own Session & Conversation.** Manage the multi-turn interaction that opens and steers Missions
   (§5–§6).
4. **Drive Missions through `MissionRuntime`** — create/plan/execute, surface the human gate, resume
   after approval — never reimplementing any of it (§7–§8).
5. **Present progress, results, and audit** back to the user by consuming the Delivery Bus / audit
   stream (§9).

**It does NOT:**
- reason, retrieve, generate, or call an LLM/tool (that is the Platform, behind `ExecutionPort`);
- persist Missions, emit Mission events, or run the outbox/relay (that is the Core);
- drive the Mission lifecycle or approval logic (the aggregate/engine do);
- resolve tenancy (auth does);
- expose HTTP/REST/UI itself — those are **thin delivery adapters** *above* the Assistant runtime, a
  separate app concern (§10).

### 2. Relationship to the frozen Core — a strict consumer

- The Assistant **depends on** `mission-integration` (the `MissionRuntime` facade),
  `mission-engine` (the `Plan` / `PlanStep` / `Mission` / `TenantContext` types it composes), and
  `pipeline-contracts` — all **frozen, consumed, never changed**.
- Every unit of work goes **through `MissionRuntime`**. The Assistant holds a `MissionRuntime` and
  calls `run_transition` / `approve` / `resume_if_approved` / `relay` / `load` — it adds the
  conversation/session/catalog layer **above** it, adding zero capability to the Core.
- **No new Core ports.** Anything the Assistant needs beyond `MissionRuntime` is built **in the
  Assistant layer**, not by extending a frozen Core interface.

### 3. Everything is a Mission — the Assistant never bypasses the Core

Every request that requires work becomes a Mission via the Catalog (§4). A greeting or a one-shot
question → a `simple` mission; "assess this vendor" → a `composite` mission with a gated plan. This
is the ADR 0042 pillar realized at the product layer: the Assistant is **mission-driven, not
chat-driven** — the conversation is one interface onto missions, exactly as ADR 0003 intended.

### 4. The Capability Catalog → the Mission Catalog — two layers between the user and `MissionRuntime`

*(Ruling 2026-07-17: the review added the **Capability Catalog** as a first-class layer above the
Mission Catalog. This is the most important structural decision in the application.)*

Users think in **capabilities** ("review this vendor", "generate a policy"), **not** in Missions. The
Assistant therefore resolves a request through **two registries**, coarse-to-fine, so the product's
vocabulary and its execution units stay separable and can evolve independently:

```
User request
   ↓  Intent Understanding (LLM — suggests, never decides)
Capability  (+ confidence + extracted inputs)
   ↓  Capability Selector (deterministic — validates against the Capability Catalog)
Capability Catalog  ──resolves to──▶  Mission type(s)
   ↓  Mission Catalog (plan factory)
Plan(s) + inputs
   ↓
MissionRuntime  (the frozen Core)
```

**The Capability Catalog** is the *product-facing* registry — **what the Assistant can do, in the
user's terms**. Each entry:
- a **stable capability name** (`vendor_review`, `policy_generator`, `iso_gap`, `risk_assessment`,
  and `ask` — the always-present fallback);
- a **product description** and an **input schema** (what the capability needs);
- a **resolution to one *or more* Mission types.** *Today a capability resolves to exactly one Mission
  type; the plural is deliberate.* A future capability may **orchestrate several Missions** — e.g.
  `vendor_review` → `VendorEvidenceMission` → `VendorAssessmentMission` → `VendorApprovalMission`, or
  `policy_generator` → `GeneratePolicyMission` → `ReviewPolicyMission` → `PublishPolicyMission`. The
  catalog is shaped so that growth is **adding a resolution**, never breaking the design.

**The Mission Catalog** is the *execution* registry — **how each Mission type is built**. Each entry
is a Mission *type* = a **plan factory** `(inputs, tenant) → (goal, Plan)` + input schema, reusing the
frozen `mission-engine` plan types. A mission type is exactly "a named way to build a `Plan`"
(ADR 0042 §11): missions differ by their **plan** (and derived `execution_profile`), not by a
separate class, store, or execution path. Example: the `vendor_risk_assessment` mission type →
goal "assess vendor X", plan `[collect_evidence, analyze, score, (consequential) approve_report,
generate_report]`.

**Why two layers, not one.** The user's mental model (capabilities) and the executable unit
(missions) change at different rates and for different reasons. Collapsing them would force either
(a) the user to think in Missions, or (b) a capability to be permanently 1:1 with a single Mission —
which breaks the day we orchestrate several Missions behind one capability. **`Capability →
Mission(s)` is the seam where future multi-Mission orchestration lands with no redesign** — the whole
reason the layer is introduced now, while it is cheap.

#### Selection is two-layer: the LLM *suggests*, a deterministic selector *decides*

Mapping free text to a capability is split so the LLM never has authority to run work (CLAUDE.md §7):

1. **Intent Understanding (LLM).** Produces a **suggestion**, not an action: a capability *intent*, a
   *confidence*, and *extracted inputs* — e.g. `{ intent: "vendor_review", confidence: 0.92, inputs:
   { vendor: "…" } }`. It **never** says "run `VendorAssessmentMission`"; it says "this looks like
   `vendor_review`".
2. **Capability Selector (deterministic).** Validates that suggestion against the **Capability
   Catalog** and the required inputs, and **decides**: pick the matching registered capability, or —
   on no match / low confidence / missing inputs — fall back to the **`ask`** capability (a
   `simple_question` Mission). A **consequential** capability is *never* entered on a bare LLM guess.

This is the ADR 0042 pillar ("the LLM suggests; the platform decides and validates") applied to
product routing, and it is the Assistant's **anti-hallucination guarantee**: the LLM can influence
*which registered capability* is chosen — it can neither invent a capability nor trigger execution.

**Extensibility (the strategic payoff):** a "new GRC application" is, in order of preference, **(a) a
new Capability that resolves to existing Mission types**, or **(b) a new Mission type in the Mission
Catalog**, or both — no new app, no Core change (CLAUDE.md §17 plugin model).

### 5. Session Model — the tenant-scoped interaction container

A **Session** is **user identity + tenant + session settings** (ruling 1) — the authenticated working
context. It is the boundary that:

- **binds tenant/principal once** and threads it into every Mission (assumption 4);
- **holds session settings** (preferences/locale/etc.) and **groups the Conversations** the user
  conducts;
- is **lightweight**: it references durable Missions (Mission Store) — it is **not** a second store
  of mission truth.

### 6. Conversation Model — an interface onto Missions, not a parallel record

A **Conversation** is a **turn log** (ruling 1) — a multi-turn exchange within a Session. Each **turn**
may **open** a new Mission or **steer** an existing one (approve a gate, add context, ask a
follow-up). A Conversation therefore:

- **links turns to Missions** — a turn records the user utterance and the `mission_id` it produced or
  acted on, and nothing more;
- **carries NO Mission state.** This is a hard rule (ruling 1): the durable, auditable "what happened"
  is the **Mission** + its event/audit trail (ADR 0019/0039), never the Conversation. The forbidden
  shape is `Conversation → Mission State`; the required shape is `Session → Conversation →
  Mission(s)`. The Conversation says *"the user asked X, which became mission M"*; only the Mission
  says *what M did* and *where M is*. If the two could ever disagree, the Conversation is not allowed
  to hold the answer.
- **surfaces the human gate**: when a Mission pauses at `AWAITING_APPROVAL`, the Conversation presents
  the pending approval (read from the Mission, not stored on the turn) and the next user turn
  (approve/reject) resolves it via `MissionRuntime` (§8).

This keeps chat as *one interface onto missions* (ADR 0003) and structurally prevents a parallel,
drift-prone copy of mission state in the transcript.

### 7. The `AssistantRuntime` interface — the product-layer composition root

`AssistantRuntime` is to the product layer what `MissionRuntime` is to the Core: the **composition
root** that wires the Catalog + Session/Conversation + `MissionRuntime` and exposes a small surface.
Its shape (decided as an interface here; implemented in later slices):

- **`handle(session, request) → AssistantResponse`** — the main entry: resolve the request to a
  **Capability** (LLM intent → deterministic selector, §4), resolve that Capability to its Mission
  type(s), build the `Plan`(s), drive through `MissionRuntime.run_transition(...)`, and return a
  response that is either a **result** (mission completed) or a **pending gate** (mission awaiting
  approval), plus the `mission_id` and a progress handle.
- **`resolve(session, mission_id, decision) → AssistantResponse`** — apply a human decision to a
  paused mission: `MissionRuntime.approve/reject`, then `resume_if_approved` to continue, streaming
  the continuation. (This is the conversation-level realization of Human Approval, Slice 3.)
- **`progress(session, mission_id) → …`** — the delivered event stream for a mission (§9).

`AssistantRuntime` holds **no** mission logic and **no** SQL — it is assembly + request→mission
mapping, exactly as `MissionRuntime` is assembly + transaction wiring. It is executor-agnostic
(assumption 5): the `MissionRuntime` (and thus the `ExecutionPort`) is injected.

### 8. Human approval, in the conversation

The Core already provides the whole mechanism (ADR 0044). The Assistant only **surfaces and relays**:
a mission pauses → the Conversation shows the pending `ApprovalRequest` (its reason) → the user's
approve/reject turn calls `MissionRuntime.approve` / `reject` → `resume_if_approved` continues the
mission → the Assistant streams the continuation and final result. No approval logic is added; the
Assistant is the human's window onto the frozen gate.

### 9. Progress, results, and audit — consume the Delivery Bus, don't rebuild it

Missions already emit their lifecycle onto the outbox → relay → **Delivery Bus** → **Audit Sink**
(ADR 0043-S4). The Assistant **subscribes a presenter** to the Delivery Bus (or reads the audit
stream) to stream progress (`mission.step_completed`, `mission.awaiting_approval`, …) and to render
final results and the decision trail to the user (CLAUDE.md §18/§19). It builds **no** new audit
model — it *presents* the mission event stream the Core already produces. (The mission-shaped
`MissionAuditSink` is the Core's; a durable/queryable audit projection remains a deferred, ADR-less
Core concern per the Roadmap.)

### 10. Package shape & boundaries

- The **`AssistantRuntime` and its models are a runtime *package*** (framework-free, testable, pure
  where possible), following the Core's package discipline (`mission-integration` is a package, not an
  app). Proposed home: `v2/packages/assistant-runtime` (name for review).
- **HTTP/REST/Workspace-UI are separate delivery adapters** *above* the runtime (an `app`), out of
  scope for this ADR — the runtime is driven the same way from an API handler, a UI server action, a
  CLI, or a test, exactly as Tools/Missions are (CLAUDE.md §5, §9 "the six callers"). This preserves
  the logic-vs-delivery split the Core kept (packages vs apps).

---

## Slice plan (very small, end-to-end, frozen before the next — the Core method)

> **Reorder ruling (2026-07-17).** The review moved **Conversation Runtime *after* the first real
> Capability**. Rationale: a conversation layer must know *what actually happens* on mission success,
> on a simple question, on an approval, and across several capabilities. Building it before we have
> **one real capability running end to end** risks designing on assumptions and redesigning after the
> first real use. So we build the **first Capability (Simple Question)** first, prove the full loop
> `User → AssistantRuntime → Capability → Mission → MissionRuntime → Response`, then build the
> Conversation Runtime on that real usage. Simple Question is chosen first because it needs **no
> tools, no complex plan, no human approval, no multiple Missions** — it is the smallest thing that
> proves the runtime works front to back.

| Slice | Scope | Delivers |
|---|---|---|
| **1 — Assistant Architecture** ⭐ | **Architecture only.** Boundaries, relationship to `MissionRuntime`, and the Capability/Mission Catalog, Session, Conversation, `AssistantRuntime` models. | This ADR (Accepted). **No code.** |
| **2 — Capability & Mission Catalog** | Both registries + the two-layer selection (`Intent (LLM suggests) → Selector (deterministic decides)`); build the `Plan` and drive it via `MissionRuntime`. **Mechanism only** — demo capabilities live in tests. | Request → Capability → the right Mission, driven via `MissionRuntime`. |
| **3 — First Capability (Simple Question)** | Ship the **first real, built-in capability** — the **AI GRC Assistant** capability resolving to a **Simple Question** Mission (single read-only step; no tools, no gate, no multi-Mission) — and prove the whole loop end to end against the real `MissionRuntime`. | The runtime demonstrably works front to back on one capability. |
| **4 — Conversation Runtime** | Session + Conversation (turn log; `Session → Conversation → Mission(s)`); link a turn to its Mission; track progress; **resume after Human Approval** — built on the *observed* behaviour of Slice 3. | A multi-turn, gate-aware conversation over Missions. |
| **5 — Response Layer** | Stream progress from the Delivery Bus; present events, final results, and the decision trail; tie audit to the user. | Observable, explainable missions in the UX. |
| **6 — Integrations** (later) | Connect Missions to real capability — the real `ExecutionPort` / Tool Registry, files, DBs, email, SharePoint — a Core/Platform build the Assistant *composes*. | Missions that do real GRC work. |

After the first capability proves the loop, GRC capabilities (Risk Assessment, Vendor Review, Policy
Generation, …) are added **one at a time on the tested foundation** — each a new Capability + Mission
type in the catalogs, not new plumbing.

---

## Design challenge (challenged before acceptance)

1. **"Isn't the Assistant just the AI Orchestrator by another name?"** No. The Orchestrator (Platform)
   plans and runs *within* a mission step, behind `ExecutionPort`; the Assistant is *above* missions —
   it decides *which mission* a request is and manages the human conversation around it. Different
   layer, different job. Conflating them would pull pipeline concerns into the product layer.
2. **"Everything-is-a-mission will make a 'hello' expensive."** A trivial request is a `simple`
   mission (`run_simple`) — one read-only step, already the cheapest path the Core has (ADR 0042 §11).
   The uniformity (one governed, audited path) is worth more than a bypass that would create an
   unaudited side-channel in a regulated product.
3. **"Conversation vs Mission will duplicate state."** Explicitly prevented (§6): the Conversation is
   a thin turn→mission log; the Mission is the durable audit record. If they ever drift, the Mission
   wins.
4. **"Selecting a mission with an LLM is non-deterministic and risky for consequential work."**
   Mitigated (§4): the LLM only *suggests*; the Catalog validates against a registered type + required
   inputs, and defaults to `simple_question` on low confidence — a consequential mission is never
   entered on a guess.
5. **"Why a package, not just an app?"** Same reason the Core split logic (packages) from delivery
   (apps): the product logic must be testable via its six callers without HTTP/UI. The app is a thin
   adapter over the package.

---

## Resolved decisions (review ruling, 2026-07-17)

All four open decisions were ruled by the Product Owner; they are now **binding** for the slices.

1. **Session / Conversation persistence — ruled.** Strict hierarchy, no state duplication:
   **`Session → Conversation → Mission(s)`**. **Session** = user identity + tenant + session settings.
   **Conversation** = a **turn log only**. **Mission** = the **source of truth**. A Conversation
   **may not carry any Mission state** — the forbidden shape is `Conversation → Mission State`. (This
   sharpens §5–§6.)
2. **Mission selection — ruled: two layers, neither a static matcher alone nor the LLM deciding.**
   `Intent Understanding (LLM) → Capability candidates → Capability Selector (deterministic) →
   MissionRuntime`. The LLM emits an **intent + confidence** (e.g. `vendor_review, 0.92`), never a
   run command; the deterministic Selector decides against the registry, falling back to
   `simple_question` when there is no match. (This is folded into §4.)
3. **Package — ruled:** `v2/packages/assistant-runtime` — a **package, not an application** (the real
   app — Web/Desktop — sits *above* it).
4. **Streaming — ruled:** **not in the runtime.** The runtime exposes **Mission Progress Events**
   only; the UI chooses SSE / WebSocket / Polling.

---

## Consequences

**Positive**
- The Core stays frozen; the Assistant is a **pure consumer** — the payoff of the ports/facade design.
- Every GRC "application" collapses into a **registered Mission type**, so the product grows by
  configuration (a plan factory), not by new stacks or Core changes (CLAUDE.md §17).
- One governed, audited path for every user action (no chat side-channel), satisfying the
  transparency/human-gate pillars end to end.

**Negative / costs**
- A product-layer package to own and test (Catalog/Session/Conversation/runtime).
- The Assistant is only as capable as the injected `ExecutionPort`: until the real Pipeline-Tool
  executor + Tool Registry land (Slice 5 / a Core build), missions run against the reference executor.
  Accepted and explicit (assumption 5).
- Session/Conversation introduce product state that must be kept from duplicating mission truth
  (guarded by §6).

## Alternatives considered

- **Build the Assistant as raw chat that sometimes calls missions.** Rejected: reintroduces a
  chat-centric, unaudited side-channel — the exact anti-pattern ADR 0003/0042 exclude.
- **Make each GRC app (Risk, ISO, Vendor, Policy) its own application/stack.** Rejected: they share
  one execution model (Missions); they are Mission *types*, not stacks. Separate stacks would
  duplicate session/approval/audit wiring per app.
- **Put the Assistant logic directly in `apps/api`/`apps/web`.** Rejected: couples product logic to a
  delivery framework and defeats testability via the six callers; the runtime is a package, the app a
  thin adapter.
- **Extend `MissionRuntime` / the Core to carry sessions/conversations/catalog.** Rejected: those are
  product concerns; pushing them into the frozen Core violates the freeze and the layer boundary.

---

## Future ADRs

- **The real `ExecutionPort` (Pipeline-Tool executor) + Tool Registry** — the Core/Platform build that
  makes mission steps do real GRC work (Slice 5 depends on it). A Core ADR, consumed by the Assistant.
- **Per GRC Mission type** (Vendor Risk, ISO Gap, Policy Generation, …) — each may warrant a short ADR
  for its plan shape, gates, and evidence expectations, registered in the Catalog.
- **Durable/queryable audit projection** — if/when the product needs persisted, searchable audit
  beyond the in-memory sink (kept ADR-less until we decide to build it; see the Roadmap).

---

## Implementation Status

- **Slice 1 — Architecture — ✅ Accepted.** This ADR: boundaries, the consumer relationship to the
  frozen `MissionRuntime`, and the models — **Capability Catalog → Mission Catalog**, Session,
  Conversation, `AssistantRuntime`. The four review decisions are ruled (above). **No code.**
- **Slice 2 — Capability & Mission Catalog — ✅ Implemented (green; pending freeze review).** New
  package `v2/packages/assistant-runtime` (mechanism only — no GRC capabilities, LLM, tools,
  streaming, or DB of its own).
  - **Capability Catalog** (`Capability` = id/name/description/input_schema/resolver — pure records)
    + **Mission Catalog** (`MissionType` = plan factory `(inputs, tenant) → (goal, Plan)`).
  - **Two-layer selection:** `IntentRecognizer` port + reference `KeywordIntentRecognizer` (LLM
    *suggests* a `CapabilityIntent`, no real LLM) → `CapabilitySelector` (deterministic: exists? →
    it, else → the `simple_question` fallback; the anti-hallucination boundary).
  - **`MissionDriver` port** — the one seam into the Core (`run_transition`); the Assistant depends
    only on `mission-engine` + `pipeline-contracts`, with `MissionRuntime` injected. **`AssistantRuntime.handle`**
    is thin: intent → capability → plan → **one** `run_transition`.
  - **Verified (the six requested proofs):** one capability→one mission; unknown→`simple_question`;
    Mission Catalog builds a drivable `Plan`; `handle` calls the Core **exactly once**; **no reverse
    dependency** on the Core (AST-checked); and **E2E against the real `MissionRuntime`** on real
    PostgreSQL. 18 tests green; `ruff` + `mypy --strict` clean on source. (Whole V2 layer: 227 green.)
- **Slice 3 — First Capability (Simple Question) — ✅ Implemented (green; pending freeze review).**
  The first real built-in capability, shipped in `assistant_runtime/builtin/`:
  - **`SIMPLE_QUESTION_MISSION_TYPE`** — a plan factory `(inputs, tenant) → (goal, single-step Plan)`;
    **`AI_GRC_ASSISTANT_CAPABILITY`** (id `ask`, name "AI GRC Assistant") resolving to it, and serving
    as the fallback; **`build_assistant(mission_runtime)`** — a one-call assembler wiring the built-in
    catalogs + reference recognizer over an injected `MissionRuntime`.
  - Slice-3 constraints honoured: **no tools, no complex plan, no human approval, no multiple
    Missions** — a single read-only step.
  - **Verified:** the full loop `User → AssistantRuntime → Capability (ask) → Mission → MissionRuntime
    → Response` proven in-memory (spy driver, one Core call) **and end-to-end on real PostgreSQL**
    (durably persisted, one recorded step). 24 tests green; `ruff` + `mypy --strict` clean.
  - With only this capability registered, **every request routes to `ask`**; GRC capabilities add
    their keywords/plans later, one at a time, on this tested foundation.
- **Slice 4 — Conversation Runtime — ⏳ Not started** (built on Slice 3's observed behaviour).
- **Slices 5–6 — ⏳ Not started** (Response Layer; Integrations).
