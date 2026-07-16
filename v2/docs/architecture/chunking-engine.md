# Rasheed V2 — Chunking Engine Architecture

- Status: **Implemented** — `v2/packages/knowledge-importer/knowledge_importer/chunking/`
  (profiles, recognizers, tabular/text strategies, finalize). The status line dated
  2026-07-11 said "nothing in this document is implemented"; that was true when written and
  stale once Phase 3 shipped. Corrected 2026-07-16 (Phase 14.5) without touching the design
  content. The 31,793 chunks in `v2/knowledge/chunks/` are this engine's output.
- Date: 2026-07-11 (design) · 2026-07-16 (status corrected)
- Revision: v1.1 — adds the **Document Profile layer** (§2, §2.1, §2.2) between discovery
  and the Recognizers, per approval feedback. A Document Profile is now the addressable
  unit that owns a chunking strategy; a Recognizer is the reusable code that implements one.
- Companion: [Knowledge Library Architecture](knowledge-library.md) §6 (Chunk & Embedding
  model), [ADR 0035](../../../docs/adr/0035-v2-knowledge-library.md)
- Scope boundary: **v2/ only**, and specifically the pipeline already running in
  `v2/packages/knowledge-importer/` (Phase 1: discovery/manifests, Phase 2: parsing). This
  document designs Phase 3 — chunking — as the next stage of that same pipeline. No V1 code,
  no database schema changes; the DB shape this must eventually feed (`knowledge_sections`)
  already exists on paper in the Knowledge Library doc §3 and is referenced, not repeated.

---

## 0. The problem this document refuses to solve the easy way

A generic RAG chunker splits text into fixed-size windows (e.g. 1200 characters, 150-token
overlap) and calls it done. That is what `apps/web`'s `document_chunks` already does, and
it is the *right* answer for one case: an arbitrary tenant document with no reliable
internal structure.

It is the *wrong* answer for almost everything else this Knowledge Library holds. An ISO
27001 control, a PDPL article, a NIST subcategory, a contract clause — these are not prose
that happens to be long. They are **the actual unit of regulatory meaning**: the thing an
auditor cites, the thing a control maps to, the thing a gap-analysis checks off. A
fixed-size window can split "Article 12(3)" in half, or worse, merge the tail of "Article
12" into the head of "Article 13" — producing a chunk that is confidently retrieved and
wrong. In a GRC product, "confidently retrieved and wrong" is the failure mode this whole
system exists to prevent.

So the design principle this document commits to, before answering the ten questions:

> **Chunk boundaries must follow the document's own regulatory structure wherever that
> structure can be reliably recognized. Fixed-size windowing is a fallback for the
> minority of documents that genuinely have no such structure — never the default.**

This is not a new idea invented here — it is [Knowledge Library §6](knowledge-library.md#6-chunk--embedding-model)'s
"structured vs. unstructured" split, already agreed. What that document left unspecified —
and what was explicitly asked for — is *how the engine actually recognizes structure across
seven very different GRC document families, in a mixed Arabic/English corpus, with no
layout metadata beyond what Phase 2's plain-text extraction preserves* (page breaks via
`\f`, nothing else — no font size, no bold, no heading styles). That recognition problem is
the actual content of this document.

---

## 1. Should chunking be semantic rather than fixed-size?

**Semantic (structure-aware) by default; fixed-size only as an explicit, logged fallback.**

Two chunking modes, selected per structural unit (not globally per document — see §7):

| Mode | When used | Boundary source |
|---|---|---|
| **Structure-aware** | A recognizer finds reliable structural boundaries — clause numbers, article markers, heading patterns — at acceptable confidence (§3). | The document's own numbering/heading structure. |
| **Windowed fallback** | No recognizer reaches confidence threshold *anywhere* in the document, or a single recognized unit is too large to embed as one chunk (e.g. a 6,000-character policy section with no finer heading). | Fixed-size sliding window, sentence/paragraph-boundary-aware — never mid-sentence. |

Critically, these are not mutually exclusive per document: a policy document might be
structure-aware down to its numbered sections, then fall back to windowing only *inside* a
single oversized section that has no finer structure. The fallback is scoped to the
smallest unit that needs it, not the whole document — see §7.

---

## 2. Should every document type have its own chunking strategy?

**Strategy is owned by a Document Profile — an explicit layer between discovery and the
Recognizers, not a direct category-to-code mapping.** Strategy is keyed to document
*genre*, not file format (a PDF and a DOCX of the same ISO standard must chunk identically;
a scanned procedure PDF and an ISO standard PDF must chunk completely differently despite
sharing a file format — format was Phase 2's axis, genre is this phase's axis) — but genre
alone, expressed as a raw category-to-recognizer table, doesn't scale. As the library grows
toward the hundreds of sources the Knowledge Catalog roadmap targets, two problems appear:
a single category folder can hold documents of genuinely different shape (a binding
directive and a heading-based internal note can both land in `Governance/`), and the same
individual document's shape has nothing to do with which folder happened to hold it.

**The fix: separate "what structure does this document have" (a Document Profile — data)
from "what code recognizes that structure" (a Recognizer — reusable code).** A profile
always resolves to exactly one Recognizer; a Recognizer may be shared by several profiles
whose underlying pattern-matching logic is identical but whose citation conventions or
expected skeleton (§3.7) differ. This is the same split ADR 0007 already established for
the Framework Engine — "frameworks are data, not code" — applied one layer down, to
document structure instead of control catalogs.

**The eight Document Profiles:**

| Document Profile | Recognizer | Skeleton / citation convention | Example sources |
|---|---|---|---|
| `iso_standard` | `StandardClauseRecognizer` | ISO's fixed 0–10 clause skeleton + Annex A controls | ISO 27001, ISO 31000, ISO 37301 |
| `control_framework` | `StandardClauseRecognizer` | Looser hierarchical skeleton (function.category-number, domain.process) — no single fixed shape assumed | NIST CSF, NIST SP 800-53, COBIT, COSO |
| `law` | `RegulationArticleRecognizer` | Chapter/Article, often with a Royal Decree-style preamble | Saudi Laws |
| `regulation` | `RegulationArticleRecognizer` | Article/Chapter, typically implementing rules under a Law; NCA ECC's domain-control-subcontrol grammar lives here | Saudi Regulations, CMA, SDAIA, NCA ECC |
| `corporate_policy` | `PolicyProcedureRecognizer` (heading mode) | Named-heading vocabulary (Purpose/Scope/Policy Statement/Enforcement) | Corporate Policies; most of Governance, Compliance, Risk Management, Internal Audit, OCEG |
| `procedure` | `PolicyProcedureRecognizer` (step mode) | Ordered steps, lettered sub-steps, RACI tables | Step-by-step procedures, wherever filed |
| `contract` | `ContractClauseRecognizer` | Numbered clauses + defined terms + schedules | Contract Templates |
| `spreadsheet` | `TabularRecognizer` | Sheet/row/column, format-determined | Any `.xlsx`-origin document, regardless of category |

**Individual documents map to a profile, not a folder.** ISO 27001, ISO 31000, and ISO
37301 all resolve to `iso_standard` even though they are three unrelated sources, because
they share the same logical structure — this is the exact scalability property being asked
for: a hundredth ISO standard added next year needs a one-line data mapping (or nothing at
all, if the category default already covers it — §2.1), never a new Recognizer.

**`corporate_policy` and `procedure` share one Recognizer, two profiles, on purpose.**
Both are heading/step-oriented rather than numbered-clause-oriented, so the underlying
pattern-matching code is the same `PolicyProcedureRecognizer` — but a procedure's chunk
sizing (step-oriented, table-heavy) and a policy's (prose-section-oriented) genuinely
differ, and CLAUDE.md's naming rule ("names describe intent") argues for keeping them
addressable as distinct profiles rather than one overloaded label.

Selection of *which* profile applies to a given document, and how a Recognizer decides
whether it can actually chunk what a profile expects, are two different mechanisms —
covered next.

### 2.1 Document Profile Assignment

A new, small pipeline stage — `ProfileAssignmentStage` — sits between `ParsingStage` and
the future `ChunkingStage`, implementing the same `PipelineStage` protocol Phases 1–2
already established. It needs no parsed text (profile assignment is decidable from
discovery-time metadata plus a data catalog), so it could in principle run immediately
after `IntakeStage`; placing it just before chunking keeps the pipeline's stage order
matching the conceptual order ("discovery → parsing → **profile assignment** → chunking")
without depending on anything `ParsingStage` didn't already need.

It writes `document_profile` and `profile_assignment_source` onto the manifest, resolved in
this priority order:

1. **Explicit mapping (highest priority — a human/curator decision always wins).** A data
   catalog — `v2/knowledge/profiles/document_profiles.json`, following the same
   "frameworks/profiles are data, not code" rule as the Framework Engine and the Knowledge
   Catalog's own controlled vocabularies — maps a document's `short_code` (or, before a
   formal `short_code` exists this early in the pipeline, its `document_id`) directly to a
   profile. This is how a document whose category folder doesn't match its actual shape
   gets corrected — e.g. an "Incident Response Procedure.docx" filed under `Internal Audit`
   (whose category default is `corporate_policy` — see next) gets an explicit override entry
   mapping it to `procedure`.
2. **Format override.** Any `.xlsx`-origin document resolves to `spreadsheet`, regardless of
   category or an explicit mapping's absence — a spreadsheet's structure is genuinely
   format-determined. (An explicit mapping from step 1 can still override this, for the rare
   case where a `.xlsx` file's *content* is better treated as, say, `contract` clauses laid
   out in a spreadsheet — step 1 always wins when a curator has made that call.)
3. **Category-level default (zero-cost fallback).** Absent an explicit mapping, Phase 1's
   `category` (the folder a document was discovered in) resolves to a default profile via a
   small, fixed table — see the closing Summary. This preserves the original design's
   zero-cost convenience (a new document in an existing category needs *no* data entry at
   all) while making the *profile*, not the raw folder name, the thing chunking logic
   actually keys off — so reorganizing folders later, or a document that doesn't fit its
   folder's usual shape, never requires touching chunking code, only the data catalog.

`profile_assignment_source` records which of the three rules actually fired
(`"explicit"` | `"format_override"` | `"category_default"`) — the same transparency
discipline as the Recognizer cascade's own logging (§3), so a reviewer can always see why a
given document ended up with the profile it did.

### 2.2 What a Profile governs

A Document Profile is a small, versioned, data-only catalog entry — never code — declaring:

| Property | Purpose |
|---|---|
| `profile_id` | Stable slug (`"iso_standard"`, `"procedure"`, ...). |
| `display_name`, `description` | Human-readable identity, for audit/traceability. |
| `recognizer` | Which Recognizer implementation runs (§3) — always exactly one. |
| `skeleton` | The citation/numbering skeleton to validate confidence against (§3.7) — e.g. `iso_standard`'s exact 0–10 clause list, versus `control_framework`'s looser structural check. Moving this out of the Recognizer's code and into the Profile's data is what lets one `StandardClauseRecognizer` implementation serve both `iso_standard` and `control_framework` without an `if/else` on which standard it's looking at. |
| `language_handling` | Bilingual AR/EN expected (`law`, `regulation`) vs. monolingual (most others). |
| `fallback_windowing` | Default window/overlap parameters for this profile's oversized-unit fallback case (§7) — e.g. a `procedure` profile's typical table-heavy sections may warrant a different default than a prose-heavy `corporate_policy` section. |

Adding a **new individual document** to an existing profile (a hundredth ISO standard, a
new Saudi regulation) costs nothing beyond Phase 1's existing discovery — it inherits its
category's default profile, or gets one explicit mapping row if its category doesn't fit.
Adding a **genuinely new document shape** the library has never seen costs one new Profile
entry (data) plus, only if no existing Recognizer's pattern logic fits, one new Recognizer
(code, isolated, following the same pluggable pattern as every existing one) — never a
change to the assignment mechanism (§2.1) or the Recognizer cascade's control flow (§3).
This is the scalability property this layer exists to buy: the number of documents grows
into the hundreds; the number of distinct chunking strategies stays small and deliberately
curated.

---

## 3. How should the engine recognize each family?

Each `Recognizer` is a pattern library plus a confidence scorer, operating on Phase 2's
already-extracted plain text (it never touches the original PDF/DOCX/XLSX again — chunking
consumes `imports/{document_id}.txt`, same layering discipline as every other stage).

**Selection cascade** (mirrors nothing existing by coincidence — it is deliberately the same
shape as ADR 0032's tiered retrieval: try the best-fit option, fall back only on genuine
failure, log which tier actually fired):

1. **Profile-assigned recognizer.** `ProfileAssignmentStage` (§2.1) has already resolved the
   document's `document_profile`; that profile's `recognizer` property (§2.2) names the
   *primary* Recognizer to try — chunking never re-derives this from raw `category` itself.
2. **Confidence check.** The primary Recognizer scans the full text and reports a
   structural confidence score (§3.7 below defines it precisely).
3. **Accept or cascade.** If confidence ≥ threshold, its boundaries are used. If not, try
   the next Recognizer in a fixed fallback order: genre-specific → generic numbered-heading
   → generic prose-heading → `FallbackWindowRecognizer`. The fallback recognizer always
   succeeds — no document ever fails to chunk outright (mirrors Phase 2's completeness
   principle: every parsed document gets *a* result, success or a clearly recorded failure).
4. **Log the decision.** Which recognizer actually ran and its confidence score are stored
   on the chunk manifest (§9, §6 of this document) — an auditor (or a future engineer) can
   always see *why* a document chunked the way it did, not just that it did.

### 3.1 ISO / NIST / COBIT / COSO — `StandardClauseRecognizer`

- Numbering patterns anchored at line start: `4`, `4.2`, `4.2.1` (main clauses); `A.5.1`,
  `A.8.23` (Annex controls, ISO); `PR.AC-1`, `ID.AM-3` (NIST CSF function.category-number);
  `AC-2`, `AC-2(1)` (NIST SP 800-53 control + enhancement — the parenthetical suffix is a
  **child** of the base control, not a sibling).
- Cross-checked against each standard's known skeleton where one exists (ISO's ten
  top-level clauses 0–10; NIST CSF's six functions) as a confidence signal, not a hard
  requirement — a document missing the skeleton isn't rejected, just scored lower.
- Section titles from a controlled vocabulary ("Scope", "Normative references", "Terms and
  definitions") boost confidence when they co-occur with numbering, since numbering alone
  can false-positive on a table of contents or a page footer.

### 3.2 Saudi Regulations / Laws / CMA / SDAIA — `RegulationArticleRecognizer`

- English: `Article 12`, `Article 12(3)`. Arabic: `المادة الثانية عشرة` (ordinal words, not
  digits — Arabic legal drafting spells out article numbers) and `المادة (12)`. Both forms
  recognized; digits normalized across Western (`0-9`) and Arabic-Indic (`٠-٩`) numerals
  before any pattern match runs, since Saudi regulatory PDFs mix both inconsistently.
- Chapter/Part hierarchy above the Article level: `Chapter Two` / `الباب الثاني`, `Part One`
  / `الجزء الأول` — becomes the `path` breadcrumb's higher levels (§6).
- An Article is one indivisible top-level unit; numbered sub-paragraphs inside it
  (`12(1)`, `12(2)`) become **child** chunks of that Article, never siblings — this matters
  because "Article 12" as a whole is frequently what's cited, while "12(2)" specifically is
  what's mapped to a control. Both need to be independently retrievable (§8, §9).
- NCA ECC-style domain-control-subcontrol codes (`1-1-1`, `2-2-P-1`) recognized as a
  distinct numbering grammar within the same recognizer, since NCA ECC is structurally a
  hybrid of "law-like domain" and "standard-like control."

### 3.3 Contracts — `ContractClauseRecognizer`

- Numbered clause hierarchy: `1.`, `1.1`, `(a)`, `(i)`.
- **Defined terms** are tagged, not just chunked as prose: a capitalized term in quotes
  followed by "means" (`"Confidential Information" means...`) is recognized and marked
  `content_type: "definition"` — future cross-reference resolution (§8) depends on being
  able to resolve "as defined in Clause 1.1" back to the term's actual definition chunk.
- Schedules / Annexes / Exhibits are recognized as distinct top-level structural siblings
  to the numbered clause body, not children of whichever clause happens to precede them in
  the text — a Schedule is its own addressable unit.

### 3.4 Policies / Governance / Compliance / Risk / Internal Audit / OCEG —
`PolicyProcedureRecognizer`

- No numbering to rely on in general — recognition is **heading-based**: a candidate
  heading line is short (under ~80 characters), not terminated by normal sentence
  punctuation, followed by a blank line, and optionally numbered (`1. Purpose`).
- A controlled vocabulary of common policy section names (`Purpose`, `Scope`,
  `Roles and Responsibilities`, `Policy Statement`, `Enforcement`, `Definitions`,
  `Review Cycle`) boosts confidence when a candidate heading matches or closely resembles
  one — this is the weakest-signal recognizer of the six precisely because policies have
  the least standardized structure, so it leans more heavily on vocabulary matching than
  the others do.
- Procedures specifically (step-by-step documents) are recognized as a sub-case: ordered
  steps (`Step 1:`, `1)`, lettered sub-steps `a)`/`b)`) nested inside named phases, often
  with imperative verbs ("Submit the request", "Obtain approval") — a lightweight signal
  that also raises confidence.

### 3.5 Spreadsheet-origin documents — `TabularRecognizer`

- Structure is already explicit from Phase 2 (`\f`-separated sheets, tab-separated rows) —
  this recognizer's job is *chunk sizing*, not boundary discovery: group rows into
  chunks of a bounded size (e.g. ~40 data rows per chunk for a large control matrix or risk
  register), repeating the header row at the top of every chunk so column context is never
  lost when a chunk is retrieved in isolation.
- A sheet with only a handful of rows (a small reference table) becomes one chunk; a
  300-row register becomes several row-group chunks, all children of one "sheet" parent
  chunk — never split mid-row, never merged with prose from a different sheet.

### 3.6 The floor — `FallbackWindowRecognizer`

- Sentence/paragraph-boundary-aware sliding window. Never invented from scratch: reuses
  the proven `apps/web` `document_chunks` default (1200 characters, 150-character overlap)
  named explicitly in [Knowledge Library §6](knowledge-library.md#6-chunk--embedding-model)
  — one fewer unvalidated number in the system.
- Always succeeds — this is what guarantees every parsed document ends up chunked one way
  or another, matching Phase 2's "every discovered document gets a manifest outcome"
  completeness guarantee.

### 3.7 Confidence scoring (how the cascade actually decides)

A Recognizer's confidence score is a function of: (a) **pattern hit density** — recognized
boundaries per page (too few, relative to the document's `page_count` from Phase 2, signals
the recognizer found only coincidental matches, e.g. numbers in a footer); (b) **skeleton
consistency** — whether recognized codes form a plausible ascending sequence (`4`, `4.1`,
`4.2`, `5` — not `4`, `9`, `2`) *against the assigned Document Profile's `skeleton` (§2.2)*,
not a skeleton hardcoded inside the Recognizer — this is what lets `StandardClauseRecognizer`
validate `iso_standard` documents against ISO's exact 0–10 clause list while validating
`control_framework` documents against a looser structural check, from the same code; (c)
**coverage** — the fraction of the document's text actually captured inside some recognized
boundary versus left as unstructured overflow. A fixed threshold (tunable, not hardcoded per
document type) determines accept-vs-cascade; the threshold and the resulting decision are
both recorded per document (§9), so the threshold itself can be revisited later against real
outcomes rather than guessed once and forgotten.

---

## 4. Headings, numbering, tables, and nested sections

- **Numbering and heading text are preserved verbatim** in both the chunk's visible text
  (so a downstream LLM sees `"A.5.15 Access control policy: ..."`, not bare prose) and in
  structured metadata (`code`, `title` — §9), so an exact-match lookup for "A.5.15" never
  depends on fuzzy text search.
- **Nesting is a real tree, never flattened.** A chunk's `parent_chunk_id` points at its
  structural parent; a `path` array carries the full ancestor breadcrumb (`["Clause 5",
  "5.1", "5.1.2"]`) for O(1) breadcrumb reconstruction without walking the tree — the exact
  shape [Knowledge Library §3](knowledge-library.md#3-database-schema)'s
  `knowledge_sections.path`/`parent_section_id` already committed to. A parent chunk's own
  `text` holds only its own lead-in content, never its children's text concatenated in —
  otherwise retrieving "Clause 5" and "Clause 5.1" would duplicate content and double-count
  it in any downstream scoring.
- **Tables never split across a chunk boundary that isn't row-aligned.** A table (or, if
  oversized, a row-group — §3.5) is always its own chunk, tagged `content_type: "table"`,
  nested under whichever heading/clause precedes it — never merged into surrounding prose,
  so a retrieval hit on tabular data isn't diluted by unrelated narrative text sharing the
  same chunk.

---

## 5. How page references are preserved for citations

Phase 2 already marks page boundaries in the extracted text with a form-feed (`\f`) per
page and records `page_count` on the manifest. The Chunking Engine walks that text
sequentially, counting `\f` occurrences consumed so far, and stamps every chunk with
`page_start`/`page_end`:

- Most chunks sit fully within one page: `page_start == page_end`.
- A clause that spans a page break legitimately keeps **both** bounds — a chunk is never
  forced onto a single page at the cost of splitting a clause mid-sentence; citation then
  reads "pp. 12–13," which is both accurate and exactly what a human auditor would cite.
- Formats with no page concept (DOCX; a sheet in `TabularRecognizer`'s output, where the
  page-equivalent is the sheet, not a page) carry `page_start = page_end = null`, the same
  convention Phase 2 already uses for `page_count: null` on DOCX.

This is what turns "the AI said so" into "the AI said so, and here is document X, page 12" —
the specific requirement CLAUDE.md §12/§19 makes non-negotiable for any factual GRC claim.

---

## 6. How parent/child relationships between chunks are stored

- Every chunk has a stable `chunk_id`, deterministic from `document_id` plus its structural
  path (never a random UUID — re-chunking an unchanged document must reproduce identical
  IDs, the same idempotency discipline Phase 1's `document_id_for()` and Phase 2's
  checksums already established). Concretely: `{document_id}::{slugified path}` when a
  recognized code/path exists (e.g. `iso--iso-27001--...::a-5-15`), or
  `{document_id}::window-{index}` for a fallback-window chunk with no structural code.
- `parent_chunk_id` is nullable — null for a top-level unit (e.g. ISO's top-level "Clause
  5"), set for anything nested under it.
- At this filesystem stage (no database yet — consistent with Phases 1–2, which are also
  pure-filesystem), a document's chunks live together in one file,
  `v2/knowledge/chunks/{document_id}.json`, as a **flat list where every entry carries its
  own `parent_chunk_id`** — flat-with-pointers, not a nested tree structure, because a flat
  list is trivially both flattenable (as stored) and reconstructible (by any consumer that
  wants the tree shape) without committing to one representation over the other.
- This shape is deliberately a direct field-for-field match to
  [Knowledge Library §3](knowledge-library.md#3-database-schema)'s `knowledge_sections`
  table (`parent_section_id`, `path`, `position`) — promoting these JSON files into that
  table later is a straight load, not a remodel, the same design bet Phases 1–2 already
  made about their own eventual promotion.

---

## 7. How overlap works

**No overlap between structure-aware chunks, ever.** "Article 11" and "Article 12" are
different regulatory units with no shared meaning — injecting tail-of-11/head-of-12 overlap
would let a retrieval hit on "Article 12" silently include unrelated content from Article
11, which is precision loss, not the recall gain overlap is supposed to buy in generic RAG.
This is a deliberate GRC-specific departure from common RAG practice, not an oversight.

**Overlap exists only inside the windowed fallback, scoped to the smallest unit that needs
it.** Two cases:

1. A whole document has no recognizable structure (`FallbackWindowRecognizer` is the top-
   level cascade result) — the entire document is windowed with overlap.
2. A document is otherwise structure-aware, but one recognized unit is too large to embed
   as a single chunk (e.g. a policy's "4. Policy Statement" running 6,000 characters with
   no finer heading) — *only that unit* is sub-windowed. The windows never bleed across the
   structural boundary into "5. Enforcement"; they remain children of "4. Policy Statement."

Window size and overlap reuse the one number already validated in production
(`apps/web`'s 1200 characters / 150-character overlap), split on the nearest sentence or
paragraph boundary to the window edge — never mid-word or mid-sentence. Overlap chunks are
tagged `content_type: "window"` with `window_index`/`window_of_total`, so downstream
retrieval and re-ranking can recognize (and deduplicate or down-weight) adjacent-window
redundancy instead of treating two overlapping windows as independent, corroborating facts.

---

## 8. How future cross-reference links will work

Chunking **detects candidate references, but never resolves them** — resolution is
explicitly future work, deferred the same way this document defers embeddings and RAG.
What chunking captures now, so nothing has to be re-parsed later:

- In-text reference patterns recognized during chunking: `"see Clause 4.2"`, `"as defined
  in Article 3"`, `"pursuant to Section 12(a)"`, `"in accordance with ISO/IEC 27001:2022
  Annex A.5.15"`.
- Each match becomes an entry in the chunk's `references` array:
  `{raw_text, target_code, target_source_hint, scope, confidence}`, where `scope` is
  `"internal"` (same document — resolvable today, directly, by matching `target_code`
  against another chunk's `code` in the same `chunks/{document_id}.json` file) or
  `"external"` (another Knowledge Source entirely — e.g. a Saudi regulation citing an ISO
  clause — which cannot be resolved without the Framework Engine's cross-mapping or a
  `short_code` lookup against `knowledge_sources`, neither of which chunking depends on).
- This is a **detection pass, confidence-scored, never authoritative** — `references` is
  raw material for a future resolution stage (which will populate the typed relationship
  graph — [Knowledge Library §7](knowledge-library.md#7-relationships--knowledge-graph-model):
  `regulation_to_obligation`, `policy_to_requirement`, the proposed `framework_to_framework`
  edge) to consume, not itself a claim the system asserts.

---

## 9. What metadata every chunk contains

| Field | Type | Purpose |
|---|---|---|
| `chunk_id` | string | Stable, deterministic identity (§6). |
| `document_id` | string | Back-reference to the Phase 1/2 manifest. |
| `category` | string | Carried from the manifest (e.g. `"ISO"`, `"Saudi Regulations"`). |
| `document_profile` | string | The Document Profile (§2, §2.1) assigned to the *whole document* — `"iso_standard"`, `"control_framework"`, `"law"`, `"regulation"`, `"corporate_policy"`, `"procedure"`, `"contract"`, `"spreadsheet"`. Drives which Recognizer runs primarily. |
| `structure_profile` | string | Which Recognizer/pattern family actually produced *this specific chunk* (`"iso_clause"`, `"regulation_article"`, `"contract_clause"`, `"policy_section"`, `"tabular_row_group"`, `"fallback_window"`) — usually matches `document_profile`'s recognizer, but can diverge locally (e.g. a `"tabular_row_group"` chunk for an embedded table inside an otherwise `iso_standard` document). |
| `content_type` | string | `"section" \| "table" \| "window" \| "definition" \| "heading_only"`. |
| `code` | string \| null | The structural number/label, verbatim (`"A.5.15"`, `"Article 12(3)"`); null for a windowed fallback chunk. |
| `title` | string \| null | Heading text, if any. |
| `path` | string[] | Ancestor breadcrumb (§4, §6). |
| `level` | int | Nesting depth. |
| `parent_chunk_id` | string \| null | §6. |
| `position` | int | Stable sibling order / sort key. |
| `text` | string | This chunk's own content only — never includes descendant chunks' text. |
| `character_count` | int | |
| `page_start` / `page_end` | int \| null | §5. |
| `window_index` / `window_of_total` | int \| null | Set only when `content_type == "window"` (§7). |
| `references` | array | Candidate cross-reference mentions, unresolved (§8). |
| `language` | string | Inherited from the document; per-chunk where a bilingual document's structure allows separating Arabic/English (see §11 — full per-paragraph bilingual tagging is explicitly out of scope for this phase). |
| `recognizer_confidence` | float (0–1) | §3.7 — surfaced, not hidden, per CLAUDE.md §19. |
| `chunker_version` | string | Versioned like Phase 2's `parser` field, so a future re-chunk with an improved recognizer is traceable and never silently indistinguishable from the old output. |
| `chunked_at` | ISO timestamp | |
| `checksum_sha256` | string | Of this chunk's own `text`, for change detection — same discipline as Phase 1's file checksums. |

This table is deliberately a near-1:1 mapping onto
[Knowledge Library §3](knowledge-library.md#3-database-schema)'s `knowledge_sections`
columns (`section_type`↔`structure_profile`, `code`↔`code`, `path`↔`path`, `title`↔`title`,
`text`↔`text`, `position`↔`position`, `parent_section_id`↔`parent_chunk_id`) — the same
design bet Phase 1/2 already made: build the filesystem artifact so the eventual database
load is a straight field mapping, not a redesign.

**Document-level manifest additions** (mirroring Phase 2's `parsed`/`parser`/`parsed_at`
pattern exactly): `document_profile: str`, `profile_assignment_source: str` (written by
`ProfileAssignmentStage`, §2.1 — `"explicit" | "format_override" | "category_default"`),
`chunked: bool`, `chunk_count: int`, `structure_profile_used: str`,
`recognizer_confidence: float`, `chunking_duration: float`, `chunked_at: str`,
`error: str | None`. A chunking failure is caught and recorded the same way a Phase 2
parsing failure is — it does not stop the pipeline, and (per §3's cascade) should be rare in
practice, since `FallbackWindowRecognizer` is a floor that always succeeds; a true `error`
here signals something lower-level broke (e.g. the extracted `.txt` file is missing or
unreadable), not merely "no structure found."

---

## 10. How this design supports what comes after

- **RAG.** The chunk *is* the embeddable/retrievable unit
  ([Knowledge Library §6](knowledge-library.md#6-chunk--embedding-model)). Citations resolve
  directly to `(document_id, chunk_id, code, page_start–page_end)` — exactly the
  source/section/page CLAUDE.md §12/§19 requires, with nothing further to derive.
- **Cross-framework mapping.** `code` and `structure_profile` are the join keys a future
  mapping job needs to match, e.g., "ISO A.5.15" against "NCA ECC 1-5-P-1" through the
  Framework Engine's existing cross-mapping mechanism
  ([Knowledge Library §7](knowledge-library.md#7-relationships--knowledge-graph-model)) —
  chunking doesn't perform the mapping, it guarantees the mapping has something addressable
  to point at.
- **AI Agents.** Every agent (Knowledge, Compliance, Risk, Policy — CLAUDE.md §11) consumes
  chunks through one uniform shape regardless of source family, so a Compliance Agent doing
  gap analysis across ISO, NCA ECC, and a tenant's own policy is one retrieval call against
  one chunk shape, not three source-specific assemblers glued together at the agent layer.
- **Compliance analysis / gap assessment.** Because the parent/child tree survives (§4, §6)
  rather than being flattened at chunk time, gap analysis can operate at whatever
  granularity the question needs — "does any policy chunk map to this specific ISO
  sub-clause" at the leaf, or "does this policy address Clause 5 at all" by rolling up its
  children — without re-parsing the source document to recover structure that chunking
  already discarded.

---

## 11. Explicit non-goals for this phase

Naming these plainly, in the same spirit as the Knowledge Library doc's own non-goals
section — this is a design boundary, not an oversight:

- **No embeddings, no vector search, no retrieval.** This document designs the chunk
  *boundary and metadata*, not what happens to a chunk afterward.
- **No cross-reference resolution.** §8's `references` array is detection only; resolving a
  reference into the typed knowledge graph is a later stage's job.
- **No per-paragraph bilingual language tagging.** A document that interleaves Arabic and
  English within the same structural unit is chunked as one mixed-language stream in this
  phase; splitting a single chunk into per-language sub-spans is a candidate future
  refinement, not designed here — flagged honestly rather than silently assumed solved.
- **No database persistence.** Chunk output is a JSON file per document under
  `v2/knowledge/chunks/`, mirroring Phase 1/2's filesystem-first approach. Promotion into
  `knowledge_sections` (§9's mapping) is future work, named, not built.
- **No recognizer-confidence threshold tuning against real outcomes yet.** §3.7's threshold
  is a design placeholder to be validated once real chunking output exists to measure
  against — not a number this document claims is already correct.
- **The Document Profile catalog (§2.1) is an initial, reviewable data set, not claimed
  exhaustive.** Eight profiles and a small number of category defaults cover what Phase 1's
  audit found in the library today; a document shape the catalog doesn't yet anticipate gets
  a new profile entry (data) when it actually appears — not a redesign of the assignment
  mechanism itself.

---

## Summary: category defaults → Document Profile → Recognizer

This is the **category-level default** tier of §2.1's three-tier resolution — the zero-cost
fallback every document gets for free. Explicit per-document overrides (e.g. a procedure
misfiled under a policy-shaped category) and the `.xlsx` format override both take priority
over this table; it is not the only thing that decides a document's profile, only what
happens absent a more specific signal.

| Phase 1 category (from directory scan) | Default Document Profile | Recognizer |
|---|---|---|
| ISO | `iso_standard` | `StandardClauseRecognizer` |
| NIST, COBIT, COSO | `control_framework` | `StandardClauseRecognizer` |
| Laws | `law` | `RegulationArticleRecognizer` |
| Saudi Regulations, CMA, SDAIA | `regulation` | `RegulationArticleRecognizer` |
| Contract Templates | `contract` | `ContractClauseRecognizer` |
| Corporate Policies | `corporate_policy` | `PolicyProcedureRecognizer` (heading mode) |
| Governance, Compliance, Risk Management, Internal Audit, OCEG | `corporate_policy` (default — individual step-oriented documents are explicitly overridden to `procedure`) | `PolicyProcedureRecognizer` |
| Any `.xlsx`-origin document, any category | `spreadsheet` (format override, §2.1 step 2) | `TabularRecognizer` |
| Anything no Recognizer reaches confidence on | — | `FallbackWindowRecognizer` |

**Worked example, exactly as raised in review:** `ISO/ISO 27001/`, `ISO/ISO 31000/`, and
`ISO/ISO 37301/` are three different Knowledge Sources with three different `document_id`s —
all three inherit the `ISO` category's default profile, `iso_standard`, with zero explicit
data entries required. If a future ISO source turns out to have a genuinely different shape
(unlikely, but the mechanism must allow it), one explicit override row reassigns just that
one document — the category default and every other ISO document are unaffected.

Not implemented until this design is approved. *(Approved 2026-07-11, with the Document
Profile layer amendment above folded in.)*
