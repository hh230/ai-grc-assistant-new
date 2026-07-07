# ADR 0031: Regulation Review & Embeddings (KI-P7) — the admin approval gate and post-approval embedding generation for the Saudi Regulations Ingestion Pipeline

- Status: Accepted
- Date: 2026-07-07
- Deciders: Product Owner (via direct working session), Architecture
- Related: CLAUDE.md §9, §12, §16, §19, §20, §22, §23; ADR 0025, 0029, 0030; ADR 0032
  (Proposed, deferred follow-up)

## Context

ADR-0030 (KI-P6) built the Saudi Regulations Ingestion Pipeline: a Google Drive catalog is
parsed, each linked Board of Experts law page is fetched and deterministically split into
chapters/articles, and every result is stored `status = 'in_review'` — explicitly never
trusted directly, per the Product Owner's own KI-P6 answer: *"Do NOT directly trust AI
extraction. Create a review workflow... Only after approval: mark as approved, generate
embeddings, expose to RAG/search."* ADR-0030 named the review workflow and embeddings as
explicit follow-up, scoped as "KI-P7," not silently dropped.

This phase (KI-P7) closes exactly that gap and nothing more, per explicit instruction: build
regulatory catalog ingestion (done, ADR-0030), official regulation storage (done, ADR-0030),
article extraction (done, ADR-0030), versioning (done, ADR-0030), the **approval workflow**,
and **embeddings after approval** — and do **not** touch the existing RAG retrieval priority,
which stays exactly as it was before this phase. The "internal regulations DB -> trusted
sources -> LLM fallback" retrieval-priority merge that KI-P6 already deferred is tracked
separately as ADR-0032 (Proposed, not built), so it is named rather than silently entangled
with this change. KI-P5 (the AI Worker Control Center) is untouched by this phase — every file
this ADR modifies is either new or an additive, backward-compatible extension of it.

## Decision

Bottom-up, matching KI-P5's own layering exactly (persistence -> RBAC -> API -> UI), since
this phase adds no new pure package or adapter — it is a review/decision layer directly over
KI-P6's existing persistence:

**1. Migration (`apps/web/lib/db/migrations/0023_regulation_section_embeddings.sql`) —
additive columns only.** `regulation_sections` gains `embedding vector(3072)`,
`embedding_model text`, `embedded_at timestamptz` — the same pgvector column shape apps/web's
own `document_chunks` (0005_document_chunks.sql) already established for OpenAI
`text-embedding-3-large`. No index (same 2000-dim pgvector index cap that migration already
documents), and — deliberately — no wiring into any retrieval/search code path in this phase.

**2. Persistence (`packages/persistence-web/grc_persistence_web/regulations.py`) — four
additive methods, zero changes to existing ones.**
- `RegulationSourceRepository.get_by_id` / `RegulationSourceVersionRepository.get_by_id` —
  needed for the review UI's detail/decide flows, which (unlike KI-P6's own ingestion path)
  address a specific version directly rather than only ever the latest-for-source.
- `RegulationSectionRepository.list_needing_embedding(document_id)` — sections with real
  article text (`text_ar IS NOT NULL`) and no embedding yet; excludes chapter headings (no
  text of their own) and, idempotently, anything already embedded by a prior attempt — the
  exact idempotency a retry after a partial embedding failure needs.
- `RegulationSectionRepository.set_embedding(section_id, embedding, model)` — writes one
  vector. asyncpg has no built-in pgvector codec, so the vector travels as its pgvector text
  literal (`'[0.1,0.2,...]'`) cast with `$2::vector`.
- `RegulationSectionRepository.bulk_insert`'s own parameter type was widened from the concrete
  `tuple[NewRegulationSection, ...]` to a Protocol-typed `Sequence[NewSectionLike]` (a
  structural port declared in this same module) — a small, incidental type-correctness fix
  found while adding `list_needing_embedding`/`set_embedding` next to it, not a behavior
  change; existing callers (which pass `NewRegulationSection` instances) are unaffected.

**3. RBAC (`grc_services.shared.authorization`) — one new `ResourceType`, mirroring
`KNOWLEDGE_WORKER` exactly.** `ResourceType.REGULATION_REVIEW`, deliberately never added to the
`_OPERATIONAL`/`_CATALOG` grant sets: `OWNER`/`ADMIN` hold every action via their existing
`_ALL_RESOURCES` grant; `AUDITOR` inherits its existing platform-wide read-only grant (can
review the queue, can never approve/reject); every other role gets a 403 on every route.
Mirrored in `apps/web/lib/auth/permissions.ts`.

**4. API (`apps/api/routers/regulation_review.py`) — four endpoints under
`/api/v1/regulation-review`, modeled on `routers/knowledge_worker.py`.** `GET /pending` (every
`in_review` version, joined with its source's identity fields), `GET /{version_id}` (full
detail: source, documents, every section — chapters and articles — for the reviewer to
actually read before deciding), `POST /{version_id}/approve`, `POST /{version_id}/reject`.
Talks directly to `grc_persistence_web` repositories rather than the gated command/query bus,
the same reasoning ADR-0029 already established for platform-scope, non-tenant-owned state.
`approve`/`reject` are state-checked (`WHERE status = 'in_review'`): deciding an
already-decided version returns `409 Conflict`, not a silent no-op or a duplicate decision —
CLAUDE.md §16's fail-safe posture applied to human decisions, not just AI ones.

**Embeddings run synchronously inside `approve`, not as a separate step or a queued job.**
Once a version is approved, every one of its not-yet-embedded, real-text sections is embedded
via the injected `EmbeddingModel` port (`grc_llm.OpenAIEmbeddingModel` in production,
`grc_llm.FakeEmbeddingModel` in tests/dev without a configured key — the exact same
`llm_provider` switch `build_chat_model` already uses, extended with a matching
`build_embedding_model`) and the vector is written back. A per-document embedding-call failure
is logged and counted, never allowed to leave the version un-approved or block another
document's sections (CLAUDE.md §16) — the response reports `sections_embedded`/
`sections_failed` explicitly, so a partial failure is visible rather than silently
under-delivered, and a follow-up `approve` call on the same (now-approved) version would 409,
so recovery from a partial failure is intentionally left as a named limitation (see
Consequences) rather than quietly built as an implicit retry-on-approve.

**5. Frontend (`apps/web`) — `/regulation-review`, admin-gated exactly like `/ai-worker`.** A
two-pane workspace: a pending-versions list (source title, version label, relative timestamp)
and a detail panel (full chapter/article tree, official citation, Approve/Reject) — mirroring
`AiWorkerWorkspace`'s component-per-concern structure and `lib/knowledgeWorker/{service,client,
types}.ts`'s exact proxy pattern (`app/api/regulation-review/*` route handlers, admin-gated a
second time — defense in depth, CLAUDE.md §20 — before ever reaching `apps/api`). Bilingual
(en/ar) message keys added to both `messages/en.json` and `messages/ar.json`; nav entry added
to `FOOTER_NAV`, admin-gated, alongside "AI Worker."

## Consequences

**Positive**
- Closes exactly what ADR-0030 named as deferred, nothing more: catalog ingestion, storage,
  extraction, and versioning were already done; this phase adds only the approval workflow and
  post-approval embeddings, leaving KI-P5 and the existing RAG retrieval priority completely
  untouched (verified: `packages/rag`, `apps/api`'s retrieval/search code paths, and every
  KI-P5 file are unmodified by this change).
- Verified live end-to-end in the browser against real data (not just tests): logged in as
  `owner`, opened `/regulation-review`, saw the real 60 pending regulations from KI-P6's live
  BOE crawl, opened "نظام الوكالات التجارية" (Commercial Agencies Law — 17 articles, real
  Arabic text), clicked Approve, and confirmed directly in Postgres: `status = 'approved'`,
  `approved_by = 'dev-user'`, and 12 sections carrying real embeddings
  (`embedding_model = 'fake-embed'` in this dev run, since apps/api's `llm_provider` was
  `fake`; the same code path calls the real `OpenAIEmbeddingModel` when configured `openai`).
  Reject was verified the same way against a second regulation (`status = 'rejected'`).
- New tests: 2 pure `persistence-web` (idempotent `list_needing_embedding`/`set_embedding`),
  9 `apps/api` (pending/detail/approve/reject, RBAC differentiation including the auditor
  read-only case, 404/409 paths, and embedding-count assertions against the fake embedding
  model) — 11 new tests, all green against the real dev Postgres; `ruff`/`black`/`mypy` clean
  on every touched Python package (zero new mypy errors versus the pre-existing baseline);
  `tsc --noEmit`, `next lint`, and `next build` all clean on the frontend.
- Zero behavior change for any existing caller: `WorkerControlRepository`/KI-P5's routes,
  KI-P6's ingestion pipeline, and every pre-existing `persistence-web` test are unaffected.

**Negative / costs**
- **A partial embedding failure after approval has no automatic retry path in this phase.**
  Since `approve` is state-checked and a version is already `approved` after the first call,
  a second `approve` call on the same version 409s rather than resuming embedding for the
  sections that failed. `list_needing_embedding`'s idempotency means a retry mechanism would
  be straightforward to add (a dedicated `POST /{version_id}/retry-embeddings` route, or
  relaxing `approve`'s state check to allow "approved but incomplete") — deliberately not
  built here since it's unneeded scope for "approval workflow + embeddings after approval"
  and no live run has yet produced a partial-failure case to size against.
- **Embeddings are generated but not exposed anywhere.** No RAG/search/agent code reads
  `regulation_sections.embedding` in this phase — by explicit instruction. This is a real,
  named gap (approved regulations do not yet inform any AI answer), not an oversight; ADR-0032
  is where the retrieval-priority work that would close it belongs.
- **No container/deployment wiring**, consistent with ADR-0028/0029/0030's own precedent —
  this phase is application code, not ops/deployment.

## Alternatives considered

- **Embed as a separate, explicitly-triggered step (e.g. a "Generate Embeddings" button
  distinct from "Approve").** Rejected: the Product Owner's own KI-P6 answer already specifies
  the sequence ("Only after approval: mark as approved, generate embeddings...") as one
  continuous human decision, not two; splitting it would leave a window where an approved
  regulation has no embeddings for no reason a reviewer chose, and would double the UI surface
  for no real benefit given approval is already infrequent, manual, and admin-only.
- **Queue embedding generation as an async background job (Workflow Engine / task queue)
  rather than running it synchronously inside the `approve` request.** Rejected for this
  phase's scale: approvals are a low-frequency, admin-initiated action (not a hot path), and a
  handful of embedding calls per approval complete well within a normal request timeout; a
  queued job would add real infrastructure (a durable job runner apps/api does not yet have
  wired for this kind of work) for a problem synchronous execution already solves correctly,
  including surfacing partial failure in the same response the admin is already looking at.
- **Wire the new embeddings directly into `grc_rag`'s existing retrieval/search so approved
  regulations are immediately searchable.** Rejected per explicit instruction for this task:
  retrieval priority is out of scope here and tracked separately (ADR-0032) so it gets its own
  properly-sized design pass (source ranking, tie-breaking against trusted-source research and
  LLM fallback) rather than being folded in as an afterthought of the approval workflow.
- **A dedicated `RegulationSectionEmbeddingRepository`/separate embeddings table instead of
  columns on `regulation_sections`.** Rejected: one section has at most one current embedding
  (the same section content, re-embedded on a model change, is a data-versioning question this
  phase does not need to solve yet), so a 1:1 column relationship is simpler than a second
  table with its own foreign key and join, matching `document_chunks`' own precedent of
  storing the vector alongside its source text rather than in a side table.
