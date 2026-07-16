# Rasheed V2 — Knowledge Library Architecture

- Status: Proposed — design document, nothing in this document is implemented yet
- Date: 2026-07-11
- Companion: [ADR 0035](../../../docs/adr/0035-v2-knowledge-library.md)
- Scope boundary: **v2/ only.** `apps/web` and every existing top-level `packages/*` path are
  frozen for the purposes of this document — nothing here modifies them. Where this design
  reuses existing code, it does so by *promoting* (copying/renaming into `v2/`) not by
  editing in place.

---

## 0. Where this design comes from

Before proposing anything new, it's worth being explicit that most of the hard design work
for a Knowledge Library **already happened** in this repository — across ADR 0007, 0008,
0025–0032 and `ARCHITECTURE_DECISION_LOG.md`'s ADL-0007/ADL-0008 — and is sitting, tested and
mostly working, in `packages/domain/grc_domain/knowledge/`, `packages/extraction*`,
`packages/framework-engine/`, `packages/knowledge-ontology/`, and `packages/rag/`. The
Knowledge Sources Audit done ahead of this document found the same conclusion from the
opposite direction: **the architecture is not the gap. Deployment is.** Nothing in the
existing Python backend was ever scheduled, containerized, or wired to a live retrieval path.

So V2's core bet is: **promote what already works, finish what's half-built, deploy it for
real this time, and only design new pieces where a real gap exists.** Section 2 below marks,
for every component, whether it's "promote as-is," "promote and extend," or "new."

---

## 1. Vision and goals

### Vision
One knowledge system — not two. Today, "what Rasheed knows" is split across a 12-control
TypeScript file, a well-designed but empty Python domain model, and a set of embeddings
nobody reads. V2 replaces that split with a single **Knowledge Library**: every framework,
regulation, and internal document a tenant can draw on, stored once, versioned, related to
each other through a typed graph, and retrievable — with citations — by every AI feature
Rasheed ships from here forward.

### Goals
1. **Comprehensive, real content** for the frameworks and regulations Rasheed claims to
   support — not representative 10-control samples.
2. **One model for global and tenant knowledge.** A framework control and a tenant's
   uploaded policy should be retrievable through the same query path, distinguished by
   scope, not by living in two unrelated systems.
3. **Config-driven extensibility** (continuing ADR 0007's rule): a new framework, regulator,
   or source is a data change, never a code change.
4. **A typed knowledge graph**, not just a flat document store — so "which controls satisfy
   this obligation" or "which policy addresses this control" are queries, not manual work.
5. **Provenance on everything** (continuing ADR 0008/CLAUDE.md §19): every AI answer traces
   to a source, a version, and a confidence score. No uncited claims.
6. **It actually runs in production.** This is the goal the current backend failed. V2 ships
   with real deployment and scheduling from day one — see §9 and §11.
7. **A defined path back to the product**, not a second permanent parallel stack. V2 is
   built to eventually become the thing `apps/web` (or its V2 successor UI) calls — see §11.

### Explicit non-goals (for this phase)
- Not migrating or rewriting Policies/Risks/Evidence — those are frozen, working production
  features; V2's Knowledge Library is additive infrastructure, not a CRUD replacement.
- Not building a graph database — see §7 for why Postgres carries the graph for now.
- Not solving multi-embedding-provider abstraction beyond what already exists in `grc_llm` —
  reused, not redesigned.

---

## 2. Folder structure for V2

A new, isolated root — `v2/` — sitting alongside `apps/` and `packages/`, never inside them.
This is a **deliberate, visible boundary**: anyone opening the repo tree immediately sees
what's frozen production and what's active V2 work.

```
v2/
├── docs/
│   └── architecture/
│       └── knowledge-library.md          # this document
│
├── apps/
│   └── api/                              # NEW: the only deployable backend V2 needs.
│                                          # FastAPI, thin — mounts the routers below.
│                                          # (unlike today's apps/api, this one ships with
│                                          # a Dockerfile + a real deploy target, see §9/§11)
│
├── packages/
│   ├── knowledge-domain/                 # PROMOTE from packages/domain/grc_domain/knowledge
│   │                                      # (KnowledgeSource, Version, Object, Relationship —
│   │                                      # already mature, already tested — see §0)
│   ├── knowledge-persistence/            # PROMOTE + FINISH packages/persistence's knowledge
│   │                                      # slice (KnowledgeSource is done — this session's
│   │                                      # 0002_knowledge_source_scope.py migration; Version/
│   │                                      # Object/Relationship repositories are the gap)
│   ├── knowledge-extraction/             # PROMOTE packages/extraction + extraction-adapters
│   │                                      # (the hexagonal ingestion pipeline — already fully
│   │                                      # ported, see §9)
│   ├── knowledge-retrieval/              # PROMOTE + EXTEND packages/rag, implementing the
│   │                                      # already-agreed ADR-0032 tiered retrieval (§10)
│   ├── framework-engine/                 # PROMOTE packages/framework-engine, seeded with
│   │                                      # real (not sample) framework data
│   └── ontology/                         # PROMOTE packages/knowledge-ontology
│
├── data/                                 # "frameworks are data" (ADR 0007) — promoted and
│   ├── frameworks/                       # expanded from /frameworks, /ontology,
│   ├── ontology/                         # /knowledge-catalog, /trusted-sources,
│   ├── knowledge-catalog/                # /regulatory-sources at the repo root
│   └── trusted-sources/
│
├── infra/
│   ├── docker/                           # NEW: Dockerfile + compose for v2/apps/api —
│   │                                      # the exact thing that never existed for the old
│   │                                      # apps/api (confirmed absent in the audit)
│   └── scheduler/                        # NEW: the cron/worker config that never existed
│                                          # either — see §9
│
└── migrations/                           # Alembic, continuing from
                                           # packages/persistence/grc_persistence/migrations
                                           # (2 revisions today; renumbered into this history)
```

**What's explicitly *not* duplicated:** `grc_domain`'s non-knowledge contexts (Controls,
Policies, Risks, Evidence, Tenancy) stay exactly where they are in `packages/domain` —
untouched, out of scope. V2 only promotes the Knowledge-related slice.

**Migration note (not performed by this document):** promotion means `git mv` plus import
path updates, done as its own reviewable PR per package — not a rewrite. Each promoted
package keeps its existing tests; a test suite passing before and after a `git mv` is the
acceptance bar for that PR.

---

## 3. Database schema

One Postgres database (pgvector enabled), continuing the pattern already proven in both
`apps/web` (`document_chunks`) and the existing Python backend (`regulation_sections`):
**global/shared tables carry no `tenant_id`; tenant-owned tables do.** The Knowledge Library
is predominantly the former — frameworks and regulations are shared reference data by
nature — with tenant-scoped rows only where §4's `KnowledgeScope` says `organization`.

```sql
-- ── Identity ─────────────────────────────────────────────────────────────────
create table knowledge_sources (
  id                    text primary key,
  scope_kind            text not null check (scope_kind in ('global','organization')),
  scope_organization_id text references organizations(id),   -- null when global
  short_code            text not null,
  title                 jsonb not null,        -- LocalizedText: [{language, text}, ...]
  authority             text not null,
  jurisdiction          text not null,
  knowledge_domain      text not null,         -- FK-by-value into knowledge_domains (§8)
  document_type         text not null,
  classification        text not null default 'confidential',
  framework_refs        jsonb not null default '[]',
  tags                  jsonb not null default '[]',
  canonical_languages   jsonb not null default '[]',
  steward               jsonb,                  -- Actor: {kind, reference, display_name}
  current_version_id    text references knowledge_source_versions(id),
  version               integer not null default 1,   -- optimistic concurrency
  created_at            timestamptz not null,
  updated_at            timestamptz not null
);
create index on knowledge_sources (scope_organization_id) where scope_organization_id is not null;
create index on knowledge_sources (short_code);
create index on knowledge_sources (knowledge_domain);

-- ── Versions (the governed, effective-dated content) ───────────────────────────
create table knowledge_source_versions (
  id                    text primary key,
  source_id             text not null references knowledge_sources(id),
  version_label         text not null,          -- e.g. "2022", "v2.0"
  status                text not null check (status in
                          ('draft','in_review','approved','published','superseded',
                           'withdrawn','archived')),
  official_citation     text,
  content_hash          text not null,          -- dedupe / re-ingestion detection
  effective_from        date,
  effective_to          date,
  approved_by           text,
  approved_at           timestamptz,
  published_at          timestamptz,
  created_at            timestamptz not null,
  updated_at            timestamptz not null,
  unique (source_id, version_label)
);
create index on knowledge_source_versions (source_id, status);

-- ── Documents (one language/format manifestation of a version) ────────────────
create table knowledge_documents (
  id                    text primary key,
  version_id            text not null references knowledge_source_versions(id),
  language              text not null,
  document_format       text not null,          -- pdf | docx | html | ...
  source_url            text,
  storage_key           text,                    -- pointer to blob storage, if retained
  created_at            timestamptz not null
);
create index on knowledge_documents (version_id, language);

-- ── Sections (the atomic, citable unit — one article/clause/control) ──────────
create table knowledge_sections (
  id                    text primary key,
  document_id           text not null references knowledge_documents(id),
  section_type          text not null,           -- article | clause | control | chapter | ...
  code                  text not null,            -- e.g. "A.5.15", "Article 12"
  path                  jsonb not null default '[]', -- structural breadcrumb, e.g. ["Ch.2","Art.12"]
  title                 jsonb,                    -- LocalizedText
  text                  jsonb,                    -- LocalizedText — the citable content
  position              integer not null,
  parent_section_id     text references knowledge_sections(id),
  amendment_note        jsonb,                    -- LocalizedText
  embedding             vector(1536),              -- see §6 for the dimension decision
  embedding_model       text,
  embedded_at           timestamptz
);
create index on knowledge_sections (document_id, position);
create index on knowledge_sections (parent_section_id);
-- vector index: see §6 — deferred until the pgvector 2000-dim cap and index-type choice
-- are settled per source volume; sequential scan is the safe default, same as today.

-- ── Extracted knowledge objects (immutable, version-pinned facts) ─────────────
create table canonical_knowledge_objects (
  id                    text primary key,
  scope_kind            text not null check (scope_kind in ('global','organization')),
  scope_organization_id text references organizations(id),
  object_type           text not null,           -- requirement | control | definition | ...
  created_at            timestamptz not null
);

create table knowledge_objects (
  id                    text primary key,
  canonical_id          text not null references canonical_knowledge_objects(id),
  source_version_id     text not null references knowledge_source_versions(id),
  section_id            text references knowledge_sections(id),
  object_type           text not null,
  payload               jsonb not null,           -- typed by object_type, see §6
  normative_strength    text not null,             -- mandatory | recommended | informative
  confidence            numeric(4,3) not null,
  provenance            jsonb not null,             -- {citation, extractor, extractor_version}
  curation_status       text not null check (curation_status in
                          ('extracted','submitted_for_review','published','rejected',
                           'superseded')),
  revision              integer not null default 1,
  created_at            timestamptz not null
);
create index on knowledge_objects (canonical_id);
create index on knowledge_objects (source_version_id);
create index on knowledge_objects (curation_status);

-- ── Relationships (the typed graph — see §7) ───────────────────────────────────
create table knowledge_relationships (
  id                    text primary key,
  relationship_type     text not null,            -- closed vocabulary, see §7
  from_ref              jsonb not null,            -- {kind, id} — polymorphic endpoint
  to_ref                jsonb not null,
  provenance            jsonb not null,
  confidence            numeric(4,3),
  source_version_id     text references knowledge_source_versions(id), -- for version-pinning
  created_at            timestamptz not null
);
create index on knowledge_relationships (relationship_type);
create index on knowledge_relationships ((from_ref->>'id'));
create index on knowledge_relationships ((to_ref->>'id'));

-- ── Ingestion run tracking (operational visibility — see §9) ──────────────────
create table knowledge_ingestion_runs (
  id                    text primary key,
  source_id             text references knowledge_sources(id),
  pipeline              text not null,            -- 'framework' | 'regulation' | 'tenant_doc'
  status                text not null check (status in
                          ('running','succeeded','failed','partial')),
  stage                 text,                      -- last stage reached, for failure triage
  items_processed       integer not null default 0,
  items_failed          integer not null default 0,
  started_at            timestamptz not null,
  finished_at           timestamptz,
  error_summary         text
);
create index on knowledge_ingestion_runs (source_id, started_at desc);
```

**Design decisions worth calling out:**
- **JSONB for `LocalizedText`, `path`, `provenance`, `payload`.** Matches the shape already
  chosen and shipped in `packages/persistence`'s `0002_knowledge_source_scope.py` migration
  this session — not a new pattern, continuity with what's already been decided.
- **`from_ref`/`to_ref` as polymorphic JSONB, not typed foreign keys.** A relationship can
  point at a `KnowledgeSection`, a `KnowledgeObject`, or (via `framework_refs`) a Framework
  Engine control — a single FK column can't span that. Trade-off accepted: referential
  integrity is enforced at the application layer (the persistence adapter validates both
  ends exist before insert), not the database — the same trade-off `ai_tool_invocations`
  already makes for its polymorphic `resource_type`/`resource_id` pair.
- **Optimistic concurrency (`version` column) on `knowledge_sources`** — reusing the exact
  `version_id_col` pattern already proven across every `apps/web` and `packages/persistence`
  aggregate table.

---

## 4. Knowledge Source model

**Promoted as-is** from `packages/domain/grc_domain/knowledge/entities.py::KnowledgeSource` —
this aggregate is already mature, already has full unit test coverage, and (per §0) is the
strongest asset in the current codebase. No redesign needed.

A `KnowledgeSource` is the **stable identity** of a body of knowledge — "ISO/IEC 27001," "the
Saudi PDPL," "Acme Corp's Information Security Policy." It is deliberately small: identity +
facets + a pointer to the currently in-force version. Content lives one level down, in
`KnowledgeSourceVersion` (§5), so a source can accrue many versions over years without the
identity record ever growing.

| Field | Purpose |
|---|---|
| `scope` | `KnowledgeScope` — `GLOBAL` (shared across every tenant) or `ORGANIZATION` (isolated to one tenant, carries `organization_id`). This is the mechanism that lets one query span both a framework and a tenant's own policy. |
| `short_code` | Stable human identifier, e.g. `iso-27001`, `nca-ecc`, `acme-infosec-policy`. |
| `title` | `LocalizedText` — multilingual by construction, not bolted on. |
| `authority`, `jurisdiction` | Who issued it, where it applies — "ISO," "international"; "NCA," "Saudi Arabia"; "Acme Corp," "internal." |
| `knowledge_domain` | One of the 11 taxonomy domains (§8). |
| `document_type` | `law \| standard \| framework \| policy \| procedure \| ...` — a controlled vocabulary (§8), not a free string. |
| `framework_refs` | Cross-links to Framework Engine controls this source relates to. |
| `tags`, `canonical_languages`, `steward` | Discovery metadata and an accountable owner. |
| `current_version_id` | Pointer to the in-force `KnowledgeSourceVersion` — the identity never holds content directly. |

**Two-library model, made concrete:** an organization's retrieval query for "what do we know
about access control" spans every `GLOBAL` source (ISO 27001, NCA ECC, PDPL, ...) plus every
`ORGANIZATION` source scoped to that one tenant (their own policies, their own uploaded
evidence) — one query shape, two visibility rules, exactly like the two-library scope this
session already implemented for `packages/persistence`'s `KnowledgeSourceRepository`.

---

## 5. Knowledge Document model

**Promoted as-is** from the same `packages/domain/grc_domain/knowledge/entities.py` module —
`KnowledgeSourceVersion`, `KnowledgeDocument`, `KnowledgeSection`.

```
KnowledgeSource  (identity)
   └─ KnowledgeSourceVersion   (one governed, effective-dated release)
        ├─ status: Draft → In Review → Approved → Published → Superseded/Withdrawn → Archived
        ├─ KnowledgeDocument   (one language/format manifestation — e.g. the Arabic PDF)
        │     └─ KnowledgeSection  (one citable unit — an article, a clause, a control)
        └─ KnowledgeDocument   (the English PDF, if bilingual)
              └─ KnowledgeSection  ...
```

**Why three levels, not one "document" blob:**
- **Version** exists because regulations and frameworks *change*, and an assessment must be
  able to say "we evaluated against the 2022 edition," permanently, even after a 2027 edition
  publishes. This is CLAUDE.md §13's "assessments pin the version they ran against" applied
  to the whole Knowledge Library, not just Framework Engine.
- **Document** exists because the same version often ships in two languages (Arabic-original
  Saudi law + an English working translation) or two formats — each is retrievable and
  citable independently, but both point at one governed version.
- **Section** exists because the citable, retrievable, embeddable unit of a law or standard
  is an *article* or a *control*, not a page or a fixed character window — this is the
  single biggest quality improvement V2 makes over `apps/web`'s current character-window
  chunking (§6) for structured sources.

**Governance lifecycle rule, carried over unchanged:** `publish()` is guarded — it fails
unless the version has already passed `Approved`, and unless it owns at least one document.
Content is immutable once published (an amendment creates a new version, it does not edit
the old one) — the same "append, never mutate" posture already enforced in the domain layer.

---

## 6. Chunk & Embedding model

> **See also:** [Chunking Engine Architecture](chunking-engine.md) — the detailed design of
> *how* structure-aware chunking recognizes ISO clauses, NIST sections, Saudi regulation
> articles, contracts, policies, and procedures; the chunk metadata schema; parent/child
> storage; overlap rules; and page-reference preservation. This section states the policy
> decision (structured vs. windowed, embedding dimension); that document is the engine.

This is the one area where V2 genuinely extends, rather than just promotes, existing design —
because today's embedding story is split three ways (`document_chunks` for tenant uploads,
`regulation_sections.embedding` for Saudi law, nothing for anything else) and none of the
three read each other.

**Unified rule: the embeddable unit is the `KnowledgeSection`, or a `KnowledgeObject` when
one exists.** Two embedding strategies, chosen per source shape:

| Source shape | Chunking strategy | Rationale |
|---|---|---|
| Structured (laws, standards, framework controls) | **Structure-aware** — one section per article/clause/control, already segmented by the ingestion pipeline's `SegmenterPort` (§9). No sliding window. | A control or article is a semantically complete, independently citable unit — splitting it loses meaning; merging several loses precision. |
| Unstructured (a tenant's uploaded policy PDF with no reliable heading structure) | **Fallback windowed chunking** — the same 1200-char/150-overlap approach `apps/web` already uses for `document_chunks`, applied inside a `KnowledgeSection` per window. | Preserves what already works for the one case (arbitrary tenant documents) where structure-aware segmentation genuinely can't be guaranteed. |

**Embedding model versioning.** `embedding_model` and `embedded_at` are columns on
`knowledge_sections`, not assumed constant — because a future switch to a new embedding
model must not silently orphan old vectors. Re-embedding is a background job keyed on
`embedding_model <> current_model`, not a destructive migration.

**Dimension choice: 1536, not 3072.** `apps/web`'s existing `document_chunks` already hit
pgvector's documented ANN-index cap at 2000 dimensions and fell back to sequential scan with
OpenAI's 3072-dim `text-embedding-3-large`. The Knowledge Library is expected to hold an
order of magnitude more vectors (every article of every regulation, not just one tenant's
uploads), where sequential scan stops being viable well before `document_chunks` felt it.
V2 defaults to `text-embedding-3-large` truncated to **1536 dimensions** (OpenAI's own
Matryoshka-style truncation support), which fits under the pgvector HNSW index cap with an
acceptable, measured recall cost — a real index, not a promise to add one "later," is the
point. This is a decision this document makes explicitly rather than leaving open, since it
directly blocks whether §10's retrieval can scale.

**What doesn't get embedded:** structural-only sections (a bare chapter heading with no body
text) are skipped — the same rule `packages/persistence-web`'s `list_needing_embedding`
already implements for `regulation_sections`, carried forward unchanged.

---

## 7. Relationships / Knowledge Graph model

**Promoted as-is**, with one addition. `packages/domain`'s `KnowledgeRelationship` aggregate
plus `packages/knowledge-ontology`'s six-member `RelationshipType` enum already define the
graph:

| Relationship type | Example |
|---|---|
| `requirement_to_control` | An NCA ECC requirement is satisfied by a specific control. |
| `control_to_evidence` | A control is evidenced by an uploaded audit report. |
| `risk_to_control` | A risk is mitigated by a control. |
| `contract_type_to_clause` | An NDA contract type requires a confidentiality clause. |
| `regulation_to_obligation` | A PDPL article gives rise to a specific obligation. |
| `policy_to_requirement` | An internal policy addresses a framework requirement. |

**V2 addition: `framework_to_framework`.** The existing `ControlCorrespondence`/cross-mapping
mechanism in `packages/framework-engine` (ISO 27001 ↔ NCA ECC) is currently a *separate*
mechanism from the ontology's relationship graph. V2 folds it in as a seventh relationship
type, so "what does this ISO control map to in NCA ECC" and "what evidence satisfies this
control" are the same kind of graph traversal, not two different subsystems a caller has to
know to query separately.

**Why Postgres, not a dedicated graph database, for now:** the audit found the existing
`/ontology/relationships.json` explicitly described as "illustrative, not a live graph" —
real edge volume is unproven. A polymorphic edge table (§3) with indexes on both endpoints
supports every traversal this design currently needs (1–2 hop lookups: "controls for this
requirement," "requirements this control satisfies") at the volumes in play. §11 names the
condition under which this should be revisited.

---

## 8. Categories and taxonomy

**Promoted and completed** from `/ontology` and `packages/knowledge-ontology` —
`KnowledgeDomain`'s 11 members are the taxonomy's spine, already used consistently across
`KnowledgeSource.knowledge_domain`, the question catalog, and the ontology's `Topic` model:

> Governance · Risk Management · Compliance · Internal Controls · Audit · Contracts ·
> Vendor Management · Data Protection · Cybersecurity Governance · Policies & Procedures ·
> Regulatory Obligations

The audit found topic data exists for 8 of these 11 today — **V2 closes that gap**,
completing Vendor Management, Audit, and Policies & Procedures as part of the initial seed
data pass (§9), so every domain a `KnowledgeSource` can declare has real ontology backing.

**Document types** (`law | executive_regulation | standard | framework | policy | procedure |
template | contract | internal_document | ...`) and **jurisdictions** (ISO 3166 country
codes, or `international`) are both **data, not enums baked into code** — a new document
type or jurisdiction is a config addition, following the same "frameworks are data" rule
(ADR 0007) applied consistently across the whole taxonomy, not just Framework Engine.

---

## 9. Document ingestion pipeline

**Promoted as-is** — `packages/extraction`'s hexagonal pipeline (`grc_extraction`) already
defines exactly the right stages, already ported and tested (see §0):

```
intake ──▶ parse ──▶ normalize ──▶ segment ──▶ classify ──▶ extract ──▶ score ──▶ map ──▶ persist
 (fetch)   (Ocr/     (clean+lang   (recover    (confirm     (candidate  (confidence  (Framework   (Knowledge
            Document  tag, keep    logical      doc type)    knowledge   score)       Engine       Ingestion
            Adapter)  structure)   skeleton)                 objects)                 controls)    Port)
```

Every stage is a port (`DocumentAdapterPort`, `NormalizerPort`, `SegmenterPort`,
`ClassifierPort`, `ExtractorPort`, `RelationshipExtractorPort`, `ConfidenceScorerPort`,
`FrameworkMappingPort`, `KnowledgeIngestionPort`) — rule-based and AI-assisted
implementations are interchangeable behind the same contract, exactly as ADR 0008 requires
("embedders, vector stores, chunking, and re-rankers sit behind swappable interfaces").

**What's actually missing, and what V2 must build (per ADL-0008):**
1. **The production `KnowledgeIngestionPort` adapter.** Today only an in-memory reference
   adapter exists. Blocked historically on the M5 persistence realignment — **already
   unblocked this session** for `KnowledgeSource` (migration `0002_knowledge_source_scope.py`);
   `KnowledgeSourceVersion`/`KnowledgeObject`/`KnowledgeRelationship` repositories are the
   remaining gap, tracked as the first V2 implementation slice.
2. **Real deployment and scheduling.** This is the actual root cause the audit surfaced —
   not missing code, a missing cron job. `v2/infra/scheduler/` (§2) is not optional
   infrastructure; it's the single change that turns "a pipeline that works when run by
   hand" into "a knowledge library that stays current." Concretely: a scheduled worker per
   source type (framework updates infrequent/manual-trigger, regulation crawls
   daily/weekly per source, tenant document ingestion event-triggered on upload).
3. **A human review gate before publish**, for every source-type — continuing the
   `Draft → In Review → Approved` lifecycle already modeled (§5), never auto-publishing
   AI-extracted content, per CLAUDE.md's human-in-the-loop principle and the existing
   `regulation_review` precedent (ADR 0031).

**Idempotency**, already a property of the existing design (`content_hash`-keyed dedupe on
`KnowledgeSourceVersion`, `KnowledgeIngestionPort.find_existing`) — carried forward unchanged.

---

## 10. AI retrieval flow

> **See also:** [Retrieval Engine Architecture](retrieval-engine.md) — the detailed design
> of **Tier 1 (internal retrieval)** below: query understanding, GRC intent classification,
> metadata filtering, document-profile routing, hybrid vector + BM25 + exact retrieval,
> cross-encoder re-ranking, citation validation, context assembly, and Arabic optimization.
> This section states the three-tier policy; that document is the Tier-1 engine.

V2 **implements ADR 0032's already-agreed, Product-Owner-specified design** — proposed in
this repo, never built. This document is where it stops being deferred.

```
query
  │
  ▼
Tier 1 — internal Knowledge Library (this document's tables)
  │  hybrid search: vector (knowledge_sections.embedding) + keyword + metadata
  │  filtered by scope (global ∪ this tenant's organization-scoped sources) first, always
  │  re-ranked, confidence-scored
  │
  ├─ confident hit? ──▶ grounded answer, cited to source + version + section, confidence shown
  │
  ▼ (no confident hit)
Tier 2 — trusted-source live research
  │  reuse packages/knowledge-research's existing ResearchCoordinator as-is (ADR 0026) —
  │  fetches from the curated /trusted-sources catalog (§2), synthesizes a cited answer
  │
  ├─ confident hit? ──▶ answer, clearly labeled "external research," cited, confidence shown
  │
  ▼ (still nothing)
Tier 3 — LLM general knowledge
  │  the one ungrounded tier — no citation is possible, and none is fabricated
  │
  └─▶ answer explicitly labeled "not grounded in a verified source" — never presented
      indistinguishably from a Tier 1/2 cited answer (CLAUDE.md §12.3)
```

**Design decisions this document is making, that ADR 0032 left open:**
- **Tier 1 spans both `document_chunks`-style tenant content and `knowledge_sections`** in
  one query, distinguished by `scope`, not two separate lookups the caller has to know to
  make — this is the direct payoff of §4's two-library model.
- **Tier 1/Tier 2 disagreement** is surfaced, not silently resolved: if both tiers return an
  answer above threshold, Tier 1 (the platform's own verified content) wins for display, but
  the response's provenance includes both, so a reviewer can see a live source disagrees
  with the internal library — a signal that the internal content may be stale, not noise to
  suppress.
- **Tier 2 only fires when Tier 1 is empty or low-confidence** — gap detection (already
  built, ADR 0025) stays a separate, async "what's missing" signal for the ingestion
  pipeline, not a blocking part of the live query path.

**Grounding contract, unchanged from ADR 0008:** every factual claim carries a citation
(source, version, section) and a confidence signal; low confidence escalates to a human
rather than guessing; retrieved source IDs and model/prompt versions are logged for
reproducibility (CLAUDE.md §19).

---

## 11. Future extensibility

- **New frameworks/regulations/sources are always a data PR**, never a code change — the
  rule ADR 0007 already established, now enforced consistently for every knowledge type,
  not just Framework Engine.
- **New relationship types** extend the closed enum (§7) plus a migration adding the new
  value to the check constraint — a small, reviewable, explicit change (a closed vocabulary
  is a deliberate choice: an *open* one would let ingestion silently invent relationship
  semantics nobody agreed to).
- **Pluggable embedding providers**, already true via `grc_llm`'s `EmbeddingModel` port —
  swapping models means adding a new `embedding_model` value, not touching retrieval code.
- **Graph database migration path, named not built:** if 1–2 hop Postgres traversals (§7)
  stop being sufficient — multi-hop reasoning across frameworks, obligations, and controls
  at real scale — the polymorphic edge table's shape (typed `from`/`to`/`relationship_type`)
  maps directly onto a property graph; migrating means an export job, not a redesign.
  Trigger condition: query latency or traversal-depth requirements that a benchmark shows
  Postgres can't meet — not speculative.
- **The path back to the product**, stated plainly: V2 is not meant to become a second
  permanent parallel backend the way the current `packages/*` is. Once the Knowledge Library
  is real and deployed, the next phase is wiring a production surface (a V2 API, then a V2
  UI or an `apps/web` integration point) to it — explicitly scoped as future work, not
  designed here, but named so V2 doesn't quietly repeat the isolation that made the current
  backend's excellent domain model deliver zero product value.
- **Multi-language expansion** beyond Arabic/English: `LocalizedText` already supports an
  arbitrary language list per field — adding a language is data, not schema.

---

## Summary: what V2 promotes vs. builds new

| Component | Promote as-is | Promote + extend | New |
|---|---|---|---|
| Knowledge Source model (§4) | ✓ | | |
| Knowledge Document/Version/Section model (§5) | ✓ | | |
| Chunk & embedding model (§6) | | ✓ dimension choice, dual chunking strategy | |
| Relationship / graph model (§7) | ✓ | ✓ + framework-to-framework edge | |
| Taxonomy (§8) | | ✓ complete the missing 3 domains | |
| Ingestion pipeline stages (§9) | ✓ | | |
| Production ingestion adapter (§9) | | ✓ finish the M5 realignment | |
| Deployment + scheduling (§9) | | | ✓ — the actual root cause fix |
| Retrieval flow (§10) | | ✓ implement ADR 0032 as designed | |
| Framework Engine seed data (§8/§11) | | ✓ real content, not 10-control samples | |
