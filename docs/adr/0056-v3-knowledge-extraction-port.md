# ADR 0056: The Knowledge Extraction boundary — one Port, per-family Realizations

- Status: **Accepted** (2026-07-25) — owner-accepted at Stage-2 kickoff **with the format- and
  tooling-agnostic constraint below**. Build order is binding: the **Port (this boundary) is built
  first**, then the first `*KnowledgeExtractor` realization — never the reverse. No Knowledge Entity
  is written until a realization runs behind this Port.
- Date: 2026-07-25
- Deciders: **Product Owner** (this is a boundary decision, reserved to the owner), Architecture
- Related: CLAUDE.md §9 (Tools as first-class capability boundaries) · §10 (Registry) · §15
  (DDD / anti-corruption layer) · §17 (plugins via registries) ·
  [CANONICAL-MODEL.md](../../v3/docs/knowledge/CANONICAL-MODEL.md) §3.5 (Entity Types), §5.4 (native
  schemas), §10 (governance) · ADR 0057 (Extraction Output Artifact) · the **mission launch
  boundary** precedent (Wave-1: define the Port before the realizations).

## Context

Stage 2 extracts Knowledge Entities from **113 heterogeneous sources** whose native structures
differ sharply (§5.4): ISO clause+annex, NIST CSF function/category/subcategory, NIST SP
family/control/enhancement, Saudi regulator domain/subdomain/control/subcontrol, KSA-law
article/provision, principle-based governance frameworks, COBIT domain/objective/practice, OCEG
capability model, and semi-structured policies/contracts.

The tempting path is one parser per framework — `ISOParser`, `NISTParser`, `LawParser`,
`PolicyParser` … — each an independent implementation. That is precisely the mistake Wave 1
corrected: **starting from implementations instead of from a boundary.** Without a unifying
contract, the extractors drift, cannot be tested uniformly, cannot be swapped, and each re-invents
guarantees (reproducibility, provenance, no-invention) inconsistently.

The owner's framing: this is **not a "Parser." It is a Knowledge Extractor.** Every source family
gets a different **Realization**, but all realizations satisfy **one boundary** — exactly the
pattern used for the mission launch boundary. *The boundary first; the realizations second.*

## Decision

**We will define a single `KnowledgeExtractionPort` as the boundary for all extraction. Every
source-family extractor is a Realization behind this Port. No extraction happens outside it.**

**The Port is format- and tooling-agnostic (owner constraint).** Its entire vocabulary is
`Source → Canonical Extraction Artifact`. It knows **nothing** about `PDF`, `DOCX`, `XLSX`, `fitz`,
or `openpyxl` — *how* a source is opened and read is the Realization's private concern. There is no
`PDFExtractionPort` and no `ISOParser`; there is **one** `KnowledgeExtractionPort` and **many**
`*KnowledgeExtractor` realizations. The boundary package carries **no I/O dependency** — it *cannot*
import `fitz`, because it does not depend on it.

**The boundary (logical, not code):**

- **Input — `ResolvedSource`:** `source_id`, `version`, `rendition` (language + variant),
  `physical_file` (path + `sha256`), and the source's **already-ratified facets** (Authority,
  License, Stability, Genre, GRC-Domains) from the Canonical Source Register. Precondition: the
  source's Status is `Ready` (§5.0).
- **Output — `CanonicalExtractionArtifact`:** the extracted Knowledge Entities plus an
  `ExtractionManifest`. Its logical shape and its replaceable serialization are governed by
  **ADR 0057**.

**Port guarantees (invariants every Realization must honor):**

1. **Deterministic & 100% reproducible.** Same physical file + same extractor version ⇒
   byte-identical artifact, provable by a content hash in the manifest. *(This is PROTO-EXT-2.)*
2. **No knowledge invention.** Entities come only from the source's own structure and text. **The
   LLM does not discover knowledge at extraction.** (An LLM may assist *interpretation* or
   *relationship-building* in later, separately-approved stages — never here.)
3. **Append-only** (Principle 11): entities are emitted once; corrections append a superseding
   entity, never mutate.
4. **Provenance-bearing:** every entity records `Source · Version · Location` (contract-minimum
   §10.7; richer lineage is BL-1, deferred).
5. **Facets inherited, never re-derived** (§3 four-axes rule): Authority/License/Stability are
   copied from the register.
6. **Honest Confidence / Unknown** (§3.7): structural ambiguity is recorded as `Unknown`, never
   guessed.
7. **Explicit native→canonical mapping.** Each Realization maps its family's native units onto the
   canonical Entity Types (§3.5), **retaining the source's own node name** in
   `native_node_type` (part of the source's semantic identity, not a mere label: canonical
   `Requirement` ↔ native `Clause`; canonical `Control` ↔ native `Enhancement`). A native unit with
   **no** canonical home is a *contract-conflict candidate* raised to the owner (§12) — **never a
   silently invented type.**
8. **Single responsibility — Verified Source in, Artifact out (PROTO-EXT-3).** The Port's input is
   **always a Verified source** (`state == Ready`, resolved by Stage-2 verification). An extractor's
   only job is `Verified Source → Canonical Artifact`; it **never** re-detects OCR, encryption,
   missing, or rejected — that responsibility ended upstream and does not return. The extractor
   contract is `accepts(source) → extract(source) → Canonical Extraction Artifact`: `accepts` is a
   capability guard (dispatch stays *data* via the registry, which cross-checks it); `extract`
   assumes the precondition and builds through `assemble_artifact`, which enforces it and fails loud.

**Realizations are `*KnowledgeExtractor`s, one per Source Family (structural archetype), not per
framework.** Names are `*KnowledgeExtractor` — never `*Parser` (a Parser reads a format; a
KnowledgeExtractor produces knowledge). Proposed set (subject to consolidation as the anchor batch
proves them):

| `*KnowledgeExtractor` | Sources (examples) | Native → canonical (§3.5) |
|---|---|---|
| `IsoKnowledgeExtractor` | ISO 27001/27002/27005/27017/37001/37301/9001 | Clause→Clause/Requirement · Annex→Annex/Control · Terms→Definition |
| `NistCsfKnowledgeExtractor` | NIST-CSF 2.0 | Function · Category · Subcategory |
| `NistSpKnowledgeExtractor` | 800-53/171/37/61 | Family→Category · Control · Enhancement→Subcontrol |
| `RegulatorControlKnowledgeExtractor` | NCA ECC/CCC/CSCC/DCC/OTCC · SAMA-CSF | Domain · Subdomain→Category · Control · Subcontrol · Principle |
| `PrincipleFrameworkKnowledgeExtractor` | COSO-IC/ERM · King IV · BCBS · OECD · IIA-GIAS | Component→Domain · Principle · Standard/Practice |
| `CobitKnowledgeExtractor` | COBIT 2019 | Domain · Objective · Practice |
| `OcegKnowledgeExtractor` | OCEG-RB/BB · Capability Model | Component→Domain · Element→Category · Practice · **Capability** |
| `KsaLawKnowledgeExtractor` | all `KSA-*-LAW` | Article · Provision→Subcontrol · Definition (Arabic → NFKC) |
| `PolicyProseKnowledgeExtractor` | corporate policies, compliance handbooks | semi-structured → Guidance/Definition (Authority = Example) |
| `ContractTemplateKnowledgeExtractor` | NDAs, MSAs, templates | clause-based → Clause/Provision (Authority = Template) |
| `ToolRenditionKnowledgeExtractor` | NCA `*/Tool` xlsx, `*/Annex` xlsx | Mapping-Entry · Assessment items |

**Selection is data, not code.** An **Extractor Registry** maps each of the 113 sources to exactly
one `*KnowledgeExtractor` (mirroring the Tool Registry, §10). Adding a new source family = registering
a realization, never editing core control flow (§17).

**Position in the V3 boundary chain (owner-articulated).** The Port is one link in a chain that is
**boundaries all the way down — not implementations**:

```
Knowledge Source → KnowledgeExtractionPort → Canonical Extraction Artifact
  → Knowledge Graph Builder → Knowledge Graph → Embeddings → AI
```

Each arrow is a contract, each box a swappable realization. This is what keeps V3 from collapsing
back into a monolith.

## Consequences

**Positive**
- The boundary exists before any implementation — the Wave-1 error is structurally impossible here.
- Every extractor is tested against one contract; reproducibility and no-invention are guaranteed
  uniformly, not per-parser.
- Format-agnostic output (pairs with ADR 0057): storage can change without touching a single
  extractor.
- New frameworks/families plug in via the registry; the core never changes (frameworks-as-data,
  extractors-as-plugins).

**Negative / costs**
- Upfront boundary-design cost before the first entity (accepted deliberately).
- The family taxonomy is provisional; the anchor batch may merge or split families.
- Native→canonical mapping demands care and may surface genuine §3.5 gaps (e.g. IIA "Standard",
  NIST "Family/Enhancement", NCA "Subdomain") — these are raised as contract-conflict candidates,
  not resolved silently.

## Alternatives considered

- **Per-framework parsers with no shared boundary** (`ISOParser`, `LawParser` …). Rejected — the
  exact Wave-1 mistake: implementations without a Port drift and cannot be swapped or tested
  uniformly.
- **One monolithic "god" parser.** Rejected — cannot handle the structural heterogeneity
  deterministically; becomes a tangle of special cases.
- **LLM-driven extraction.** Rejected — not reproducible and it *invents* knowledge, violating the
  Port's core guarantees and the owner's rules.
