# V1 Execution Plan — Vertical Slices

> **Product Design Foundation is 🧊 Frozen** (2026-07-22). This plan is the *derivative*: how we turn the
> nine Foundational Documents into working software **vertically** — one usable View at a time — not
> horizontally (all backend, then all frontend).
>
> Governed by [PRODUCT_DEVELOPMENT_PROCESS.md](./PRODUCT_DEVELOPMENT_PROCESS.md) (routing + freeze rule).
> **Status:** ready to execute (human-led). **Last updated:** 2026-07-22.

---

## Why vertical, not horizontal

Horizontal work (finish all backend, then all frontend) produces layers no one can try until the end.
**Vertical slices** each cut through the stack, so every slice is **usable and reviewable against the
Foundation** the moment it lands. This is how we keep "the product drives the code" honest during
implementation.

**Each slice starts from acceptance, not from the technical layer.** The sequence is inverted:

```
Execution Contract → Backend → API → Frontend → Acceptance Verification → Slice Retrospective → Closed
(what = success)                                   (did we meet it?)        (what did we learn?)
```

A slice closes only after a **Slice Retrospective** (half a page, appended to its Execution Contract):
did we edit any Foundational Document? · what did we learn? · does it affect the next slice? · Close or
Rework. Every slice is a **Learning Unit** — and the retrospective is where the Freeze rule is measured.

*Acceptance appears twice* — as **definition** (a one-page Execution Contract in `docs/execution/`, written
**before** any code) and as **verification** (the slice is done only when it passes). We do **not** start
from Read Models; we start from *"what will the user count as success?"* — then derive the backend from it.
Verification = the View passes the **Design Review Checklist** (Gate 0 → Gate 7) **and** the contract's
Given/When/Then + UX metrics hold.

---

## The Product API Host *(fixed 2026-07-22 — ADR 0052)*

All endpoints in the REST API Contract are served by **one official host: `v2/apps/grc-api`**
(FastAPI) — a **Composition Root only** (Auth · Tenant Context · Read Models · Mission Engine/Runtime
· Tool Registry · Routes); business logic stays in `v2/packages/*`. It composes v2 packages
exclusively and never touches the old `apps/`/`packages/` generation. The frontend host is a separate
decision, taken at S1's frontend step.

## Enabling layer (the minimum backend that makes Views alive)

These are the **Domain-Model §3 gaps** — additive, no frozen-Core break — built thin, only as far as the
first slices need. **No RBAC expansion yet** (the API contract already declares the role guards; we wire
identity + tenant first, enforcement later).

1. **Read Models** — the list-by-tenant reads three Views depend on:
   - `list_missions(tenant)`
   - `list_deliverables(tenant)` *(derived — not a new stored object; Domain Model rule)*
   - `list_pending_approvals(tenant)`
2. **Auth + Tenant Context** — user identity · tenant · context propagation end-to-end (fail-closed).
   *RBAC enforcement deferred; the guards stay declared in the API contract.*
3. **Document Store** — upload metadata + ingestion status + list (Knowledge View depends on it).

*(pgvector persistence for the tenant knowledge base is the remaining §3 gap — scheduled with the slice
that first needs real retrieval, not before.)*

---

## The slices (each: Execution Contract → Backend → API → Frontend → Verification)

| # | Slice (View) | Depends on | Acceptance (against the docs) |
|---|---|---|---|
| **1** | **Mission List** | Read Models · Auth/Tenant | see this tenant's missions with real status; Gate 0–7 pass |
| **2** | **Mission Detail** (Work Surface) | Slice 1 · poll `GET /missions/{id}` | open a mission, watch it run, see findings+citations; five state variants render |
| **3** | **Deliverable** | Slice 2 · derive + export | read a completed deliverable, verify a citation, export MD/DOCX/PDF; Trust Bar present |
| **4** | **Knowledge** | Document Store | upload a document, see ingestion status, grouped by evidence type |
| **5** | **Dashboard** | Read Models | "what needs my attention?" — waiting/running/failed ordered |
| **6** | **Approvals** | Read Models · Auth (Approver) | decision queue; approve/reject drives the mission |
| **7** | **New Mission + Mission Created** | `POST /missions` · `PATCH /plan` · `POST /run` | create → confirm (summary+plan) → run; steer the plan |

*Order rationale:* Mission List is the spine (every journey reaches a mission through it); Mission Detail is
the product's centre; Deliverable closes Time-to-Deliverable. Knowledge/Dashboard/Approvals/New-Mission
follow once the spine is live. (Library · Settings remain minimal in V1.)

---

## Definition of Done for a slice

- [ ] **Execution Contract written first** (`docs/execution/S<n>_<NAME>.md`) and approved — before code.
- [ ] Backend gap built additively (no frozen-Core change); tenant-scoped, fail-closed; tests green
      (`uv run pytest`, ruff, mypy --strict).
- [ ] API matches the **REST API Contract** exactly (no invented endpoints; declared guards present).
- [ ] Frontend renders the **Wireframe** View and its state variants; Empty/Loading/Error/Success defined.
- [ ] **Design Review Checklist** run on the View → *Approved* (Approval block recorded).
- [ ] The user journey the View backs actually works end-to-end.
- [ ] **No Foundational Document edited** — unless implementation contradicted one, in which case it was
      stopped, the doc fixed with approval, then resumed (the Freeze rule).
- [ ] **Slice Retrospective** appended to the Execution Contract; decision = **Close Slice**.

---

*From here: implementation is the derivative. Any change in vision or behaviour goes back to the documents
first, then into the code — never the reverse. **The product drives the code.***
