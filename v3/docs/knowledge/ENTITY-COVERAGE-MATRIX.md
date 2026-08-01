# Entity Coverage Matrix — deriving the anchor batch by Entity-Type coverage

> **Subordinate to [`CANONICAL-MODEL.md`](./CANONICAL-MODEL.md) v1.3 (§3.5 Entity Types, §5.4 native
> schemas) and [ADR 0056](../../../docs/adr/0056-v3-knowledge-extraction-port.md).** Owner rule
> (Stage-2 kickoff): the anchor batch must prove **"can the system extract every Entity *Type*?"** —
> selection is **Entity Coverage**, never **Framework Coverage**. This document computes that
> coverage and derives the minimal batch. No extraction performed.

---

## 1. The property under test

Not "did we cover ISO / NIST / COSO?" but **"does every canonical Entity Type (§3.5) have a
working Realization behind the Extraction Port (ADR 0056)?"** The anchor batch is the **minimal set
of in-scope sources whose union covers all 16 Entity Types** — plus, as a secondary benefit, the
widest spread of Source Families.

## 2. Coverage table — Entity Type → in-scope sources that yield it

*(Derived from §5.4 native schemas. "◆ rare" = essentially one source yields it → it forces that
source into the batch.)*

| # | Entity Type (§3.5) | Sources that yield it | Note |
|--:|---|---|---|
| 1 | **Domain** | NCA-ECC, SAMA-CSF, COBIT, IIA-GIAS | common |
| 2 | **Function** | **NIST-CSF** | ◆ rare (CSF only) |
| 3 | **Category** | NIST-CSF (·NIST-SP Family, NCA Subdomain →map) | common |
| 4 | **Subcategory** | **NIST-CSF** | ◆ rare (CSF only) |
| 5 | **Clause** | ISO-27001, ISO family | ISO |
| 6 | **Article** | **KSA-\*-LAW** | ◆ rare (laws only) · Arabic/NFKC |
| 7 | **Objective** | **COBIT** | ◆ rare (COBIT only) |
| 8 | **Principle** | BCBS-OPRISK, COSO-IC/ERM, ISO-31000, IIA-GIAS, King IV, SAMA | common |
| 9 | **Practice** | COBIT, OCEG, King IV | common |
| 10 | **Capability** | **OCEG** (Capability Model / RB) | ◆ rare (OCEG only) |
| 11 | **Requirement** | ISO-27001 (clauses 4–10), ISO family | ISO |
| 12 | **Control** | ISO-27001 Annex A, ISO-27002, NIST-SP-800-53, NCA-\*, SAMA | very common |
| 13 | **Subcontrol** | **NCA-ECC** | ◆ rare (NCA only) · Arabic digits |
| 14 | **Definition** | ISO-27001 (clause 3), KSA laws (art. 1), NIST glossaries | common |
| 15 | **Annex** | ISO-27001 (Annex A), NCA-OTCC Annex | ISO |
| 16 | **Mapping-Entry** | **NCA-OTCC Annex (xlsx)**, NIST-CSF refs | ◆ rare · xlsx |

## 3. Minimal covering set (the derived anchor batch)

The ◆ rare types pin their sources; ISO-27001 alone covers five types. Minimal union:

| Source (derived, not chosen) | Entity Types it contributes | Why it's in the set |
|---|---|---|
| **NIST-CSF@2.0** | Function ◆, Subcategory ◆, Category | only source of Function + Subcategory |
| **ISO-27001@2022** | Clause, Requirement, Control, Definition, Annex | 5 types in one source |
| **NCA-ECC@2-2024** | Subcontrol ◆, Domain, Control | only source of Subcontrol; Arabic-digit path |
| **COBIT@2019** | Objective ◆, Domain, Practice | only source of Objective |
| **BCBS-OPRISK@2011** | Principle | smallest, cleanest Principle source (11, 27p, EN) |
| **OCEG** (Capability Model @3.5-AR / RB) | Capability ◆, Practice | only source of Capability |
| **KSA-PDPL-LAW** | Article ◆, Definition, Provision | only source of Article; proves **NFKC** end-to-end |
| **NCA-OTCC Annex (xlsx)** | Mapping-Entry ◆, Assessment | only clean Mapping-Entry; proves the xlsx/tool path |

**→ 8 sources cover all 16 Entity Types.** This matches the owner's intuition ("قد يكفي 8").

**Secondary benefit — Family coverage:** these 8 span 8 distinct Source Families (NIST-CSF
Taxonomy, ISO Clause+Annex, Regulator Control, COBIT, Principle Framework, OCEG, KSA Law,
Rendition/Tool). The 3 not exercised here — NIST-SP Catalog, Policy/Compliance Prose,
Contract/Template — are lower-risk and validated in the long tail.

## 4. Decisions this matrix surfaced

1. **Mapping-Entry (row 16) — DECIDED: Option A (owner, 2026-07-25).** `NCA-OTCC Annex` **is in** the
   anchor: prove **all 16 types + the xlsx path from the start**. Rationale (owner): deferring it
   would create an **exception inside the Port in its first version** — and the Port must be shown to
   produce *every* Entity Type from day one. `openpyxl` is installed when the
   `ToolRenditionKnowledgeExtractor` is built. Anchor stays **8 sources**.
2. **Native→canonical gaps (per ADR 0056 guarantee 7).** The anchor will surface native units with
   no exact §3.5 home — NIST `Family`/`Enhancement`, NCA `Subdomain`, IIA `Standard`, COSO
   `Component`, OCEG `Element`, law `Provision`, ISO `Point-of-Focus`/`Attribute`. Default handling:
   **map to nearest canonical type + retain the source's own node name** (`native_node_type`);
   escalate any true orphan as a contract-conflict candidate (§12) — never invent a §3.5 type.

## 5. Outcome

The anchor batch is **§3.5-derived**, not framework-picked. Extracting these 8 sources exercises
every Entity Type and 8 of ~11 Source Families through the single Extraction Port — proving the
boundary before the long tail, and locking the canonical artifact shape (ADR 0057) under review.

## 6. Realization proof order — prove source-*independence*, not ease (owner, 2026-07-25)

The first realizations are sequenced to prove the Port is **independent of source structure** — that
it was not secretly designed around ISO's "Clause". A source that does **not** rely on Clause comes
first:

1. **`NistCsfKnowledgeExtractor`** — Function → Category → Subcategory *(no Clause at all)*
2. **`IsoKnowledgeExtractor`** — Clause → Requirement → Annex Control
3. **`KsaLawKnowledgeExtractor`** — Article → Provision *(Arabic; NFKC)*
4. **`RegulatorControlKnowledgeExtractor`** — Domain → Subdomain → Control → Subcontrol (NCA-ECC)

If the same boundary produces valid artifacts across these four structurally different families, the
Port is confirmed source-independent. NIST is first for *that* reason — not because it is
Public-Domain.
