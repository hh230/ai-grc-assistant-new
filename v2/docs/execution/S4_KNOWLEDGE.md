# Slice S4 — Knowledge (the tenant's Evidence)

> The first slice out of the Mission world and into Knowledge. It feeds every mission the customer's
> own data (P1). Derived from the **Knowledge** View ([../WIREFRAMES_V1.md](../WIREFRAMES_V1.md)) and
> the Knowledge / Upload endpoints ([../REST_API_CONTRACT_V1.md](../REST_API_CONTRACT_V1.md) §3, §4).
> **Status:** ✅ **CLOSED** (owner sign-off 2026-07-22, *Approved with changes* — both applied). Two
> design rules — *Evidence Collections are the unit* and *Upload is an event / a Document is an
> entity* — and one Freeze finding: `evidence_kind` + `size` added to the REST Contract's `Document`
> (its S4 footnote). Owner changes at review: `Other` → **Unclassified**; Reality-Gate-caught-four
> recorded as a methodology Metric. **Last updated:** 2026-07-22.

---

## Reality Gate — what the system actually provides (before any commit)

*Filled first, per the process. First the **Source of Truth**, then "what can the system do / store
today?" — never "what do we want to show?"*

**Source of Truth for this slice:** **Knowledge Runtime** (owns *ingestion* — turning an uploaded file
into retrievable chunks) **+ a Document Projection** (the read side S4 builds — owns *"a document exists,
of this evidence type, with this ingestion status"*). Two owners, deliberately: ingestion is a process,
the document is a record.

| Knowledge element | Exists today? | Note |
|---|---|---|
| Chunk ingestion (for retrieval) | ✅ `knowledge-runtime` (`TenantKnowledgeBase`, `ingest_document`) | stores **chunks**, not documents |
| Chunk `category` | ✅ (ingest `category`, default `"customer_documents"`) | a retrieval tag — **not** the evidence type |
| A **document record** (filename · status · uploaded_at) | ❌ **not stored anywhere** | a Domain §3 gap — **must be built** |
| List a tenant's documents | ❌ | needs the read model |
| **`evidence_kind`** (Policy/Procedure/…) | ❌ | a **product field** set at upload; not derivable from the chunk category. *Named `evidence_kind`, not `*_type` (overloaded) — REST Contract S4 footnote* |
| Upload endpoint | ❌ | a §3 gap |

**Finding:** like S1, the read side does not exist — there is **no Document store**. S4 therefore
**builds a product-owned Document read model** (the same pattern as `mission-read-model`): a tenant-
scoped projection `{document_id · tenant_id · filename · evidence_kind · status · uploaded_at · size}`,
written at upload, read by the Knowledge View. Ingestion (chunks) stays `knowledge-runtime`'s job behind
it.

> **Freeze finding (owner-decided, 2026-07-22).** Filling this gate surfaced a real contradiction: the
> approved design needs an evidence classification on the Document, but the **frozen REST API Contract**
> defined `Document` as `id · filename · status · uploaded_at` — no such field. A gap between the Product
> Contract and the REST Contract (not between product and code) → the REST Contract was corrected (its
> S4 footnote), consistent with how Mission already carries product-projection fields. The field is named
> **`evidence_kind`** (not `*_type`: "type" is overloaded — Mission Type · Content-Type · MIME · Result
> type — and this is a *classification*), and **`size`** (bytes) was added at the same time as an
> intrinsic file property. This is S4's Freeze catch, the peer of S1 (`type`/`scope`) and S2 (`retry`).

---

## Design rule 1 (owner) — Knowledge = **Evidence Collections**, not a File Manager

**The product is not Dropbox.** The user does not want files; they want **Evidence**. And the unit they
work with is the **collection**, not the file. The UI model is:

```
Knowledge  →  Evidence Collections (by type)      ┐
   Policies (12)                                  │  the collection is the unit —
   Procedures (8)                                 │  a named group of evidence,
   Standards (4)                                  │  with a count
   SOC Reports (2)                                │
   Risk Registers (1)                             ┘
        └─ open a collection → the evidence inside it (the individual documents/versions)
```

**not** `Knowledge → documents → pdf/docx/xlsx`. Grouping is by **evidence type**, never by folder or
format. The *file* is the implementation, hidden behind its **evidence role**.

**Why the collection is the unit (not the file):** it makes future growth *natural without a UI redesign*
— revisions, a new version of the same policy, or several files for one control all live **inside** a
collection. If the file were the unit, every one of those would force the screen to change. Modelling the
collection now buys that room for free.

## Design rule 2 (owner) — **Upload is an event; a Document is an entity** (never fuse them)

The most consequential architectural rule of this slice. Do **not** make "Upload" and "create a Document"
the same thing. The contract speaks in four distinct steps — **even though S4's implementation performs
them in one synchronous call:**

```
Upload            an event: the user submits a file + its evidence type
   ↓
Ingestion         knowledge-runtime turns the file into retrievable chunks
   ↓
Document Projection   the product-owned read record appears  {filename · evidence_kind · status · size …}
   ↓
Evidence Collection   the document is shown inside its collection (grouped by type)
```

Keeping these separate in the *language* is what lets us add — with no redesign — a **re-upload** of the
same policy, a **new version**, **OCR**, **re-processing**, **re-index**, **delete a version**, or
**re-extraction** later: each is a new event or a status change against an existing Document entity, not a
new fused "upload = document". Fuse them today and every one of those becomes a rewrite. So `status`
(`ingesting → ready | failed`) models the **ingestion lifecycle** of a Document, not a property of an
upload — S4 collapses it to one call, but the seam is drawn where growth will need it.

---

**Goal.** Let a tenant see and grow its evidence — grouped in GRC language, with ingestion status — so
missions have real customer data to work on.

**User question (rule 11):** *"What evidence do we have?"* · **Primary decision:** is my evidence ready
(and upload more). *(Knowledge is a navigation/management view — **no Trust Bar**; that is only for
views that end in a decision.)*

---

**Given / When / Then**

```
Given   a tenant T with documents of several evidence types (and another tenant T2 with its own),
When    the user opens Knowledge,
Then    they see **Evidence Collections** first — one per evidence type, each with its **count**
        (Policies (12) · Procedures (8) · Standards (4) · SOC Reports (2) · Risk Registers (1) · Other)
        — never a flat file list; the collection is the unit;
When    the user opens a collection,
Then    they see the **evidence inside it** — each document with its filename and **ingestion status**
        (ingesting · ready · failed);
And     the user can **Upload** a document, choosing its evidence type; the upload is ingested and a new
        Document appears in that collection as "ingesting" then "ready";
And     T never sees T2's documents or collections (fail-closed);
And     no chunk ids, embeddings, or pgvector detail ever appear — only the document + its status.
```

---

**UX Metrics** (targets — a "No" is a finding)

- Clicks to reach Knowledge: **1** (sidebar).
- Clicks to upload: **≤ 2**.
- Grouping is by **evidence type**, not folders/format.
- Cross-tenant leakage: **0** (asserted by test).

---

**APIs used** (from the REST API Contract; the read model + upload are the Domain §3 gap S4 builds)

- `GET /v1/documents` → this tenant's documents + ingestion status (grouped client-side by type).
  *(⚠️ needs the new Document read model.)*
- `POST /v1/documents` (multipart) `{file, evidence_kind}` → ingest via `knowledge-runtime`; project the
  document into the read model; status `ingesting → ready`. Practitioner · idempotency key.

---

**Referenced Design Checklist** — View: **Knowledge**

- **Gate 0** delete test: removing it breaks feeding missions the customer's data (P1).
- **Gate 1** **user language — Evidence, not files**; grouped by evidence type; the file is hidden.
- **Gate 5** every action ↔ a real endpoint (`GET`/`POST /v1/documents`).
- **Gate 6** one question / one decision; Empty/Loading/Error/Success defined; **no Trust Bar** (not a
  decision view).
- **Gate 7** tenant-scoped, fail-closed; no chunk/embedding/pgvector internals exposed.

---

**Done Definition**

- [ ] A **Document read model** (product projection): tenant-scoped, fail-closed; documents with
      `filename · evidence_kind · status · uploaded_at · size`; list-by-tenant **and** collections-by-kind
      (evidence_kind + count) so the collection can be the unit. (Postgres adapter + in-memory, like
      `mission-read-model`.)
- [ ] The write path is expressed as **Upload → Ingestion → Document Projection** (rule 2): the endpoint
      ingests via `knowledge-runtime`, **then** projects a Document; `status` models the ingestion
      lifecycle of the Document, not a property of the upload. One call today; seam drawn for growth.
- [ ] `GET /v1/documents` returns the tenant's documents; `POST /v1/documents` uploads (ingest + project);
      status transitions surfaced.
- [ ] Frontend **Knowledge** view — **Evidence Collections first (name + count), open one to see its
      evidence**; ingestion status; Upload (with type); Presenter→Client; Empty/Loading/Error/Success.
      "documents/files/folders" never shown as the model; the **collection is the unit**.
- [ ] Tests green: `uv run pytest` · ruff · mypy --strict (DB-gated skip where Postgres absent).
- [ ] Design Review Checklist → **Approved**; **Slice Retrospective** appended.
- [ ] **No Foundational Document edited** (unless implementation contradicts one → stop / fix / resume).

---

**Approval block** *(filled at verification)*

```
View:      Knowledge
Gates:     0✔ 1✔ 2✔ 3✔ 4✔ 5✔ 6✔ 7✔
Findings:  0 🔴 · 0 🟠 · 2 🟡 · 2 🔵
Status:    Approved with changes (owner) → both changes applied → CLOSED
Reviewer:  Owner (mam0022)
Date:      2026-07-22
Version:   S4 v1
```

**Findings & disposition**
- 🟡 **"Other" is a basket, not a Collection** → **fixed**: the `other` kind now *displays* as
  **"Unclassified"** (shown last; hidden when empty). Wire value stays `other` — product language ≠
  implementation, so the REST contract is untouched.
- 🟡 **Counts could carry status** (`Policies · 3 Ready · 0 Ingesting · 0 Failed`) → **deferred**
  (owner: "not now; today the count is enough"). Recorded as a future enhancement.
- 🔵 **Ingestion seam placement** → **keep in `grc-api`** as a composition adapter (owner: it is not
  Domain/Application/Read-Model — just composition). Extract only when a *second* consumer appears
  (CLI · Worker · Batch import · Scheduler); extracting now would be a premature abstraction.
- 🔵 **A repeating projection pattern** (`MissionProjection · DocumentProjection · ResultProjection`,
  and likely `ApprovalProjection` after S5) → **watch, don't extract**. Consider a shared Projection
  library only at 3–4 near-identical projections; premature now.

---

**Slice Retrospective** *(filled at close — the Learning Unit)*

1. **Did we edit any Foundational Document?** **Yes** — the **REST API Contract** (§2/§3): added
   `evidence_kind` + `size` to the `Document` entity, owner-approved, recorded as the S4 Freeze
   finding. This was a genuine contradiction between the **Product Contract** and the REST Contract
   (not between product and code, and not convenience) — exactly what the Freeze rule exists to
   catch. Everything else (Domain/IA/Flows/Wireframes) was untouched.

2. **What did we learn that wasn't visible before implementation?**
   - **Reality Gate is now a methodology Metric, not luck: it has prevented four design errors before
     the first commit** — S1 `type`/`scope` · S2 `retry` · S3 `Builders` · S4 `evidence_kind`. Four
     for four; the gate earns its place at the top of every Execution Contract.
   - **"Knowledge = Evidence Collections" held** — making the *collection* (not the file) the unit
     kept the view natural, and will absorb versions/revisions without a redesign. A corollary the
     build surfaced: a **label leaks implementation** — "Other" reads as a real Collection when it is
     a **basket**; renamed **"Unclassified"** (display only; wire value stays `other`).

3. **Does this affect S5 (Dashboard)?** Two watch-items, neither an action now: (a) the **projection
   pattern** is repeating (Mission/Document/Result, likely +Approval) — extract a shared library only
   at 3–4 near-identical projections, not before; (b) the **ingestion write-side** stays a `grc-api`
   composition adapter until a second consumer appears. S5 adds another read model, not new writes.

4. **Decision:** **Close Slice.**
