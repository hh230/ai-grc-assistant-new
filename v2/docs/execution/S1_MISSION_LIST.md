# Slice S1 — Mission List

> The first vertical slice and the **spine** of the product: every journey reaches a mission through it.
> Derived from the **Missions** View ([../WIREFRAMES_V1.md](../WIREFRAMES_V1.md)) and the **Mission List**
> query ([../REST_API_CONTRACT_V1.md](../REST_API_CONTRACT_V1.md) §4, a Domain §3 read-model gap).
> **Status:** ✅ **CLOSED** — owner sign-off 2026-07-22 (Passed; Design Review passed after minor UX
> improvements; Architecture & Product Freeze intact). **Last updated:** 2026-07-22.

---

**Progress log**

- ✅ **Backend read model** — new package `v2/packages/mission-read-model` (`MissionListItem` ·
  `MissionPage` · `MissionListReadModel` port · `InMemoryMissionListReadModel`). Tenant-scoped
  fail-closed; filter by status/type; case-insensitive title search; newest-first; bounded paging.
  11 acceptance tests green; ruff + mypy --strict clean.
- 🔎 **Surfaced assumption (retro Q2):** the Core `Mission` stores `goal`, **not** `type`/`scope`;
  Mission Type is a product concept (`MissionCatalog`) never persisted on the aggregate. Resolution
  (no Core change, no Foundational-Doc edit — the API contract & Domain §3 already assume a read
  model with type/scope): a **product-owned projection** carries type + title + a status snapshot.
- 🏛️ **Architectural decision (ADR 0052):** the official V1 Product API Host is **`v2/apps/grc-api`**
  (`apps/api` is the old generation — never built on). Composition root only.
- ✅ **API host + `GET /v1/missions`** — `v2/apps/grc-api` (FastAPI): `create_app` composition root ·
  **dev bearer → `TenantContext`** resolver (fail-closed 401, the seam OIDC replaces with zero route
  change) · uniform error envelope (§5) · health probe · `GET /v1/missions` wired to the read model
  with `status`/`type`/`q`/`page`/`page_size`. 11 HTTP acceptance tests green (401 fail-closed,
  tenant isolation across two tokens, row shape hides impl, filters/search/paging, 400 validation);
  ruff + mypy --strict clean.
- ✅ **Identity seam renamed** (owner review): `IdentityProvider` / `DevelopmentIdentityProvider`
  (bearer is transport in `require_tenant`, not part of the design).
- ✅ **Projector** — new package `v2/packages/mission-projection` (`MissionProjector.project(mission,
  *, mission_type, scope)`): the CQRS write side that supplies the two product-only fields the Core
  omits and records the mission's status snapshot; idempotent upsert on every transition; tenant-
  scoped. 3 tests green; ruff + mypy --strict clean.
- 🕓 **Frontend host deferred** (owner): S1 does not depend on it — the Missions View can be built on
  any temporary React app; the Web host is decided at the first full frontend slice (S4/S5), not now.
- 🏛️ **Architectural decision (ADR 0053):** Read Models are the CQRS read side; **projection is an
  Application-layer, synchronous concern** (the product Application Service calls the projector after
  persisting; event-driven-ready via the existing outbox). This is the pattern for Approvals,
  Deliverables, and Dashboard read models too — not a one-off.
- ✅ **Postgres read-model adapter** — `PostgresMissionListReadModel` (same port), lazy psycopg,
  tenant isolation enforced in SQL, filters/search/paging, upsert; `schema.py` DDL + tenant-first
  index. Driver-free tests always run; the DB-gated integration test auto-skips without Postgres
  (13 passed, 1 skipped); ruff + mypy --strict clean.
- ✅ **Missions View frontend** — `v2/apps/mission-web-spike` (temporary Vite + React + TS; host still
  deferred). ViewModel is **only** the API's `MissionListItem`/`MissionListResponse` (owner's rule);
  a Vite proxy keeps it same-origin (no CORS). Renders Loading/Error/Empty/Success, filter-by-
  status/type, title search, paging; one primary action (open a mission → S2).
- ✅ **Verified end-to-end (browser):** React → Vite proxy → `grc-api` (dev-seeded) → read model.
  Confirmed live: 4-of-5 rows on page 1 with color-coded status; **tenant isolation** (tenant-b's
  mission absent through the UI); status+search combined → **Empty state**; **paging** to page 2
  (`Iso Controls · Annex A lookup · Failed`, "Page 2 · 5 total"); `401` without a credential; no
  console errors. *(Projector→AssistantRuntime wiring lands with the create flow, Slice S7, per ADR
  0053 — S1 is the read side, seeded until then.)*

**Backend of S1 is complete and green.**

- 🔎 **Owner Design Review (2026-07-22)** — strong on IA / simplicity / domain-discipline (no
  tool/pipeline/chunk leaked). Findings (usability, "data list → work list"), all **frontend-only,
  no API/backend/Foundation change** — applied and re-verified:
  1. **`+ New Mission` CTA** (the product's primary button; placeholder → Slice S7).
  2. **Attention summary strip** — `Running · Awaiting approval · Completed · Failed` counts, so the
     page answers its user question *"what work needs my attention?"* (chips also quick-filter).
  3. **Whole-row click target** with a clear hover state.
  4. **Relative timestamps** ("3 min ago", "yesterday") — dev seed given realistic times.
  - *Deferred (needs a data/API field, not in S1's no-touch scope):* a separate **Framework** badge —
    the API carries `scope` as free text, not a first-class `framework`; noted for a later slice.

**Frontend build rule (owner):** the ViewModel must **not exceed the API boundary** — React consumes
**only the API's `MissionListItem`/`MissionListResponse` shape**, never the Mission aggregate, the
projection, a DB row, or an ORM model. The REST API is the frontend's single contract.

**Backlog (not now — do not build preemptively):** with Deliverables, Dashboard, Approvals, and
Knowledge read models coming, watch for real `*Projector` duplication; if it appears (after a slice
or two), consider a small **Projection Framework**. Build only when the repetition is real.

---

**Goal.** A Practitioner opens the Missions area and sees *their tenant's* missions with real status — the
one reliable place to find and resume any work.

---

**User question (rule 11):** *"Which mission do I open?"* · **Primary decision:** open/resume one.

---

**Given / When / Then**

```
Given   a Practitioner in tenant T with 3 missions (various types & statuses),
        and another tenant T2 that also has missions.

When    they open the Missions area.

Then    • they see exactly their 3 missions, most-recently-updated first;
        • each row shows type · scope · a real status badge · updated-at;
        • they can filter by status and by type (server-side);
        • they can search by scope/type text;
        • they NEVER see any mission belonging to T2 (fail-closed);
        • an empty tenant sees the "No missions yet → New Mission" empty state;
        • a load failure shows an Error state with retry (never a blank page).
```

---

**UX Metrics** (targets — a "No" is a finding)

- Clicks to reach the list from app entry: **1** (sidebar → Missions).
- Time to first meaningful paint: **< 1.0s** (list of ≤ 50 on a warm API).
- List query server time: **< 200ms** p95 for a tenant with ≤ 1,000 missions (paginated).
- Cross-tenant leakage: **0** — asserted by test, not by convention.

---

**APIs used** (from the REST API Contract — no invented endpoints)

- `GET /v1/missions?status=&type=&page=` → this tenant's missions (the ⚠️ list-by-tenant read port).
- *(entry to next slice)* row click → `GET /v1/missions/{id}` (S2, not built here).

*Backend built additively (Domain §3 gap): a `list_missions(tenant, filters, page)` read port over the
Mission Store — no change to the frozen Core write path.*

---

**Referenced Design Checklist** — View: **Missions**

- **Gate 0** delete test: removing it breaks *every* path to a mission → the View is justified.
- **Gate 1** user language (type/scope/status), no tool names.
- **Gate 4** rows reflect real lifecycle states.
- **Gate 5** every action ↔ a real endpoint; poll model respected.
- **Gate 6** one question / one decision; Empty/Loading/Error/Success all defined.
- **Gate 7** tenant-scoped, fail-closed (cross-tenant ⇒ `404`/absent, existence not revealed).

---

**Done Definition**

- [ ] Given/When/Then all hold end-to-end; UX metrics met (or a tracked 🟡 with owner+date).
- [ ] `list_missions(tenant)` read port: tenant-scoped, filtered, paginated; **fail-closed** proven by a
      cross-tenant test (T cannot see T2).
- [ ] `GET /v1/missions` matches the contract (params, shape, guards); representation hides implementation.
- [ ] Frontend Missions View renders rows + filters + search + all four states.
- [ ] Tests green: `uv run pytest` · ruff · mypy --strict. (DB-gated tests skip where Postgres is absent.)
- [ ] Design Review Checklist → **Approved** (block recorded below).
- [ ] **No Foundational Document edited** (unless implementation contradicted one → stop, fix, resume).
- [ ] **Slice Retrospective** filled below; decision = **Close Slice**.

---

**Approval block** *(filled at verification)*

```
View:      Missions
Gates:     0✅ 1✅ 2✅ 3✅ 4✅ 5✅ 6✅ 7✅
Findings:  0 🔴 · 1 🟠 · 3 🟡 · 0 🔵   (owner review; all applied & re-verified)
Status:    Approved with changes — changes applied, re-verified; final owner sign-off pending
Reviewer:  Product Owner (Design Review); Claude applied the changes
Date:      2026-07-22
Version:   S1 v2 (post-review)
```

*Owner-review findings (all frontend-only, now applied):* 🟠 the page answered "here are the missions"
not its user question "what needs my attention?" → **attention summary strip** added. 🟡 missing
**+ New Mission** CTA · 🟡 no **timestamps** · 🟡 row click-target/hover unclear. No 🔴; no API, backend,
or Foundational-Document change.

*Gate notes:* **G0** removing Missions breaks every path to a mission → justified. **G1** user language
(type/scope/status), no tool names. **G4** rows are real lifecycle states. **G5** every action ↔ a real
endpoint (`GET /v1/missions`); poll model respected. **G6** one question / one decision (open a mission);
Empty/Loading/Error/Success all present and shown live. **G7** tenant-scoped, fail-closed (`401` no
credential; tenant-b invisible), representation hides implementation.

---

**Slice Retrospective** *(filled at close — the Learning Unit)*

1. **Did we edit any Foundational Document?** **No.** The Foundation held through the first real slice
   — the strongest evidence yet that the design was sound. Two *additive* ADRs were written (0052
   Product API Host, 0053 Read Models & Projection); neither contradicts a frozen document.
2. **What did we learn that wasn't visible before implementation?** (a) The Core `Mission` stores
   `goal`, not `type`/`scope` — Mission Type is a product concept, so read models are **product-owned
   projections** (ADR 0053). (b) Projection is a *general pattern* (Approvals/Deliverables/Dashboard
   follow) — watch for `*Projector` duplication; a small Projection Framework may be warranted later,
   built only when the repetition is real (backlog, not now).
3. **Does this affect S2 (Mission Detail)?** **Yes (informing, not blocking).** S2 reads a single
   mission live from the Core (`GET /v1/missions/{id}`, the existing `MissionStorePort.get`), not the
   read model. And the projector's wiring into the create flow lands with **S7** — the read model is
   seeded until then.
4. **Decision:** **Close Slice** ✅ — owner signed off 2026-07-22.

*Owner notes carried forward (S2+):* (i) never let the **dev seed drive design** — seed = demo only,
API = contract, UI = consumer; (ii) the summary-strip-as-filter realises **navigate by work, not
implementation** — keep it; (iii) **do not expand the Missions list into an ERP** — the new **List-vs-
Detail rule** (added to the Design Review Checklist): *if the user needs a fact to decide "open the
mission", it stays in the list; if they need it after opening, it belongs in Mission Detail.*
