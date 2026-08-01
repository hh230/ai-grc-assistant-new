# AI GRC Platform — Conceptual Domain Model (V1) · **APPROVED**

> **The bridge between the Product Specification and the Architecture** — the official contract between
> product language and the Core, and the source the Information Architecture, Screen Flows, and API are
> derived from.
>
> **Founding rule.** *The Conceptual Domain Model describes the **user's mental model**, not the
> implementation model.* Every concept **maps** to the implementation, but the implementation must
> **never leak** into the language of the product.
>
> **Governing rule.** Every object the user sees has an **Owner** (aggregate root), an **Identity**, and
> a **Lifecycle** — the DDD aggregate discipline (CLAUDE.md §15) in product language.
>
> **This document describes; it does not plan.** §3 lists what the Core does *not* support today —
> *candidate* solutions only, not committed work (some gaps may change or disappear once the IA is
> designed). **Core Support:** ✅ today · ⚠️ additive extension (no frozen break) · ❌ absent (new).
> **User Visibility:** ✅ shown · ⚠️ partial (curated view only) · ❌ never surfaced. **Status:**
> approved by the owner. **Last updated:** 2026-07-20.

---

## 1. The object catalog

Each object: **Core Mapping · Owner · Identity · Lifecycle · Relationships · V1/Later · Core Support ·
User Visibility.**

### Workspace
- **Core:** `TenantContext` (a context on every operation — *not* a stored aggregate). **Owner:** the
  Organization. **Identity:** `tenant_id`. **Lifecycle:** created at onboarding → active.
- **Relationships:** *owns* Missions, Documents, Deliverables, Knowledge, Users.
- **V1** · **Core Support:** ⚠️ *(context exists; org provisioning + settings unbuilt).* · **Visible:** ✅

### Mission ⭐ *(the unit of work)*
- **Core:** `Mission` (mission-engine aggregate; persisted). **Owner:** itself, within a Workspace.
  **Identity:** `mission_id`. **Lifecycle:** Draft → Running → Waiting for approval → Completed /
  Failed → History.
- **Relationships:** *belongs to* 1 Workspace · *has* 1 Plan · *produces* 1 Deliverable · *cites* many
  Documents · *assessed against* 1 Framework (V1) · *has* 0..n Approvals.
- **V1** · **Core Support:** ✅ · **Visible:** ✅

### Mission Type *(what kind of work)*
- **Core:** `Capability` + `MissionType`. **Owner:** system catalog. **Identity:** capability id.
  **Lifecycle:** static. **Relationships:** a Mission *is of* 1 Type.
- **V1 — exactly six** (Ask · Gap Assessment · Risk Assessment · Policy Generator · Vendor Review · ISO
  Controls) · **Core Support:** ✅ · **Visible:** ✅

### Plan
- **Core:** `Plan` (versioned) + `PlanStep`. **Owner:** Mission. **Identity:** plan `version`.
  **Lifecycle:** created at planning; **steered** before run; re-plan = new version.
- **Relationships:** *owned by* 1 Mission · *contains* 1..n Steps.
- **V1** · **Core Support:** ✅ remove/reorder; ⚠️ disable-but-keep (no skip flag) · **Visible:**
  ⚠️ **partial** — a *human-readable* plan (steps as verbs, steerable), never raw structure/tools.

### Step
- **Core:** `PlanStep` (definition) + `StepResult` (outcome). **Owner:** Plan / Mission. **Identity:**
  `step_id`. **Lifecycle:** defined → executed → result recorded (citations/confidence).
- **Relationships:** *belongs to* 1 Plan · *may require* 1 Approval · *cites* Documents.
- **V1** · **Core Support:** ✅ · **Visible:** ⚠️ **partial** (surfaced as *Findings*, below; the raw
  step/tool is hidden).

### Findings *(the visible view of execution — not a separate entity)*
- **Core:** the Mission's `step_results`, curated. **Owner:** Mission. **Identity:** none of its own.
  **Lifecycle:** exists once steps run; shown for **transparency** (Principle #2).
- **V1** · **Core Support:** ✅ · **Visible:** ✅ *(this is the presentation of the ⚠️-partial step
  results — what/why/sources, not internals).*

### Approval
- **Core:** `Approval`/`ApprovalRequest`/`ApprovalDecision` (ADR 0044 — a value object on the Mission).
  **Owner:** a **Mission Step** (the consequential one). **Identity:** approval id. **Lifecycle:**
  requested at the gate → approved/rejected (who/when) → mission resumes.
- **Relationships:** *belongs to* 1 Step; the **Approvals Queue** is a cross-mission *view* of the same
  entity (one entity, two perspectives).
- **V1** · **Core Support:** ✅ entity + gate/resume; ⚠️ the queue view. Product decision pending:
  *which* actions are consequential. · **Visible:** ✅

### Deliverable ⭐ *(the sellable artifact — a Representation, not a stored object)*
- **Core:** the `deliverables` package, **derived** from a completed Mission (Deliverable / Gap Matrix
  + MD/DOCX/PDF export). **Owner:** Mission. **Identity:** the mission's id (no independent id).
  **Lifecycle:** **produced on demand from the mission; not stored** — may be **cached later for
  performance only** (never a standalone object). It is a *representation of the mission*, which keeps
  the model clean: no deliverable versioning, editing, regeneration, or survival-after-delete
  questions in V1, and approval is on the **Mission**, never on the deliverable.
- **Relationships:** *produced by* 1 Mission · *references* Controls · *references* Evidence.
- **V1** · **Core Support:** ✅ build + export; ⚠️ browsing a *list* (derived, see §3) · **Visible:** ✅

### Knowledge *(the tenant's private evidence base)*
- **Core:** `TenantKnowledgeBase` (in-memory) over tenant-scoped `CorpusChunk`s. **Owner:** Workspace.
  **Identity:** tenant-scoped. **Lifecycle:** grows via ingestion; queried tenant-isolated (fail-closed).
- **Relationships:** *owned by* 1 Workspace · *contains* many Documents.
- **V1** · **Core Support:** ⚠️ ingestion + retrieval exist, but **in-memory** (needs pgvector for
  prod). · **Visible:** ✅ (the Knowledge area)

### Document *(uploaded evidence)*
- **Core:** the file → `CorpusChunk`s (`document_id`); a manifest at import. **Owner:** Knowledge.
  **Identity:** `document_id`. **Lifecycle:** uploaded once → ingested → **cited by many missions** →
  (deleted?).
- **Relationships:** *cited by* **many** Missions (n:n, by reference — never copied).
- **V1** · **Core Support:** ⚠️ chunks carry `document_id`, but no Document aggregate for management
  (metadata, status, list, delete). · **Visible:** ✅

### Evidence *(a role, not an owned object)*
- **Core:** the Documents a Mission/Step *cites* (`source_ids`). **Owner:** Knowledge (as Documents) —
  the Mission **references**, never owns. **Identity:** the referenced ids. **Lifecycle:** that of the
  Document.
- **Relationships:** a Mission *cites* Evidence · a Deliverable *references* Evidence.
- **V1** · **Core Support:** ✅ (references are first-class) · **Visible:** ✅ (as citations —
  Principle #2)

### Framework
- **Core:** `Framework` (frameworks-as-data). **Owner:** system catalog. **Identity:** framework id.
  **Lifecycle:** versioned data (new framework = a JSON file).
- **Relationships:** *defines* many Controls · a Mission is *assessed against* 1 (V1); changing it =
  re-plan.
- **V1:** ISO 27001 (CIS, NIST loaded) · **Core Support:** ✅ · **Visible:** ✅ (Library)

### Control
- **Core:** `Control`. **Owner:** Framework. **Identity:** control id (`iso_27001:A.8.5`).
  **Lifecycle:** static data. **Relationships:** *defined by* 1 Framework · *referenced by*
  Deliverables.
- **V1** · **Core Support:** ✅ · **Visible:** ✅

### User & Role
- **Core:** `TenantContext.principal_id` + `roles`; `ToolSpec.required_roles` (declared, **not
  enforced**). **Owner:** Workspace. **Identity:** principal id. **Lifecycle:** provisioned at
  onboarding.
- **Relationships:** a User *has* 1 of 3 roles — **Practitioner · Approver · Admin**.
- **V1** · **Core Support:** ⚠️ roles in context, but no user store / auth / enforcement · **Visible:** ✅

### Dashboard *(a read model, not a stored aggregate)*
- **Core:** none — an aggregation over Missions / Deliverables. **Owner:** Workspace. **Lifecycle:**
  computed on read.
- **V1** (basic) · **Core Support:** ⚠️ needs read models · **Visible:** ✅

### Source *(connected system)*
- **Core:** none. **Owner:** Knowledge. **Later** (M365 / cloud / IAM / ticketing) · **Core Support:**
  ❌ · **Visible:** shown as *coming soon* only.

### Not user-visible — implementation only (❌)
Per the founding rule, these **never appear in product language**: **Tool** · **Pipeline / AI
Orchestrator** · **CorpusChunk** (the user sees the *Document*, not its chunks) · **RegistryExecutor** ·
**Event Bus / Outbox** · **Mission Store**. The IA and UI must not surface them.

---

## 2. Relationships (logical, verbed)

```
Workspace (Tenant)
   ├── owns ──► Documents, Missions, Deliverables, Knowledge, Users

Mission
   ├── is of ───────────► Mission Type        (1 : 1)
   ├── has ─────────────► Plan → Steps → Approval?   (1:1 · 1:n · 0:1 per consequential step)
   ├── has ─────────────► Findings            (view of step results)
   ├── produces ────────► Deliverable          (1 : 1 in V1)
   ├── cites ───────────► Documents (Evidence) (n : n, by reference)
   └── assessed against ► Framework            (1 : 1 in V1; n later)

Framework ── defines ──► Controls              (1 : n)
Deliverable ── references ──► Controls, Evidence   (n : n)
Approval ── belongs to ──► Step  (surfaced in the Approvals Queue view)
Document ── cited by ──► many Missions         (n : n)
```

**Cardinality (V1) — owner-confirmed:** Mission→Deliverable **1:1** · Deliverable→Framework **1** (V1) ·
Document↔Mission **n:n by reference** · Approval→**Step** (not the whole mission) · Framework **chosen at
creation** (change = re-plan).

---

## 3. Gaps — *what the Core does not support today* (description, not a plan)

Candidate solutions are **options to consider**, not committed work — the IA may change or remove some.

| Gap | Reason | Impact | Candidate solution(s) |
|---|---|---|---|
| **Mission List** (per tenant, filterable) | store port is get/save/find-by-key only | the Missions area can't be populated | a list/query **read** port (ADR 0043 §2 already flags this) |
| **Deliverables Index** (browse all) | deliverable is **derived, not stored** | can't list deliverables directly | derive+list from missions, or a read model / perf cache |
| **Approvals Queue** (cross-mission) | no list-by-tenant read | the reviewer's queue can't be built | reuse the list read, filtered to *Waiting for approval* |
| **Document management** (list/status/delete) | only chunks are stored | Knowledge area is thin | a Documents read/store model over the ingested chunks |
| **Dashboard** (counts, coverage %) | no read models | no at-a-glance view | aggregations / read models over missions + deliverables |
| **Tenant Knowledge persistence** | `TenantKnowledgeBase` is in-memory | not production-durable | migrate to **pgvector** (same provider interface) |
| **Auth + tenant/user provisioning** | no auth/user store | no real multi-user | an auth/tenancy layer (OIDC/SSO) |
| **RBAC enforcement** (3 roles) | `required_roles` declared, unenforced | roles are cosmetic | a policy hook at the executor/orchestrator |
| **Plan "disable/skip" a step** | no per-step enabled flag | steering is remove/reorder only | additive per-step *enabled* flag |
| **Which steps are consequential** | no capability gates yet | approvals never trigger | *product* decision — Core already gates |
| **Connectors (Sources)** | none | uploads only | later / Enterprise |
| **Background / async missions** | synchronous only | long missions block "fast feel" | later — mission-lease ADR when needed |
| **Notifications** | none | no out-of-app signal | later / Enterprise |

---

## 4. Where this sits in the sequence

1. ✅ Product Vision · 2. ✅ Product Specification · **3. ✅ Conceptual Domain Model (this)** → 4.
Information Architecture → 5. Screen Flows → 6. Wireframes → 7. REST API (derived) → 8. Frontend → 9.
Backend additions (only to close real gaps from §3).

*Each layer derives from the one above. This model is the **contract**: the IA is its navigational
projection over the **user-visible** objects, the screens render those objects, the API exposes their
operations, and the backlog is whatever §3 turns out to require after the IA.*
