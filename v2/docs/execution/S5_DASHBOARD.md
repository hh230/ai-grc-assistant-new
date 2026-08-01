# Slice S5 — Dashboard (the tenant's "What needs me now?")

> The **first slice of the Product Expansion Phase** — and the first real test of the language built in
> S1–S4. It should *speak* that language, not reinvent it. Derived from the **Dashboard** View
> ([../WIREFRAMES_V1.md](../WIREFRAMES_V1.md) — "attention-first, not reports") and the Dashboard query
> ([../REST_API_CONTRACT_V1.md](../REST_API_CONTRACT_V1.md) §4). **Status:** drafted; direction (a
> Dashboard **Projection**, not a God endpoint) owner-approved 2026-07-22. **Status:** ✅ **CLOSED**
> (owner sign-off 2026-07-23, *Approved with changes* — all 5 UX changes applied & verified live).
> First slice of the Product Expansion Phase; first successful use of the New Component Justification
> guard (New 4 · Reused 11 · Reuse ≈ 73%). **Last updated:** 2026-07-23.

---

## Product Question *(the one line every card must serve)*

> ### "What needs my attention right now?"

Every card earns its place by answering **this** — and nothing else. Waiting · Running · Failed ·
Recently completed · Coverage Snapshot all answer it. **Explicitly out of scope** (they answer a
*different* question — that is *analytics*, and **Dashboard ≠ Analytics**): user counts, document
counts, last-upload, storage used. If a card does not help the practitioner decide **what to act on
next**, it does not belong in S5 — no matter how easy it would be to add.

---

## Reality Gate — what the system actually provides (before any commit)

**Source of Truth:** **`mission-read-model` (S1)** for the attention counts and recently-completed; the
**Gap Results (S3)** for the coverage. A thin **Dashboard Projection** *composes* them — it owns no new
state of its own.

| Dashboard element | Source | Exists today? |
|---|---|---|
| Waiting-for-you count | missions `status = awaiting_approval` | ✅ `mission-read-model.list_missions(status=…)` + `total` |
| Running / Failed counts | `status = executing`(+created/planned/resumed) / `failed` | ✅ same read model |
| Recently completed | `status = completed`, newest-first, top N | ✅ same read model |
| **Coverage Snapshot** | rollup over the **latest completed Gap Assessments'** results | ❌ **no rollup exists** — per-mission coverage exists (`GapMatrix.coverage`, S3), no cross-mission aggregate |
| A "system state now" read / endpoint | — | ❌ §4 had **no dashboard query** |

**Composable from existing projections?** *(the bridge question)* — **Partially.**
- Attention counts + recently-completed → **Yes**: compose `mission-read-model`. **No new projection.**
- Coverage Snapshot → **No**: cannot be derived from `mission-read-model` alone (it needs the Gap
  Results) → a new **`CoverageRollupProvider`** — and it is its **own capability**, not a limb of the
  dashboard (it will be reused by future Executive / Vendor / Compliance dashboards). Justified, guard 7.
- The "system state now" read boundary → a **different business question** than the mission list → a
  new **`DashboardProjection`**, justified under guard 7 — but a **read-only aggregation, computed on
  read** (see design rule 4).

**Finding (owner-decided, in the REST Contract's S5 footnote):** the Dashboard View existed in the
Wireframes but §4 listed no query. Added `GET /v1/dashboard`, deliberately shaped as a **read of one
Dashboard Projection** — the endpoint carries no business logic. Flow:
`mission-read-model → coverage rollup → Dashboard Projection → GET /v1/dashboard`.

**To build:** a **`DashboardProjection`** — a **read-only aggregation, computed on read** (no table, no
projector, no persistence) — that composes **two independent providers**:

```
DashboardProjection  (computed on read)
    ├── MissionSummaryProvider   → over the reused mission-read-model (S1)
    └── CoverageRollupProvider   → the new metric over completed Gap Results (its own capability)
```

plus `GET /v1/dashboard` (reads the projection) and the Dashboard view. **Default = computed-on-read;**
materialize into a stored projection *only* if performance later demands it — never up front.

---

## Foundation Reuse *(speak the language, don't reinvent it)*

| Question | Answer |
|---|---|
| Which **Read Model** do I reuse? | **`mission-read-model` (S1)** — every attention count + the recently-completed list |
| Which **Query** do I reuse? | the **read-model query pattern (S1)** for counts/recent; **the Gap Result / coverage read (S3)** as the rollup's input |
| Which **Presenter / registry** do I reuse? | the **Summary-strip pattern** (already a mini-dashboard), **status chips + labels**, the **left rail** (S4), the **Presenter→Client** layering |
| What is **genuinely new**? | `DashboardProjection` (computed-on-read; a new business question) · `MissionSummaryProvider` (thin, over the reused read model) · `CoverageRollupProvider` (a new metric, its own capability) · `DashboardView` (new UI) — **no new stored table, no projector** |

Expected shape at close: **mostly reuse**, with 2–3 new components, each justified (guard 7). If this
section grows inventions, S5 is re-inventing S1 — stop.

---

## Design rules (owner)

1. **Dashboard = a Projection, not a God endpoint.** `GET /v1/dashboard` reads **one** projection
   representing "system state now". The aggregation lives *in* the projection, never in the handler —
   `read → compose → return`, not `endpoint → query missions → query results → calculate → aggregate`.
2. **Coverage *Snapshot*, not Coverage %.** A point-in-time picture from the latest completed Gap
   Assessments — **not** a compliance report. Consistent with **Result ≠ Report · Evidence Mapping ≠
   Attestation · Dashboard ≠ Analytics**.
3. **Attention-first order** (Wireframe): **Waiting → Running → Failed → Recently completed → Coverage
   Snapshot** (coverage *last*, not first — the page answers "what needs me now?", not "how are we
   doing overall?").
4. **`DashboardProjection` is a read-only aggregation, computed on read.** No table, no projector, no
   persistence — just a query that composes existing projections at read time. Only if performance
   becomes a real problem does it *then* become a stored projection. The default is never storage.
5. **`CoverageRollupProvider` is its own capability, not a limb of the Dashboard.** The projection
   *composes* it (alongside `MissionSummaryProvider`); it does not compute coverage inline. Coverage
   will be reused by future Executive / Vendor / Compliance dashboards — a new *type* is an **addition**,
   not a modification, so it lives on its own from day one.

---

**Goal.** A practitioner lands in the workspace and immediately sees **what needs them now** — waiting
approvals, running/failed missions, what just completed, and a coverage snapshot — each actionable in
one click, all tenant-scoped.

**User question (rule 11):** *"What needs me now?"* · **Primary decision:** which item to act on next.
*(An attention / navigation view — **no Trust Bar**; that is only for a view that ends in a single
evidence-backed decision.)*

---

**Given / When / Then**

```
Given   a tenant T with missions across states (some awaiting_approval, executing, failed, completed)
        and ≥1 completed Gap Assessment with coverage — and another tenant T2 with its own,
When    the user opens the Dashboard,
Then    they see, in this order: Waiting for you (N) · Running (N) · Failed (N) · Recently completed
        (list) · Coverage Snapshot (a %); coverage is LAST;
And     each count opens the matching filtered Missions view, and each recent item opens its mission
        (≤ 1 click); "＋ New Mission" is present;
And     the numbers are exactly T's (a count equals what the Missions list shows for that status);
And     T never sees T2's numbers or coverage (fail-closed);
And     the Coverage Snapshot is labelled a *snapshot* (from latest completed Gap Assessments), never a
        compliance score; no chunk/tool/pipeline/coverage-math internals are exposed.
```

---

**UX Metrics** (targets — a "No" is a finding)

- Clicks to reach the Dashboard: **0** (context landing) or **1** (rail).
- Time to first paint: **< 1s**; one request (`GET /v1/dashboard`), never N+1.
- Counts reconcile with the Missions list (same read model) — **exact**.
- Cross-tenant leakage: **0** (asserted by test).

---

**APIs used** (from the REST API Contract §4)

- `GET /v1/dashboard` → the **Dashboard Projection**: attention counts (waiting·running·failed) ·
  recently completed · Coverage Snapshot. Reads a projection; no business logic in the endpoint.

---

**Referenced Design Checklist** — View: **Dashboard**

- **Gate 0** delete test: removing it removes the "what needs me now?" landing (the practitioner's
  daily entry) — a real journey breaks.
- **Gate 1** **user language** — "what needs me now", **Coverage Snapshot** (not "Coverage %"), no
  internals.
- **Gate 5** every count/item ↔ a real destination (a filtered Missions view / a mission).
- **Gate 6** one question ("what needs me now?"); Empty/Loading/Error/Success defined; **no Trust Bar**.
- **Gate 7** tenant-scoped, fail-closed; no tool/pipeline/coverage-math internals.

---

**Done Definition**

- [ ] A **`DashboardProjection`** — a **read-only aggregation, computed on read** (tenant-scoped,
      fail-closed; **no table / projector / persistence**) — composing a **`MissionSummaryProvider`**
      (over the reused `mission-read-model`) and an independent **`CoverageRollupProvider`** (over
      completed Gap Results). The endpoint carries no business logic.
- [ ] `GET /v1/dashboard` returns the projection (one request); counts reconcile with the Missions list.
- [ ] Frontend **Dashboard** view — attention-first order (Waiting→Running→Failed→Recently completed→
      Coverage Snapshot); each item ≤1-click actionable; Presenter→Client; Empty/Loading/Error/Success;
      "Coverage Snapshot" wording (never "Coverage %").
- [ ] Tests green: `uv run pytest` · ruff · mypy --strict (DB-gated skip where Postgres absent).
- [ ] Design Review Checklist → **Approved**; **Slice Retrospective** appended (incl. Foundation Reuse
      Ratio + New Component Justification).
- [ ] **No Foundational Document edited** beyond the owner-approved §4 dashboard addition (done) —
      unless implementation contradicts one → stop / fix / resume.

---

**Approval block** *(filled at verification)*

```
View:      Dashboard
Gates:     0✔ 1✔ 2✔ 3✔ 4✔ 5✔ 6✔ 7✔
Findings:  0 🔴 · 0 🟠 · 5 🟡 · 0 🔵
Status:    Approved with changes (owner) → all 5 applied → CLOSED
Reviewer:  Owner (mam0022)
Date:      2026-07-23
Version:   S5 v1
```

**Findings & disposition** *(all frontend/product; no backend or contract change)*
- 🟡 **Waiting is the Primary CTA** → done: a prominent full-width accent card ("Waiting for you · Approvals
  that need your decision · Review now →") when `waiting > 0`; the eye lands there first.
- 🟡 **Recently completed shows *what* finished, not a count** → done: the last two missions (type · scope ·
  time), each a link to its Work Surface.
- 🟡 **Coverage needs a caveat** → done: "*Based on completed Gap Assessments only.*" under the snapshot —
  it protects the Evidence-Mapping ≠ Compliance line the whole product defends.
- 🟡 **Coverage is clickable** → done: the card links to the **filtered Gap Assessments** (Coverage → Mission
  List → Gap Assessments → Result), never to a "report".
- 🟡 **"Nothing needs your attention"** → done: when waiting/running/failed are all 0, a small positive
  banner replaces the cards; Recently completed + Coverage still show, so the page stays alive.

---

**Slice Retrospective** *(filled at close — the Learning Unit; guards 5–7 from S5 on)*

1. **Did we edit any Foundational Document?** **Yes** — only the **REST API Contract §4**: added
   `GET /v1/dashboard` as a **Projection read** (its S5 footnote), owner-pre-approved. Nothing else moved.
2. **What did we learn that wasn't visible before implementation?**
   - **The Foundation Phase proved out.** S5 is the first slice the owner reviewed as *"a product, not a
     feature"* — the S1–S4 language was **used, not reinvented**. That is the test the Foundation was
     built to pass, and it passed.
   - **Every dashboard card must earn its place against the one Product Question.** The build's temptation
     was "nice" tiles (doc counts, storage); the Product Question rule kept them out — the guard is a
     filter, not decoration.
3. **Does this affect S6 (Approvals)?** The projection pattern held (computed-on-read; provider
   composition; no new stored table). S6 is the **Approvals queue** — a genuine *list* read (the detailed
   cross-mission items, vs. S5's *count*), so expect a small justified new read component there; reuse
   should stay high.
4. **Decision:** **Close Slice.**
5. **Foundation Reuse Ratio:** `New: 4 · Reused: 11 · Ratio ≈ 73%` — headline reuse: **no new stored
   projection/table, and no new write path.** Reused: mission-read-model · ResultQuery + coverage types ·
   Presenter→Client layering · status chips + helpers · the Summary-strip pattern · the left rail ·
   grc-api host plumbing (require_tenant / errors / deps / injection) · MissionsView (+ a small
   `initialStatus`/`initialType`) · the read-model list/filter/total · the GapMatrix / builder registry ·
   the view-model→schema mapping.
6. **New Component Justification** *(one line each — a new concept, not a duplicate):*
   ```
   DashboardProjection     ✓ a different business question than the mission list; computed-on-read
                             (no table/projector/persistence).
   MissionSummaryProvider  ✓ the dashboard's mission-attention read; a thin composition of the reused
                             mission-read-model, not a duplicate of it.
   CoverageRollupProvider  ✓ a new business metric; not derivable from mission-read-model alone; its
                             OWN capability (future Executive/Vendor/Compliance dashboards reuse it).
   DashboardView           ✓ the UI is genuinely new.
   (no existing component was duplicated; no new stored projection/table was introduced)
   ```
