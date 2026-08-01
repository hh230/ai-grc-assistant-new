# ADR 0057: Extraction produces a canonical Artifact — the format is replaceable

- Status: **Accepted** (2026-07-25) — owner-accepted **with the Artifact Identity, `summary`, and
  `structural_relationships` additions** (see Decision). Supersedes the earlier "ADR-EXT-1 / Entity
  Store" sketch in
  [stage-2-extraction-readiness.md](../../v3/docs/reports/stage-2-extraction-readiness.md), which the
  owner **rejected** for binding a stage to JSON storage. The canonical shape defined here is what
  Supabase (Phase 5) and embeddings (Phase 6) also conform to.
- Date: 2026-07-25
- Deciders: **Product Owner**, Architecture
- Related: ADR 0056 (Knowledge Extraction Port — this is its output type) ·
  [CANONICAL-MODEL.md](../../v3/docs/knowledge/CANONICAL-MODEL.md) §1 (document ≠ knowledge), §10.11
  (append-only), §11 (physical schema is a later, separately-approved stage) · ADR 0041 (knowledge
  source storage) · ADR 0045 (persistence mechanism).

## Context

The Extraction Port (ADR 0056) must emit its result somewhere. The first sketch proposed
`v3/knowledge/entities/*.json` as an "Entity Store." The owner rejected the **framing**: it makes
JSON *the* temporary database and re-couples an entire stage to one storage mechanism — repeating
the very coupling V3 exists to break.

> **Knowledge ≠ Storage.** V3 already separated *document* from *knowledge*; it must equally
> separate the *knowledge artifact* from the *storage format*.

The output of extraction is an **Extraction Output** — an **Artifact**, not a **Repository**. If in
a month the output should land directly in PostgreSQL, Parquet, or SQLite, that must **not** change
this decision or any extractor.

## Decision

**We will define extraction's output as a *Canonical Extraction Artifact* whose logical shape is
fixed, and whose serialization format is a replaceable Realization. This ADR names a shape, not a
storage.**

**The Artifact is Canonical, not Temporary (owner principle).** It is the **official output of the
Extraction stage**, not a scratch file. The same artifact is later consumed for **rebuild,
regression, cross-version diff, debugging, and embedding re-generation** — so it is retained and
append-only (§10.11), never overwritten in place.

- **The canonical artifact (fixed contract):**
  - an **`ArtifactIdentity`** — the identity of *the artifact itself*, **distinct from entity
    provenance**. It answers *"a year from now, why does this ISO-27001 artifact differ — did the
    **source** change or did the **extractor** evolve?"* Fields:
    `artifact_id · source_id · source_version · extractor_version · protocol_version ·
    contract_version · content_hash · generated_at`.
    - `content_hash` = the reproducibility hash over the canonical entities **and structural
      relationships** (ADR 0056 guarantee 1).
    - `generated_at` = wall-clock, **metadata only — excluded from `content_hash` and `artifact_id`**,
      so a reproducible re-run stays byte-identical.
    - `artifact_id` = a deterministic composite of the identity axes
      (`source@version ~ extractor ~ protocol ~ contract ~ content_hash`), so any change is
      **attributable** to source vs extractor vs protocol vs contract.
  - a **`summary`** — a compact, self-describing header so a consumer/agent learns what the artifact
    holds **without reading every entity**: `entities`, `structural_relationships`, `warnings`,
    `unknown` (counts), `counts_by_type`, `state`, `language`, `normalization` (e.g. `NFKC`). Derived
    data only — no new facts.
  - a set of **Knowledge Entities**, each carrying the 14 logical fields ratified with the owner:
    `source_id · version · entity_id · parent · type · name · number · description · language ·
    authority · license · stability · confidence · provenance` (+ the retained `native_node_type`).
    *(`description` for `Licensed` sources is marked egress-restricted per §10.6.)*
  - a set of **`structural_relationships`** — the parent hierarchy the extractor **read** from the
    source's own structure, materialized as explicit `contains` edges (parent → child). See the
    Structure-vs-Semantics rule below.
  - a **`warnings`** list — difficulties the extractor honestly surfaced (empty when clean).

**Structure is not Semantics (owner separation).** The extractor emits **structural** relationships
because the *source's own structure* states them (e.g. NIST's identifier scheme makes `GV` *contain*
`GV.OC`) — reading them invents nothing, so they belong to the Artifact. **Semantic** relationships
(Tier-2, cross-framework `maps_to`/`implements`/… — canonical model §4) are the **Graph Builder's**
later output and are **not** in the Artifact. The Graph Builder never has to *infer* structure from
code names; it receives it. This cleanly splits `Extractor → structure` from `Graph Builder →
semantics`.

**Storage is not Egress (owner separation).** The Artifact stores the **complete truth** — full
`description`/text — **even for `Licensed` sources**. It is what the whole system reasons over; a
truncated artifact would degrade the Knowledge Graph itself. `KnowledgeEntity.egress_restricted`
(derived: `license != "Public-Domain"`, §3.2 / §10.6) is a **marker, not a redaction** — it never
blanks stored content. What a *user* is shown is decided by a separate, downstream **Egress Policy**:

```
Licensed Source → complete Artifact → complete Graph → Egress Policy → what the user sees
```

The Egress Policy is a **future downstream layer** (not built at extraction time; recorded as a
future component). The extractor's only duty is to **store fully and mark honestly**. This is the
operational meaning of the License axis designed from the start. *(Consequence: reviews of Licensed
sources show structure/ids/counts, never the Licensed body text — the reviewer is itself an egress
point.)*
- **The format is a replaceable Realization behind an `ArtifactWriter`.** The **first Realization is
  JSON files** under `v3/knowledge/entities/<SOURCE_ID>@<version>` — chosen for reviewability during
  the anchor batch. It may be swapped for PostgreSQL / Parquet / SQLite **without changing this ADR,
  ADR 0056, or any Family Realization.**
- **JSON is the first Realization, not the decision.** This ADR is satisfied by *any* writer that
  round-trips the canonical artifact faithfully and append-only (§10.11).

## Consequences

**Positive**
- The storage choice is deferred to the persistence stage (§11) where it belongs; extraction is not
  hostage to it.
- Swapping JSON → Postgres/Parquet later is a writer change, invisible to the Port and extractors.
- The 14-field logical shape becomes the single contract that Supabase (Phase 5) and embeddings
  (Phase 6) also conform to — one shape, many realizations.
- **Attributable diffs:** the artifact's own identity (source/extractor/protocol/contract versions +
  content hash) makes any future re-extraction difference traceable to its cause — *document changed*
  vs *extractor evolved* — which is what enables rebuild, regression, and cross-version diff.
- **Self-sufficient artifact:** the `summary` gives an agent O(1) insight without reading the whole
  file, and `structural_relationships` mean no later stage re-derives structure from code names —
  Structure (Extractor) and Semantics (Graph Builder) are cleanly separated.

**Negative / costs**
- A thin indirection (`ArtifactWriter`) instead of writing JSON directly — a deliberate,
  low-cost seam.
- The canonical shape must be right early, since every realization round-trips it.

## Alternatives considered

- **"Entity Store" = JSON as the temporary database** (the rejected sketch). Rejected — couples a
  stage to a storage; conflates artifact with repository.
- **Write straight to PostgreSQL/Supabase now.** Rejected — premature persistence before the graph
  is extracted, normalized, and validated (contract stage order §0.1); also un-reviewable during the
  anchor batch.
- **Leave the format implicit per extractor.** Rejected — divergent outputs break the uniform Port
  contract (ADR 0056).
