# V3 Canonical Knowledge Model — The Contract

> **Status:** Stage 1 **CLOSED** · Contract **v1.2** — **RATIFIED** · frozen through Stage 2 (§12)
> **Nature:** Official, binding reference model for the entire V3 knowledge layer.
> **This document is documentation only.** It defines *meaning and identity*, not storage.
>
> **Hard constraints honored by this document (and by anyone editing it):**
> no code · no database · no migration · no Supabase · no schema/DDL · no embeddings ·
> no extraction · no ingestion · **Stage 2 not started.**
>
> Every later stage (extraction, knowledge graph, retrieval, cross-framework mapping,
> control library, gap assessment) **must conform to this contract.** If a later stage needs
> something this contract does not allow, the contract is amended first (see §12) — the model
> never drifts silently.

---

## 0. How to read this document

This is the **canonical metadata model** for V3. It replaces the idea of "a folder of PDFs"
with a precise vocabulary for *identity*, *classification*, and *relationships*. It is the
product of Stage 1 and supersedes the two earlier review artifacts (the Inventory and the
Canonical Knowledge Manifest v1/v2) — their content is folded in here.

It is **not** a database schema. Field lists below are *logical* — they describe the shape of
meaning the system commits to, not tables or columns. Physical storage is a separate, later,
separately-approved decision.

### 0.1 Where this sits — the V3 stage roadmap

This contract is **Stage 1**. It governs every stage after it:

1. ✅ **Stage 1 — Contract** (this document; closed)
2. **Stage 2 — Extraction** (Source → Knowledge Entities)
3. **Stage 3 — Entity normalization**
4. **Stage 4 — Relationship graph** (Tier-2 entity relationships)
5. **Stage 5 — Validation**
6. **Stage 6 — Supabase persistence**
7. **Stage 7 — Embeddings**
8. **Stage 8 — AI engines**

*(This refines the original 10-step import mission into the canonical V3 sequence: knowledge is
extracted, normalized, and graphed **before** persistence, and embeddings come **after** the graph
is validated and stored.)*

---

## 1. Purpose — the V2 → V3 shift

```
V2:   DOCUMENT  =  the unit of knowledge         (PDF in → chunks out)

V3:   DOCUMENT  =  a SOURCE / CONTAINER only
      KNOWLEDGE =  the graph extracted FROM it
```

The single most important principle of V3:

> **The document is formally a container. Knowledge lives in the entities and edges.**

A source document is where knowledge *came from* (provenance). The knowledge itself is a graph
of **entities** (clauses, controls, requirements, principles…) connected by typed
**relationships** (implements, maps_to, supports…). Everything in this contract exists to make
that graph well-identified, well-classified, trustworthy, and traceable back to its source.

The knowledge layers:

```
SOURCE            (a work — e.g. ISO-27001)                    ← identity & provenance
  └─ EDITION      (a version — e.g. ISO-27001@2022)            ← what changed over time
       └─ RENDITION (language + variant — e.g. …/EN/Official)  ← the published form
            └─ PHYSICAL FILE (a copy on disk, by hash)         ← an alias/instance
                 └─ ENTITY   (Clause / Control / Requirement…) ← the real knowledge unit
                      └─ RELATIONSHIP (implements / maps_to…)  ← the graph
                           └─ EVIDENCE (customer-side, later)  ← proof a control operates
```

---

## 2. The Identity Spine — Source ≠ Version *(Refinement 1)*

Identity is layered so that **a new edition never changes the identity of the work.** Adding
ISO 27001:2027 tomorrow adds a *Version under an existing Source* — it does not mint a new,
disconnected document.

### 2.1 The five identity levels

| Level | What it identifies | Stable? | Example |
|---|---|---|---|
| **Source** | The abstract work/standard | **Permanent** | `ISO-27001` |
| **Version** | A specific edition of the Source | added over time | `2022`, later `2027` |
| **Language** | Language of a published form | — | `EN`, `AR` |
| **Variant** | The nature of that form | — | `Official`, `IPD` (draft), `Annex`, `Tool`, `Printable` |
| **Physical File** | One copy on disk | — | a `sha256` + path |

A **Source** owns many **Versions**; a Version owns many **Renditions** (Language × Variant);
a Rendition may have many **Physical Files** (duplicates, print variants — all kept as aliases).

### 2.2 Canonical notation

```
Source ID          ISO-27001
Edition            ISO-27001@2022
Rendition          ISO-27001@2022/EN/Official
Entity ID          ISO-27001@2022::A.5.7          (Annex A control 5.7, in the 2022 edition)
Physical file      alias of a Rendition, keyed by sha256
```

Rules:
- **The Source ID is the only permanent anchor.** Relationships at the source level use it
  (§4.1). It carries **no** version, language, or variant.
- **Entity IDs are version-pinned** (`@version`), because a control's text and numbering can
  change between editions. A mapping made against 2022 must not silently apply to 2027.
- **Filenames and folder paths are never identifiers.** They are recorded only as physical-file
  aliases (§7). Folder structure was treated as a hint and, where wrong, corrected.

### 2.3 Source ID minting convention

`‹PUBLISHER›-‹CODE›` (uppercase, hyphenated). Publisher prefixes:
`ISO` (ISO/IEC), `NIST`, `COSO`, `COBIT` (ISACA), `OCEG`, `OECD`, `IODSA`, `BCBS`, `IIA`,
`NCA`, `SAMA`, `SDAIA`, `CMA`, `KSA` (Saudi law/gazette).
Non-authoritative material uses namespaced prefixes: `EX-` (example), `TMPL-` (template),
`METHOD-` (methodology), `REF-` (reference). Absent-but-referenced works get a reserved Source
ID flagged `ABSENT` (§8). Unverifiable works are flagged `UNRESOLVED` (§9).

---

## 3. Faceted classification

Every Source is described by **independent facets**. They are orthogonal on purpose — mixing
them is the mistake V3 avoids.

> **The four independent dimensions (contract rule).** Every Source — and later every Entity —
> carries **four orthogonal readings that must each be stored explicitly and never inferred from
> one another**: **Identity** (§2), **Authority Profile** (§3.1), **License** (§3.2), and
> **Knowledge Stability** (§3.9). `Authority = Normative` does **not** imply `License = Public`,
> and neither implies `Stability = Stable`. The remaining items in §3 are descriptive facets that
> enrich, but never override, these four.

### 3.1 Authority Profile — epistemic weight *(Refinement 3, NEW)*

*How much authority the system grants this content.* This is the axis that governs behavior
(can the system state a requirement from it? weight it in a gap assessment?). **Distinct from
license.**

| Profile | Meaning | Examples |
|---|---|---|
| **Normative** | Defines conformance ("shall"); the system may assert requirements/controls from it | ISO standards' normative clauses, NIST CSF/800-53 |
| **Regulatory** | Legally mandated by a regulator/law; binding by force of law | NCA ECC, SAMA CSF, CMA rules, KSA laws, PDPL |
| **Interpretive** | Official guidance that explains/implements a normative or regulatory source | ISO 27002 guidance, SDAIA PDPL guides, NIST SP guidance |
| **Reference** | Authoritative best-practice that informs but does not mandate | Basel Principles, OECD Principles, King IV, Three Lines, risk textbooks |
| **Example** | Illustrative real-world artifact; never a source of requirements | corporate compliance handbooks, sample policies |
| **Template** | Reusable blank artifact | contract templates, risk-register template |
| **Internal** | Organization-produced internal material | (none yet) |

> A corporate policy sample may be *Licensed* (someone's copyright) yet only *Example* — it must
> **never** be treated as Normative. ISO is *Licensed* **and** *Normative*. NIST is *Public-Domain*
> **and** *Normative*. License and Authority Profile are two different questions.

### 3.2 License Classification — legal usage rights

*What we are legally allowed to do with it.* Governs storage, egress, and whether content may
appear in outputs.

`Public-Domain` (US-gov NIST; official KSA gazette texts) ·
`Licensed` (copyrighted; access-controlled — ISO, OCEG, COSO, ISACA/COBIT, IIA, OECD, King IV) ·
`Internal` (org-produced) · `Customer` (customer data — none yet) ·
`Unknown` (third-party corporate handbooks/templates — **legal review required before use**).

### 3.3 Document Genre — descriptive publication type

*What kind of publication it is* (human-facing metadata; does not by itself govern behavior).
`International-Standard · Framework · Law · Regulation · Guidance · Best-Practice · Methodology ·
Assessment-Tool · Workbook · Example · Template`.

### 3.4 Control Levels present — kinds of knowledge inside

A Source is a container of several kinds of knowledge; record the **set** it holds.
`Framework · Requirement · Control · Guideline · Process · Procedure · Evidence · Template ·
Assessment · Checklist · Example`.

### 3.5 Knowledge Entity Types — structural nodes *(to be extracted in Stage 2+)*

The node types the graph will contain. Extraction maps each Source's native structure onto these:
`Domain · Function · Category · Subcategory · Clause · Article · Objective · Principle ·
Practice · Capability · Requirement · Control · Subcontrol · Definition · Annex · Mapping-Entry`.

### 3.6 GRC Domains — topical, multi-valued

Every Source (and later every Entity) maps to **one or more** GRC domains — not only its parent
framework. *(This was the owner's key addition: ISO 27001 is not "just ISO"; it is Governance,
Risk, Compliance, Information Security, Asset Management, Third-Party, Business Continuity,
Internal Control, and Audit at once.)*

`GOV` Governance · `RSK` Risk · `CMP` Compliance · `IC` Internal Control · `AUD` Audit/Assurance ·
`ISEC` Information Security · `CYB` Cybersecurity · `PRIV` Privacy/Data Protection ·
`ASSET` Asset Management · `TPRM` Third-Party/Vendor · `BCM` Business Continuity/Resilience ·
`AIG` AI Governance · `OPR` Operational Risk · `FIN` Financial/Market · `LEG` Legal ·
`ETH` Ethics/Conduct · `ABC` Anti-Bribery · `AML` Anti-Money-Laundering · `QMS` Quality ·
`HR` Human Resources · `PROC` Procurement/Contracting.

### 3.7 Confidence — never guess *(Refinement carried from v2)*

Attached to identity, edition, structure, and **every relationship edge**:
`100%` confirmed (embedded title/keywords or authoritative public fact) · `95%` strong ·
`80%` reasonable — verify · `Unknown` (**must be verified; never asserted as fact**).

### 3.8 Product Usage — why this Source exists

Which engines consume it:
`Risk-Engine · Compliance-Engine · Governance-Engine · Audit-Engine · AI-Assistant ·
Knowledge-Graph · Control-Library · Question-Answering · Gap-Assessment`.

### 3.9 Knowledge Stability — how fast it changes *(Refinement 4, NEW — the fourth independent axis)*

*How volatile the knowledge is over time.* Governs **re-ingestion cadence, knowledge-graph
rebuilds, answer freshness, caching TTLs, and "a newer edition exists" alerts.** Fully
**independent of Identity, Authority, and License** — never inferred from them.

| Stability | Meaning | Operational implication |
|---|---|---|
| **Stable** | Effectively fixed for years; changes only with a rare new edition | re-ingest rarely; long cache TTL |
| **Version-bound** | Fixed *within* an edition, but the body issues discrete new editions | cache per edition; **alert when a newer edition ships** |
| **Living** | Rolling amendments with no neat edition boundary (guidelines, laws, regulator rules) | re-check periodically; freshness-sensitive |
| **Draft** | Not final; will be superseded | quarantine from Normative use; expect churn |
| **Volatile** | Changes frequently, instance-specific | example-only; low cache value |

**Stability register** (shown beside Authority and License to demonstrate the axes are independent):

| Source / family | Authority | License | Stability |
|---|---|---|---|
| ISO-27001, ISO-27002, COSO-IC | Normative | Licensed | **Stable** |
| ISO-27005/27017/31000/37001/37301/22301/9001 | Normative | Licensed | Stable |
| IODSA-KINGIV, BCBS-OPRISK, IIA-3LINES, COSO-ERM | Reference | Licensed | Stable |
| ISO-42001 (young standard) | Normative | Licensed | Version-bound |
| IIA-GIAS, COBIT-2019, OCEG-RB/BB, OECD-CG | Normative/Reference | Licensed | Version-bound |
| NIST-CSF, NIST-SP-800-53/171/37/61 | Normative/Interpretive | Public-Domain | **Version-bound** |
| NCA-ECC/CCC/CSCC/DCC/OTCC, SAMA-CSF | Regulatory | Public-Domain (Official) | Version-bound |
| NIST-AI-600 (profile) | Interpretive | Public-Domain | **Living** |
| SDAIA-*-GUIDE, CMA-LISTING/CGR | Interpretive/Regulatory | Public-Domain (Official) | Living |
| KSA-*-LAW (+ bylaws) | Regulatory | Public-Domain (Official) | Living |
| NIST-PF@1.1-IPD | Normative (draft) | Public-Domain | **Draft** |
| EX-CMP-*, EX-POL-*, TMPL-* | Example/Template | Unknown/Internal | **Volatile** |
| Unresolved (§9) | — | — | assign after verification |

> The columns do **not** correlate: ISO = Normative + Licensed + Stable; NIST = Normative + Public +
> Version-bound; a KSA law = Regulatory + Public + Living; a policy sample = Example + Unknown +
> Volatile. Four independent readings on every Source.

---

## 4. Relationships — two tiers, never conflated *(Refinement 2)*

The graph has **two distinct relationship registries.** Keeping them separate is mandatory.

### 4.1 Tier 1 — Source Relationships *(inferential, coarse)*

- **Between Source IDs** (version-free): `ISO-27001 maps_to NIST-CSF`.
- **Preliminary and inferential** — a human/expert-seeded hint that two *works* relate.
- Used for navigation and to *guide* Stage-2 extraction. **Not** an audit-grade control mapping.
- Every edge carries a confidence (§3.7). None are asserted above the evidence.

### 4.2 Tier 2 — Entity Relationships *(authoritative, version-pinned)*

- **Between Entity IDs**: `ISO-27001@2022::A.5.7  maps_to  NIST-CSF@2.0::PR.AA-03  maps_to  NCA-ECC@2-2024::2-3-1`.
- **This is the real knowledge.** It is what lets the assistant answer precisely and defend a
  cross-framework mapping to an auditor.
- **Version-pinned** and provenance-bearing (which source paragraph justified the edge).
- **Populated only in Stage 2+.** As of this contract, **zero Tier-2 edges are asserted** — they
  are `Unknown` until extracted with evidence. Tier-1 edges may later be *decomposed into* and
  *validated by* Tier-2 edges, but a Tier-1 hint never auto-promotes to a Tier-2 fact.
- **Temporally scoped (Validity).** Every Tier-2 edge carries a **Validity** — the edition context
  in which it holds (e.g. valid for `ISO-27001@2022`). Edges are **immutable**: when a mapping
  changes for a new edition, a **new** edge is minted against the new versions and the old edge is
  **retained** and linked via `superseded_by` (§4.3). We can therefore always answer *"this mapping
  was valid in the 2022 edition."* (See Principle 11, §10.)

### 4.3 Relationship type vocabulary (shared by both tiers)

`implements` · `detailed_by` · `maps_to` · `supports` · `overlaps` (symmetric) · `depends_on` ·
`expands` · `profile_of` · `annex_of` · `assesses` · `translates` · `derived_from` ·
`supersedes` / `superseded_by` · `duplicate_of` · `references` · `related_to` · `contradicts`.

### 4.4 Seeded Tier-1 Source Relationships (confidence-scored)

```
InfoSec / Cyber
  ISO-27001  detailed_by(100%)  ISO-27002
  ISO-27002  expanded_by(100%)  ISO-27017
  ISO-27001  maps_to(90%)       NIST-CSF
  NIST-CSF   maps_to(85%)       NCA-ECC
  NIST-CSF   detailed_by(90%)   NIST-SP-800-53
  NCA-ECC    overlaps(80%)      SAMA-CSF
  NCA-ECC    expanded_by(85%)   {NCA-CCC, NCA-CSCC, NCA-DCC, NCA-OTCC}
  COBIT      overlaps(75%)      NIST-CSF

Risk
  ISO-27005  implements(90%)    ISO-31000
  ISO-31000  overlaps(80%)      COSO-ERM
  NIST-SP-800-37 supports(85%)  NIST-CSF
  BCBS-OPRISK related_to(70%)   ISO-31000

Governance
  {COBIT, IODSA-KINGIV, OECD-CG, CMA-CGR}  overlaps(75%)  (each other)
  IIA-3LINES supports(85%)      COSO-IC

Compliance / Ethics / Privacy
  ISO-37301  related_to(80%)    ISO-37001
  SDAIA-PDPL-GUIDE implements(95%) KSA-PDPL-LAW
  KSA-PDPL-LAW related_to(85%)  {SDAIA-DTRANS-GUIDE, NCA-DCC, NIST-PF}

AI
  ISO-42001  overlaps(80%)      NIST-AI-100 (ABSENT)
  NIST-AI-600 profile_of(100%)  NIST-AI-100 (ABSENT)

Lineage / physical
  NIST-PF@1.1-IPD  supersedes(planned)  NIST-PF@1.0 (ABSENT)
  IIA-GIAS/AR      translates            IIA-GIAS/EN
  (duplicate_of edges — see §7 DG-1..DG-3)
```

---

## 5. Canonical Source Register — authoritative core

Facets per Source: **Authority Profile · License · Genre · Confidence · GRC Domains · Product usage.**
Flags: 🔒 encrypted · 🖨️ scanned→OCR · 📝 draft.

### 5.1 ISO/IEC & IIA — Authority: Normative · License: Licensed

| Source | Version(s) | Lang | C | GRC Domains | Used by |
|---|---|---|---|---|---|
| `ISO-27001` | 2022 | EN | 100% | GOV RSK CMP ISEC CYB ASSET TPRM BCM IC AUD | Control-Library, Compliance, Gap, KG, QA, Audit |
| `ISO-27002` (Interpretive) | 2022 | EN | 100% | ISEC CYB ASSET TPRM PRIV IC | Control-Library, Compliance, KG, QA |
| `ISO-27005` (Interpretive) | 2018 | EN | 100% | ISEC RSK CYB | Risk, KG, QA |
| `ISO-27017` | 2015 | EN | 100% | ISEC CYB TPRM ASSET | Control-Library, Compliance, KG |
| `ISO-31000` | 2018 | EN | 95% | RSK GOV | Risk, Governance, KG, QA |
| `ISO-37001` 🔒 | 2016 | EN | 100% | ABC CMP GOV ETH RSK | Compliance, Control-Library, KG |
| `ISO-37301` 🔒 | 2021 | EN | 95% | CMP GOV ETH RSK IC | Compliance, Governance, KG |
| `ISO-42001` 🖨️ | 2023 | EN | 100% | AIG GOV RSK CMP ETH | Compliance, Risk, AI-Assistant, KG |
| `ISO-22301` | 2019 | EN | 100% | BCM RSK GOV | Risk, Compliance, KG |
| `ISO-9001` 🔒 | 2015 | EN | 100% | QMS GOV RSK IC | Compliance, KG |
| `ISO-37300` ⚠ | — | EN | **Unknown** | — | *pending verification (§9)* |
| `IIA-GIAS` 🔒 | 2024 | EN, AR | 100% | AUD GOV RSK IC CMP ETH | Audit, Governance, KG, QA |
| `IIA-3LINES` (Reference) 🔒 | 2020 | EN | 100% | GOV RSK IC AUD | Governance, Audit, Risk, KG |

### 5.2 Frameworks — NIST (Public-Domain), COSO/COBIT/OCEG/OECD/IoDSA/Basel (Licensed)

| Source | Version(s) | Lang | Profile | License | C | GRC | Used by |
|---|---|---|---|---|---|---|---|
| `NIST-CSF` | 2.0 | EN | Normative | Public | 95% | CYB GOV RSK ISEC | Governance, Compliance, Control-Library, KG, QA |
| `NIST-SP-800-53` | R5 | EN | Normative | Public | 100% | ISEC CYB PRIV IC CMP | Control-Library, Compliance, Risk, KG |
| `NIST-SP-800-171` | R2 | EN | Normative | Public | 100% | ISEC CYB CMP TPRM | Compliance, Control-Library, KG |
| `NIST-SP-800-37` | R2 | EN | Normative | Public | 100% | RSK ISEC CYB GOV CMP | Risk, Governance, KG |
| `NIST-SP-800-61` | R2 | EN | Interpretive | Public | 100% | CYB ISEC BCM | Risk, KG, QA |
| `NIST-AI-600` | 1 (2024) | EN | Interpretive | Public | 100% | AIG RSK ETH | AI-Assistant, Risk, KG |
| `NIST-PF` 📝 | 1.1-IPD | EN | Normative (**draft**) | Public | 100%* | PRIV RSK GOV | KG, QA *(quarantine, see §9)* |
| `COSO-IC` | 2013 | EN | Normative | Licensed | 100% | IC GOV CMP RSK AUD FIN | Audit, Governance, Compliance, Risk, KG |
| `COSO-ERM` | 2017 (App-Tech only) | EN | Reference | Licensed | 95% | RSK GOV IC | Risk, Governance, KG |
| `COBIT` | 2019 | EN | Normative | Licensed | 100% | GOV RSK CMP IC AUD | Governance, Audit, Compliance, KG |
| `OCEG-RB` | 3.5 | AR | Reference | Licensed | 95% | GOV RSK CMP ETH AUD IC | Governance, Risk, Compliance, KG |
| `OCEG-BB` 🔒 | 3.5.1 | EN | Methodology | Licensed | 95% | GOV RSK CMP AUD | Audit, Gap, KG |
| `OCEG-ASSESS-AR` 🔒 ⚠ | — | AR | — | Licensed | Unknown | — | *pending (§9)* |
| `OECD-CG` | 2023 | EN | Reference | Licensed | 100% | GOV ETH FIN | Governance, KG, QA |
| `IODSA-KINGIV` 🔒 | 2016 | EN | Reference | Licensed | 100% | GOV ETH RSK AUD IC | Governance, Audit, KG |
| `BCBS-OPRISK` | 2011 | EN | Reference | Licensed | 100% | OPR RSK GOV IC | Risk, Governance, KG |

\* Identity confidence 100%; but it is a **draft** — see §9 quarantine rule.

### 5.3 Saudi regulators — NCA/SAMA/CMA/SDAIA · Authority: Regulatory/Interpretive · License: Public-Domain (Official)

| Source | Version(s) | Lang | Profile | C | GRC | Used by |
|---|---|---|---|---|---|---|
| `NCA-ECC` | 2-2024 | EN | Regulatory | 100% | CYB ISEC GOV RSK CMP TPRM BCM | Control-Library, Compliance, Gap, KG, QA |
| `NCA-CCC` | 1 (~2020) | EN | Regulatory | 90% | CYB ISEC TPRM CMP | Control-Library, Compliance, KG |
| `NCA-CSCC` | 1 (~2019) | AR | Regulatory | 90% | CYB ISEC CMP | Control-Library, Compliance, KG |
| `NCA-DCC` | 1 (~2022) | EN | Regulatory | 90% | CYB ISEC PRIV CMP | Control-Library, Compliance, KG |
| `NCA-OTCC` | 1-2022 | EN | Regulatory | 95% | CYB ISEC CMP | Control-Library, Compliance, KG |
| `SAMA-CSF` | 2017 | EN | Regulatory | 100% | CYB ISEC GOV RSK CMP TPRM BCM | Control-Library, Compliance, Risk, Gap, KG |
| `SAMA-RISK` 🚨 ⚠ | — | — | Regulatory | Unknown | RSK CMP FIN GOV | *pending decomposition (§9)* |
| `CMA-LISTING` | — | AR | Regulatory | 95% | FIN GOV CMP LEG | Compliance, Governance, KG |
| `CMA-CGR` | — | AR (+EN?) | Regulatory | 95% | GOV FIN CMP ETH | Governance, Compliance, KG |
| `SDAIA-PDPL-GUIDE` | — | AR | Interpretive | 95% | PRIV CMP LEG GOV | Compliance, KG, QA |
| `SDAIA-DTRANS-GUIDE` | — | AR | Interpretive | 95% | PRIV CMP LEG TPRM | Compliance, KG |
| `SDAIA-EMPLOYER-GUIDE` | — | AR | Interpretive | 90% | PRIV CMP HR LEG | Compliance, Gap, QA |

**Assessment-Tool renditions (xlsx):** `NCA-CSCC/…/Tool` `assesses` `NCA-CSCC`; `NCA-OTCC/…/Tool`
`assesses` `NCA-OTCC`; `NCA-OTCC/…/Annex` `annex_of` `NCA-OTCC` (carries cross-framework mappings).

### 5.4 Native structural schemas — the entity yield (heart of the model)

What Stage 2 will mint from each authoritative Source (drives `Knowledge Entity Types`, §3.5):

| Source | Native hierarchy → entities |
|---|---|
| `ISO-27001@2022` | Clause 4–10 › **Requirement**; Annex A › **Control** (93 controls, 4 themes) |
| `ISO-27002@2022` | **Control** › Attributes › Guidance (93) |
| `NIST-CSF@2.0` | **Function** (GV, ID, PR, DE, RS, RC) › **Category** › **Subcategory** |
| `NIST-SP-800-53@R5` | Family (20) › **Control** › Enhancement |
| `COBIT@2019` | Domain (EDM, APO, BAI, DSS, MEA) › **Objective** (40) › **Practice** › Activity |
| `COSO-IC@2013` | Component (5) › **Principle** (17) › Point-of-Focus |
| `COSO-ERM@2017` | Component (5) › **Principle** (20) |
| `ISO-31000@2018` | **Principle** · Framework · **Process** (clauses) |
| `OCEG-RB@3.5` | Component (LEARN, ALIGN, PERFORM, REVIEW) › Element › **Practice** |
| `NCA-ECC@2-2024` | Main-Domain (5) › **Subdomain** › **Control** › **Subcontrol** |
| `SAMA-CSF@2017` | Domain › Subdomain › **Principle** › **Control** |
| `IIA-GIAS@2024` | Domain (5) › **Principle** (15) › **Standard** |
| `IODSA-KINGIV@2016` | **Principle** (17) › Recommended Practice |
| `ISO-42001@2023` | Clause › **Requirement**; Annex A/B/C › **Control**/Guidance |
| `BCBS-OPRISK@2011` | **Principle** (11) |
| `KSA-*-LAW` | **Article** › Provision |

---

## 6. Bulk sources

### 6.1 Saudi Laws — `KSA-*` · Regulatory · Public-Domain (Official) · C 95% · Entity yield: Article › Provision

`KSA-COMPANIES-LAW` · `KSA-LABOR-LAW` · `KSA-CIVIL-TRANSACTIONS-LAW` · `KSA-BANKRUPTCY-LAW` ·
`KSA-PDPL-LAW` · `KSA-AML-LAW` · `KSA-ANTICONCEALMENT-LAW` · `KSA-ECOMMERCE-LAW` ·
`KSA-CAPITAL-MARKET-LAW` · `KSA-COMPETITION-LAW` · `KSA-EVIDENCE-LAW` ·
`KSA-COMMERCIAL-REGISTER-LAW` · `KSA-COMMERCIAL-REGISTER-BYLAW` (`derived_from` the law) ·
`KSA-TRADENAMES-LAW` · `KSA-TRADENAMES-BYLAW` (`derived_from`) · `KSA-INVESTMENT-LAW` ·
`KSA-SHARIA-PROCEDURE-LAW` · `KSA-PUBLICOFFICE-CRIMES-LAW` ·
`KSA-ECOMMERCE-COMPLIANCE-CHECKLIST` (Genre: Assessment-Tool) ·
`KSA-TOURISM-SERVICES-REG` (reclassified out of "Corporate Policies").
GRC domains vary per law (LEG always; +FIN/HR/PRIV/AML/ABC/GOV as applicable).
⚠ Reclassified out of "Laws": the franchise incorporation contract → `TMPL-INCORP-01` (Template).

### 6.2 Governance references

`SA-CGR-EN` (EN Saudi Corporate-Governance Regulations — candidate `translates` `CMA-CGR`, C 80%) ·
`REF-GOV-CORPGOV-BOOK-AR` ("Issues in Corporate Governance", License Unknown) ·
`REF-GOV-PUBSECTOR-BOOK-AR` ("Governance in the Public Sector", License Unknown) ·
`REF-GOV-BOOKLET13` ⚠ unresolved.

### 6.3 Non-authoritative pool — Authority: Example/Template · License: Unknown/Internal · Used by: AI-Assistant only

**Excluded from Control-Library and Gap-Assessment.** Retained as drafting reference / examples.

- **Compliance examples (6):** `EX-CMP-HHS-OIG-2023` (License Public-Domain) · `EX-CMP-WECOMPLY` ·
  `EX-CMP-EISAI-7E` · `EX-CMP-ETHICS-HANDBOOK` · `EX-CMP-PROGRAM-GUIDE-FR` · `EX-CMP-WHATIS-CMS`.
- **Corporate policy samples (11):** `EX-POL-COC-01/02` · `EX-POL-HR-MANUAL` · `EX-POL-PROCUREMENT` ·
  `EX-POL-TRAVEL` · `EX-POL-DATAPRIVACY` · `EX-POL-PRIVACY-GUIDE` · `EX-POL-WHISTLEBLOW` ·
  `EX-POL-DOA` · `EX-POL-INFOSEC` · `EX-BEST-COMARCH-VENDOR` (Best-Practice).
- **Contract templates (18 + 1 docx):** `TMPL-NDA-01/02/03` · `TMPL-MSA` · `TMPL-SAAS-01/02` ·
  `TMPL-DISTRIB-01/02` · `TMPL-FRANCHISE` · `TMPL-SHAREHOLDER-01/02/03` · `TMPL-PARTNERSHIP` ·
  `TMPL-AGENCY-01/02` · `TMPL-COMMERCIAL-AGENCY` · `TMPL-VENDOR-KSA` · `TMPL-INCORP-01` ·
  `TMPL-UNRESOLVED-01/02` (⚠ `doc_4`, `masterassurences`).
- **Risk pool:** `EX-RSK-CONCEPTS-5E-2015` · `EX-RSK-ILO-EBMO` · `TMPL-RSK-REGISTER` ·
  `METHOD-RSK-BOWTIE` · `REF-RSK-APPETITE` ⚠. The 2nd physical ISO-31000 copy is an **alias of
  `ISO-31000@2018`** (§7), not a separate Source.

---

## 7. Physical files, duplicates & renditions

**Never delete a physical copy.** Each is recorded as an alias of a Rendition, keyed by `sha256`.
Exact byte-duplicates form a **Duplicate Group** with one nominated **canonical** copy.

| Group | Type | Members (paths, abbreviated) | Canonical | Rel |
|---|---|---|---|---|
| **DG-1** | exact ×2 | King IV — `Governance/Corporate Governance/…` · `GRC/King IV/…` | the Governance copy | `duplicate_of` |
| **DG-2** | exact ×2 | OECD-CG `ed750b30-en` — `Governance/IT Governance/…` · `GRC/OECD…/…` | the GRC/OECD copy | `duplicate_of` |
| **DG-3** | exact ×3 | NIST-PF `CSWP.40.ipd` — `AI RMF Playbook/` · `NIST CSWP/` · `NIST Privacy Framework/` | the Privacy-Framework copy | `duplicate_of` |
| **CD-A** | content-equal | IIA-GIAS EN `…january9.pdf` · `…january9_printable-2.pdf` | `…january9.pdf` | `Printable` variant alias |
| **CD-B** | same standard | `ISO/ISO 31000/…` · `Risk Management/ISO-31000.pdf` | ISO-folder copy | alias (verify edition) |

**Renditions (not duplicates):** `IIA-GIAS/AR` `translates` `IIA-GIAS/EN`; `OCEG-RB@3.5/AR` is the
only present rendition (EN Red Book absent, §8); `NCA-*/Tool` xlsx are Assessment-Tool renditions.

*(The full physical-file ↔ Rendition binding table, with sha256 for all 117 files, is maintained
as the Stage-1 inventory companion and can be attached as an appendix on request. It is inventory
data, not part of this model contract.)*

---

## 8. Absent-but-referenced Sources (gaps)

Reserved Source IDs, flagged `ABSENT`, so relationships can point at them and the gap is explicit:

`NIST-AI-100` (core AI RMF — only the 600-1 GenAI Profile is present) · `NIST-AI-RMF-PLAYBOOK`
(folder held the Privacy draft instead) · `NIST-PF@1.0` (only the 1.1 **draft** is present) ·
`COSO-ERM@2017` core framework (only Application-Techniques present) · `OCEG-RB/EN` (only the AR
rendition is present).

---

## 9. Unresolved Sources — `Unknown` confidence (never asserted as fact)

| Source | Problem | Disposition |
|---|---|---|
| `ISO-37300` | 4 pages, no title — likely a preview or mislabeled `ISO 37000` | verify via first-page probe (Stage 2, on approval) |
| `SAMA-RISK` 🚨 | 1,281-page print-to-PDF **bundle** — many docs merged | must be decomposed into constituent Sources before any use |
| `OCEG-ASSESS-AR` | Arabic OCEG doc, encrypted, exact title unconfirmed | verify identity + decryptability |
| `REF-GOV-BOOKLET13`, `REF-RSK-APPETITE`, `TMPL-UNRESOLVED-01/02` | opaque filenames, null titles | title from first-page probe (deferred) |
| **11 encrypted files** | Spotlight "Password Encrypted" — owner-vs-user password unknown | probe openability before Stage 2; user/owner password may be required |
| `NIST-PF@1.1-IPD` | valid identity but a **DRAFT** | **Quarantine:** kept in graph, tagged `draft`, **excluded from Normative use** until a final edition supersedes it |

---

## 10. Contract governance — what every later stage must obey

1. **Identity:** reference works by **Source ID**; pin entities and Tier-2 relationships to
   `@version`. Never identify anything by filename or folder path.
2. **Container principle:** a document is provenance, not a knowledge unit. Knowledge = entities +
   relationships extracted from it.
3. **Two relationship tiers:** keep Source Relationships (Tier 1, inferential) and Entity
   Relationships (Tier 2, authoritative) in separate registries. A Tier-1 hint never
   auto-promotes to a Tier-2 fact.
4. **Confidence discipline:** nothing is asserted above its evidence; `Unknown` is a valid,
   required value. No invented relationships.
5. **Authority Profile governs behavior:** only `Normative`/`Regulatory` content may be the source
   of a stated requirement or a gap finding. `Reference`/`Interpretive` informs; `Example`/
   `Template` never asserts requirements.
6. **License governs egress:** `Licensed` and `Unknown`-license content is access-controlled and
   must not leak into external outputs; `Unknown`-license needs legal review before use.
7. **Provenance always:** every entity and every Tier-2 edge must trace back to a Source, Version,
   and location within it.
8. **Additive evolution:** a new edition is a **new Version under an existing Source**, never a new
   Source. Physical copies are never deleted — only aliased.
9. **Four independent dimensions:** every Source and Entity stores **Identity, Authority, License,
   and Stability** explicitly; none may be inferred from another (§3 rule).
10. **Stability drives operations:** re-ingestion cadence, knowledge-graph rebuilds, answer
    freshness, caching TTLs, and new-edition alerts are keyed off `Knowledge Stability` — not off
    Authority or License.
11. **Knowledge is immutable — extraction appends, never mutates.** Once a Knowledge Entity or a
    Tier-2 relationship is created it is **never edited, overwritten, or corrected in place.** This
    system is a **Knowledge Archive**, and an archive does not rewrite history.
    - *Entities:* when a Source's edition changes (`ISO-27001@2022` → `@2027`), old entities
      (`ISO-27001@2022::…`) are **kept as-is**; new entities (`ISO-27001@2027::…`) are **appended**.
    - *Relationships:* mappings are not changed in place — a new, version-scoped edge is appended
      with its own **Validity**, and the prior edge is retained and linked via `superseded_by`.
    - *Corrections:* a genuine extraction error is fixed by appending a **new, superseding**
      entity/edge with corrected provenance; the erroneous one is marked superseded, **not deleted**.
    - *Outcome — Temporal Traceability:* Identity, Version, Authority, License, and Stability all
      become answerable **as of any point in time**. The knowledge graph is append-only.

---

## 11. Constraints & non-goals of this document

This document **does not and must not**: generate code, define a database, write a migration,
touch Supabase, produce a physical schema, extract or ingest content, create embeddings, or begin
Stage 2. It is the **conceptual contract only.** Physical schema and pipeline are later,
separately-approved stages that must conform to this contract.

---

## 12. Change control & amendment log

Any change to identity rules (§2), the relationship tiers (§4), or the classification facets (§3)
is an **amendment**: proposed, reviewed, and recorded here before any downstream code relies on it.
The model is versioned; downstream stages pin the contract version they were built against.

**Freeze during execution (owner rule).** Once ratified, this contract is **frozen through
Stage 2**. It is amended **only** if extraction discovers a *real conflict with reality* — never
for improvements, refinements, or new ideas that surface mid-work. The stability of the contract
is itself a project asset; better ideas are logged for a future contract version, not applied live.

| Contract ver. | Date | Change |
|---|---|---|
| draft — Inventory | Stage 1 | 117-item inventory; duplicates, editions, risks |
| draft — Manifest v1 | Stage 1 | added Authority Level, GRC-domain mapping, cross-framework relationships |
| draft — Manifest v2 | Stage 1 | added Canonical IDs, Entity Types, Control Levels, Relationship Types, Confidence, License, Product-Usage |
| v1.0 | Stage 1 | Source≠Version identity spine; Source vs Entity relationship tiers; Authority Profile axis |
| v1.1 — RATIFIED | Stage 1 **CLOSED** | added Knowledge Stability as the 4th independent axis; the four-dimensions rule (Identity · Authority · License · Stability, none inferred); freeze-through-Stage-2 rule |
| **v1.2 (this) — RATIFIED** | Stage 1 close | **Principle 11 — Knowledge is Immutable: append-only extraction, version-scoped entities, relationship Validity, Temporal Traceability; recorded the V3 stage roadmap (§0.1)** |

*End of contract. **Stage 1 is CLOSED and this contract is RATIFIED.** Knowledge is append-only
(§10.11); the contract is frozen through Stage 2 and amended only on a real conflict with reality
(§12). Stage 2 (extraction) begins only on the owner's explicit approval.*
