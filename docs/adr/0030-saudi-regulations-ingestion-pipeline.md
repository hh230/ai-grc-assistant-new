# ADR 0030: Saudi Regulations Ingestion Pipeline (KI-P6) — catalog-driven regulation fetch, deterministic Arabic legal parsing, and pending-review persistence for `grc_domain.knowledge`

- Status: Accepted
- Date: 2026-07-07
- Deciders: Product Owner (via direct working session), Architecture
- Related: CLAUDE.md §5, §9, §12, §13, §15, §16, §19, §22, §23; ADR 0025, 0026, 0028, 0029;
  ADL-0008

## Context

The Product Owner supplied a Google Drive PDF ("فهرس الأنظمة السعودية" — Index of Saudi
Regulations) and asked for a pipeline that turns Saudi regulations into structured,
per-article knowledge, reusing the existing KI-P4/KI-P5 worker architecture rather than
building a parallel system.

Two things changed the shape of this during investigation, both confirmed against real data:

1. **The PDF is a catalog, not a law's text.** It has no articles to chunk, but it contains
   387 real embedded hyperlinks (PDF `/Annots` link annotations — invisible in plain-text
   extraction) to `https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/{uuid}/1`, Saudi's official
   Board of Experts (هيئة الخبراء بمجلس الوزراء) legal portal.
2. **A BOE law page is real, static, server-rendered HTML** (confirmed live against
   `النظام الأساسي للحكم` / Basic Law of Governance): chapters (الباب), articles (المادة) with
   real legal text, article amendments (تعديلات المادة) citing the amending Royal Order, and
   issuance/publication/status metadata. Genuinely ingestible — no OCR, no JS-rendering
   problem (unlike the SPA homepages KI-P5 hit for NCA/SAMA/CMA).

Via `AskUserQuestion`, the Product Owner chose: (a) ingest the index as a catalog, then
fetch+parse each linked regulation rather than stopping at the catalog; (b) store extracted
regulations as `pending_review` (never trusting AI/parser extraction directly — an explicit
admin approval gate is required before anything reaches RAG/search); (c) persist through
`grc_domain.knowledge`'s existing rich model (`KnowledgeSource → KnowledgeSourceVersion →
KnowledgeDocument → KnowledgeSection`) rather than bolting columns onto the flat
`knowledge_items` table, since this model already has the chapter/article/version/
bilingual-text/approval-gate shape the task needs — simply unused today (zero Postgres
persistence existed for it); (d) defer the "internal DB → internet → LLM" retrieval-priority
merge to a separate follow-up.

**A decision this ADR makes explicit, since it determines the whole shape:**
`grc_domain.knowledge`'s own intended persistence path is the M6 Extraction Engine's
`KnowledgeIngestionPort`, backed by `packages/persistence`'s SQLAlchemy UnitOfWork/outbox.
That path is explicitly blocked (ADL-0008: the Knowledge persistence layer is structurally
out of sync with the refactored domain; re-aligning it needs Product Owner approval — not a
live option today). So this phase adds **new repositories in `packages/persistence-web`**
(the same asyncpg, hand-written-SQL, platform-scope pattern every prior Knowledge
Intelligence phase already uses), talking directly to new tables that mirror the domain
entities — exactly the same choice KI-P1 (ADR-0025) already made over the gated SQLAlchemy
line, for the same reason. The M6 engine itself is not reused as a running pipeline (its own
segmenter is English-only and its ingestion port is the blocked one); what is reused is the
domain model it was built for, the "chunk by article/chapter, never split one" principle, and
the KI-P4/P5 worker skeleton (`LearningCycleScheduler`, `WorkerEvent`/`WorkerEventSink`,
`WorkerControlPort`, the AI Worker Control Center's activity timeline) for scheduling, admin
control, and observability.

**Scope of this phase vs. next:** this ADR covers catalog ingestion, real fetch, Arabic-aware
chapter/article/amendment parsing, and storage as `pending_review` with full logging — the
part that answers "did we ingest real regulations." Admin approve/reject UI+API and embedding
generation on approval are explicitly scoped as the immediately-following KI-P7, not silently
dropped.

## Decision

Bottom-up, matching this repo's established layering (domain → persistence → pure package →
adapters → composition root):

**1. Domain (`packages/domain/grc_domain/knowledge/entities.py`) — one additive field.**
`KnowledgeSection` gained `text: LocalizedText | None = None` (its own docstring already
named this as a "later phase" — this is that phase). No change to invariants or lifecycle.

**2. Migration (`apps/web/lib/db/migrations/0021_regulation_knowledge.sql`,
`0022_regulation_worker_control.sql`) — platform-scope, like `knowledge_items`.**
- `regulation_sources` — stable identity (short_code unique, title, authority, jurisdiction,
  knowledge_domain, document_type, boe_source_url); created once, never overwritten by
  re-ingestion.
- `regulation_source_versions` — one row per fetched revision; `status` mirrors
  `VersionStatus` (draft/in_review/approved/published/superseded/withdrawn/archived/rejected),
  `content_hash` unique per source for idempotent dedup, `approval_check` CHECK
  (`(approved_by IS NULL) = (approved_at IS NULL)`). Every version this pipeline writes lands
  `in_review` ("pending_review"); nothing here ever sets `approved`/`published`.
- `regulation_documents` — one fetched document per version (language, format, source_url,
  content_hash, byte_size).
- `regulation_sections` — one row per legal unit (chapter/article/clause), `path` (chapter
  breadcrumb), self-referencing `parent_section_id`, `amendment_note_ar`/`_en` — never a
  fragment of one article split across two rows.
- `regulation_worker_control` — a second, independent singleton control row, same shape as
  KI-P5's `worker_control`, so this pipeline's enable/interval/manual-trigger state never
  shares a row (and therefore a cadence) with the Knowledge Worker.

**3. Persistence (`packages/persistence-web/grc_persistence_web/regulations.py`) — new
repositories, `knowledge.py`'s exact idiom.**
`RegulationSourceRepository` (`upsert`, create-if-absent), `RegulationSourceVersionRepository`
(`upsert_draft` — idempotent on `content_hash`: unchanged content is a no-op, changed content
drafts a new version, never edits a prior one — mirroring `KnowledgeSourceVersion`'s own
immutability rule; `list_pending`/`approve`/`reject`, state-checked
`WHERE ... AND status = 'in_review'`, seams for KI-P7), `RegulationDocumentRepository`,
`RegulationSectionRepository` (`bulk_insert` in one transaction). `bulk_insert` accepts a
`Sequence[NewSectionLike]` — a Protocol-typed parameter, not the concrete `NewRegulationSection`
dataclass directly — so a sibling adapters package's own mirrored Protocol can satisfy it
under `mypy --strict` without importing this package's concrete type (see "Two mypy-strict
gaps" below).

`WorkerControlRepository` (KI-P5) was generalized to accept `table: str = "worker_control"`
(backward-compatible default) so `regulation_worker_control` reuses the exact same class and
`WorkerControlPort` contract instead of a second one.

**4. Pure package (`packages/regulation-ingestion`) — mirrors `grc_knowledge_worker` exactly.**
`RegulationCatalogEntry` (name_ar, category, source_url); `AutonomousRegulationIngestionWorker`
— same shape as `AutonomousKnowledgeWorker`: an injected `LearningCycleScheduler` (reused from
`grc_knowledge_worker`, not reimplemented), `WorkerControlPort`/`WorkerEventSink` (reused, not
a second vocabulary), a structurally-matched `RegulationFetchRunnerPort`. `tick()` loads the
catalog once per due cycle, then runs the injected runner over it, emitting
`cycle_started`/`questions_loaded`/`cycle_completed`/`error` — the same event types KI-P5's
dashboard already renders.

**5. Adapters (`packages/regulation-ingestion-adapters`) — real I/O.**
- `DriveIndexCatalogSource` / `parse_regulation_index` — downloads the index PDF (the direct-
  download URL form `https://drive.google.com/uc?export=download&id={file_id}`), reads each
  page's `/Annots` link annotations (`pypdf`), pairs each link with its preceding bullet's
  text by vertical position, dedupes consecutive identical URIs.
- `parse_boe_page` (`boe_parser.py`) — deterministic, regex-based, no LLM (matching this
  repo's "no LLM where a reviewable pattern suffices" posture): extracts the metadata block
  (law name ar/en, issuance/publication dates, status, official citation), splits on `الباب`
  (chapter) and `المادة` (article) headings. **Never splits one article across two sections**
  — the `المادة` heading is the one hard boundary. A found-and-fixed parsing trap: a real BOE
  page repeats an article's own code immediately under its own `تعديلات المادة` (amendment)
  block, restating which article the amendment note belongs to; naively treating every
  `المادة` match as a new boundary would have split that restatement into a phantom extra
  article. `_is_amendment_restatement` excludes a heading match from the boundary list when
  nothing but whitespace separates it from the nearest preceding `تعديلات المادة` marker.
- `BoeRegulationPageFetcher` — fetches one BOE page through the existing
  `grc_regulatory_crawlers` primitives (`PoliteRateLimiter`, `RobotsChecker`, `html_to_text`),
  computes a SHA-256 content hash for dedup.
- `RegulationGapRunner` — the fetch→parse→store orchestration, structurally matching
  `KnowledgeGapResearchRunner`'s role: per catalog entry, upsert the source → fetch+parse →
  emit timeline events (`gap_detected`/`source_searched`/`knowledge_discovered`/`item_saved`)
  → `upsert_draft` the version (idempotent, returns early with `stored=False` on an unchanged
  re-fetch) → insert the document → bulk-insert sections. One regulation's failure (a fetch
  error, a parse edge case) is logged (`regulation_ingestion.fetch_failed`/`save_failed`) and
  isolated — it never blocks the next catalog entry (CLAUDE.md §16).

**6. Composition root (`apps/worker/src/grc_worker/regulation_ingestion_loop.py`) — a second,
independent entrypoint alongside `knowledge_learning_loop.py`.** Same `_load_dev_env`
(reused, not reimplemented), a `RegulationWorkerSettings.from_env()` that fails fast on
missing `DATABASE_URL`/`GRC_REGULATION_INDEX_DRIVE_FILE_ID`, `build_worker()` wiring the real
Drive download, the real polite BOE fetcher/parser, the real Postgres repositories, and
`WorkerControlRepository(database, table="regulation_worker_control")` — and the same
fail-safe `run_forever` shape (one bad tick is logged, the loop continues at the next poll).
Registered as its own `regulation-ingestion-dev` launch config entry — **not folded into the
Knowledge Worker's own tick**, since these are a different content type (whole regulations,
not individual GRC question answers) on an independent cadence, sharing only the underlying
architecture and the same database.

**Two mypy-strict Protocol gaps found and fixed, both only surfaced once the composition root
wired both sides together (the same category of gap ADR-0028 §7 named):**
- A Protocol member declaring a collection **return type** as `list[object]` rejects a
  concrete implementation returning `list[SpecificRecord]` under `mypy --strict`, because
  `list` is invariant — the fix (matching KI-P4's own precedent) is to declare the Protocol's
  return type as `Sequence[object]` (covariant), not `list[object]`.
- A Protocol member declaring a collection **parameter** type as `tuple[SomeProtocol, ...]`
  can be satisfied by a concrete implementation accepting a different, independently-declared
  but structurally identical Protocol only if the *concrete* method's own parameter type is
  itself a Protocol (or a supertype) — never the concrete dataclass directly — since two
  independently-declared Protocols with matching shapes are mutually assignable under
  structural typing, but a Protocol is never assignable to an unrelated concrete nominal
  class. Fixed by widening `RegulationSectionRepository.bulk_insert`'s own parameter type in
  `grc_persistence_web` from `tuple[NewRegulationSection, ...]` to `Sequence[NewSectionLike]`
  (a Protocol declared in that same module), which `packages/regulation-ingestion-adapters`'
  own mirrored `NewSectionLike` Protocol then satisfies without importing the sibling
  adapters package's concrete type at all.

**7. A real-environment SSL gap found and fixed in `grc_regulatory_crawlers`'s
`UrllibHttpFetcher`, shared by every crawler/fetcher in the repo.** Live verification against
`laws.boe.gov.sa` failed with `CERTIFICATE_VERIFY_FAILED` even though `curl` and macOS
Safari/Chrome fetch the same URL successfully. Root cause, confirmed by direct inspection:
(a) this uv-managed CPython build does not link to the macOS Keychain trust store at all
(`ssl.create_default_context()`'s platform default finds nothing), and (b) even with
`certifi`'s public CA bundle supplied explicitly, BOE's own TLS server sends only its leaf
certificate, omitting the DigiCert intermediate CA a compliant server should include —
browsers paper over this via out-of-band AIA chasing, which Python's `ssl` module does not do.
Fixed, not worked around: `UrllibHttpFetcher` now builds its `SSLContext` from `certifi.where()`
plus one vendored, well-known public intermediate certificate
(`grc_regulatory_crawlers/_ca_supplement.pem` — fetched once from DigiCert's own official
`cacerts.digicert.com` repository, verified against its published SHA-256 fingerprint before
vendoring). This is not a verification bypass: it supplies the exact chain the server should
have sent itself, using only official CA material, and is reproducible in any environment
(including containers) the same way it was reproduced here — rather than depending on the
local machine's own trust store being correctly wired up for Python specifically.

## Consequences

**Positive**
- Verified live end-to-end, not just against tests: the real `regulation-ingestion-dev`
  process, run against the real `.env` and the real 387-entry Drive catalog, fetched and
  parsed dozens of real BOE pages (including the Basic Law of Governance: 9 chapters, 35
  articles) and stored every one `status = 'in_review'` — confirmed by direct Postgres query,
  including a spot-check of Article 1's real Arabic text
  (`"المملكة العربية السعودية، دولة عربية إسلامية..."`) traced back to the actual fetched
  page, zero fabrication.
- Zero behavior change for any existing caller: `WorkerControlRepository`'s new `table`
  parameter defaults to `worker_control`, so every KI-P5 caller is unaffected; the
  `UrllibHttpFetcher` SSL fix is purely additive (a fetch that already verified correctly
  still does).
- New tests: 5 pure `regulation-ingestion` (worker tick/schedule/event-emission, mirroring
  `grc_knowledge_worker`'s own suite), 8 `regulation-ingestion-adapters` (catalog PDF link
  extraction, BOE page parsing incl. the amendment-restatement trap), 5 `persistence-web`
  (source/version/document/section repositories against the real dev Postgres) — 18 new
  tests, all green; ruff/black/mypy-strict clean across every new and touched package.
- No new consequential automation: every stored regulation is `pending_review` — nothing in
  this phase reads from, embeds, or exposes this data to RAG/search/agents. The human
  approval gate (KI-P7) is structural, not a runtime check that could be bypassed.

**Negative / costs**
- **Not every catalog entry parses into articles.** A handful of linked regulations (e.g. a
  royal-decree-only page with no `المادة`-numbered body) parsed to zero sections. This is
  fail-safe by design (CLAUDE.md §16: one regulation's imperfect result never blocks another),
  and every such document is still stored (traceable, reviewable) rather than silently
  dropped — but it means KI-P7's review queue will show some documents with no extracted
  sections, worth surfacing distinctly in that UI rather than looking identical to a genuine
  parse failure.
- **The vendored intermediate certificate is a point-in-time fix**, not a general AIA-chasing
  solution — if BOE's certificate is reissued under a different, still-incomplete chain, or
  another misconfigured government site is added later, the same class of fix (fetch, verify
  the fingerprint, vendor) would need repeating. A general AIA-chasing HTTP client was judged
  out of scope for this phase.
- **No container/deployment wiring**, consistent with ADR-0028/0029's own precedent — this
  phase is application code, not ops/deployment.

## Alternatives considered

- **Bolt regulation/article columns onto the flat `knowledge_items` table** (KI-P1's shape).
  Rejected per the Product Owner's own explicit choice: `grc_domain.knowledge`'s existing
  `KnowledgeSource → KnowledgeSourceVersion → KnowledgeDocument → KnowledgeSection` model is
  the correct fit for versioned, approval-gated, chaptered legal text — extending the flat
  table would have meant reinventing that shape informally, worse-typed, alongside a
  model already built for exactly this.
- **Wait for the M5↔M3 knowledge persistence re-alignment (ADL-0008) and use the M6 engine's
  own `KnowledgeIngestionPort`.** Rejected: that path is explicitly blocked pending Product
  Owner approval and unrelated to this phase's own scope; KI-P1 already established the
  precedent of a direct `persistence-web` repository instead, and this phase follows it rather
  than either reopening ADL-0008 or blocking on it.
- **Disable TLS verification (`context=ssl._create_unverified_context()` or equivalent) to
  work around the BOE SSL failure.** Rejected outright — CLAUDE.md's security posture and this
  repo's own conventions never trade away verification for convenience; the actual, minimal,
  reviewable fix (supply the chain the server omitted, from official CA material, fingerprint-
  verified) was preferred and took no more effort.
- **Fold this pipeline into the existing Knowledge Worker's own `tick()`.** Rejected per
  explicit instruction: regulations are a different content type on an independent cadence
  from individual GRC question-answer gap research; a second composition root sharing the
  same architecture (scheduler, control seam, event sink, database) was chosen over
  conflating two schedules and two control rows into one.
- **Trust parser/AI extraction directly and expose regulations to RAG immediately.** Rejected
  per the Product Owner's explicit answer: every stored version is `pending_review`
  (`status = 'in_review'`); an explicit human approval step (KI-P7) is required before
  anything is embedded or exposed to search — CLAUDE.md §9's "propose, don't auto-apply"
  human-in-the-loop principle applied literally to a new content type.
