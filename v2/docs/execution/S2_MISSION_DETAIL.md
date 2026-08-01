# Slice S2 — Mission Detail (the Work Surface)

> The product's centre: a Mission is a **small Workspace, not a page**. Derived from the **Mission
> Detail** View ([../WIREFRAMES_V1.md](../WIREFRAMES_V1.md)), **Screen Flow 2**
> ([../SCREEN_FLOWS_V1.md](../SCREEN_FLOWS_V1.md)), and the Mission Status / approval commands
> ([../REST_API_CONTRACT_V1.md](../REST_API_CONTRACT_V1.md)). Reads the mission **live from the Core**
> (`MissionStorePort.get`) — not the read model (ADR 0053; S1 retro Q3). **Status:** ✅ **CLOSED**
> (owner sign-off 2026-07-22 — Approved with changes, applied & verified). **Last updated:** 2026-07-22.

---

**Progress log**

- ✅ **Owner-approved** with 4 constraints applied (one-tab-one-question · View-Model-not-aggregate ·
  ETag-aware polling noted · hide-not-guard approval controls).
- ✅ **Read path — `GET /v1/missions/{id}`** on `grc-api`: a **`MissionDetail` View Model** (`detail.py`)
  composing live Core state (`MissionStorePort.get`) with read-model type/scope; renders plan (verbs
  only), findings (title/summary/citations/confidence), and the approval gate. **Hides all internals** —
  a test asserts the tool name, instruction, and chunk/source ids never appear (constraint 2). Tenant
  fail-closed → `404` (missing or cross-tenant). Added read-model `get(id, tenant)`. 6 endpoint tests +
  2 read-model tests green; ruff + mypy --strict clean.
- ✅ **Application-layer extraction (owner review)** — new package `v2/packages/mission-application`
  (framework-free: no FastAPI/Pydantic). `MissionDetailQuery` now composes store + read model + the
  View Model mapper; `MissionDetailView` is a plain dataclass. The `grc-api` route is a **thin
  adapter**: `view = query.execute(...); 404 if None; return view` — so `grc-api` stays a Composition
  Root + HTTP adapter (ADR 0052) and business logic won't accumulate in routes. Mapping logic is now
  **unit-tested without HTTP** (5 tests); the HTTP suite keeps the serialized no-leak / 404 / 401
  checks (17). This sets the CQRS split: **Queries → Application Query · Commands → Application
  Command** — the same package will host the S2 write commands.
- ✅ **Application-layer conventions (owner review), applied from the start:** `mission-application`
  split into **`queries/`** (`queries/mission_detail.py`) and **`commands/`** — one class per file, so
  growth stays natural. Every Query and Command's entry point is **`execute(...)`** (no run/handle/
  invoke/call). A Command receives only resolved inputs (tenant · principal · mission_id · step_id) and
  returns an Application result — **never** a `Request`/`Response`/JWT/header. All green.
- ✅ **Application-layer contract settled first (ADR 0054, owner-driven):** (a) commands hold
  **policies** not a facade — authorize → precondition → drive Core → **project on success** → emit
  (later); (b) **CQRS by dependency** — queries use store + read models, commands use engine +
  projector + publisher (no crossing); (c) a typed **`CommandResult{mission_id, status,
  approval_pending}`**, with failure as typed Application errors (`NotAuthorized`→403 ·
  `MissionNotFound`→404 · `IllegalCommand`→409), not a `success` flag. Implemented (`result.py`,
  `errors.py`) + tested; all green.
- ✅ **Application-layer *language* settled & ADR 0054 CLOSED (owner review):** `contracts/` holds the
  shared vocabulary — **`CommandContext`** (explicit `tenant_id` · `principal_id` · `roles` — *not*
  derived from the tenant, since a tenant is not a user — + correlation/request/clock; `.has_role()`,
  `.tenant_context()` bridge), **`CommandResult`**, the typed errors, and a **generic
  `ProjectionPort[T]`** (not mission-bound). ADR 0054 adds a **Use-Case boundary**: the layer holds
  orchestration/authorization/projections/policies/validation — never SQL/HTTP/JWT/FastAPI/psycopg.
- ✅ **Command shape frozen (owner review, final ADR 0054 additions §7–§8):** a command loads through a
  **`MissionAccess`** port (never the raw store — locking/OCC/audit/cache hooks land behind it); every
  mutating command is a **`MissionCommand` Template Method** — *authorize → load → validate → invoke →
  project → CommandResult* written once, a subclass fills only the hooks. Verified with fakes (order,
  `MissionNotFound` on missing, authorize short-circuits before load). **15 tests green.** ADR 0054 is
  now the frozen Application-layer *language*.
- ✅ **The three commands built (on the frozen base, no contract changed):** `MissionWorkflow` port
  added (last extraction — the engine abstraction, owner-requested), then `ApproveMissionStepCommand`
  / `RejectMissionStepCommand` / `RetryMissionCommand` as `MissionCommand` subclasses — each just
  three hooks (authorize role · validate state · invoke the workflow). 22 tests green (role gates,
  state preconditions, workflow driven, projection on success), ruff + mypy --strict clean. *The
  language sufficed: writing the commands required no change to ADR 0054's contracts.*
- ✅ **Adapters + approve/reject endpoints, integration-tested through the whole chain.** `grc-api`
  adapters (`StoreMissionAccess`→`store.get`; `ReadModelProjection`→read-model status re-projection;
  `EngineWorkflow`→engine — where **`approve_step` = engine.approve + engine.resume**, a *business
  action*, not a 1:1 mirror). Endpoints `POST …/approvals/{step}/approve|reject` (thin; the command
  holds the policy). Application errors mapped **once** → `403`/`404`/`409` (+ `401`). **6 integration
  tests** drive a real gated mission end-to-end: approve → **Completed** + projection updated; reject →
  **Cancelled** + projection updated; 403 non-Approver · 404 missing · 409 not-awaiting · 401 no auth.
  **23 grc-api tests green; ruff + mypy --strict clean. No contract changed — ADR 0054 held.**
- ✅ **S2 finding resolved (owner-decided):** the frozen Core makes **FAILED terminal**, so retry-in-
  place is impossible → **retry is redefined as a re-run** (`engine.create` a new mission from the
  failed one's inputs; the failed mission stays an audit record). No Core change. Re-run is a *create*,
  not a transition, so it lands with the **create flow (Slice S7)** — the incorrectly-shaped
  `RetryMissionCommand` + `MissionWorkflow.retry` were **removed** (cleanup); `approve`/`reject`
  shipped unaffected. REST API contract updated (retry → re-run, S7).
- ✅ **Frontend Work Surface built & verified end-to-end (browser).** Owner's two frontend rules
  applied: (1) **layering** `MissionDetailView → useMissionDetail → MissionDetailPresenter →
  MissionApiClient → REST` — React never calls `fetch`; the Presenter (framework-agnostic) holds
  polling, permissions (`canApprove`), the load/error state machine, and error mapping. (2) **Tabs are
  views of one Work-Surface state** (Summary/Plan/Findings/Evidence/Approvals/Deliverable — one
  mission, one `detail`, local tab UI), not independent pages. Gate card shows **Approve/Reject only
  for an Approver** (constraint 4). Verified live against a real gated mission: opened the Work
  Surface → Approvals gate → **Approve → mission drove to Completed** (full write chain: UI →
  Presenter → Client → API → command → EngineWorkflow approve+resume → Core → projection → refresh);
  Findings tab shows both steps; no console errors. `tsc` clean; the REST client unified S1's list too.
- ✅ **Owner Design Review of the Work Surface → Approved with changes, applied & verified:**
  (1) a **Trust Bar** atop the Work Surface (`N evidence · Human review: <status> · Updated …`) — the
  "can I trust this?" question starts here, not only on the Deliverable; (2) **Findings tab renamed
  Execution** — these are execution steps, not GRC findings (honest naming, like Evidence Mapping;
  "Finding" is reserved until it means one, S3/S4); (3) the approval card became a **Decision Card** —
  *Proposed action · AI recommendation · Evidence* then the buttons, so "AI explains before it
  recommends" is visible. The AI-recommendation line reads **"not available yet"** (honest — the Core
  produces none), and cleaning the proposed-action text also removed the internal step-id leak. `tsc`
  clean; verified live in the browser.
- ✅ **S2 CLOSED** (owner pre-approved close on applying the three). *Retry → re-run lands in S7.*

---

## Design constraints (owner review — apply before first commit)

1. **One tab, one question** (so the Work Surface never becomes a crowded dashboard). Each tab answers
   exactly one user question — **Plan** → *what will the system do?* · **Progress** → *what is happening
   now?* · **Findings** → *what did it discover?* · **Evidence** → *why does it say that?* · **Approvals**
   → *what decision is needed?* · **Deliverable** → *what did it ship?* If a tab starts answering two, it
   needs re-splitting.
2. **`GET /v1/missions/{id}` returns a View Model, not the aggregate.** `Mission (Core) → Mission Detail
   View Model → JSON`. It exposes only what the View needs — never `PlanStep` internals, tool ids, the
   pipeline, or internal execution state. (The product describes the user's model, not the implementation.)
3. **Polling is ETag-aware.** `GET /v1/missions/{id}` carries an `ETag`/version; a poll with
   `If-None-Match` returns `304` when nothing changed. *(Not required in the first commit — noted here so
   it is not forgotten as poll volume grows.)*
4. **Approval controls are hidden, not just guarded.** If the caller is not an Approver, the Approve /
   Reject buttons **do not render at all** — not merely a `403` on click. (A UX decision, above the
   security guard.)

---

**Goal.** Open a mission and, in one surface, watch it run, decide at its human gate, read its findings
with evidence, and reach its deliverable — without page-hopping.

---

**User question (rule 11):** *"What is happening with this mission?"* · **Primary decision:** continue /
approve / open the result (one at a time, by state).

---

**Given / When / Then** — one View, five state variants (the state changes what is shown & actionable)

```
Given   a mission owned by tenant T (in each of the lifecycle states below),
        and a caller authenticated for T.

When    they open the mission (from the Missions list — one click).

Then    the Work Surface shows a header (type · scope · live status) and the mission's plan and
        findings, and the state variant renders:
        • Draft            → the steerable plan; primary action Run.
        • Running          → progress (polled: steps_completed/total) + findings with citations as
                             steps complete; no consequential control offered.
        • WaitingApproval  → a gate card: the proposed action + its evidence; Approve / Reject shown
                             ONLY to an Approver (constraint 4) — nothing consequential proceeds without it.
        • Completed        → findings + a link to the Deliverable (View is Slice S3).
        • Failed           → the reason + Retry.

And     progress is obtained by POLL of GET /v1/missions/{id} (no websocket/SSE);
And     a mission belonging to another tenant resolves to 404 (fail-closed — existence not revealed);
And     no tool name, pipeline, executor, or chunk id ever appears (only human-readable findings +
        citations).
```

---

**UX Metrics** (targets — a "No" is a finding)

- Clicks to open from the list: **1**.
- Time to first paint of the surface: **< 1.0s**.
- Poll cadence while `Running`: **1–2s**; the UI **never blocks** on it (Principle 10).
- Cross-tenant leakage: **0** (asserted by test).
- Approve/Reject visible **only** to an Approver; absent for a Practitioner.

---

**APIs used** (from the REST API Contract — no invented endpoints; all Core-supported)

- `GET /v1/missions/{id}` → the mission **View Model** (constraint 2): `type · scope · status · plan
  (human-readable steps only) · findings(+citations) · the active approval`. New endpoint on `grc-api`,
  composing the live `MissionStorePort.get` (status/plan/findings/approval) with the read model's product
  metadata (type/scope, per ADR 0053) — additive, no Core change. Carries an `ETag` (constraint 3).
- `POST /v1/missions/{id}/approvals/{step_id}/approve` `{comment?}` → approve + resume (ADR 0044).
- `POST /v1/missions/{id}/approvals/{step_id}/reject` `{comment?}` → reject, fail-safe (ADR 0044).
- `POST /v1/missions/{id}/retry` → re-drive from Failed.
- *(Run/Create belong to the New Mission flow — Slice S7 — not built here.)*

---

**Referenced Design Checklist** — View: **Mission Detail (Work Surface)**

- **Gate 0** delete test: removing it breaks executing & governing all work → justified.
- **Gate 1** user language; the Work Surface hosts Plan/Progress/Findings/Approvals/Deliverable/Evidence/
  Activity — no implementation leaks.
- **Gate 3/7** evidence shown for findings; **approval explicit** (Principle 7); honest about uncertainty.
- **Gate 4** all five state variants render the correct visible info & actions; only legal transitions.
- **Gate 5** every action ↔ a real endpoint; **poll** model; approve/reject carry the Approver guard.
- **Gate 6** one user question / one primary decision per state; Empty/Loading/Error/Success defined.
- **Gate 7** tenant-scoped, fail-closed (cross-tenant ⇒ 404).

---

**Done Definition**

- [ ] Given/When/Then hold for **all five state variants** end-to-end; UX metrics met.
- [ ] `GET /v1/missions/{id}` returns a **View Model** (constraint 2 — no `PlanStep` internals, tool ids,
      pipeline, or internal state), composing live Core state + read-model type/scope, tenant-scoped
      **fail-closed** (cross-tenant ⇒ 404), proven by test.
- [ ] Each tab answers **one question** (constraint 1); Approve/Reject **render only for an Approver**
      (constraint 4), not merely `403` on click.
- [ ] Approve / Reject / Retry match the contract (ADR 0044 guards; Approver role declared).
- [ ] Frontend Work Surface renders the header + the five variants + the gate card; poll while Running;
      Empty/Loading/Error/Success defined. ViewModel stays within the API boundary (owner's rule).
- [ ] Tests green: `uv run pytest` · ruff · mypy --strict (DB-gated skip where Postgres absent).
- [ ] Design Review Checklist → **Approved** (block recorded).
- [ ] **No Foundational Document edited** (unless implementation contradicts one → stop, fix, resume).
- [ ] **Slice Retrospective** appended; decision = **Close Slice**.

---

**Approval block**

```
View:      Mission Detail (Work Surface)
Gates:     0✅ 1✅ 2✅ 3✅ 4✅ 5✅ 6✅ 7✅
Findings:  0 🔴 · 0 🟠 · 3 🟡 · 0 🔵   (owner review: Trust Bar, Findings→Execution, Decision Card — all applied)
Status:    Approved with changes → changes applied & re-verified → Closed
Reviewer:  Product Owner (Design Review); Claude applied the changes
Date:      2026-07-22
Version:   S2 v2 (post-review)
```

---

**Slice Retrospective** *(the Learning Unit)*

1. **Did we edit any Foundational Document?** **Yes — one, and it is the Freeze rule working.** The
   **REST API Contract** changed `retry → re-run` because implementation revealed the Core makes
   FAILED terminal (a real contradiction → stop, fix the doc, continue). No *other* Foundational
   Document changed; ADR 0054 (the Application-layer language) held through the whole slice unchanged.
2. **What did we learn that wasn't visible before implementation?** (a) FAILED is terminal → retry is
   really a **re-run (a create)**, not a transition — good for immutability/audit. (b) The
   Application-layer language matured enough that the three commands + adapters needed **no contract
   change** (the ADR 0054 extractions-by-pressure paid off). (c) The frontend needs its **own
   layering** (Presenter) — the StrictMode fix stayed inside the Presenter, proving it.
3. **Does this affect S3 (Deliverable)?** **Yes (informing).** The Deliverable is derived from the
   completed mission; the **Trust Bar** introduced here is the seed of the Deliverable's trust bar;
   and the Work Surface's Deliverable tab links into S3.
4. **Decision:** **Close Slice** ✅ (owner pre-approved on applying the three changes, 2026-07-22).
