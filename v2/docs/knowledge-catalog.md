# Rasheed Knowledge Catalog

- Status: Living document — single source of truth for Rasheed's knowledge base
- Date: 2026-07-11
- Owner: Chief Knowledge Officer function (this document)
- Companion: [V2 Knowledge Library Architecture](./architecture/knowledge-library.md), [ADR 0035](../../docs/adr/0035-v2-knowledge-library.md)
- Grounding: the repository knowledge sources audit performed this session, `RASHEED_GRC_PROJECT_BRIEF.md`'s Phase 3 roadmap, and direct inspection of every framework/regulation/ontology file currently in the repo

This is not a technical specification. It is the master knowledge roadmap for Rasheed V2.
Every future AI capability — RAG, Agents, Missions, Workflows, the Knowledge Graph — reads
its ground truth from what this document says exists, and its next priorities from what this
document says is missing. Nothing in this document creates a database table, writes code, or
touches production. It is the plan those things will follow.

---

## How to read this catalog

**Knowledge ID.** A permanent, stable identifier — never reused, never renumbered, even if a
source is later deprecated. Pattern: `<ISSUER>-<SHORT-NAME>` (e.g. `ISO-27001`, `NCA-ECC`) for
external standards/regulations/laws; `TPL-<NAME>` for policy/procedure templates; `CTR-<NAME>`
for contract templates; `CHK-<NAME>` for checklists. This is the same `short_code` field the
[Knowledge Library architecture](./architecture/knowledge-library.md#4-knowledge-source-model)
defines on `KnowledgeSource` — every row below is a future `KnowledgeSource` record, not just
a catalog line.

**Status.**
- **Available** — real, usable content exists in the repository today (even if partial).
- **Planned** — infrastructure or a pipeline exists (built, sometimes even proven once), but
  the content is not live/deployed/retrievable today.
- **Missing** — nothing exists yet.

**Priority.** Critical / High / Medium / Low — how much a working Saudi-market GRC
professional would miss this source if it were never added. Independent of Status.

**Owned by us?** Yes (we hold the authoritative content) / Partial (we authored a
representative sample, not the licensed official text) / No (nothing acquired).

**Capability legend.** ✅ available now · ⏳ designed, not yet built · ❌ not started.

---

## Knowledge Categories

The 17 categories requested, plus one addition: **Vendor & Third-Party Risk Management**
(§19) — already a recognized domain in the existing `KnowledgeDomain` taxonomy
(`packages/knowledge-ontology`) but absent from the initial category list, and distinct
enough from Risk Management generally (it concerns a third party's controls, not the
organization's own) to warrant its own category as the catalog scales.

1. International Standards
2. Saudi Regulations
3. Saudi Laws
4. Governance
5. Risk Management
6. Compliance
7. Cybersecurity
8. Internal Audit
9. Privacy & Data Protection
10. AI Governance
11. Business Continuity
12. Quality Management
13. Policy Templates
14. Procedures
15. Contract Templates
16. Checklists
17. Best Practices
18. Reference Books
19. Vendor & Third-Party Risk Management

---

### 1. International Standards

**Contribution to Rasheed's intelligence.** International standards are the vocabulary every
other category borrows — a Saudi regulation's requirement is usually explainable as "this is
NCA ECC's version of ISO 27001 A.5.15," and a tenant's uploaded policy is graded against
these control lists. This category is the backbone of cross-framework mapping (§7 of the
architecture doc) and the first thing a GRC professional expects Rasheed to know cold.

| ID | Name | Publisher | Version | Language | Region | Type | Status | Priority | Owned | Added | Processed | Searchable | AI-Enabled | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ISO-27001 | ISO/IEC 27001 — Information Security Management | ISO/IEC | 2022 | EN | International | Standard | Available | Critical | Partial | Yes | Yes | No | Partial | 12 representative controls seeded, not the full 93+; not embedded/searchable |
| ISO-27002 | ISO/IEC 27002 — Code of Practice for Controls | ISO/IEC | 2022 | EN | International | Standard | Missing | High | No | No | No | No | No | The detailed implementation guidance behind every 27001 control |
| ISO-27005 | ISO/IEC 27005 — Information Security Risk Management | ISO/IEC | 2022 | EN | International | Standard | Missing | Medium | No | No | No | No | No | |
| ISO-31000 | ISO 31000 — Risk Management Guidelines | ISO | 2018 | EN | International | Standard | Missing | High | No | No | No | No | No | |
| ISO-37301 | ISO 37301 — Compliance Management Systems | ISO | 2021 | EN | International | Standard | Missing | High | No | No | No | No | No | |
| ISO-22301 | ISO 22301 — Business Continuity Management | ISO | 2019 | EN | International | Standard | Missing | Medium | No | No | No | No | No | |
| ISO-9001 | ISO 9001 — Quality Management Systems | ISO | 2015 | EN | International | Standard | Missing | Low | No | No | No | No | No | |
| ISO-38500 | ISO/IEC 38500 — IT Governance | ISO/IEC | 2015 | EN | International | Standard | Missing | Low | No | No | No | No | No | |
| NIST-CSF | NIST Cybersecurity Framework | NIST | 2.0 | EN | US / International | Framework | Available | Critical | Partial | Yes | Yes | No | Partial | 7 top-level Functions/Categories only, no Subcategories seeded |
| NIST-800-53 | NIST SP 800-53 — Security and Privacy Controls | NIST | Rev. 5 | EN | US | Standard | Missing | Medium | No | No | No | No | No | |
| NIST-AI-RMF | NIST AI Risk Management Framework | NIST | 1.0 | EN | US | Framework | Missing | High | No | No | No | No | No | See §10 AI Governance |
| COBIT-2019 | COBIT 2019 — Governance of Enterprise IT | ISACA | 2019 | EN | International | Framework | Missing | High | No | No | No | No | No | Named in marketing copy only today |
| COSO-ERM | COSO Enterprise Risk Management Framework | COSO | 2017 | EN | International | Framework | Missing | High | No | No | No | No | No | Named in marketing copy only today |
| CIS-CONTROLS | CIS Critical Security Controls | CIS | v8 | EN | International | Standard | Missing | Medium | No | No | No | No | No | Named in marketing copy only today |
| PCI-DSS | PCI Data Security Standard | PCI SSC | v4.0 | EN | International | Standard | Missing | Medium | No | No | No | No | No | Zero repository mentions today |
| SOC2 | SOC 2 — Trust Services Criteria | AICPA | 2017 TSC | EN | US / International | Standard | Missing | Medium | No | No | No | No | No | Referenced only as illustrative example text in code/docs |

**Capability matrix (Available sources only — Missing sources have no capability enabled yet):**

| ID | Semantic Search | Q&A | Citation | Summarization | Doc Comparison | Doc Review | Gap Analysis | Compliance Assessment | Risk Assessment | Control Mapping | Policy Review | Policy Generation | Evidence Mapping | Cross-Framework Mapping | Mission Support | Agent Support |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ISO-27001 | ❌ | ⏳ | ⏳ | ❌ | ❌ | ❌ | ⏳ | ⏳ | ❌ | ✅ | ❌ | ❌ | ✅ | ⏳ | ❌ | ❌ |
| NIST-CSF | ❌ | ⏳ | ⏳ | ❌ | ❌ | ❌ | ⏳ | ⏳ | ❌ | ✅ | ❌ | ❌ | ✅ | ⏳ | ❌ | ❌ |

`Control Mapping`/`Evidence Mapping` are ✅ because both are usable today as reference
catalogs a tenant can link Evidence and Risk records against — the one real capability the
current 12/7-control samples deliver. Everything else needs the full control set plus the
V2 retrieval pipeline (§10 of the architecture doc) to become real.

**Category summary**
- **Already in Rasheed:** ISO 27001 and NIST CSF as small, unembedded reference samples.
- **Owned but not added:** nothing — no licensed/official standard text has been acquired.
- **Missing:** the other 14 standards entirely; full control text for the 2 partial ones;
  every standard's embedding/retrieval layer.
- **Recommended priority:** Critical — complete ISO 27001, NIST CSF, add COBIT 2019 and
  COSO ERM (both already marketed as supported with zero backing data — the highest-risk
  gap in the whole catalog, a claim Rasheed can't yet back up).

---

### 2. Saudi Regulations

**Contribution to Rasheed's intelligence.** This is Rasheed's home-market differentiator —
every competitor has ISO/NIST content; almost none have real, current Saudi regulator text.
Getting this category right is the single highest-leverage thing Rasheed's knowledge base can
do for a Saudi GRC professional.

| ID | Name | Publisher | Version | Language | Region | Type | Status | Priority | Owned | Added | Processed | Searchable | AI-Enabled | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NCA-ECC | NCA Essential Cybersecurity Controls | NCA | 2:2024 | AR/EN | Saudi Arabia | Regulation | Available | Critical | Partial | Yes | Yes | No | Partial | 10 of ~114 real controls seeded |
| NCA-CCC | NCA Cloud Cybersecurity Controls | NCA | 1:2020 | AR | Saudi Arabia | Regulation | Missing | High | No | No | No | No | No | |
| NCA-OTCC | NCA Operational Technology Cybersecurity Controls | NCA | 1:2022 | AR | Saudi Arabia | Regulation | Missing | Medium | No | No | No | No | No | |
| SAMA-CSF | SAMA Cybersecurity Framework | SAMA | current | AR/EN | Saudi Arabia | Regulation | Missing | Critical (financial sector) | No | No | No | No | No | Marketing/dashboard name only |
| SAMA-BCM | SAMA Business Continuity Management Framework | SAMA | current | AR/EN | Saudi Arabia | Regulation | Missing | Medium | No | No | No | No | No | |
| SAMA-ITGF | SAMA IT Governance Framework | SAMA | current | AR/EN | Saudi Arabia | Regulation | Missing | Medium | No | No | No | No | No | |
| CMA-CGR | CMA Corporate Governance Regulations | CMA | current | AR | Saudi Arabia | Regulation | Missing | High | No | No | No | No | No | CMA exists only as a crawl-target config entry today |
| CMA-RFMI | CMA Rules for Financial Market Institutions | CMA | current | AR | Saudi Arabia | Regulation | Missing | Medium | No | No | No | No | No | |

**Capability matrix:**

| ID | Semantic Search | Q&A | Citation | Summarization | Doc Comparison | Doc Review | Gap Analysis | Compliance Assessment | Risk Assessment | Control Mapping | Policy Review | Policy Generation | Evidence Mapping | Cross-Framework Mapping | Mission Support | Agent Support |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NCA-ECC | ❌ | ⏳ | ⏳ | ❌ | ❌ | ❌ | ⏳ | ⏳ | ❌ | ✅ | ❌ | ❌ | ✅ | ⏳ | ❌ | ❌ |

**Category summary**
- **Already in Rasheed:** NCA ECC, 10-control sample.
- **Owned but not added:** nothing licensed/official; a crawl-target config exists for CMA
  and SAMA with zero actual content.
- **Missing:** NCA CCC, NCA OTCC, both SAMA frameworks beyond the CSF name, both CMA
  regulations — every one of these has zero real content today.
- **Recommended priority:** Critical — this category should lead V2's content acquisition
  work, ahead of expanding international standards, because it is Rasheed's stated market.

---

### 3. Saudi Laws

**Contribution to Rasheed's intelligence.** Laws are the legal authority regulations sit on
top of — a compliance answer that cites the regulation but not the underlying law reads as
less authoritative to a Saudi legal/compliance reviewer. This category also anchors the one
genuinely proven ingestion pipeline in the repository (`SA-BOE`).

| ID | Name | Publisher | Version | Language | Region | Type | Status | Priority | Owned | Added | Processed | Searchable | AI-Enabled | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SA-BOE | Bureau of Experts regulation library (cross-cutting law repository) | BOE | rolling | AR | Saudi Arabia | Law repository | Planned | Critical | Yes | Partial | Partial | No | No | One law (Commercial Agency Law) fully ingested, parsed, and embedded once — proven, but not deployed and embeddings unread |
| PDPL | Personal Data Protection Law | SDAIA | 2023 (amended) | AR/EN | Saudi Arabia | Law | Missing | Critical | No | No | No | No | No | Name/label only; dashboard coverage numbers for it are illustrative |
| SA-ACCL | Anti-Cyber Crime Law | Saudi Government | 2007 | AR | Saudi Arabia | Law | Missing | High | No | No | No | No | No | |
| SA-ECL | E-Commerce Law | Ministry of Commerce | 2019 | AR | Saudi Arabia | Law | Missing | Medium | No | No | No | No | No | |
| SA-CL | Companies Law | Ministry of Commerce | 2022 | AR | Saudi Arabia | Law | Missing | Medium | No | No | No | No | No | |
| SA-AML | Anti-Money Laundering Law | Saudi Government | 2017 | AR | Saudi Arabia | Law | Missing | Medium | No | No | No | No | No | |
| SA-GTPL | Government Tenders and Procurement Law | Ministry of Finance | 2019 | AR | Saudi Arabia | Law | Missing | Low | No | No | No | No | No | |
| SA-LL | Labor Law | MHRSD | 2005 (amended) | AR | Saudi Arabia | Law | Missing | Low | No | No | No | No | No | |

**Capability matrix:**

| ID | Semantic Search | Q&A | Citation | Summarization | Doc Comparison | Doc Review | Gap Analysis | Compliance Assessment | Risk Assessment | Control Mapping | Policy Review | Policy Generation | Evidence Mapping | Cross-Framework Mapping | Mission Support | Agent Support |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SA-BOE | ⏳ | ⏳ | ⏳ | ⏳ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

Every capability for `SA-BOE` is ⏳, not ✅, even though the content and embeddings exist —
because nothing reads them yet (ADR 0032). This is the clearest "quick win" in the entire
catalog: the work is retrieval wiring, not content acquisition.

**Category summary**
- **Already in Rasheed:** one law, fully processed and embedded, sitting unused.
- **Owned but not added:** nothing else acquired.
- **Missing:** PDPL's actual text (despite being marketed), and 6 other foundational laws.
- **Recommended priority:** Critical for `SA-BOE` activation (near-zero new work, pure
  retrieval wiring); High for PDPL given its centrality to the Privacy category (§9); the
  remaining laws are High/Medium/Low as marked, expandable via the same proven BOE pipeline.

---

### 4. Governance

**Contribution to Rasheed's intelligence.** Governance content lets Rasheed answer "who
should approve this" and "what does good board oversight look like," not just "is this
control implemented" — the layer above individual controls that ties a compliance answer back
to accountability and decision rights.

| ID | Name | Publisher | Version | Language | Region | Type | Status | Priority | Owned | Added | Processed | Searchable | AI-Enabled | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| COSO-IC | COSO Internal Control — Integrated Framework | COSO | 2013 | EN | International | Framework | Missing | High | No | No | No | No | No | Distinct from COSO ERM (§1) — control-design focus, not risk focus |
| OECD-CGP | G20/OECD Principles of Corporate Governance | OECD | 2023 | EN | International | Guide | Missing | Low | No | No | No | No | No | |
| CMA-CGR | *(see §2, Saudi Regulations)* | | | | | | | | | | | | | Cross-referenced, not duplicated |
| TPL-BOARD-CHARTER | Board Charter Template | Internal | v1 | AR/EN | — | Template | Missing | Medium | No | No | No | No | No | |
| TPL-GOV-POLICY | Corporate Governance Policy Template | Internal | v1 | AR/EN | — | Template | Missing | Medium | No | No | No | No | No | |

**Capability matrix:** no source in this category is Available — every capability is ❌ for
every row above.

**Category summary**
- **Already in Rasheed:** nothing (CMA-CGR is cataloged under §2, has no content).
- **Owned but not added:** nothing.
- **Missing:** the entire category.
- **Recommended priority:** Medium — governance content matters, but is lower-frequency in
  daily GRC work than Cybersecurity/Compliance; sequence after those.

---

### 5. Risk Management

**Contribution to Rasheed's intelligence.** Risk content connects a control gap to its actual
business consequence — the difference between "this control is missing" and "this control is
missing, and here's what that exposes you to." Rasheed already has a live, structured Risk
Register; this category's job is to ground *how* a risk should be assessed, not just record
that one exists.

| ID | Name | Publisher | Version | Language | Region | Type | Status | Priority | Owned | Added | Processed | Searchable | AI-Enabled | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RISK-REGISTER | Rasheed Risk Register (internal module) | Internal | live | AR/EN | — | Internal system | Available | Critical | Yes | Yes | Yes | Partial | No | Production CRUD, 5×5 scoring, acceptance workflow — a working *record-keeping* tool, not a knowledge source in the RAG sense |
| ISO-31000 | *(see §1)* | | | | | | | | | | | | | Cross-referenced |
| COSO-ERM | *(see §1)* | | | | | | | | | | | | | Cross-referenced |
| ISO-27005 | *(see §1)* | | | | | | | | | | | | | Cross-referenced |
| FAIR | FAIR Risk Quantification Model | FAIR Institute / Open Group | 2.0 | EN | International | Method | Missing | Low | No | No | No | No | No | |
| TPL-RISK-APPETITE | Risk Appetite Statement Template | Internal | v1 | AR/EN | — | Template | Missing | Medium | No | No | No | No | No | |

**Capability matrix:**

| ID | Semantic Search | Q&A | Citation | Summarization | Doc Comparison | Doc Review | Gap Analysis | Compliance Assessment | Risk Assessment | Control Mapping | Policy Review | Policy Generation | Evidence Mapping | Cross-Framework Mapping | Mission Support | Agent Support |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RISK-REGISTER | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (manual) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

`Risk Assessment` is ✅ but marked "manual" deliberately — a human scores likelihood/impact
today; nothing AI-assists that score yet (a currently disconnected AI-analysis-found-risk
concept exists separately, see the architecture doc's Internal Knowledge findings).

**Category summary**
- **Already in Rasheed:** a real, working Risk Register — the strongest internal-knowledge
  asset in this whole catalog.
- **Owned but not added:** nothing.
- **Missing:** every methodology source (ISO 31000, COSO ERM, ISO 27005, FAIR) that would let
  Rasheed *explain* a risk score, not just store one.
- **Recommended priority:** High — bridging the AI-analysis risk findings into the Risk
  Register (a gap named in the earlier internal-knowledge audit) is higher-value than new
  methodology content and should be sequenced first within this category.

---

### 6. Compliance

**Contribution to Rasheed's intelligence.** This category is the connective tissue between
"what a regulation requires" and "what we've actually done about it" — obligation tracking is
the mechanism that turns a pile of regulatory text into a checkable to-do list per tenant.

| ID | Name | Publisher | Version | Language | Region | Type | Status | Priority | Owned | Added | Processed | Searchable | AI-Enabled | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| REG-OBLIGATIONS | Regulatory Obligations Library (internal, schema-only) | Internal | — | AR/EN | Saudi Arabia | Internal system | Planned | Critical | Yes | Partial | No | No | No | Real table exists (`regulatory_obligations`), empty — no scheduled writer |
| ISO-37301 | *(see §1)* | | | | | | | | | | | | | Cross-referenced |
| COMPLIANCE-PROGRAM-GUIDE | Compliance Program Design Guide | Internal | v1 | EN | — | Guide | Missing | Medium | No | No | No | No | No | |

**Capability matrix:** no source in this category is Available — `REG-OBLIGATIONS` is Planned
(schema exists, zero rows), so every capability is ❌ today.

**Category summary**
- **Already in Rasheed:** an empty, correctly-shaped table.
- **Owned but not added:** nothing.
- **Missing:** the classification pipeline that would populate `REG-OBLIGATIONS` was built
  (`packages/regulatory-intelligence-adapters`) but never scheduled — same root cause as
  `SA-BOE` above.
- **Recommended priority:** Critical — activating this table (scheduling the already-built
  classifier) is pure deployment work, the second "quick win" after `SA-BOE`.

---

### 7. Cybersecurity

**Contribution to Rasheed's intelligence.** The single most-asked-about domain in Saudi GRC
today, and — via NCA ECC and ISO 27001 — the category with the most existing (if thin)
content. This is where Rasheed's current credibility is highest and where completeness
matters most.

| ID | Name | Publisher | Version | Language | Region | Type | Status | Priority | Owned | Added | Processed | Searchable | AI-Enabled | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NCA-ECC | *(see §2)* | | | | | | | | | | | | | Cross-referenced |
| ISO-27001 | *(see §1)* | | | | | | | | | | | | | Cross-referenced |
| ISO-27002 | *(see §1)* | | | | | | | | | | | | | Cross-referenced |
| NIST-CSF | *(see §1)* | | | | | | | | | | | | | Cross-referenced |
| CIS-CONTROLS | *(see §1)* | | | | | | | | | | | | | Cross-referenced |
| MITRE-ATTCK | MITRE ATT&CK Framework | MITRE | v15 | EN | International | Knowledge base | Missing | Medium | No | No | No | No | No | Threat/technique reference, not a compliance control set |
| OWASP-TOP10 | OWASP Top 10 | OWASP | 2021 | EN | International | Best Practice | Missing | Low | No | No | No | No | No | |

**Capability matrix:** identical to the Available rows already shown in §1/§2 (NCA-ECC,
ISO-27001, NIST-CSF) — not repeated here to avoid duplication; see those sections.

**Category summary**
- **Already in Rasheed:** the three strongest sources in the whole catalog, still each a
  small sample.
- **Owned but not added:** nothing.
- **Missing:** ISO 27002 (the implementation detail behind 27001), CIS Controls, and two
  reference knowledge bases (MITRE ATT&CK, OWASP) that support technical-control assessment.
- **Recommended priority:** Critical — complete the existing three before adding new sources
  here; this category's ROI-per-control is the highest in the catalog.

---

### 8. Internal Audit

**Contribution to Rasheed's intelligence.** Internal Audit content lets Rasheed support the
assurance function specifically — audit planning, sampling, and reporting have their own
professional standards distinct from the control frameworks being audited.

| ID | Name | Publisher | Version | Language | Region | Type | Status | Priority | Owned | Added | Processed | Searchable | AI-Enabled | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| IIA-IPPF | IIA International Professional Practices Framework | IIA | 2024 | EN | International | Standard | Missing | High | No | No | No | No | No | |
| COSO-IC | *(see §4)* | | | | | | | | | | | | | Cross-referenced |
| TPL-AUDIT-CHARTER | Internal Audit Charter Template | Internal | v1 | AR/EN | — | Template | Missing | Medium | No | No | No | No | No | |
| CHK-AUDIT-PROGRAM | Audit Program Checklist Set | Internal | v1 | AR/EN | — | Checklist | Missing | Medium | No | No | No | No | No | |

**Capability matrix:** every source in this category is Missing — no capabilities enabled.

**Category summary**
- **Already in Rasheed:** nothing.
- **Owned but not added:** nothing.
- **Missing:** the entire category.
- **Recommended priority:** Medium — real value, but secondary to closing the Cybersecurity
  and Saudi Regulations gaps first.

---

### 9. Privacy & Data Protection

**Contribution to Rasheed's intelligence.** PDPL enforcement is active and increasingly
scrutinized in Saudi Arabia; this category is where a data-protection-specific gap analysis
or data-classification recommendation would be grounded — currently the widest gap between
what Rasheed's marketing claims (PDPL support, shown on demo dashboards) and what exists.

| ID | Name | Publisher | Version | Language | Region | Type | Status | Priority | Owned | Added | Processed | Searchable | AI-Enabled | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PDPL | *(see §3)* | | | | | | | | | | | | | Cross-referenced |
| GDPR | EU General Data Protection Regulation | EU | 2016/679 | EN | International (reference) | Regulation | Missing | Medium | No | No | No | No | No | Common benchmark reference for PDPL-adjacent questions |
| ISO-27701 | ISO/IEC 27701 — Privacy Information Management | ISO/IEC | 2019 | EN | International | Standard | Missing | Medium | No | No | No | No | No | |
| TPL-DATA-CLASSIFICATION | Data Classification Policy Template | Internal | v1 | AR/EN | — | Template | Missing | High | No | No | No | No | No | |

**Capability matrix:** every source in this category is Missing — no capabilities enabled.

**Category summary**
- **Already in Rasheed:** nothing real (PDPL is name-only).
- **Owned but not added:** nothing.
- **Missing:** the entire category, including the flagship regulation itself.
- **Recommended priority:** Critical — this is the largest gap between marketed capability
  and actual content in the catalog; PDPL should be sequenced immediately after the
  Cybersecurity trio (§7) and `SA-BOE` activation (§3).

---

### 10. AI Governance

**Contribution to Rasheed's intelligence.** A newer but fast-moving domain — organizations
adopting AI (including Rasheed's own customers, adopting Rasheed itself) increasingly need
governance content for their AI use, not just their traditional IT/cyber controls. Timely,
low-competition category for a differentiated Saudi GRC platform.

| ID | Name | Publisher | Version | Language | Region | Type | Status | Priority | Owned | Added | Processed | Searchable | AI-Enabled | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NIST-AI-RMF | *(see §1)* | | | | | | | | | | | | | Cross-referenced |
| ISO-42001 | ISO/IEC 42001 — AI Management System | ISO/IEC | 2023 | EN | International | Standard | Missing | High | No | No | No | No | No | |
| SDAIA-AI-ETHICS | SDAIA AI Ethics Principles | SDAIA | 2023 | AR/EN | Saudi Arabia | Guide | Missing | High | No | No | No | No | No | The Saudi-specific angle for this category |
| EU-AI-ACT | EU Artificial Intelligence Act | EU | 2024 | EN | International (reference) | Regulation | Missing | Low | No | No | No | No | No | |

**Capability matrix:** every source in this category is Missing — no capabilities enabled.

**Category summary**
- **Already in Rasheed:** nothing.
- **Owned but not added:** nothing.
- **Missing:** the entire category.
- **Recommended priority:** High — small, high-signal category; SDAIA AI Ethics Principles
  and NIST AI RMF are cheap wins that differentiate Rasheed for a growing customer need.

---

### 11. Business Continuity

**Contribution to Rasheed's intelligence.** Grounds Rasheed's ability to review or generate
BCP/DR content and assess an organization's resilience posture — a recurring audit and
regulatory-examination topic, especially for SAMA-regulated entities.

| ID | Name | Publisher | Version | Language | Region | Type | Status | Priority | Owned | Added | Processed | Searchable | AI-Enabled | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ISO-22301 | *(see §1)* | | | | | | | | | | | | | Cross-referenced |
| SAMA-BCM | *(see §2)* | | | | | | | | | | | | | Cross-referenced |
| TPL-BCP | Business Continuity Plan Template | Internal | v1 | AR/EN | — | Template | Missing | Medium | No | No | No | No | No | |
| TPL-DRP | Disaster Recovery Plan Template | Internal | v1 | AR/EN | — | Template | Missing | Medium | No | No | No | No | No | |

**Capability matrix:** every source in this category is Missing — no capabilities enabled.

**Category summary**
- **Already in Rasheed:** nothing.
- **Owned but not added:** nothing.
- **Missing:** the entire category.
- **Recommended priority:** Medium.

---

### 12. Quality Management

**Contribution to Rasheed's intelligence.** The smallest-footprint category for a GRC-focused
platform, but relevant where quality and compliance management systems intersect (ISO 9001
shops that also need 27001, common in Saudi manufacturing/industrial tenants).

| ID | Name | Publisher | Version | Language | Region | Type | Status | Priority | Owned | Added | Processed | Searchable | AI-Enabled | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ISO-9001 | *(see §1)* | | | | | | | | | | | | | Cross-referenced |
| ISO-20000 | ISO/IEC 20000-1 — IT Service Management | ISO/IEC | 2018 | EN | International | Standard | Missing | Low | No | No | No | No | No | |
| TPL-QMS-MANUAL | Quality Management System Manual Template | Internal | v1 | AR/EN | — | Template | Missing | Low | No | No | No | No | No | |

**Capability matrix:** every source in this category is Missing — no capabilities enabled.

**Category summary**
- **Already in Rasheed:** nothing.
- **Owned but not added:** nothing.
- **Missing:** the entire category.
- **Recommended priority:** Low.

---

### 13. Policy Templates

**Contribution to Rasheed's intelligence.** Templates are what turns "Rasheed found a gap"
into "Rasheed can help you close it" — the difference between an assessment tool and an
authoring assistant. This category is also where the existing, working Policies module (a
real production feature) and the *template* concept (currently entirely absent, per the
earlier internal-knowledge audit) meet.

| ID | Name | Publisher | Version | Language | Region | Type | Status | Priority | Owned | Added | Processed | Searchable | AI-Enabled | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| POLICIES-MODULE | Rasheed Policies module (internal system) | Internal | live | AR/EN | — | Internal system | Available | Critical | Yes | Yes | Yes | Partial | No | Production draft→review→publish workflow — a record-keeping tool, not a template library |
| TPL-INFOSEC-POLICY | Information Security Policy Template | Internal | v1 | AR/EN | — | Template | Missing | Critical | No | No | No | No | No | |
| TPL-AUP | Acceptable Use Policy Template | Internal | v1 | AR/EN | — | Template | Missing | High | No | No | No | No | No | |
| TPL-ACCESS-CONTROL-POLICY | Access Control Policy Template | Internal | v1 | AR/EN | — | Template | Missing | High | No | No | No | No | No | |
| TPL-DATA-RETENTION-POLICY | Data Retention Policy Template | Internal | v1 | AR/EN | — | Template | Missing | Medium | No | No | No | No | No | |
| TPL-IR-POLICY | Incident Response Policy Template | Internal | v1 | AR/EN | — | Template | Missing | High | No | No | No | No | No | |
| TPL-VENDOR-POLICY | Vendor Management Policy Template | Internal | v1 | AR/EN | — | Template | Missing | Medium | No | No | No | No | No | |
| TPL-REMOTE-WORK-POLICY | Remote Work Policy Template | Internal | v1 | AR/EN | — | Template | Missing | Low | No | No | No | No | No | |
| TPL-PASSWORD-POLICY | Password Policy Template | Internal | v1 | AR/EN | — | Template | Missing | Medium | No | No | No | No | No | |

**Capability matrix:**

| ID | Semantic Search | Q&A | Citation | Summarization | Doc Comparison | Doc Review | Gap Analysis | Compliance Assessment | Risk Assessment | Control Mapping | Policy Review | Policy Generation | Evidence Mapping | Cross-Framework Mapping | Mission Support | Agent Support |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| POLICIES-MODULE | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

Every capability is ❌ even for the live module — it stores policy *text* a tenant writes
by hand; nothing AI-touches Policies today (confirmed in the earlier internal-knowledge
audit — Policies imports no AI code at all).

**Category summary**
- **Already in Rasheed:** a real system to store and govern policies, but no templates and
  no AI assistance.
- **Owned but not added:** nothing.
- **Missing:** every template; AI drafting/review for the existing module.
- **Recommended priority:** Critical — templates plus `Policy Generation`/`Policy Review`
  capability is one of the highest-value, most-requested GRC-professional workflows and
  currently has zero coverage despite a working storage system already in place.

---

### 14. Procedures

**Contribution to Rasheed's intelligence.** Procedures are the operational "how" beneath a
policy's "what" — currently the most structurally absent internal-knowledge concept in the
whole product (no distinct entity exists anywhere, confirmed in the earlier audit).

| ID | Name | Publisher | Version | Language | Region | Type | Status | Priority | Owned | Added | Processed | Searchable | AI-Enabled | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TPL-IR-PROCEDURE | Incident Response Procedure Template | Internal | v1 | AR/EN | — | Template | Missing | High | No | No | No | No | No | |
| TPL-ACCESS-PROV-PROCEDURE | Access Provisioning Procedure Template | Internal | v1 | AR/EN | — | Template | Missing | Medium | No | No | No | No | No | |
| TPL-CHANGE-MGMT-PROCEDURE | Change Management Procedure Template | Internal | v1 | AR/EN | — | Template | Missing | Medium | No | No | No | No | No | |
| TPL-BACKUP-PROCEDURE | Backup & Recovery Procedure Template | Internal | v1 | AR/EN | — | Template | Missing | Medium | No | No | No | No | No | |
| TPL-VENDOR-ONBOARD-PROCEDURE | Vendor Onboarding Procedure Template | Internal | v1 | AR/EN | — | Template | Missing | Low | No | No | No | No | No | |

**Capability matrix:** every source in this category is Missing — no capabilities enabled.

**Category summary**
- **Already in Rasheed:** nothing — Procedures have no distinct entity anywhere, not even a
  reference catalog.
- **Owned but not added:** nothing.
- **Missing:** the entire category, plus the underlying product concept of "Procedure" as
  distinct from "Policy."
- **Recommended priority:** High — this is a genuine product gap, not just a content gap;
  should be scoped together with §13's template work.

---

### 15. Contract Templates

**Contribution to Rasheed's intelligence.** The one category where real, curated seed data
already exists in the repository — the ontology's contract-clause taxonomy — but it was built
for a different (Python, unscheduled) pipeline and has never reached a tenant-facing feature.

| ID | Name | Publisher | Version | Language | Region | Type | Status | Priority | Owned | Added | Processed | Searchable | AI-Enabled | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CTR-NDA | Non-Disclosure Agreement — clause taxonomy | Internal | v1 | EN | — | Contract | Planned | Medium | Yes | Partial | No | No | No | Real clause data exists (`ontology/contracts.json`) — required/risk/protective clauses, negotiation points — not deployed to any product surface |
| CTR-DPA | Data Processing Agreement Template | Internal | v1 | AR/EN | — | Contract | Missing | High | No | No | No | No | No | Rising priority given PDPL (§3/§9) |
| CTR-SLA | Service Level Agreement Template | Internal | v1 | AR/EN | — | Contract | Missing | Medium | No | No | No | No | No | |
| CTR-VENDOR-AGREEMENT | Vendor/Supplier Agreement Template | Internal | v1 | AR/EN | — | Contract | Missing | Medium | No | No | No | No | No | |
| CTR-EMPLOYMENT | Employment Contract Template | Internal | v1 | AR/EN | — | Contract | Missing | Low | No | No | No | No | No | |

**Capability matrix:**

| ID | Semantic Search | Q&A | Citation | Summarization | Doc Comparison | Doc Review | Gap Analysis | Compliance Assessment | Risk Assessment | Control Mapping | Policy Review | Policy Generation | Evidence Mapping | Cross-Framework Mapping | Mission Support | Agent Support |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CTR-NDA | ❌ | ❌ | ❌ | ❌ | ❌ | ⏳ | ⏳ | ❌ | ❌ | ❌ | ❌ | ⏳ | ❌ | ❌ | ❌ | ❌ |

`Document Review`, `Gap Analysis`, and `Policy Generation` (read here as "contract clause
generation") are ⏳ rather than ❌ specifically because the underlying clause taxonomy already
exists and is real — the missing piece is a retrieval/generation surface, not new content.

**Category summary**
- **Already in Rasheed:** one real, well-curated contract type (NDA) as data, unreachable
  from any product surface.
- **Owned but not added:** the NDA clause taxonomy — genuinely owned, genuinely unused.
- **Missing:** every other contract template; the product surface to expose any of it.
- **Recommended priority:** Medium overall, but High specifically for surfacing the existing
  NDA data — the lowest-effort win in this category by far.

---

### 16. Checklists

**Contribution to Rasheed's intelligence.** Checklists are the fastest-to-produce,
highest-frequency-use artifact a GRC professional touches — self-assessments and audit prep
in particular. Confirmed completely absent from the codebase (zero mentions, in either
implementation) in the earlier audit.

| ID | Name | Publisher | Version | Language | Region | Type | Status | Priority | Owned | Added | Processed | Searchable | AI-Enabled | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CHK-NCA-ECC-SELFASSESS | NCA ECC Self-Assessment Checklist | Internal | v1 | AR | Saudi Arabia | Checklist | Missing | Critical | No | No | No | No | No | Highest-value single checklist given §2/§7's priority |
| CHK-ISO27001-READINESS | ISO 27001 Readiness Checklist | Internal | v1 | AR/EN | — | Checklist | Missing | High | No | No | No | No | No | |
| CHK-VENDOR-DUE-DILIGENCE | Vendor Due Diligence Checklist | Internal | v1 | AR/EN | — | Checklist | Missing | Medium | No | No | No | No | No | |
| CHK-IR-CHECKLIST | Incident Response Checklist | Internal | v1 | AR/EN | — | Checklist | Missing | Medium | No | No | No | No | No | |
| CHK-ONBOARDING-SECURITY | New Employee Security Onboarding Checklist | Internal | v1 | AR/EN | — | Checklist | Missing | Low | No | No | No | No | No | |

**Capability matrix:** every source in this category is Missing — no capabilities enabled.

**Category summary**
- **Already in Rasheed:** nothing.
- **Owned but not added:** nothing.
- **Missing:** the entire category and concept — confirmed a genuine, total gap.
- **Recommended priority:** High — cheap to produce once §7's frameworks are complete
  (checklists derive directly from control lists), high perceived value.

---

### 17. Best Practices

**Contribution to Rasheed's intelligence.** Practitioner-level guidance that sits below formal
standards — configuration hardening, common vulnerability patterns — useful for technical
control assessment specifically, complementing (not duplicating) §7's formal frameworks.

| ID | Name | Publisher | Version | Language | Region | Type | Status | Priority | Owned | Added | Processed | Searchable | AI-Enabled | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CIS-BENCHMARKS | CIS Benchmarks (configuration hardening guides) | CIS | rolling | EN | International | Best Practice | Missing | Medium | No | No | No | No | No | Distinct from CIS Controls (§1) |
| SANS-TOP25 | SANS/CWE Top 25 Software Weaknesses | SANS / MITRE | 2024 | EN | International | Best Practice | Missing | Low | No | No | No | No | No | |
| NIST-SP-800-SERIES | NIST Special Publications (general guidance series) | NIST | rolling | EN | US | Best Practice | Missing | Medium | No | No | No | No | No | |

**Capability matrix:** every source in this category is Missing — no capabilities enabled.

**Category summary**
- **Already in Rasheed:** nothing.
- **Owned but not added:** nothing.
- **Missing:** the entire category.
- **Recommended priority:** Medium — useful depth, not foundational.

---

### 18. Reference Books

**Contribution to Rasheed's intelligence.** Longer-form professional reference material —
useful for training an Agent's "how would an experienced GRC practitioner reason about this"
behavior, distinct from the citable, structured content the other categories provide.

| ID | Name | Publisher | Version | Language | Region | Type | Status | Priority | Owned | Added | Processed | Searchable | AI-Enabled | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OCEG-REDBOOK | OCEG GRC Capability Model ("Red Book") | OCEG | 3.0 | EN | International | Reference Book | Missing | Medium | No | No | No | No | No | The field's own reference model for what "GRC" as a discipline covers |
| ISACA-CISA-MANUAL | ISACA CISA Review Manual | ISACA | current | EN | International | Reference Book | Missing | Low | No | No | No | No | No | |

**Capability matrix:** every source in this category is Missing — no capabilities enabled.

**Category summary**
- **Already in Rasheed:** nothing.
- **Owned but not added:** nothing.
- **Missing:** the entire category — this is also the category most likely to require an
  actual purchase/license (reference books, unlike most regulator publications, are
  typically not free to redistribute).
- **Recommended priority:** Low — nice-to-have depth, not a near-term gap.

---

### 19. Vendor & Third-Party Risk Management

**Contribution to Rasheed's intelligence.** Distinct from internal Risk Management (§5) —
this category grounds questions about a *third party's* control posture, an increasingly
common GRC workflow as organizations depend more on external vendors and cloud providers.

| ID | Name | Publisher | Version | Language | Region | Type | Status | Priority | Owned | Added | Processed | Searchable | AI-Enabled | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TPL-VENDOR-RISK-QUESTIONNAIRE | Vendor Risk Assessment Questionnaire | Internal | v1 | AR/EN | — | Template | Missing | Medium | No | No | No | No | No | |
| SIG-QUESTIONNAIRE | Shared Assessments SIG Questionnaire | Shared Assessments | 2024 | EN | International | Best Practice / Template | Missing | Low | No | No | No | No | No | Industry-standard vendor risk questionnaire |
| TPL-TPRM-POLICY | Third-Party Risk Management Policy Template | Internal | v1 | AR/EN | — | Template | Missing | Medium | No | No | No | No | No | |

**Capability matrix:** every source in this category is Missing — no capabilities enabled.

**Category summary**
- **Already in Rasheed:** nothing — `Vendor Management` already exists as a named
  `KnowledgeDomain` in the taxonomy (§8 of the architecture doc), but has no content behind
  it.
- **Owned but not added:** nothing.
- **Missing:** the entire category.
- **Recommended priority:** Medium — real demand, but sequenced after the categories with
  existing partial content or built-but-dormant pipelines.

---

## Coverage Summary

Coverage = weighted share of each category's sources that are Available (full weight) or
Planned (partial weight, since the content/pipeline exists but isn't live). Every number
below is derived directly from the tables above — none is an estimate independent of them.

```
International Standards            ██░░░░░░░░  ~13%   (2 of 16 sources partially available)
Saudi Regulations                   ██░░░░░░░░  ~13%   (1 of 8 sources partially available)
Saudi Laws                          █░░░░░░░░░   ~5%   (1 of 8, planned/dormant only)
Governance                          ░░░░░░░░░░    0%
Risk Management                     ██░░░░░░░░  ~17%   (Risk Register is live; methodology content is not)
Compliance                          █░░░░░░░░░  ~13%   (schema exists, empty)
Cybersecurity                       ████░░░░░░  ~43%   (3 of 7 sources partially available — the strongest category)
Internal Audit                      ░░░░░░░░░░    0%
Privacy & Data Protection           ░░░░░░░░░░    0%   (despite being marketed as supported)
AI Governance                       ░░░░░░░░░░    0%
Business Continuity                 ░░░░░░░░░░    0%
Quality Management                  ░░░░░░░░░░    0%
Policy Templates                    █░░░░░░░░░  ~11%   (the storage system is live; templates are not)
Procedures                          ░░░░░░░░░░    0%
Contract Templates                  █░░░░░░░░░   ~8%   (NDA taxonomy exists, unreachable)
Checklists                          ░░░░░░░░░░    0%
Best Practices                      ░░░░░░░░░░    0%
Reference Books                     ░░░░░░░░░░    0%
Vendor & Third-Party Risk Mgmt      ░░░░░░░░░░    0%
```

**Reading this honestly:** Cybersecurity is the only category with meaningful coverage, and
even there it's three thin samples, not complete standards. Every other category is either
empty or has a single dormant asset. This is the accurate starting line V2 builds from — not
a discouraging result, but the reason a deliberate, prioritized catalog (rather than ad hoc
content addition) is the right first V2 deliverable.

---

## V2 Roadmap

Ordered by value delivered to a working GRC professional per unit of effort — not
alphabetically, and not by category size. Two "quick wins" lead because they require no new
content acquisition, only activating what's already built (a direct continuation of
`RASHEED_GRC_PROJECT_BRIEF.md`'s own Phase 3: *"the Framework Engine in production... the
Saudi-regulation ingestion worker keeping framework knowledge current"*).

**Phase 1 — Activate what's already built (near-zero content-acquisition cost)**
1. Wire retrieval to `SA-BOE`'s existing embeddings (§3) — content and vectors already exist.
2. Schedule the regulatory-obligation classifier to populate `REG-OBLIGATIONS` (§6) — the
   pipeline is built, only deployment is missing.
3. Surface the existing `CTR-NDA` clause taxonomy (§15) to a real product surface.

**Phase 2 — Complete the core three, close the credibility gap**
4. Expand `ISO-27001`, `NCA-ECC`, `NIST-CSF` (§1/§2/§7) from representative samples to their
   full, real control sets — the highest-frequency content in daily GRC use.
5. Acquire `PDPL` (§3/§9) — the largest gap between marketed and actual capability in the
   catalog.

**Phase 3 — Saudi regulatory breadth**
6. `NCA-CCC`, `NCA-OTCC`, `SAMA-CSF`, `SAMA-BCM`, `SAMA-ITGF`, `CMA-CGR` (§2) — Rasheed's
   market-differentiating content.

**Phase 4 — Cross-framework intelligence**
7. `COBIT-2019`, `COSO-ERM`, `ISO-31000`, `ISO-37301` (§1) — already publicly marketed as
   supported with zero backing data; also unlocks real cross-framework mapping (§7 of the
   architecture doc), which needs at least two complete frameworks to be meaningful.

**Phase 5 — Internal-knowledge tooling**
8. Policy/Procedure/Contract/Checklist templates (§13–§16) — turns Rasheed from an assessment
   tool into an authoring assistant; sequenced after Phase 2–4 because templates are most
   useful once they can be checked against complete framework content.

**Phase 6 — Emerging and supporting categories**
9. AI Governance (§10), Business Continuity (§11), Vendor & Third-Party Risk (§19), Quality
   Management (§12), Best Practices (§17), Reference Books (§18) — real value, lower
   frequency than Phases 1–5.

---

## Vision

A GRC professional's first question to Rasheed is rarely "what can you do" — it's "do you
actually know NCA ECC," or "have you read the PDPL." Today, honestly, the answer for most of
what this catalog covers is no. What Rasheed has built well is everything *around* the
knowledge — the domain model, the ingestion pipeline, the retrieval design (all promoted
into V2's architecture in the companion document) — and what it has never done is the
patient, unglamorous work of actually acquiring, curating, and activating the knowledge
itself.

This catalog exists so that work stops being ad hoc. Every AI capability V2 ships —
grounded chat, gap analysis, policy generation, agent-driven missions — will only ever be as
good as what's in this document, marked Available. The roadmap above is not a technical
sequencing exercise; it's a bet on which gaps, closed first, make a working GRC professional
trust Rasheed's answer without checking it themselves. That trust, not feature count, is
what this catalog is actually building toward — and it is meant to keep growing, source by
source, category by category, toward the hundreds of entries a mature GRC knowledge base
genuinely needs, without ever losing the discipline of marking honestly what's real and what
isn't.
