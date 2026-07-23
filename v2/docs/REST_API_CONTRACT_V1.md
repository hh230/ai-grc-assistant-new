# AI GRC Platform — REST API Contract (V1) · **APPROVED**

> **Derived from the Screen-Flow state machines, not from resources.** The API is the *programmatic
> expression of the system's events* — so if the UI changes, the API does not, because its source is
> **behaviour**, not screen shape. Commands come first (they are the state-machine events); resources
> and queries serve them. Every command maps to a real Core operation.
>
> **Status:** draft for approval. **Base:** `/v1` · JSON · OIDC Bearer auth · tenant-scoped from the
> token. **Last updated:** 2026-07-22.

---

## 1. Design principles

- **Event-driven, not resource-CRUD.** Endpoints are **Commands** (state transitions) and **Queries**
  (reads) — never generic `PUT /resource`. The command set *is* the Screen-Flow event set.
- **Mission-centric.** The Mission is the aggregate; almost every command acts on one.
- **Idempotent commands.** Every consequential `POST` accepts an `Idempotency-Key` header; replaying it
  returns the same result (the Core carries a mission `idempotency_key`). Running/approving an already-
  advanced mission is a safe no-op returning current state.
- **Async-ready (sync in V1).** V1 runs synchronously (fast feel), but the shape does not assume it:
  `run` returns the mission's current state and the client **polls**; when execution later moves to a
  background worker, the *same* contract holds (the mission just transitions over more polls).
- **Tenant-scoped, fail-closed.** Every request is bound to the token's tenant; another tenant's data
  is never returned — a cross-tenant reference resolves to `404` (existence is not revealed).
- **Evidence-first.** Any response carrying a GRC claim carries its **citations/provenance**
  (`source_ids` → documents/controls). Deliverables carry per-section citations and coverage.
- **Role-guarded.** Commands declare the required role (**Practitioner / Approver / Admin**).
  *(Enforcement is a Domain-Model §3 gap — the contract defines the guards; wiring them is pending.)*

---

## 2. Resource model *(the nouns commands & queries reference — representations hide implementation)*

| Resource | Fields (representation) | Notes |
|---|---|---|
| **Mission** | `id · type · scope · status · plan · findings · approvals · created_at · updated_at` | `status` ∈ Draft·Running·WaitingApproval·Completed·Failed·Archived |
| **Plan** | `version · steps:[{ id · description · enabled }]` | **human-readable** steps only — **no tool names** (Visibility ❌) |
| **Finding** | `step_id · title · summary · citations:[…] · confidence?` | the visible view of a step result |
| **Approval** | `id · step_id · status · proposed_action · evidence:[…] · decided_by? · decided_at?` | one entity; the queue is a cross-mission view |
| **Deliverable** | `mission_id · title · sections:[{ heading · body · citations · confidence? }] · coverage?` | **derived** from the mission; not stored |
| **Document** | `id · filename · evidence_kind · status · uploaded_at · size` | `evidence_kind` ∈ policy·procedure·standard·soc_report·risk_register·other · `status` ∈ ingesting·ready·failed · `size` in bytes |
| **Framework / Control** | `id · name · version · controls:[{ code · title · domain }]` | read-only catalog |

*Never represented (Visibility ❌): tools, pipeline, chunks, executor, store — no field exposes them.*

---

## 3. Commands *(state-machine events → endpoints)*

| Event (Screen Flow) | Endpoint | Core operation | Role · Guards · Idempotency | Result (new state) |
|---|---|---|---|---|
| **Create Mission** | `POST /v1/missions` `{type, scope, document_ids?}` | `engine.create` + `engine.plan` | Practitioner · type ∈ the 6 · `Idempotency-Key` | Mission **Draft** + the human-readable plan |
| **Steer Plan** | `PATCH /v1/missions/{id}/plan` `{steps:[…] | {step_id,enabled}}` | re-plan (new plan version) | Practitioner · mission **Draft** · ≥1 enabled step | Mission **Draft** (updated plan) |
| **Run Mission** | `POST /v1/missions/{id}/run` | `engine.execute` | Practitioner · mission **Draft** · idempotent no-op if already run | **Running** / **WaitingApproval** / **Completed** |
| **Approve Step** | `POST /v1/missions/{id}/approvals/{step_id}/approve` `{comment?}` | ADR 0044 approve **+ resume** | **Approver** · mission **WaitingApproval** at that step · idempotent | Mission resumes → **Running** / **Completed** |
| **Reject Step** | `POST /v1/missions/{id}/approvals/{step_id}/reject` `{comment?}` | ADR 0044 reject | **Approver** · same guard | **Failed** (stopped, fail-safe) |
| **Resume Mission** | `POST /v1/missions/{id}/resume` | `resume_if_approved` | Practitioner/Approver · only if an approved gate awaits driving | **Running** / **Completed** *(usually implicit in Approve — explicit for out-of-band approvals)* |
| **Re-run Mission** *(was "Retry", ⚠️ see note)* | `POST /v1/missions/{id}/rerun` | `engine.create` a **new** mission with the failed one's type/scope/documents | Practitioner · source mission **Failed** | a **new** mission **Draft** (the failed one stays as an audit record) |
| **Upload Documents** | `POST /v1/documents` (multipart) `{file, evidence_kind}` | `knowledge-runtime` ingest **+ project a Document** | Practitioner · file type supported · `evidence_kind` ∈ the 6 · `Idempotency-Key` | Document(s) **ingesting → ready** |

*Note: **Create Mission returns the plan** (create+plan) and **Run is separate** — this is exactly Screen
Flow 1 (Plan Review before Run), and why there is no "create-and-run" shortcut in V1.*

*⚠️ **Re-run (Slice S2 finding, owner-decided):** the original contract assumed a `retry` that re-drove a
failed mission (Failed → Running). Implementation surfaced that the frozen Core makes **FAILED terminal**
(lifecycle: FAILED → ARCHIVED only), so retry-in-place is impossible. Retry is therefore **redefined as a
re-run** — it `engine.create`s a **new** mission from the failed one's inputs, leaving the failed mission as
an audit record. No Core change; it lands with the **create flow (Slice S7)**, not S2. The `approve`/
`reject` commands were unaffected and shipped in S2.*

*⚠️ **`evidence_kind` + `size` on Document (Slice S4 finding, owner-decided, 2026-07-22):** the Reality
Gate for Knowledge found the product depends on **Evidence Collections**, which cannot be derived without
an evidence classification on the Document — yet the Document entity omitted it (a gap between the Product
Contract and this REST Contract, **not** between product and implementation). Corrected here, consistent
with the entity table's own pattern (Mission already carries the product-projection fields `type`/`scope`
that the Core aggregate does not store). The field is named **`evidence_kind`** — deliberately not
`*_type`, since "type" is already overloaded (Mission Type · Content-Type · MIME type · Result type); this
is a **classification of evidence** (`policy·procedure·standard·soc_report·risk_register·other`), so
`kind` reads truer. **`size`** (bytes) is added at the same time — an intrinsic file property, cheaper to
add now than to break the contract for later. No other fields. Grouping into Collections stays
**presentation** (the client groups `GET /v1/documents` by `evidence_kind`); no `GET /collections`
endpoint is added — the same discipline as "Mission List isn't stored by the Core" and "Result ≠
Deliverable".*

---

## 4. Queries

| Query | Endpoint | Returns | Core support |
|---|---|---|---|
| **Dashboard** *(landing)* | `GET /v1/dashboard` | one **Dashboard Projection** — "system state now": attention counts (waiting·running·failed) · recently completed · **coverage snapshot** | ⚠️ **reads a projection** (composes `mission-read-model` + a coverage rollup; §3, Slice S5) |
| **Mission Status** *(the poll endpoint)* | `GET /v1/missions/{id}` | full mission: status · plan · findings(+citations) · approvals | ✅ |
| **Mission List** | `GET /v1/missions?status=&type=&page=` | this tenant's missions | ⚠️ **needs a list-by-tenant read port** (Domain §3) |
| **Deliverable** | `GET /v1/missions/{id}/deliverable` | the derived deliverable (sections·citations·coverage) | ✅ (derived; `409` if not Completed) |
| **Deliverables (index)** | `GET /v1/deliverables?page=` | all deliverables (each links to its mission) | ⚠️ **needs a read model** (derive/list) |
| **Approvals (queue)** | `GET /v1/approvals?status=waiting` | cross-mission items awaiting a decision | ⚠️ **needs list read** · Approver |
| **Knowledge** | `GET /v1/documents` | the tenant's documents + ingestion status | ⚠️ **needs a documents read model** |
| **Library** | `GET /v1/frameworks` · `GET /v1/frameworks/{id}` | framework catalogs → controls | ✅ |

*⚠️ **Dashboard = a Projection, not a God endpoint (Slice S5 finding, owner-decided, 2026-07-22):** the
Dashboard View existed in the Wireframes but §4 listed no query for it. Added as `GET /v1/dashboard`, and
deliberately shaped as a **read of one Dashboard Projection** representing "system state now" — the
endpoint carries **no business logic**. The source of truth is unchanged (`mission-read-model` for the
attention counts / recently-completed; the Gap Results for coverage); a thin **coverage rollup** + a
**Dashboard Projection** compose them behind the read. Flow: `mission-read-model → coverage rollup →
Dashboard Projection → GET /v1/dashboard`, never `GET /v1/dashboard → query missions → query results →
aggregate`. The coverage figure is a **Coverage Snapshot** (a point-in-time picture from the latest
completed Gap Assessments) — **not** a compliance "Coverage %", consistent with Result ≠ Report and
Dashboard ≠ Analytics.*

---

## 5. Error model

Uniform shape: `{"error": {"code": "...", "message": "...", "details": {...}?}}`.

| HTTP | code | When |
|---|---|---|
| 400 | `validation_error` | malformed body / bad params |
| 401 | `unauthorized` | missing/invalid token |
| 403 | `forbidden` | role not permitted (e.g. non-Approver approving) |
| 404 | `not_found` | absent — **or cross-tenant** (existence not revealed; fail-closed) |
| 409 | `conflict` | illegal transition (run a non-Draft, approve a non-waiting step, deliverable before Completed) |
| 422 | `unprocessable` | e.g. steering to an empty plan |
| 500 | `internal_error` | never leaks provider/SDK detail (Principle: honest, safe) |

Transitions are guarded by the **mission's state** — the API can only trigger a legal event; an illegal
one is a `409`, never a silent wrong action.

---

## 6. Polling contract

- `GET /v1/missions/{id}` is the single progress source. It returns `status`, `progress`
  (`steps_completed / steps_total`), the current state, and `updated_at` (+ `ETag`).
- The client polls while `status ∈ {Running}` (and briefly around `WaitingApproval`) — suggested 1–2s;
  supports `If-None-Match` for cheap 304s.
- **Async-ready:** identical contract when execution moves to a background worker — `run` returns
  immediately with `Running`, and the state advances over subsequent polls. **No WebSocket/SSE in V1**
  (Principle 10: never block; poll suffices for fast missions).

---

## 7. Export contract

- `GET /v1/missions/{id}/deliverable/export?format=md|docx|pdf`
- Returns the file **bytes** with `Content-Type` (`text/markdown` · `application/vnd.openxmlformats-
  officedocument.wordprocessingml.document` · `application/pdf`) and `Content-Disposition: attachment;
  filename="…"`. Maps to the `deliverables` package exporters.
- Guard: mission **Completed** (else `409`). The deliverable is **derived, not editable** — there is no
  write/PUT for a deliverable (Principle 6).

---

## Cross-cutting

- **Auth:** OIDC Bearer; tenant + principal + roles resolved from the token.
- **Versioning:** `/v1`; breaking changes → `/v2`.
- **Idempotency:** `Idempotency-Key` on all consequential `POST`s (maps to the Core mission idempotency).
- **RBAC:** guards above are the **contract**; enforcement (a policy hook reading `required_roles`) is a
  Domain-Model §3 gap to build.

## Backend work this contract implies *(from Domain-Model §3 — additive, no frozen break)*

1. A **list/query read port** (Mission List · Approvals Queue · Deliverables Index — one read, filtered).
2. A **Documents read/store model** (upload metadata, ingestion status, list).
3. **Deliverable** derivation/caching for the index.
4. **Auth + tenancy** layer and **RBAC enforcement** hook.
5. **pgvector** persistence for the tenant knowledge base.

*Everything else in this contract is already supported by the frozen Core.*

---

## Where this sits

1. ✅ Vision · 2. ✅ Spec · 3. ✅ Domain Model · 4. ✅ IA · 5. ✅ Interaction Principles · 6. ✅ Screen
Flows · **7. REST API Contract (this)** → 8. Wireframes (low-fidelity) → 9. Frontend → 10. Backend
additions (exactly the list above). *The API's source is behaviour; the wireframes render the same
states this contract already commits to.*
