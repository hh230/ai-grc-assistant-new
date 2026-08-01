# Stage 2 — Extraction Readiness & Kickoff Report

> **Subordinate log to [`CANONICAL-MODEL.md`](../knowledge/CANONICAL-MODEL.md) v1.3.** This report
> prepares the **Extraction** stage (owner's "Phase 1"). It records the corpus location, the
> tooling, the feasibility findings, the proposed method, the proposed entity artifact, and two
> logged discoveries. **Nothing has been extracted. No entity, no DB, no Supabase, no embeddings,
> no contract edit.** Awaiting the owner's explicit approval to begin (per §5.0 readiness gate and
> the contract rule "Stage 2 begins only on the owner's explicit approval").
>
> **⟳ Update (2026-07-25) — owner feedback reconciled.** §5 (Entity Artifact) and §6 (anchor batch)
> below are **superseded**: the "Entity Store" framing was rejected and replaced by
> [ADR 0056 — Knowledge Extraction Port](../../../docs/adr/0056-v3-knowledge-extraction-port.md) and
> [ADR 0057 — Extraction Output Artifact (format replaceable)](../../../docs/adr/0057-v3-extraction-output-artifact.md);
> the anchor batch is now **derived by entity-type coverage** in
> [ENTITY-COVERAGE-MATRIX.md](../knowledge/ENTITY-COVERAGE-MATRIX.md). See §9 (reconciliation) at the end.

---

## 0. Status

- **Grounding complete:** contract v1.3 (§0–§12), `CONTRACT-BACKLOG.md` (BL-1, BL-2), and
  `stage-2-verification.md` fully read.
- **Readiness gate (contract §5.0):** `Unknown = 0`, `Blocked = 0` — satisfied. Extraction may
  operate on resolved sources; Missing/Rejected are documented managed absences, not halts.
- **This report is documentation only.** Method + artifact shape below are **proposals pending
  approval**, not implemented.

---

## 1. Corpus location & tooling *(previously undocumented in the repo — now recorded)*

- **Source corpus (outside the repo):**
  `/Users/mohamedalsayyar/Documents/قاعدة بيانات مشروع Ai GRC/`
- **File count:** 117 files across 16 folders (CMA, COBIT, COSO, Compliance, Contract Templates,
  Corporate Policies, GRC, Governance, ISO, Internal Audit, Laws, NIST, OCEG, Risk Management,
  SDAIA, Saudi Regulations) — **matches the contract's 117-source register exactly.**
- **Extraction tooling present:** `PyMuPDF/fitz 1.26.5` (the version the contract mandates),
  `pypdf 6.14.2`, `arabic_reshaper`, `python-bidi`, `Pillow`.
- **Missing handlers (install when those sources are reached):** `openpyxl` (2 xlsx),
  `python-docx` (1 docx), `pytesseract` (OCR — **not needed**, see §3).

---

## 2. Scope of the Extraction stage

Per contract §5.0 post-decision snapshot:

- **In scope — 113 `Ready` sources.** Extracted into Knowledge Entities.
- **Excluded as documented states (not halts):**
  - 🕳️ **Missing Canonical Source (2):** `ISO-42001`, `ISO-22301` — present files are image-only
    scans; Source IDs retained; canonical copies pending Knowledge Acquisition. **No entities minted.**
  - 🚫 **Rejected (2):** `SAMA-RISK` (derived print bundle), `EX-POL-TRAVEL` (low-value scan).
    **No entities minted.**
- **Non-authoritative pool (§6.3 — Examples/Templates):** extracted **last** and flagged
  `Authority = Example/Template`; excluded from Control-Library/Gap per §10.5. Retained as
  drafting reference only.

Each excluded/absent source is recorded as a **state** in the per-source manifest, never silently
dropped (owner rule 6).

---

## 3. Feasibility findings *(evidence-based, read-only structural probes)*

1. **English structured standards — recoverable with per-source patterns.** `fitz` text yields
   clean native numbering. `ISO-27001@2022`: clauses 4–10 and Annex A controls appear as `n.n`
   line-starts (`4.1 … 5.1 …`), 104 distinct. *(The "`A.`" prefix is a citation convention; the
   document body numbers controls `5.x–8.x` under the four themes.)* A **generic** regex fails —
   **per-source structural mapping is required**, confirming a deterministic-but-source-aware method.
2. **Arabic-numeral identifiers — recoverable.** `NCA-ECC@2-2024`: 142 dash-numbered control IDs
   found in **Arabic-Indic digits** (`١-١-١ …`). Requires digit normalization, then usable.
3. **Arabic prose corruption + fix (DISCOVERY).** `fitz` extracts Arabic as **Unicode Presentation
   Forms** (e.g. `KSA-PDPL-LAW`: 15,295 presentation-form vs 4,888 base chars), so even `المادة`
   is unmatchable in raw text. **`unicodedata.normalize("NFKC", text)` fully recovers logical
   words** (`البيانات`, `حماية`, `المادة`, `الشخصية` all recovered). **No OCR, no bidi reversal**
   (line-reversal/bidi actually *break* it). → logged as **PROTO-EXT-1** (§7).
4. **Non-PDF renditions.** 2 xlsx (`NCA-CSCC/…/Tool`, `NCA-OTCC/…/Tool`) + 1 docx need
   `openpyxl`/`python-docx`. Low priority (Assessment-Tool/Template renditions). The
   `NCA-OTCC/…/Annex` xlsx carries cross-framework mappings → relevant to the later relationship
   stage, not this one.
5. **No true blockers remain.** `Unknown = 0`, `Blocked = 0`; Arabic solved by NFKC; scans/rejects
   excluded as states.

---

## 4. Proposed extraction method *(pending approval)*

**Deterministic, source-by-source, native-schema-mapped.**

- For each in-scope Source, open with `fitz`; for Arabic sources apply **NFKC** first.
- Map the source's **native structure** (contract §5.4) onto the contract **Entity Types** (§3.5):
  e.g. ISO clauses→`Requirement`, ISO Annex A→`Control`; NIST CSF→`Function`/`Category`/`Subcategory`;
  NCA-ECC→`Domain`/`Subdomain`/`Control`/`Subcontrol`; COSO-IC→`Component`/`Principle`; KSA laws→
  `Article`/`Provision`; etc.
- **No LLM invention of entities.** Entities come from the source's own structure and text; the
  model organizes, it does not fabricate. `Confidence` and `Unknown` are used honestly (owner rules
  1, 3, 4). A structural ambiguity is recorded as `Unknown`, never guessed.
- **Append-only (Principle 11).** Entities are written once, never mutated; corrections append a
  superseding entity.
- **Facets inherited from the Source register** (§5.1–5.3): `Authority`, `License`, `Stability`
  are copied from the source's already-ratified classification — not re-derived (§3 four-axes rule).

---

## 5. Proposed Entity Artifact — the pre-Supabase store *(ARCHITECTURAL — needs approval; logged as ADR-EXT-1)*

The contract is documentation-only and does **not** define where extracted entities live before
Supabase (Phase 5). Proposed working artifact:

- **Location:** `v3/knowledge/entities/<SOURCE_ID>@<version>.json` — one append-only file per Source
  edition, plus a sibling `_manifest.json`.
- **Record schema = the 14 contract fields (owner's list):**

  | Field | Example | Notes |
  |---|---|---|
  | `source_id` | `ISO-27001` | permanent anchor (§2) |
  | `version` | `2022` | edition |
  | `entity_id` | `ISO-27001@2022::A.5.7` | version-pinned (§2.2) |
  | `parent` | `ISO-27001@2022::A.5` or source root | graph parent |
  | `type` | `Control` | from §3.5 |
  | `name` | *(title)* | short title |
  | `number` | `5.7` / `GV.OC-01` / `المادة 5` | native numbering |
  | `description` | *(entity text)* | **License-gated:** for `Licensed` sources marked egress-restricted (§10.6) |
  | `language` | `EN` / `AR` | |
  | `authority` | `Normative` | inherited from Source |
  | `license` | `Licensed` | inherited from Source |
  | `stability` | `Stable` | inherited from Source |
  | `confidence` | `100% / 95% / 80% / Unknown` | §3.7; never above evidence |
  | `provenance` | `{source, version, location, extractor:"fitz", normalization:"NFKC"?}` | contract-minimum (§10.7); richer lineage = **BL-1, deferred** |

- **Per-source `_manifest.json`:** counts by `type`, total entities, `Unknown` count, language,
  method, normalization applied, warnings, and the source's resolved **state**.
- **Not a contract amendment.** Physical form of the store is an implementation decision the
  contract already defers to "later, separately-approved stages" (§11); recorded here as ADR-EXT-1.

---

## 6. Proposed sequencing & the Phase-1 gate *(pending approval)*

**Anchor batch first, then the long tail** — to prove fidelity and lock the artifact contract
before mass extraction.

- **Anchor batch (12 flagship sources)** — chosen to exercise nearly every Entity Type + both
  languages + the NFKC path:
  `ISO-27001@2022`, `ISO-27002@2022`, `NIST-CSF@2.0`, `NIST-SP-800-53@R5`, `COSO-IC@2013`,
  `COBIT@2019`, `IIA-GIAS@2024`, `ISO-31000@2018`, `BCBS-OPRISK@2011`, `NCA-ECC@2-2024`,
  `SAMA-CSF@2017`, `KSA-PDPL-LAW` (Arabic, proves NFKC end-to-end).
- **Interim review → owner approves the pattern + artifact contract.**
- **Long tail:** remaining `Ready` sources (Arabic laws, SDAIA, CMA, remaining NCA, OCEG, ISO
  family, NIST family, references), then the non-authoritative pool last.
- **Full Phase-1 review** (all counts) → owner approval → next phase (relationships).

---

## 7. Logged discoveries *(recorded, not implemented — owner rules)*

- **ADR-EXT-1 (architectural):** the Entity Store artifact (§5) — physical form of extracted
  entities before Supabase. To be ratified when the persistence stage is approved; not applied to
  the frozen contract.
- **PROTO-EXT-1 (methodological):** Arabic PDF sources extract as Unicode Presentation Forms under
  `fitz`; **NFKC normalization** recovers logical text (no OCR, no bidi). Verified on
  `KSA-PDPL-LAW`. Belongs to the Stage-2 Preprocessing family alongside the OCR handling already in
  §5.0.

---

## 8. Not done / awaiting approval

No entities, no normalization committed, no artifact files, no DB, no Supabase, no embeddings, no
contract edit. **Awaiting owner approval** of: (a) the extraction method (§4), (b) the Entity
Artifact contract (§5 / ADR-EXT-1), and (c) the anchor-batch-first sequencing (§6). On approval,
extraction begins with the 12-source anchor batch and returns for the interim review.

---

## 9. Reconciliation with owner feedback (2026-07-25)

The owner approved the direction with four corrections. This section records how §4–§7 change; the
new boundary decisions live in the ADRs, not here.

1. **Method (§4) — approved + reinforced.** Added rule **PROTO-EXT-2**: extraction is **deterministic
   and 100% reproducible**; **the LLM never discovers knowledge at extraction** (it may assist
   *interpretation* or *relationship-building* in later, separately-approved stages only). Now a Port
   guarantee in ADR 0056.
2. **Entity Artifact (§5) — SUPERSEDED.** The "Entity Store = JSON" framing was **rejected**
   (*Knowledge ≠ Storage*; don't bind a stage to a storage). Replaced by **ADR 0057**: extraction
   produces a **canonical Artifact** whose logical shape (the 14 fields + manifest) is fixed and whose
   **format is a replaceable Realization** (JSON = first realization only, swappable for
   Postgres/Parquet/SQLite without touching the Port or any extractor). The 14-field shape in §5
   stands as the canonical *shape*; only its "store" framing is retired.
3. **Anchor batch (§6) — SUPERSEDED.** No hand-picked framework list. The batch is now **derived by
   Entity-Type coverage** — see [ENTITY-COVERAGE-MATRIX.md](../knowledge/ENTITY-COVERAGE-MATRIX.md):
   **8 sources** cover all 16 Entity Types (NIST-CSF, ISO-27001, NCA-ECC, COBIT, BCBS-OPRISK, OCEG,
   KSA-PDPL-LAW, NCA-OTCC-Annex). Selection criterion = **Entity Coverage, not Framework Coverage**.
4. **New boundary decision — ADR 0056 (Knowledge Extraction Port).** Extraction is not a "Parser" but
   a **Knowledge Extractor**: one **Port** (the boundary) with per-**Source-Family** Realizations (ISO,
   NIST, Regulator, Law, Principle, COBIT, OCEG, Policy, Contract, Tool), registered as data. *Boundary
   first, realizations second* — the mission-launch-boundary pattern; the Wave-1 error (starting from
   implementations) is structurally prevented.

**Logged discoveries (updated §7):** ADR 0056 (Port) · ADR 0057 (Artifact) · PROTO-EXT-1 (Arabic
NFKC) · PROTO-EXT-2 (deterministic/reproducible, no-LLM-at-extraction).

### 9.1 Decisions closed (owner, 2026-07-25)

- **ADR 0056 — Accepted**, with the constraint that the Port is **format- and tooling-agnostic**
  (no PDF/DOCX/XLSX/`fitz`/`openpyxl` in the boundary); realizations are `*KnowledgeExtractor`s, not
  `*Parser`s.
- **ADR 0057 — Accepted**, with **Artifact Identity** added (`artifact_id · source_version ·
  extractor_version · protocol_version · contract_version · content_hash · generated_at`) so a future
  diff is attributable; and the **Canonical-not-Temporary** principle (official stage output, reused
  for rebuild/regression/diff/debug/embedding-regen).
- **Mapping-Entry — Option A**: `NCA-OTCC-Annex` is in the anchor (all 16 types + the xlsx path from
  the start; no Port exception in v1). Anchor = **8 sources**.
- **Binding build order:** build the **`KnowledgeExtractionPort` (boundary) first**; only after the
  boundary is complete, build the first `*KnowledgeExtractor` realization (ISO/NIST) — never the
  reverse. *"Last architectural decision before the first Knowledge Entity is now closed."*

The V3 boundary chain the architecture now guarantees:
`Source → KnowledgeExtractionPort → Canonical Extraction Artifact → Knowledge Graph Builder →
Knowledge Graph → Embeddings → AI` — boundaries, not implementations.

### 9.2 Port built + second-round refinements (owner, 2026-07-25)

The `KnowledgeExtractionPort` boundary is **built and green**:
`v3/packages/knowledge-extraction/` — pure stdlib, zero deps; **12 pytest green · mypy --strict
clean**. Three owner refinements were folded in:

- **`native_type` → `native_node_type`.** It is the source's own **node name** (part of its semantic
  identity), not a label: canonical `Requirement` ↔ native `Clause`; `Control` ↔ `Enhancement`.
- **Single responsibility / terminal verification (PROTO-EXT-3).** An extractor is `Verified Source
  in → Artifact out`; it never re-detects OCR/encryption/missing/rejected. The Port asserts
  `state == "Ready"`, and the extractor contract is `accepts(source) → extract(source) → Artifact`
  (dispatch stays data via the registry, which cross-checks `accepts`).
- **Realization proof order** (matrix §6): NIST-CSF → ISO-27001 → KSA-PDPL-LAW → NCA-ECC — chosen to
  prove the Port is **source-independent** (a non-Clause source first), not for ease.

**Discoveries now: PROTO-EXT-1 (NFKC) · PROTO-EXT-2 (deterministic/no-LLM) · PROTO-EXT-3 (extractor
single responsibility) · ADR 0056 · ADR 0057.** Next: build `NistCsfKnowledgeExtractor` (first real
Knowledge Entities → interim review).

### 9.3 Extractors #1 (NIST) and #2 (ISO) built; new separations (owner, 2026-07-25)

- **NIST-CSF Reference Realization — approved final.** `v3/packages/nist-csf-extractor/`:
  6 Functions · 22 Categories · 106 Subcategories = 134 entities, 128 `contains` edges, 0 unknown.
- **ISO-27001 built — first Licensed, multi-structure source.** `v3/packages/iso-27001-extractor/`.
  Proves three properties: **(1) Native ≠ Canonical** (native `Theme` → canonical `Category`);
  **(2) Storage ≠ Egress** (Licensed: full text stored, `egress_restricted=true`); **(3) the
  Extractor describes reality, it does not complete it.** Annex A extracted fully — **4 Categories +
  93 Controls = 97 entities**, 93 `contains` edges; `content_hash a8f986c1…`. Management Clauses (4–10)
  recorded as a formal `ExtractionNote` (**Partial**), *not* extracted — this rendition's clause
  layout is not deterministically recoverable.
- **Storage ≠ Egress** — enshrined in ADR 0057 + the Port's `egress_restricted` docstring: the Artifact
  stores complete truth even for Licensed sources; a downstream **Egress Policy** (future layer) governs
  what a user sees.
- **Source ≠ Rendition (OBSERVATION, not a new ADR unless it recurs).** ISO gave the first practical
  proof that *rendition quality* affects extraction while *source identity* does not change. A
  `Partial` extraction due to rendition quality is **not** a Missing/Rejected Source and **not**
  Knowledge Acquisition — it belongs to the Source/Rendition layer (`Source → Version → Language →
  Variant → Physical File`). Recorded via the extractor's `ExtractionNote`.
- **Three layers separated (owner):** **Architecture** (canonical types, `Clause → Requirement`) ·
  **Extraction Policy** (tunable, e.g. `Depth = 2`) · **Extractor** (the realization). Extraction depth
  is a *policy* value, not a model property. `ExtractionPolicy` is **deferred** (not built) until the
  clauses are extracted from a clean rendition — no unused abstraction.
- **New contract element — `ExtractionNote`** (formal structured warning: `subject · status · reason ·
  recommended_action`) so an extractor can *describe* a limitation honestly.
- **Shared `artifact-writers` package** created; `JsonArtifactWriter` moved out of NIST (second
  extractor = the anticipated trigger).
- **Green:** port 14 · artifact-writers 2 · nist 8 · iso 8 pytest; `mypy --strict` clean on all four.
  After ISO's three properties, remaining extractors are expected to be *applications of the pattern*,
  not architectural discoveries.

### 9.4 Extractor #3 (KSA PDPL) — first Arabic source (owner, 2026-07-25)

`v3/packages/ksa-pdpl-law-extractor/`. Proves: **(1) language does not change the Port** (an Arabic
source → contract-conforming artifact, no exception in the Port); **(2) canonical type follows legal
FUNCTION, not node name** — every sub-item is natively a `Provision` but maps to `Definition` *or*
`Requirement` by a **structural definitions detector** (`term: meaning`), *never* by article number;
**(3) NFKC is a normalization STEP** (`summary.normalization=["NFKC"]`), not logic. Real run:
**43 articles · 19 definitions · 137 Requirement + 19 Definition = 156 entities**, 113 `contains`;
`content_hash 8cbe170b…`; Public-Domain (`egress_restricted=false`).

- **Honesty correction — describe reality, don't invent a *problem*.** The Design-on-Reality probe
  read a raw text slice as bidi-reversed; verifying the *actual* extraction found **0 reversed spans
  across all 156 entities** (289 correct-order word hits, 0 reversed). So the pre-attached
  content-fidelity note was **false and was removed** — the extractor invents no problem, just as it
  invents no knowledge. Content here is clean on **both** structure and content.
- **Structural Completeness ≠ Content Fidelity** — recorded as a methodological **observation**
  (alongside `Source ≠ Rendition`), *not* an ADR. PDPL did not exhibit it (clean on both); it remains
  the correct model for any future rendition that is structurally recoverable but content-degraded.
- **Green:** port 14 · artifact-writers 2 · nist 8 · iso 8 · **pdpl 7** = 39 pytest; `mypy --strict`
  clean on all five. Proof-order remaining: **NCA-ECC** (regulator control tree; Arabic-digit ids).

### 9.5 Extractor #4 (NCA-ECC) — DEFERRED: Identifier-degraded rendition (owner, 2026-07-25)

Design-on-Reality found a genuine **4-layer** tree (`Domain 1..4 → Subdomain → Control → Subcontrol`;
109 controls, 96 subcontrols; first Regulatory Controls; Arabic/Public-Domain) — **but** the current
rendition (`ECC-2-2024---NCA.pdf`) **reverses multi-digit identifier components** under RTL extraction:
subdomain `1-10` (Awareness) is always read `1-01`, `1-10`/`2-10` never appear, and `12 ↔ 21` is
**silently ambiguous**. ~70 of 233 identifiers carry a ≥2-digit component.

**Owner decision: B (not A).** This is **Identity Fidelity**, not Content Fidelity — the corruption is
in the *identifier itself*, the system's first pillar (§2). **No V3 principle permits a Reference
Artifact with identifiers known to be wrong, even marked `Partial`.** Option A (extract only the clean
single-digit subtree) was rejected: excluding ~30% would make the first Regulatory-Controls reference
*incomplete and unfit as a baseline* — a permanent "but" inside the Reference Realizations. So:

- **`NcaEccKnowledgeExtractor` is NOT built on this rendition.** No extractor, no artifact.
- **The Source `NCA-ECC` remains Canonical** (Verified). Only this **rendition** is degraded — a
  `Source ≠ Rendition` matter, not Missing/Rejected, not the Extractor's fault, and numbers are **not**
  algorithmically "fixed."
- **Recorded `ExtractionNote` (rendition status):**
  `status: Identifier-degraded` ·
  `reason: Current rendition does not preserve identifier fidelity for multi-digit identifier components.` ·
  `recommended_action: Acquire a higher-quality rendition of the same source.`
- **Reference Realizations phase status: OPEN — closure condition not yet met** (an *engineering*
  reason, not operational — **not** "waiting for an ECC file", but "not every reference property has
  been demonstrated yet"). **Phase DoD:** *the Reference Realizations phase closes only when every
  reference property has been demonstrated at least once by a canonical realization.* Closure is tied
  to the **property**, not the source — a future source that demonstrates the same property (better than
  ECC) can close it too; ECC is not the goal, *Identity Fidelity in Regulatory Controls* is. *(Refined 2026-07-25 — see the
  status update below: the Reference Guarantees prove design quality but are **not a Production Gate**;
  expansion may proceed with any guarantee left unproven **due to rendition** carried as Technical
  Debt, never hidden. `no new Extractor may break a **proven** guarantee` still holds.)*

**New protocol — PROTO-EXT-4: Identity Fidelity precedes Content Fidelity.** *If identifier integrity
conflicts with content extractability, sacrifice content, never identity.* (A protocol, not an ADR — it
changes how we verify work, not the architecture. Sits alongside the `Source ≠ Rendition` and
`Structural Completeness ≠ Content Fidelity` observations.)

**Architectural Stabilization Point (owner, 2026-07-25).** V3 has reached a point where further work
adds no new principles easily — it replicates the proven reference pattern. The phase's **key
discovery** is a qualitative shift: **Reference Extractors → Reference *Guarantees*.** An Extractor is
merely a *means* to prove a guarantee; once proven, the source holds no architectural privilege. What
must persist over time is the **guarantees**, not the source names.

**The eight Reference Guarantees** (the durable model; rows are *guarantees*, not extractors):

| # | Reference Guarantee | Proven By | Status |
|--:|---|---|---|
| 1 | Source Independence | NIST | ✅ |
| 2 | Native ≠ Canonical | ISO | ✅ |
| 3 | Storage ≠ Egress | ISO | ✅ |
| 4 | Language Independence | PDPL | ✅ |
| 5 | Functional Typing | PDPL | ✅ |
| 6 | Variable Depth | NCA | ⏸ |
| 7 | Regulatory Controls | NCA | ⏸ |
| 8 | Identity Fidelity | NCA | ⏸ |

**Naming at phase close (owner directive):** the document is the **Reference Guarantees Matrix**
(a.k.a. Reference Compliance Matrix) — rows = guarantees, never extractor names. Its DoD: *no new
Extractor may break any proven guarantee.*

**Resume protocol — when a clean ECC rendition is available (owner, 2026-07-25).** Do **not** start
writing the extractor directly. Follow the now-fixed pattern:

1. **Design-on-Reality** — inspect structure only, no entities.
2. **Decision gate — is *Identity Fidelity* deterministically achievable on this rendition?** (Identity
   first: if not, do **not** build — record the rendition status and keep waiting.)
3. If yes → build `NcaEccKnowledgeExtractor`; prove guarantees **#6 Variable Depth · #7 Regulatory
   Controls · #8 Identity Fidelity**.
4. Instantiate the **Reference Guarantees Matrix** (rows = guarantees, not extractor names).
5. **Formally declare the Reference Realizations phase closed.**
6. *Only then* begin **Production Scale** (the 113-source expansion) — disciplined execution against the
   frozen guarantee baseline, never conflated with architectural discovery.

### 9.6 Downstream pipeline started — Stage 4 Graph Builder built (2026-07-25)

Per [ADR 0058](../../../docs/adr/0058-v3-pipeline-execution-model.md), the first downstream stage is
built: **`graph-builder`** (Stage 4) + the **append-only Knowledge Graph** (System of Record), plus a
**`JsonArtifactReader`** so any stage reads the archive independently of the extractors. Proven **live
on the 3 real artifacts**: **387 nodes · 334 edges · 3 sources**
(`Function 6 · Category 26 · Subcategory 106 · Control 93 · Requirement 137 · Definition 19`);
re-appending the same three is a no-op (**idempotent**), a conflicting redefinition raises
(**append-only**), and it imports no extractor (**independent**).

**Stage 5 — Graph Projection boundary built ([ADR 0059](../../../docs/adr/0059-v3-graph-projection-port.md)).**
`graph-projection`: `ProjectionRequest` (Source/Delta/Snapshot) → `GraphProjector` (target-agnostic) →
**immutable** `ProjectionPackage` (operations, no SQL) → `ProjectionTarget` boundary + the
`MemoryProjectionTarget` **reference realization**. Proven live on the real graph:
`ProjectSource(ISO-27001@2022)` → 97 nodes / 93 edges / 190 ops (**request-scoped**, not the whole
387-node graph), applied to the serving view and **idempotent** on re-apply; `ProjectSnapshot` →
387/334; package `frozen=True`. Only the real `SupabaseProjection` remains before Embeddings.

**Full regression: 52 tests across 7 packages, `mypy --strict` clean.** Next: `SupabaseProjection`
(when a Supabase env exists) → Embeddings → AI; then the ~110 remaining extractors in parallel.

---

**Status update (owner, 2026-07-25) — the pipeline is NOT frozen.** Reference Guarantees prove *design*
quality; they are **not a Production Gate**. `NCA-ECC` is reframed from `STOP` to
`Pending · debt = IDENTITY_FIDELITY · Skip` (see **[technical-debt.md](technical-debt.md)**). The
pipeline continues on the extractable sources; a clean ECC rendition is **upserted incrementally**
later (no full rebuild). Foundation mature (5/8 guarantees proven at design level); the three ECC-tied
guarantees (#6–#8) are carried as **open, tracked debt**, not a freeze — quality is neither compromised
nor hidden, and the project is not frozen by one isolated rendition.

**Honest reality check (provenance discipline).** "113 Success" is the *target* pipeline shape, **not**
current state. Built and verified so far: **3 real extractors** (NIST, ISO, PDPL) → 3 artifacts on
disk. **~110 sources still need extractors** (Production Scale — pattern application). **5 debt items**
recorded (ECC + ISO-42001 + ISO-22301 + SAMA-RISK + EX-POL-TRAVEL). Downstream stages (Graph Builder →
Supabase → Embeddings → AI) are **designed-in the roadmap but not yet built.**

**What comes after — a different nature of work:** not building Architecture, but **Production Scale**.
The question turns from *"how should an Extractor work?"* to *"how do we produce 113 Extractors without
breaking any Guarantee?"* — disciplined execution against a frozen guarantee baseline, not new
architectural discovery. This is the end of establishing V3's language and rules, not merely the end of
a set of Extractors.
