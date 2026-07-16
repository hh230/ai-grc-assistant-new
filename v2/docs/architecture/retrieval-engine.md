# Rasheed V2 — Retrieval Engine Architecture

- Status: **Partially implemented** — `v2/packages/retrieval-engine/` (the status line dated
  2026-07-12 said "nothing here is implemented"; stale since Phase 8. Corrected 2026-07-16
  (Phase 14.5) without touching the design content). **Built:** planning, hybrid fusion,
  deterministic ranking, the citation gate, the in-memory providers, and the pgvector
  provider (Phase 9B). **Designed here but NOT built** — do not read this document as a
  description of the running system: the **tenant scope predicate** of §4/§170 (there is no
  tenant enforcement anywhere in V2 — see
  [ADR 0040](../../../docs/adr/0040-v2-tenancy-model.md)), the caching layers of §533, and
  the reranker. See [platform-overview](platform-overview.md) §5.
- Date: 2026-07-12 (design) · 2026-07-16 (status corrected)
- Companions: [Knowledge Library](knowledge-library.md) (esp. §10 *AI retrieval flow* — this
  document is the detailed design of that section's **Tier 1, internal retrieval**),
  [Chunking Engine](chunking-engine.md), [ADR 0035](../../../docs/adr/0035-v2-knowledge-library.md).
  **Retrieval sits *below* the [Decision Engine](decision-engine.md) — the Decision Engine
  decides whether, when, and how many times retrieval runs; this document is one Tool the
  Decision Engine's plan may call, not an always-on front door.**
- Scope boundary: **v2/ only.** Design of the read path that consumes the artifacts the
  Knowledge Pipeline already produces (manifests, chunks, embeddings). This phase does
  **not** implement anything, and does **not** cover generation / AI answering, the vector
  database itself (pgvector is already chosen — Knowledge Library §6), or the external
  Tier-2/Tier-3 fallbacks (Knowledge Library §10). Those are separate phases.

---

## 0. Why this is not a generic RAG retriever

A generic RAG retriever embeds the query, does a vector top-k over one flat index, and
hands the raw chunks to a model. That throws away almost everything the Knowledge Pipeline
worked to preserve.

Every chunk Rasheed produced already carries **structured GRC metadata** — a clause `code`
(`A.5.15`, `Article 12`, `المادة الثانية عشرة`, `1-1-1`), a `document_profile`
(`iso_standard`, `law`, `regulation`, `contract`, …), a `structure_profile`, a
`heading_path`, `page_start`/`page_end`, a `language`, and a fully-formed `citation` block.
A generic retriever ignores all of it. This engine treats it as **first-class ranking and
routing signal**:

- A query naming a specific control ("ISO 27001 A.5.15", "المادة 12 من نظام الشركات") must
  resolve to that **exact clause** — an exact-code lookup, not a fuzzy vector guess that
  might return a neighbouring control.
- A query about the law ("obligations under PDPL") must be routed to `law`/`regulation`
  profiles, not blended with contract templates.
- Every result must be **citable** — resolvable to (source, code/section, page) — because in
  GRC, an uncited or mis-cited answer is the failure mode the whole system exists to
  prevent (CLAUDE.md §12/§19). Retrieval **gates on citability**, it doesn't just rank.
- The corpus is **bilingual Arabic/English**, and an Arabic query must be able to find an
  English ISO control (and vice versa) — cross-lingual retrieval with real Arabic
  normalization, not an English-only pipeline with Arabic bolted on.

So the design principle, before the fifteen required topics:

> **Retrieval is structured, routed, and citation-gated — the chunk's metadata decides
> where to look and what to trust, not just the vector distance. Semantic vector search is
> one signal among several, never the whole engine.**

---

## 1. Retrieval stages (the pipeline)

Ten stages, each a swappable port behind the orchestrator (hexagonal, mirroring
`packages/extraction`'s ingestion pipeline). The funnel is **recall-first, then
precision, then citation-gated**.

```
                          ┌──────────────────────────────────────────────┐
  query (+ tenant scope,  │  the RetrievalOrchestrator owns the flow,     │
   language?, filters?)   │  budgets, and the retrieval trace             │
                          └───────────────────────┬──────────────────────┘
                                                  ▼
  1  QUERY UNDERSTANDING     normalize · detect language · extract entities (framework,
                            │ clause code, article, dates) · expand acronyms/synonyms
                            ▼
  2  INTENT CLASSIFICATION   map to a GRC intent (lookup_clause, conceptual, cross_map,
                            │ obligation, comparison, policy_lookup, …)
                            ▼
  3  RETRIEVAL PLANNING      intent + entities → a RetrievalPlan: which document_profiles /
                            │ categories, which retrievers, their weights, k, rerank model
                            ▼
  4  METADATA FILTERING      resolve the filter predicate: tenant scope (global ∪ org) FIRST,
                            │ then profile / category / structure / language / code / page
                            ▼
      ┌─────────────────────┼───────────────────────────────┐   (run in parallel)
      ▼                     ▼                                ▼
  5a EXACT MATCH        5b VECTOR SEARCH                 5c KEYWORD SEARCH (BM25)
   code / metadata       filtered ANN over               filtered BM25 over the
   direct lookup         knowledge_sections.embedding    language-specific analyzers
      └─────────────────────┼───────────────────────────────┘
                            ▼
  6  HYBRID FUSION           reciprocal-rank fusion of the three candidate lists,
                            │ intent-weighted → one candidate set (~top 50–100)
                            ▼
  7  CROSS-ENCODER RERANK    multilingual cross-encoder scores (query, chunk) pairs →
                            │ precision ordering of the candidate set
                            ▼
  8  BUSINESS-RULE RANKING   deterministic boosts: exact-code, profile match, normative
                            │ strength, version recency, scope preference, confidence
                            ▼
  9  CITATION VALIDATION     drop / flag any candidate that can't resolve to a live,
                            │ checksum-matching citation (source · code · page)
                            ▼
 10  CONTEXT ASSEMBLY        expand leaves with parent heading context, dedupe overlapping
                            │ windows, order, budget → a structured, cited context bundle
                            ▼
                       RetrievalResult  (ranked cited chunks + intent + plan + trace + timings)
```

Nothing downstream of stage 10 is in scope here — the bundle is the hand-off to the future
generation phase, which never sees a raw index.

---

## 2. Query Understanding *(topic 1)*

Turns a raw query string into a structured `AnalyzedQuery`. Pure, fast (<30 ms), no LLM on
the hot path by default (an optional LLM assist is a pluggable enrichment, not a
dependency).

- **Normalization.** Unicode NFKC; Arabic-Indic ↔ Western digit unification; Arabic
  orthographic normalization (§13). Produces a normalized form for matching without ever
  altering what's shown to the user.
- **Language detection.** Per-query `ar` / `en` / `mixed`, driving analyzer selection for
  BM25 and cross-lingual handling (§12).
- **Entity extraction — reusing the recognizers.** The same pattern libraries the Chunking
  Engine already uses (`standard_clause`, `regulation_article`, `contract_clause`) are
  reused **in reverse** to pull structured entities out of the query:
  - clause codes (`A.5.15`, `AC-2(1)`, `1-1-1`), article references (`Article 12`,
    `المادة الثانية عشرة`, `المادة (12)`), chapter/part;
  - framework / regulator names → `framework_refs` (ISO 27001, NCA ECC, PDPL, SAMA, NIST
    CSF, COBIT, …), including Arabic and English aliases and acronyms;
  - document-type words ("policy", "contract", "law", "نظام", "لائحة", "عقد", "سياسة").
- **Expansion.** Controlled acronym expansion (`ECC` ↔ Essential Cybersecurity Controls,
  `PDPL` ↔ نظام حماية البيانات الشخصية), curated GRC synonym sets, and Arabic↔English term
  linking from a small bilingual GRC lexicon (data, not code — same "config not code"
  discipline as the framework catalog). Expansion feeds keyword/BM25, **not** the vector
  query (the embedding model handles semantics natively).
- **Output** `AnalyzedQuery`: `{ normalized_text, language, detected_codes[],
  framework_refs[], doc_type_hints[], expansions[], has_explicit_locator: bool }`. The
  `has_explicit_locator` flag is what later routes a "find me clause X" query down the
  exact-match path with high weight.

---

## 3. Intent Classification *(topic 2)*

A closed, GRC-specific intent taxonomy — not a generic "question vs. keyword" split. Intent
decides routing (which profiles, which retrievers, exact-vs-semantic balance, whether
cross-framework traversal is needed, which rerank model).

| Intent | Example | Routing consequence |
|---|---|---|
| `lookup_clause` | "ISO 27001 A.5.15", "المادة 12 من نظام الشركات" | exact-match dominant; profiles from the named framework; k small |
| `conceptual` | "what is information security risk treatment" | vector-dominant; broad profiles; rerank on |
| `definition` | "define personal data under PDPL" | vector + exact-term; prefer `content_type: definition` (contracts) / definitions clauses |
| `obligation_extraction` | "what are our obligations for data transfer" | `law`/`regulation` profiles; boost mandatory normative strength |
| `cross_framework_mapping` | "how does ISO 27001 map to NCA ECC" | needs the framework-mapping graph (Knowledge Library §7); dual-profile retrieval |
| `comparison` | "difference between ISO 27001 and 27002" | multi-source retrieval, grouped by source |
| `procedural` | "steps to onboard a vendor" | `procedure`/`corporate_policy`; prefer step-sequence chunks |
| `policy_lookup` | "what does our infosec policy say about access" | **org-scoped** `corporate_policy`; scope preference flips to organization |
| `coverage_gap` | "do our policies cover PDPL Article 5" | two-sided: obligation side (`law`) + control/policy side; assembled for comparison |
| `evidence_lookup` | "which control evidences access management" | `iso_standard`/`control_framework`; relationship-aware |

**Implementation shape:** a fast rule/heuristic classifier (entity presence + query-shape
features) as the default, behind an `IntentClassifierPort` so an LLM-backed classifier can
be swapped in for ambiguous queries without touching callers. Low-confidence classification
degrades safely to a broad `conceptual` plan rather than mis-routing (fail-safe, CLAUDE.md
§6). Intent + confidence are recorded in the trace.

---

## 4. Metadata Filtering *(topic 3)*

The filter predicate is resolved **before** candidate generation and applied inside every
retriever, using the metadata already on the chunk/embedding records — no post-hoc
filtering that would silently wreck ANN recall.

- **Tenant scope is always first and non-negotiable.** `scope_kind = 'global'` ∪
  (`scope_kind = 'organization'` AND `organization_id = :tenant`). This is the two-library
  model from Knowledge Library §4, enforced as the outermost `WHERE` on every query.
  Cross-tenant retrieval is impossible by construction, not by convention (CLAUDE.md §20).
- **Structured facets**, all directly present on the records: `document_profile`,
  `category`, `structure_profile`, `language`, `content_type`, `document_id`/`source`,
  `code` (exact or prefix), `page` range, framework version, `embedding_version` (to avoid
  mixing vector generations).
- **Filter × ANN interaction.** For vector search this is a **pre-filtered ANN** query.
  Because aggressive pre-filtering can degrade HNSW recall, the plan chooses per selectivity:
  high-selectivity filters (single document, single code prefix) → exact/relational path or
  post-filter over a larger ANN fetch; low-selectivity filters (a whole profile) →
  pre-filter with an enlarged `ef_search`. This tradeoff is measured in evaluation (§16),
  not guessed.
- Filters are represented as a typed `FilterSpec` (data), compiled once into the
  SQL/predicate each retriever needs — so a new facet is a data/columns change, never new
  control flow.

---

## 5. Document Profile Selection *(topic 4)*

The GRC-specific routing step a generic retriever lacks. Intent + extracted entities map to
a **target profile set** and category set, narrowing the search space to the document
*genres* that can actually answer the question, which is both a precision win and a latency
win.

- Named framework → its profiles/categories (PDPL → `law` + `Laws`; NCA ECC → `regulation`
  + `Saudi Regulations`; ISO 27001 → `iso_standard` + `ISO`; NIST CSF → `control_framework`
  + `NIST`).
- Intent → default profiles when no framework is named (`policy_lookup` → `corporate_policy`
  org-scoped; `procedural` → `procedure`; `obligation_extraction` → `law`+`regulation`).
- The selection is a **soft prior**, not a hard gate by default: the primary retrieval runs
  within the selected profiles, but a *fallback widening* re-runs across all profiles if the
  in-profile candidate set is thin or low-confidence — so a mis-routed query still finds
  content (the same "try best-fit, widen on failure" shape as the Chunking Engine's
  recognizer cascade). `lookup_clause` with an explicit locator is the one case that stays a
  hard filter, because there the code *is* the answer.
- Selection reads the **Document Profile catalog** (`document_profiles.json`) the Chunking
  Engine already owns — one source of truth for what profiles exist.

---

## 6. Hybrid Retrieval *(topic 5)*

Three candidate generators run **in parallel**, each returning a ranked list with scores;
their outputs are fused (§ fusion below). Running all three and fusing — rather than
picking one — is what makes retrieval robust across the intent taxonomy: exact match nails
locators, BM25 nails rare tokens and exact Arabic/English terms, vector nails paraphrase and
cross-lingual meaning.

| Generator | Strength | Weight is high when… |
|---|---|---|
| Exact match (§5a) | precise locator / metadata hits | `has_explicit_locator`, `lookup_clause` |
| Vector (§8) | paraphrase, concept, cross-lingual | `conceptual`, `definition`, cross-language query |
| BM25 (§10) | rare terms, exact phrases, acronyms, Arabic morphology | keyword-heavy queries, named entities |

**Fusion = weighted Reciprocal Rank Fusion (RRF).** `score(d) = Σ_r w_r / (k + rank_r(d))`
across retrievers `r`, with intent-derived weights `w_r` and a small constant `k` (≈60).
RRF is chosen over raw-score blending because the three retrievers produce
non-comparable score scales (cosine vs. BM25 vs. exact) — RRF fuses on rank, which is
scale-free and robust. Fusion is cheap (<5 ms) and fully explainable (every candidate keeps
its per-retriever ranks in the trace).

---

## 7. Vector Search *(topic 6)*

- **Index:** pgvector HNSW over `knowledge_sections.embedding` (`vector(1536)`), the
  dimension the Knowledge Library (§6) chose specifically to fit under pgvector's ANN index
  cap. Cosine distance (embeddings are L2-normalized).
- **Query embedding** goes through the **same provider abstraction as Phase 4** — the
  `EmbeddingProvider` port — so the query is embedded with the *same model and version* as
  the corpus. A mismatch (`embedding_version` differs) is a hard error, not a silent
  degrade: you cannot compare vectors from two models. The query-embedding call is cached
  aggressively (§ cache).
- **Filtered ANN** per §4, with `ef_search` tuned by selectivity. Fetch depth is
  over-provisioned (e.g. top-`k`×3) ahead of fusion+rerank so precision stages have room to
  work.
- **Multilingual by construction:** a multilingual embedding model (e.g.
  `text-embedding-3-large`) places an Arabic query and an English control near each other,
  which is what enables cross-lingual recall (§12) with no translation step.
- **Structural-parent skip:** heading-only/empty parent chunks were embedded from a
  synthesized label (Phase 4) — the plan can exclude `content_type: heading_only` from
  vector candidates and re-introduce them only during assembly (§10), so a bare heading
  never out-ranks its substantive children.

---

## 8. Keyword Search *(topic 7)* & BM25 *(topic 8)*

Keyword retrieval is **BM25**, not plain `ILIKE`/`ts_rank`, because BM25's term-frequency
saturation and length normalization matter for a corpus mixing 1-page checklists with
1,200-page rulebooks.

- **Engine options (decision deferred to a benchmark, not guessed):** (a) an in-Postgres
  BM25 extension (e.g. `pg_search`/ParadeDB or VectorChord-BM25) — keeps retrieval next to
  the relational + vector data, honouring CLAUDE.md's "keep retrieval close to the data";
  or (b) a dedicated engine (OpenSearch/Elastic) for its mature Arabic analyzers. The
  architecture treats keyword search as a `KeywordSearchPort`, so the engine choice is an
  adapter, not a rewrite.
- **Per-language analyzers.** Separate Arabic and English analysis chains (tokenization,
  normalization, stemming/light-stemming, stopwords). Query language (§2) selects the
  analyzer; a `mixed` query fans out to both and the results fuse.
- **Fielded BM25.** `title`/`code`/`heading_path` are indexed as boosted fields separately
  from `text`, so a query term matching a control's title or code outranks the same term
  buried in body prose.
- **Same metadata filter** (§4) applies as structured predicates alongside the BM25 match.

---

## 9. Cross-Encoder Re-ranking *(topic 9)*

Fusion produces recall; the cross-encoder produces precision. The top ~50–100 fused
candidates are re-scored by a **multilingual cross-encoder** that jointly encodes
(query, chunk_text) — far more accurate than the bi-encoder vector similarity, at a cost
that's acceptable only because it runs on a small candidate set.

- **Vendor-neutral behind a `RerankerPort`**, exactly mirroring the Phase 4
  `EmbeddingProvider` pattern: candidate adapters include `bge-reranker-v2-m3` (open, strong
  Arabic/CJK/multilingual — a natural fit given the bilingual corpus and the "local model"
  slot), Cohere Rerank multilingual, or Voyage rerank. No business code binds to a vendor;
  the model is configuration.
- **Reranking is skippable per plan.** For `lookup_clause` with a confident exact hit,
  reranking adds latency for no gain and is bypassed. For `conceptual` it's the main
  precision lever and always on.
- Rerank scores are recorded per candidate; the final order is the reranked order **then**
  adjusted by the deterministic business-rule layer (§ ranking strategy), never the other
  way around — learned relevance first, business policy second.

---

## 10. Citation Validation *(topic 10)* & Context Assembly *(topic 11)*

**Citation validation — the GRC gate.** Before anything is returned, every surviving
candidate must produce a **valid, live citation**:

1. **Resolvable locator:** the `citation` block (already on every embedding record) has a
   non-null `source_filename` + at least one locator (`code` and/or `page_start`). A chunk
   that can't be cited is dropped from the answer set (it may still inform ranking, but it
   never surfaces as a citable source) — no uncited GRC claims, ever (CLAUDE.md §12.3).
2. **Freshness:** the candidate's `chunk_checksum` still matches the current chunk's
   checksum. A mismatch means the index is stale relative to a re-chunk — the candidate is
   flagged and excluded, and the staleness is surfaced to ops (this is why the checksum was
   carried onto the embedding record in Phase 4).
3. **Scope re-check:** the candidate's tenant scope is re-verified at the boundary (defence
   in depth over the query-time filter).

Validation also produces the **citation payload** the future generation phase will be
constrained to: a generated answer may only cite (source, code/page) pairs that appear in
this validated set — which is how the next phase will detect and reject hallucinated
citations. Retrieval builds the allow-list; generation must stay inside it.

**Context Assembly.** The reranked, validated leaves are assembled into a **structured,
cited context bundle** — not a concatenated blob:

- **Parent expansion:** each leaf is expanded with its `heading_path` breadcrumb and, when
  budget allows, its parent chunk's lead-in — so the model sees "ISO 27001 › Clause 5 › 5.1
  Leadership: …", not an orphaned paragraph. The parent/child tree the Chunking Engine
  preserved is what makes this a lookup, not a re-parse.
- **Window de-duplication:** overlapping fallback-window chunks (same `document_id`,
  adjacent `window_index`) are merged/deduped using the `window_of_total` metadata, so
  overlap-duplicated text isn't double-counted or double-cited.
- **Ordering & budget:** results are grouped by source and ordered by `position` within a
  source for readability, then trimmed to a token budget with the highest-ranked sources
  kept whole where possible.
- **Output** is a `ContextBundle`: an ordered list of `{ text, citation, scores, confidence,
  document_profile, structure_profile, page_start/end }` plus an overall confidence and the
  full retrieval trace. Confidence is surfaced, never hidden; a low-confidence bundle is the
  signal the generation phase will use to say "insufficient evidence" rather than guess.

---

## 11. Multi-language Retrieval *(topic 12)* & Arabic Optimization *(topic 13)*

The corpus is genuinely bilingual (20+ Arabic laws/regulations, Arabic SDAIA/OCEG guides,
English ISO/NIST/COBIT). Retrieval is cross-lingual by design, and Arabic is a first-class
citizen, not an afterthought.

**Cross-lingual retrieval:**

- A **multilingual embedding model** means an Arabic query retrieves relevant English ISO
  content and vice versa **without a translation hop** — the vector space is shared. This is
  the primary cross-lingual mechanism.
- BM25 is inherently monolingual, so a `mixed`/cross-language query fans out to both
  analyzers and fuses; for pure cross-language (Arabic query → English-only target), vector
  carries the recall and BM25 contributes within-language precision.
- Optional, pluggable **query translation** (behind a port) for the keyword leg only, when
  eval shows a cross-language BM25 gap — never on the hot path unless it earns its latency.
- Language is a **soft preference, not a hard filter** by default: results are cross-lingual,
  but a language match gets a ranking boost, and an explicit `language` filter is honoured
  when the caller sets one.

**Arabic optimization:**

- **Orthographic normalization** on both query and index text used for matching: unify alef
  forms (أ/إ/آ → ا), hamza variants, taa marbuta (ة/ه), alef maqsura (ى/ي), strip tatweel
  (ـ) and optional diacritics — so "الأنظمة" and "الانظمة" match. (Applied to the matching
  representation only; the stored/displayed text and citations are never altered — the same
  discipline the Chunking Engine used for digit normalization.)
- **Arabic-Indic ↔ Western digit unification** so "المادة ١٢" and "Article 12" reconcile.
- **Arabic morphology** in the BM25 analyzer (light stemming / lemmatization; Arabic
  stopwords) — Arabic's rich inflection makes plain token matching weak.
- **RTL-correct** handling and isolation throughout (the Knowledge Center already
  demonstrates `unicode-bidi: isolate` for mixed strings).
- **Arabic-aware clause recognition** in query understanding reuses the
  `regulation_article` patterns (spelled-out ordinals "المادة الثانية عشرة", "الباب",
  "الفصل", NCA ECC codes) — so an Arabic locator query hits the exact-match path just like
  an English one.
- **Known caveat, carried forward honestly:** a handful of Arabic source PDFs had
  glyph-corruption at parse time (documented in earlier phases; the parser-fallback fixed
  the ISO cases but some remain in the fallback set). Evaluation (§16) tracks Arabic-vs-
  English parity explicitly so this corpus-quality gap is measured, not masked; a
  down-weighting signal for low-quality-extraction chunks is available to the ranker.

---

## 12. Retrieval Evaluation *(topic 14)*

Retrieval quality is regression-tested like any other component (CLAUDE.md §22 — AI
components get eval tests, not just unit tests).

- **Golden set** built from the real 117-document corpus: a curated, bilingual query set
  spanning every intent (§3) and every document profile, each with judged relevant
  chunk_ids and the expected citation(s). Includes hard cases: exact-locator lookups,
  cross-lingual queries, cross-framework mappings, org-scoped policy lookups, and
  Arabic-only queries.
- **Metrics:**
  - *Candidate stage:* **Recall@k** (did the relevant chunk survive to rerank?) — the number
    that must stay high or precision downstream is moot.
  - *Final ranking:* **nDCG@10**, **MRR@10**.
  - *GRC-specific:* **citation validity rate** (fraction of returned results with a live,
    resolvable citation — target ~100%), **citation accuracy** (is the cited locator the
    correct one), **answerable-rate** vs. correct "insufficient evidence".
  - *Fairness:* **Arabic-vs-English parity delta** on matched query pairs — a first-class,
    tracked metric, not an afterthought.
  - *Latency:* p50/p95/p99 per stage and end-to-end (§13).
- **Harness:** offline, reproducible, runnable in CI as a regression gate; ranking changes
  ship behind a flag and are A/B'd; a human-graded GRC-correctness rubric backs the
  automated metrics. The Knowledge Center is the natural surface to later visualize eval
  runs and per-query traces.

---

## 13. Performance Targets *(topic 15)*

Interactive retrieval, generation excluded. Budgets are targets to design and benchmark
against, not guarantees, and assume the corpus scale of the current library growing toward
the catalog's hundreds of sources.

| Stage | p50 budget | p95 budget | Notes |
|---|---|---|---|
| Query understanding + intent | < 15 ms | < 40 ms | pure/rule-based; no LLM on hot path |
| Query embedding | < 10 ms (cache hit) | < 150 ms (miss) | cached; miss = provider round-trip |
| Candidate retrieval (vector ∥ BM25 ∥ exact) | < 80 ms | < 200 ms | parallel; dominated by ANN + BM25 |
| Fusion | < 5 ms | < 10 ms | RRF, in-memory |
| Cross-encoder rerank (≤100 cand.) | < 120 ms | < 300 ms | skipped for confident `lookup_clause` |
| Citation validation + assembly | < 20 ms | < 60 ms | metadata-only; no source re-read |
| **End-to-end** | **< 250 ms** | **< 700 ms** | excludes generation |

Quality targets: **Recall@50 ≥ 0.95** on the golden set (candidate stage), **nDCG@10 ≥
0.80**, **citation validity ≈ 100%**, **Arabic/English parity delta ≤ a small, tracked
threshold**. Cold-path (index build / re-embed) is offline and does not count against these.

---

## 14. Architecture, services & APIs

**Hexagonal, ports-and-adapters** — consistent with `packages/extraction`'s ingestion
pipeline and Phase 4's provider abstraction. Every external capability is a port; the
orchestrator owns control flow and knows only the ports.

Services / ports:

| Service | Port(s) it owns / uses | Responsibility |
|---|---|---|
| **RetrievalOrchestrator** | — | owns the stage flow, budgets, trace, fail-safe degradation |
| QueryUnderstanding | `QueryAnalyzerPort` | normalize, detect language, extract entities, expand |
| IntentClassifier | `IntentClassifierPort` | GRC intent + confidence (rules default, LLM optional) |
| RetrievalPlanner | — | intent+entities → `RetrievalPlan` (filters, profiles, weights, k) |
| VectorRetriever | `VectorSearchPort`, `EmbeddingProvider` (reused from Phase 4) | filtered ANN over pgvector |
| KeywordRetriever | `KeywordSearchPort` | BM25, per-language analyzers |
| ExactMatchRetriever | `MetadataStorePort` | code/metadata direct lookup |
| Fusion | — | weighted RRF |
| Reranker | `RerankerPort` | multilingual cross-encoder (vendor-neutral) |
| CitationValidator | `MetadataStorePort` | citability + freshness + scope gate |
| ContextAssembler | — | parent expansion, window dedupe, budget, bundle |
| RetrievalCache | `CachePort` | multi-layer cache (§ cache) |
| EvaluationHarness | — | golden-set metrics, regression gate |

**APIs.** Retrieval is exposed both as a REST endpoint and as a registered **Tool**
(`retrieve_knowledge.v1`), so it's callable from all six callers (CLAUDE.md §9): the AI
Orchestrator, the API, the UI (a future Knowledge Center "search/trace" view), the Workflow
Engine, scheduled jobs, and tests.

```
POST /api/v1/retrieve
  request  {
    query, language?, scope { tenant_id, organization_id },
    filters?  { profiles[], categories[], structure_profiles[], language?, code?, page? },
    intent_override?, top_k?, rerank?, explain?
  }
  response {
    intent, plan,                     # what the engine decided
    results: [ {                      # the cited, ranked bundle
      chunk_id, document_id, text,
      citation { source_filename, code, title, heading_path, page_start, page_end },
      document_profile, structure_profile, language,
      scores { exact, vector, bm25, fused, rerank, final }, confidence
    } ],
    overall_confidence, warnings[], trace, timings
  }

POST /api/v1/retrieve/explain     # full stage-by-stage trace for debugging / the KC
GET  /api/v1/retrieve/health      # index freshness, embedding_version, analyzer status
```

Every response carries the **retrieval trace** (intent, plan, per-retriever ranks, rerank
scores, filters applied, drops with reasons) — the reproducibility/transparency requirement
(CLAUDE.md §19) applied to the read path, and exactly what the Knowledge Center would later
visualize.

---

## 15. Data flow

```
  client / agent / tool
        │  POST /api/v1/retrieve
        ▼
  RetrievalOrchestrator ──────────────────────────────────────────────► trace + timings
        │
        ├─ QueryUnderstanding ─► AnalyzedQuery ──┐
        ├─ IntentClassifier ───► Intent ─────────┤
        │                                        ▼
        │                                 RetrievalPlanner ─► RetrievalPlan (filters, profiles, weights, k)
        │                                        │
        │             ┌──────────────────────────┼──────────────────────────┐
        │             ▼                           ▼                          ▼
        │   ExactMatchRetriever         VectorRetriever              KeywordRetriever
        │   (MetadataStore)          (EmbeddingProvider→pgvector)   (BM25 analyzers)
        │             │                           │                          │
        │             └──────────────► Fusion (weighted RRF) ◄───────────────┘
        │                                        │  candidate set (≤100)
        │                                        ▼
        │                                   Reranker (cross-encoder, RerankerPort)
        │                                        ▼
        │                              Business-rule ranking (§ ranking)
        │                                        ▼
        │                              CitationValidator (drop/flag non-citable, stale, out-of-scope)
        │                                        ▼
        │                              ContextAssembler (parent expand · window dedupe · budget)
        ▼                                        ▼
  RetrievalResult  ◄──────────────────  ContextBundle (cited, ordered, confidence)

  reads only:  knowledge_sections + embeddings + chunk/embedding metadata (+ caches).
  never reads: PDFs or any original source. (Same discipline as the Knowledge Center.)
```

---

## 16. Cache strategy

Multi-layer, all keys **tenant-scoped**, all invalidation keyed on the pipeline's existing
change signals (`chunk_checksum`, `embedding_version`) — so a re-chunk or re-embed cleanly
busts stale entries.

| Layer | Key | TTL / invalidation | Why |
|---|---|---|---|
| **Query-embedding cache** | `hash(normalized_query, model, version)` | long TTL; bust on `embedding_version` change | embedding is the most expensive hot-path call; identical/similar queries recur |
| **Analyzed-query cache** | `hash(raw_query)` | medium TTL | understanding+intent are deterministic per query |
| **Retrieval-result cache** | `hash(normalized_query, filterspec, scope, plan)` | short TTL (freshness-sensitive) | popular queries; must respect scope in the key |
| **Rerank cache** | `hash(query, chunk_id, rerank_model)` | medium TTL; bust on `chunk_checksum` change | cross-encoder pair scores are stable per (query, chunk) |
| **Static indexes** | — | rebuilt/updated incrementally offline | HNSW vector index + BM25 inverted index + metadata filter structures are cold-path assets |
| **Filter/facet metadata** | facet values per tenant | invalidate on ingest | powers the filter UI and predicate compilation |

Rules: **scope is always part of the cache key** (no cross-tenant leakage via cache);
result-cache entries store the validated citation payload so a cache hit is still citable;
caches are an optimization, never a correctness dependency — a cold cache changes latency,
not answers.

---

## 17. Ranking strategy

A single, explicit **multi-stage funnel**: recall → learned precision → deterministic
business policy → citation gate. Each stage narrows and re-orders; the order of operations
is deliberate.

1. **Candidate generation (recall).** Hybrid retrieval (§6) over-fetches; the goal is that
   the relevant chunk is *present*, not yet on top. Measured by Recall@k.
2. **Fusion (rank-space merge).** Weighted RRF (§6) — scale-free, intent-weighted.
3. **Learned precision.** Cross-encoder rerank (§9) — the primary relevance signal for
   conceptual intents.
4. **Deterministic business boosts** (applied *after* learned relevance, transparently, each
   logged in the trace):
   - **exact-code match** — a candidate whose `code` equals a query-extracted locator is
     pinned to the top for `lookup_clause`;
   - **profile alignment** — candidate `document_profile` ∈ the intent's selected profiles;
   - **normative strength** — mandatory obligations/controls over recommended/informative
     (from the extracted `KnowledgeObject.normative_strength`, Knowledge Library §3);
   - **version recency** — the in-force framework version over a superseded one (assessments
     pin versions — Knowledge Library §5/§13);
   - **scope preference** — flips by intent: `policy_lookup` prefers the organization's own
     policy; a standards question prefers the global source;
   - **language match** — small boost for same-language results (cross-lingual still allowed);
   - **extraction-quality** — down-weight chunks flagged low-quality (e.g. the Arabic
     glyph-corruption set, §11).
5. **Diversity / de-dup.** Collapse near-duplicate windows and over-representation of a
   single source so the top-k isn't ten slices of one page.
6. **Citation gate (final cut).** §10 — anything not citable/live/in-scope is removed
   *after* ranking, so ranking never depends on, nor is polluted by, un-citable text.

The split is intentional: **learned models decide relevance; deterministic rules encode GRC
policy; the citation gate is absolute.** A reviewer can read the trace and see exactly why
any result placed where it did — which is the auditability the domain requires.

---

## 18. Extensibility & explicit non-goals

**Extensible by the same seams as every prior phase:**
- New embedding or reranker vendor → a new adapter behind `EmbeddingProvider` / `RerankerPort`
  (Voyage, Gemini, local BGE/Nomic, Ollama) — config, not code.
- New intent → one entry in the intent taxonomy + a routing rule; low-confidence still
  degrades to `conceptual`.
- New document profile / category → already flows from the Chunking Engine's profile catalog;
  profile selection (§5) picks it up as data.
- Keyword engine (in-Postgres BM25 vs. dedicated) → a `KeywordSearchPort` adapter choice
  settled by benchmark.
- **Cross-framework mapping retrieval** (`cross_framework_mapping` intent) leans on the
  typed relationship graph from Knowledge Library §7 — this document routes to it; the graph
  traversal itself is that document's concern.

**Explicit non-goals for this phase (named, not overlooked):**
- **No generation / AI answering.** This engine produces a cited `ContextBundle` and stops.
  Turning it into an answer — grounded generation, "insufficient evidence" behaviour,
  hallucinated-citation rejection against this bundle's allow-list — is the next phase.
- **No vector database build-out.** pgvector is already the decision (Knowledge Library §6);
  this is the read design over it.
- **No Tier-2 (trusted-source research) or Tier-3 (LLM general knowledge) fallback** — those
  remain as Knowledge Library §10 describes; this document is Tier-1 internal retrieval.
- **No multi-hop / agentic retrieval loops** — single-shot retrieval now; iterative
  retrieval is future work, named not designed.
- **No code.** Architecture only — implementation is a later, separately-approved phase.

---

## Implementation status

- **Phase 9A** — the engine core (ports & adapters: metadata filtering → vector + keyword
  fusion → ranking → citation validation → assembly) is implemented in
  `v2/packages/retrieval-engine/` with in-memory providers.
- **Phase 9B** — the "No vector database build-out" non-goal above is now realized as the
  production storage adapter: `PgVectorProvider` (PostgreSQL + pgvector, HNSW/cosine) is a
  drop-in behind the `VectorSearchProvider` port, so the engine, planner, fusion, ranking,
  citation, and assembly are **unchanged** — the engine remains unaware of where vectors
  live. Schema, index-strategy rationale (HNSW vs IVFFlat), the idempotent/incremental
  import pipeline, and benchmark/validation numbers are documented in
  [`v2/packages/retrieval-engine/OPERATIONS.md`](../../packages/retrieval-engine/OPERATIONS.md).

Generation / AI answering, Tier-2/Tier-3 fallback, cross-encoder reranking, and multi-hop
retrieval remain future phases, as named above.

*Living design document. Proceed to implementation one stage at a time, on explicit
approval, consistent with how the Knowledge Pipeline was built.*
