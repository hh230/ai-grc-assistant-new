# Slice S7 — New Mission (starting the work)

> The last V1 slice, and the **first to add *behavior*** — every slice before it added a *question*
> (a new read); this one **creates work**. So the Reality Gate matters most here: a wrong assumption
> feeds straight into the command side. Derived from the **New Mission** + **Mission Created** Views
> ([../WIREFRAMES_V1.md](../WIREFRAMES_V1.md)) and the Create/Run commands
> ([../REST_API_CONTRACT_V1.md](../REST_API_CONTRACT_V1.md) §3). **Status:** ✅ **Approved** (owner,
> 2026-07-23) with 4 product-language/experience refinements — **"Start mission"** not "Run"
> (`StartMissionCommand`); `MissionDefinitionProvider` (returns `(goal, plan)`, not just a plan);
> **Mission Created = a review station**; plan-review is part of Done. Reality Gate settled the Draft
> question from code (**no Draft**). Owner Design Review → **Approved with changes** (5 UX touches, all
> applied & verified live). **Status:** ✅ **CLOSED** — V1's final slice; the product surface (S1–S7) is
> complete. **Last updated:** 2026-07-23.

---

## Product Question *(the one line the view answers)*

> ### "What work should we start?"

Not "Create Mission", not "New Workflow", not "Start Assessment". The user starts **work**; the
implementation makes that real. The product word is **New Mission** (the action) leading to a
**Mission** (the object) — never "Draft", "Job", or "Workflow".

---

## Reality Gate — verified from the code (before any commit)

*The first slice where the write side is real, so nothing is assumed.*

**Source of Truth:** the frozen **`MissionEngine`** (create → plan → execute) + the
**`MissionCatalog`** (assistant-runtime) that turns a Mission type into a plan.

| Question | Answer (from the code) |
|---|---|
| The creation entry point | **`MissionEngine.create(goal, tenant, *, idempotency_key)` → a `Mission` directly** (`Mission.create(...)`, status `CREATED`). Not a factory, not a two-phase build. |
| Who builds the Plan | **`MissionCatalog.build(type_id, inputs, tenant) → (goal, Plan)`** — *"a Mission type **is** a plan factory"* (ADR 0046 §4). `default_mission_catalog()` registers all **6** types. |
| Who sets Type / Scope | **the product**, not the Core. The Core stores a free-text `goal`; the catalog maps `(type, {"request": scope}) → (goal, Plan)`; the **S1 projection** records `type`/`scope`. |
| Is create+plan already done anywhere | **Yes** — `AssistantRuntime._drive` is literally `engine.create(goal, tenant); engine.plan(mission, plan)`. S7 does the same for a *structured* request (a type + scope), skipping the NL capability resolver. |
| `POST /v1/missions` / `POST …/run` in grc-api | **No** — only the read + approve/reject exist. S7 builds these two commands. |

### The decisive question — **does S7 need a `Draft`? → NO.**

The Core lifecycle is `created · planned · executing · awaiting_approval · resumed · completed ·
failed · cancelled · archived` — **there is no `DRAFT` state, and `create()` returns a `Mission`, not
a draft.** "Draft" is only the product's word for a mission **before it is run** (CREATED/PLANNED). So:

- **No `MissionDraft` aggregate, no Domain concept, no Application entity.** Adding one would be a
  whole aggregate the Core does not need — the exact premature-abstraction the guards exist to stop.
- The **input form is Presentation State only** — the selected type, the scope text, the chosen
  documents live in the New Mission *view's* state until the user starts the work, at which point the
  command creates a real `Mission`. There is no draft to persist.

**Composable from existing capabilities?** *(the bridge question — filled from reality)*

| Capability | Reused | New |
|---|---|---|
| Mission Engine (`create`/`plan`/`execute`) | ✓ | |
| Mission Catalog — a plan per type (assistant-runtime) | ✓ | |
| Mission projection → Mission List / Dashboard / Decisions / Result | ✓ | |
| `StartMissionCommand` (load by id → `execute`) via the S2 `MissionCommand` template | ✓ (template) | the concrete command |
| The **create** command + the ports it needs + the New Mission / Mission Created UI | | ✓ |
| A `Draft` aggregate / model | | ✗ **not built** (Core creates a Mission directly) |

**To build:** a **`CreateMissionCommand`** (the first create behavior) composing a **`MissionDefinitionProvider`**
port (type → `(goal, Plan)`, adapter over `default_mission_catalog`) + the engine (create + plan) +
the **S1 projection**; a **`StartMissionCommand`** (reusing the S2 `MissionCommand` template →
`engine.execute`); `POST /v1/missions` and `POST /v1/missions/{id}/run`; and the **New Mission** +
**Mission Created (Confirm)** views (Presentation State, no Draft).

---

## Foundation Reuse *(the read side is almost entirely reused; the write side is the new part)*

| Question | Answer |
|---|---|
| Which **Read Models** do I reuse? | **`mission-read-model`** — the created mission is projected once and then *every* surface (Mission List, Dashboard, Decisions, Result) shows it with **no special path** |
| Which **Commands / engine ops** do I reuse? | **`MissionEngine.create`/`plan`/`execute`** (frozen); the **`MissionCatalog`** plan factories (the 6 types); the **S2 `MissionCommand` template** for Start |
| Which **Presenters / components** do I reuse? | the **Presenter→Client** layering, the **plan display** (human-readable steps, S2), **status chips**, the **left rail**, the Mission Detail Work Surface (where the started mission lands) |
| What is **genuinely new**? | `CreateMissionCommand` (first create behavior) · a `MissionDefinitionProvider` port + adapter (`(type, inputs) → (goal, Plan)` — the mission *definition*, not just a plan) · `StartMissionCommand` (concrete; template reused) · the **New Mission** + **Mission Created** views — **no `Draft`, no new Aggregate, no new Domain** |

---

## Design rules

1. **No Draft.** The Core creates a `Mission` directly; the input form is Presentation State. If the
   user leaves without starting, nothing was created (no orphan drafts to manage).
2. **The product says "Start mission", never "Run".** The Core op is `engine.execute`, but the user
   *starts work* — so the languages stay separate (as `Deliverable → Result`, `ApprovalQueue →
   Decisions`): UI **"Start mission"** → Application **`StartMissionCommand`** → the engine's
   `execute`. The endpoint path `POST …/run` is a frozen-contract detail (like `/approvals` under
   Decisions), never surfaced as a word.
3. **`Mission Created` is a review station, not a formal success.** After Create it does **not** jump
   to execution and does **not** return to the list — it shows *"Mission created · Review the
   execution plan"* with **[Start mission]** / **[Back]**. Human reviews before execution — the
   product's founding stance, made a screen.
4. **Create returns the plan; Start is separate** (Screen Flow 1). `POST /v1/missions` creates + plans
   and returns the **human-readable plan**; the review station shows it; **Start** then executes. No
   "create-and-run" shortcut — plan review *is* the point of S7.
5. **The plan is shown in product language** — the plan-factory step *descriptions*, never tool names
   (Visibility ❌). Reuses the S2 plan presenter.
6. **Type is chosen from the 6; scope is free text.** The `MissionDefinitionProvider` maps them (via
   the catalog) to the Core's `(goal, plan)`; the projection records `type`/`scope`; unknown type →
   `400` at the boundary.
7. **The created mission reflects everywhere via the existing projection** — no surface gets a special
   "new mission" path; the projection is the single seam (Success Criteria below).

---

**Goal.** Let a Practitioner start real GRC work: choose a mission type and scope, **review the
plan**, and start it — after which the mission flows through the whole product (list, dashboard,
decisions, result) with no new machinery.

**User question (rule 11):** *"What work should we start?"* · **Primary decision:** start this
mission — or adjust it first. *(A create flow whose review station ends in the Start decision —
"human reviews before execution".)*

---

**Given / When / Then**

```
Given   a tenant with ingested evidence,
When    the user opens New Mission, picks a type (one of the 6) and enters a scope,
Then    they land on a **Mission Created review station** — type · scope · the human-readable plan
        (step descriptions, no tool names) — with **[Start mission]** / **[Back]** (not auto-run,
        not back-to-list): human reviews before execution;
When    they **Start** it,
Then    the mission executes (or pauses at a human gate), and immediately appears — with the right
        status — in the Mission List, the Dashboard counts, Decisions (if it gates), and its Result
        (once completed), all via the existing projection, with no special path;
And     it is tenant-scoped (another tenant never sees it) and idempotent (a repeat create with the
        same key returns the same mission, never a duplicate);
And     no Draft is persisted, and no tool/pipeline internals appear — only type, scope, and the plan.
```

---

**UX Metrics** (targets — a "No" is a finding)

- Clicks to start a mission: **≤ 3** (New Mission → fill → **Start**).
- The flow is **Create → Review Plan → Start** — the review station is never skipped (part of DoD).
- The created mission appears in the Mission List / Dashboard **without a manual refresh path** (same
  projection).
- Cross-tenant leakage: **0**; duplicate on repeat create (same idempotency key): **0**.
- No `Draft` row/table exists (asserted by the absence of any draft persistence).

---

**APIs used** (from the REST API Contract §3 — the two new commands)

- `POST /v1/missions` `{type, scope, document_ids?}` → `engine.create` + `engine.plan` (via the
  catalog); returns the mission (its pre-run "Draft" = CREATED/PLANNED) + the human-readable plan.
  Practitioner · type ∈ the 6 · `Idempotency-Key`.
- `POST /v1/missions/{id}/run` → `engine.execute` (the reused `MissionCommand` template) — the
  **"Start mission"** action in the UI; the `/run` path is the frozen-contract detail, not a product
  word. Practitioner · mission not already started (idempotent no-op if it was).
- *(Re-run, the S2 finding, lands here too: `POST /v1/missions/{id}/rerun` = `engine.create` a **new**
  mission from a Failed one's type/scope — the same create path, a follow-on within S7.)*

---

**Referenced Design Checklist** — Views: **New Mission** · **Mission Created**

- **Gate 0** delete test: without it the product can only *show and manage* work, never *start* it —
  the system cannot create, only observe.
- **Gate 1** user language — "start work", type, scope, a **plan** (not tool names); never "Draft".
- **Gate 5** every action ↔ a real command (`POST /v1/missions`, `POST …/run`).
- **Gate 6** one question / one decision (start this work); Empty/Loading/Error/Success defined.
- **Gate 7** tenant-scoped; idempotent; no Draft persisted; no tool/pipeline internals surfaced.

---

**Done Definition**

- [ ] A **`CreateMissionCommand`** — composes a `MissionDefinitionProvider` (type → `(goal, Plan)`, over the
      reused catalog) + `engine.create`/`plan` + the **S1 projection**; tenant-scoped, idempotent; **no
      Draft persisted**.
- [ ] A **`StartMissionCommand`** — reuses the S2 `MissionCommand` template (load by id → `engine.execute`
      → project the new status).
- [ ] `POST /v1/missions` returns the mission + human-readable plan; `POST /v1/missions/{id}/run` starts it.
- [ ] Frontend **New Mission** (type + scope form = Presentation State) → **Mission Created** *review
      station* ([Start mission] / [Back], never auto-run or back-to-list); Presenter→Client;
      Empty/Loading/Error/Success.
- [ ] **Success Criteria met (the S7 essence):** the full chain **Create → Review Plan → Start →
      (Mission List · Dashboard · Decisions · Result)** works — the started mission appears on every
      surface **through the existing projection only**, no special path — and the **plan-review station
      is part of it, never skipped**. Verified live.
- [ ] Tests green: `uv run pytest` · ruff · mypy --strict (DB-gated skip where Postgres absent).
- [ ] Design Review Checklist → **Approved**; **Slice Retrospective** appended (Reuse Ratio + New
      Component Justification).
- [ ] **No Foundational Document edited** (the §3 endpoints already exist) — unless implementation
      contradicts one → stop / fix / resume.

---

**Approval block** *(filled at verification)*

```
Views:     New Mission · Mission Created
Gates:     0✔ 1✔ 2✔ 3✔ 4✔ 5✔ 6✔ 7✔
Findings:  0 🔴 · 0 🟠 · 5 🟡 · 0 🔵
Status:    Approved with changes (owner) → all 5 applied & verified → CLOSED
Reviewer:  Owner (mam0022)
Date:      2026-07-23
Version:   S7 v1
```

**Findings & disposition** *(all product-language / experience; no architecture change)*
- 🟡 **A clear summary atop Mission Created** → done: **Mission · Scope · Steps · Human approvals**
  above the plan (steps + gates counted from the plan by the command) — "what did I create?" before
  "how?".
- 🟡 **Start = sole primary, Back = the only other CTA** → done (no third action on the review station).
- 🟡 **A beat of "Starting mission…"** → done: a ~700 ms dwell before navigating, so a sub-second run
  doesn't feel like nothing happened.
- 🟡 **Product language for the plan steps** → done **at the source**: the 6 plan factories now read
  "Identify applicable controls / Gather supporting evidence / Compute coverage and gaps", etc. — which
  also cleans the S2 Plan tab and the Result section headings, not just S7.
- 🟡 **The V1 one-question review** → done: [../V1_ONE_QUESTION_REVIEW.md](../V1_ONE_QUESTION_REVIEW.md)
  audits all seven screens against their single product question (all pass).

---

**Slice Retrospective** *(filled at close — the Learning Unit; guards 5–7)*

1. **Did we edit any Foundational Document?** **No.** The §3 `create`/`run` commands already existed.
   The plan-step wording became product language, but that was a copy change in `assistant-runtime`'s
   plan factories — not a Foundational-doc edit.
2. **What did we learn that wasn't visible before implementation?**
   - **The Reality Gate's best result to date: it proved an assumption *wrong* before it became code.**
     "We might need a Draft" → the Core has **no `DRAFT` state**; `create()` returns a Mission directly.
     So no aggregate, no Application/Domain concept — the input form stayed **Presentation State**.
     Disproving a wrong assumption pre-commit beats finding a bug later (owner's words).
   - **`create()` and `plan` are separate, and a repeat with the same idempotency key returns the
     already-*planned* mission** — so the creator plans only a fresh one (re-planning a PLANNED mission
     is an illegal transition). A small real-code fact, surfaced by a test, not from reading the header.
3. **Does this affect anything after V1?** No — V1's product surface is **complete (S1–S7)**. The next
   step is **not V2** but a **V1 Product Review** (walk the whole product as a new user; see
   [../V1_ONE_QUESTION_REVIEW.md](../V1_ONE_QUESTION_REVIEW.md)).
4. **Decision:** **Close Slice.**
5. **Foundation Reuse Ratio:** `New: 7 · Reused: 11 · Ratio ≈ 61%` — **deliberately the lowest of the
   Product-Expansion slices, and the correct signal:** S7 is the first slice to *add behavior*, so the
   write side is genuinely new. The **read side is fully reused** — the created mission then reflects on
   every surface (List · Dashboard · Decisions · Result) through the existing projection, no special path.
6. **New Component Justification** *(the write side earns its keep — a new concept, not a duplicate):*
   ```
   CreateMissionCommand      ✓ the first create behavior; no existing command creates a mission.
   MissionDefinitionProvider ✓ type → (goal, plan) at the command boundary (the catalog behind a port).
   MissionCreator            ✓ the Core create+plan seam (as EngineWorkflow is the approve+resume seam).
   MissionWorkflow.start     ✓ a new write op (the Core's execute); StartMissionCommand REUSES the template.
   CreationProjection        ✓ the first (creation) projection with type/scope; reuses the ProjectionPort.
   NewMission / Created UI    ✓ starting work is a genuinely new experience.
   (NO MissionDraft — the Core creates a Mission directly; the form is Presentation State.)
   ```
