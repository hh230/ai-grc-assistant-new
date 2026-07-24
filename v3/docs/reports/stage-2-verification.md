# Stage 2 — Source Verification Report

> **Subordinate log to [`CANONICAL-MODEL.md`](../knowledge/CANONICAL-MODEL.md) v1.3.** This report explains *why* the
> Canonical Manifest changed to v1.3; the manifest (§5.0) is the single source of truth. Read-only
> verification — **no** extraction, chunking, entities, relationships, embeddings, Supabase, DB, or file changes.

> **Post-report decisions (2026-07-24).** The raw verification states below (3 OCR, 1 "Needs Decomposition") were refined in the manifest into the **6-state Source Status model**: `SAMA` print-dump → **Rejected Source** (derived bundle); `ISO 42001`/`ISO 22301` scans → **Missing Canonical Source** (IDs retained; canonical copies via Knowledge Acquisition); `Annex-8` → **Rejected**. `CANONICAL-MODEL.md` §5.0 holds the authoritative states.

## Verdict
Every source has a **resolved** state · **Unknown = 0** · **Blocked = 0**. Stage-2 exit = every source Canonical (`Ready`) or documented-absence (`Missing`/`Rejected`). Stage 2 stays **managed-open** (Knowledge Acquisition) until Missing/Rejected are replaced — it does **not** halt waiting for a human.

## Method
PyMuPDF/`fitz` 1.26.5 structural inspection — font dictionaries, image objects, encryption & openability — cross-checked with `pypdf`. **Scanned** detected as *image objects + zero fonts* (no page text read). **Identity** = first-page heading only, for 4 opaque files. No poppler/qpdf/OCR CLI tools present. **Extraction must use `fitz`**: `pypdf` in this environment fails on 5 files (3 AES-encrypted need the `cryptography` lib; `ISO 27005`/`ISO 27017` trip its strict parser); `fitz` reads all.

## State counts (117 sources)
| State | Count |
|---|--:|
| ✅ Ready | 109 |
| 🔍 OCR Required | 3 |
| ✂️ Needs Decomposition | 1 |
| ⚠ ID Identity Correction Required | 4 |
| ⛔ Blocked | 0 |
| **Unknown** | **0** |

## 🔍 OCR Required (3)
| Source | Pages | Evidence | Handling |
|---|--:|---|---|
| `ISO-42001` (SCAN-…-Web) | 61 | 16/16 sampled pages image-only, 0 fonts | OCR text layer, or obtain born-digital licensed copy |
| **`ISO-22301`** (…2019-2) | 29 | 16/16 image-only, ~700 KB/page — **newly found scan** | same |
| `EX-POL-TRAVEL` (Annex-8) | 34 | 16/16 image-only | OCR, or drop (low-value sample) |

## ✂️ Needs Decomposition (1)
`SAMA-RISK` (`Print Manager.pdf`, 1,281p) — generic print-to-PDF bundle. Split into constituent Sources, assign each a Canonical ID, then re-verify each part.

## ⚠ Identity Correction Required (4) — verified via first-page peek
| File | Was | Actually is | Corrected registration |
|---|---|---|---|
| `ISO 37300.pdf` | `ISO-37300` | TÜV guidance leaflet *about* ISO 37301 (not a standard) | `REF-TUV-ISO37301-GUIDE` · Reference · Unknown-license |
| `مدقق.pdf` | `OCEG-ASSESS-AR` | OCEG GRC Assessment Framework (Burgundy) v3.5.1 **Arabic** | `OCEG-BB@3.5.1` AR · `translates` EN |
| `Booklet_13.pdf` | `REF-GOV-BOOKLET13` | CMA **Corporate Governance** guide | `CMA-CG-GUIDE` · `relates_to CMA-CGR` |
| `64355_riskapp…` | `REF-RSK-APPETITE` | 'Risk Appetite & Tolerance' Guidance Paper | `REF-RSK-APPETITE` · Reference · RSK |

## Encryption (resolved — 0 blockers)
11 files are encrypted; **all open with an empty/owner password** (verified `fitz` **and** `pypdf`). None require a real user password. They are **not** blockers — extract with `fitz`.

- 🔓 `GRC/King IV/IoDSA_King_IV_Report_-_WebVersion.pdf`
- 🔓 `GRC/Three Lines Model/tlm_assurance_advice_support_effective_gov_en.pdf`
- 🔓 `Governance/Corporate Governance/IoDSA_King_IV_Report_-_WebVersion.pdf`
- 🔓 `ISO/ISO 31000/ISO 31000.pdf`
- 🔓 `ISO/ISO 37001/ISO 37001.pdf`
- 🔓 `ISO/ISO 37301/ISO-37301-2021.pdf`
- 🔓 `ISO/ISO 9001/ISO 9001.pdf`
- 🔓 `Internal Audit/Global Internal Audit Standards 2024/globalinternalauditstandards_2024january9.pdf`
- 🔓 `Internal Audit/Global Internal Audit Standards 2024/globalinternalauditstandards_2024january9_printable-2.pdf`
- 🔓 `OCEG/GRC Assessment Framework/GRC Assessment Framework v3.5.1-protected.pdf`
- 🔓 `OCEG/GRC Assessment Framework/مدقق.pdf`

## Watchlist — Ready, but a few image-only pages (spot-check at extraction)
- 1/10 image-only sampled · `Contract Templates/Non-Disclosure Agreement Form.pdf`
- 1/9 image-only sampled · `Contract Templates/Non-Disclosure+Agreement.pdf`
- 2/16 image-only sampled · `Corporate Policies/Code_of_Conduct_-_English_final2.pdf`
- 2/16 image-only sampled · `Governance/Digital Government/publication.pdf`

## ⛔ Blocked / files preventing Stage 3
**None.** `Blocked = 0`. No source prevents progress; the 4 non-Ready need one preprocessing step each (OCR ×3, decomposition ×1) before extraction, handled in the Stage-2 Preprocessing Addendum.

## Full classification — all 117 sources
### CMA (2)
- ✅ قواعد الإدراج.pdf  (89p)
- ✅ لوائح الحوكمة.pdf  (65p)

### COBIT (1)
- ✅ COBIT 2019/    COBIT 2019 Framework.pdf  (302p)

### COSO (2)
- ✅  COSO ERM/ERM - COSO Application Techniques.pdf  (113p)
- ✅ Internal Control/    Internal Control Framework.pdf  (194p)

### Compliance (6)
- ✅     Corporate Compliance.pdf  (51p)
- ✅ A Guide for Developing and Implementing a Corporate Compliance Program - FR.pdf  (13p)
- ✅ Eisai-Compliance-Handbook-7th-edition-English-version.pdf  (66p)
- ✅ Ethics-and-Compliance-Handbook.pdf  (56p)
- ✅ HHS-OIG-GCPG-2023.pdf  (91p)
- ✅ cms.pdf  (19p)

### Contract Templates (19)
- ✅ 489_Fecc Model Distribution Contract -_2022.pdf  (31p)
- ✅ Annex 2 Sample Partnership Agreement innovative partnerships_05_12_2022 (1).pdf  (20p)
- ✅ Attachment 2 - Master Service Agreement Template.pdf  (19p)
- ✅ Basic-Non-Disclosure-Agreement.pdf  (2p)
- ✅ CONTRACT_OF_AGENCY_SELF_NOTES.pdf  (12p)
- ✅ Commercial-agency-models.pdf  (2p)
- ✅ Distribution Agreement.pdf  (10p)
- ✅ Franchise Agreement - Retail.pdf  (87p)
- ✅ KSA_labourlaw_annex38.pdf  (31p)
- ✅ LABOR LAW.pdf  (93p)
- ✅ Non-Disclosure Agreement Form.pdf  (10p)
- ✅ Non-Disclosure+Agreement.pdf  (9p)
- ✅ doc_4.pdf  (12p)
- ✅ enable-shareholders-agreement-redacted.pdf  (62p)
- ✅ masterassurences.pdf  (19p)
- ✅ mlh-saas-agreement.pdf  (28p)
- ✅ shareholderagreement.pdf  (12p)
- ✅ vendor-services-agreement-ksa.pdf  (7p)
- ✅ نموذج-عقد-SaaS.docx  (docx)

### Corporate Policies (12)
- ✅ APPROVED-Procurement-Policy.pdf  (15p)
- 🔍 Annex-8-Travel-Policy.pdf  (34p)
- ✅ COMARCH ICT - BEST PRACTICES FOR EFFECTIVE & EFFICIENT VENDOR MANAGEMENT.pdf  (30p)
- ✅ Code-of-Conduct-English-2.pdf  (56p)
- ✅ Code_of_Conduct_-_English_final2.pdf  (60p)
- ✅ Data-Privacy-Policy-.pdf  (21p)
- ✅ HR Policy Manual 2023 (8).pdf  (208p)
- ✅ PrivacyPolicyGuideline.pdf  (18p)
- ✅ Travel-and-Tourism-Services-Regulations-En-V012.pdf  (26p)
- ✅ Whistle Blowing.pdf  (9p)
- ✅ acsom1102pdf-56448.pdf  (12p)
- ✅ information_security_policy_0.pdf  (18p)

### GRC (4)
- ✅ Basel Operational Risk/bcbs195.pdf  (27p)
- ✅ 🔓 King IV/IoDSA_King_IV_Report_-_WebVersion.pdf  (128p)
- ✅ OECD Governance Principles/ed750b30-en.pdf  (53p)
- ✅ 🔓 Three Lines Model/tlm_assurance_advice_support_effective_gov_en.pdf  (26p)

### Governance (6)
- ✅ Corporate Governance/CorporateGovernanceRegulations1.pdf  (61p)
- ✅ 🔓 Corporate Governance/IoDSA_King_IV_Report_-_WebVersion.pdf  (128p)
- ✅ Digital Government/publication.pdf  (16p)
- ✅ Digital Government/نسخة من publication.pdf  (20p)
- ⚠ ID Governance Guides/Booklet_13.pdf  (16p)
- ✅ IT Governance/ed750b30-en.pdf  (53p)

### ISO (11)
- 🔍 ISO 22301/ISO-22301-2019-2.pdf  (29p)
- ✅ ISO 27001/ISO 27001-2022 rm.pdf  (26p)
- ✅ ISO 27002/ISO 27002.pdf  (164p)
- ✅ ISO 27005/ISO IEC 27005-2018.pdf  (60p)
- ✅ ISO 27017 (Cloud Security)/ISO IEC 27017-2015.pdf  (44p)
- ✅ 🔓 ISO 31000/ISO 31000.pdf  (26p)
- ✅ 🔓 ISO 37001/ISO 37001.pdf  (54p)
- ⚠ ID ISO 37300/ISO 37300.pdf  (4p)
- ✅ 🔓 ISO 37301/ISO-37301-2021.pdf  (15p)
- 🔍 ISO 42001/SCAN-ISO-420012023_-Web.pdf  (61p)
- ✅ 🔓 ISO 9001/ISO 9001.pdf  (40p)

### Internal Audit (3)
- ✅ Global Internal Audit Standards 2024/global-internal-audit-standards-arabic.pdf  (106p)
- ✅ 🔓 Global Internal Audit Standards 2024/globalinternalauditstandards_2024january9.pdf  (120p)
- ✅ 🔓 Global Internal Audit Standards 2024/globalinternalauditstandards_2024january9_printable-2.pdf  (120p)

### Laws (20)
- ✅ اللائحة التنفيذية لنظام الأسماء التجارية.pdf  (10p)
- ✅ اللائحة التنفيذية لنظام السجل التجاري.pdf  (11p)
- ✅ أنظمة جرائم الوظيفة العامة والأموال.pdf  (375p)
- ✅ قائمة الامتثال للمتاجر الإلكترونية.pdf  (1p)
- ✅ نظام الاستثمار ولائحته التنفيذية.pdf  (57p)
- ✅ نظام الأسماء التجارية.pdf  (8p)
- ✅ نظام الإثبات مع الفهارس.pdf  (119p)
- ✅ نظام الإفلاس ولوائحه وقواعده.pdf  (374p)
- ✅ نظام التجارة الالكترونية.pdf  (10p)
- ✅ نظام السجل التجاري.pdf  (10p)
- ✅ نظام السوق المالية.pdf  (44p)
- ✅ نظام الشركات ولوائحه التنفيذية.pdf  (210p)
- ✅ نظام العمل ولوائحه التنفيذية.pdf  (134p)
- ✅ نظام المرافعات الشرعية ولوائحه التنفيذية مع الفهارس.pdf  (164p)
- ✅ نظام المعاملات المدنية مع الفهارس.pdf  (218p)
- ✅ نظام المنافسة ولائحته التنفيذية.pdf  (55p)
- ✅ نظام حماية البيانات الشخصية.pdf  (16p)
- ✅ نظام مكافحة التستر ولوائحه التنفيذية.pdf  (44p)
- ✅ نظام مكافحة غسل الأموال.pdf  (21p)
- ✅ ‎⁨عقد التأسيس شركة دليل الامتياز للمحاماة والاستشارات القانونية⁩.pdf  (13p)

### NIST (9)
- ✅ AI RMF Playbook/NIST.CSWP.40.ipd.pdf  (51p)
- ✅ NIST AI RMF/NIST.AI.600-1.pdf  (64p)
- ✅ NIST CSF/    Cybersecurity Framework.pdf  (32p)
- ✅ NIST CSWP/NIST.CSWP.40.ipd.pdf  (51p)
- ✅ NIST Privacy Framework/NIST.CSWP.40.ipd.pdf  (51p)
- ✅ NIST SP 800-171/NIST.SP.800-171r2.pdf  (114p)
- ✅ NIST SP 800-37/NIST.SP.800-37r2.pdf  (183p)
- ✅ NIST SP 800-53/NIST.SP.800-53r5.pdf  (492p)
- ✅ NIST SP 800-61/NIST.SP.800-61r2.pdf  (80p)

### OCEG (3)
- ✅ 🔓 GRC Assessment Framework/GRC Assessment Framework v3.5.1-protected.pdf  (165p)
- ⚠ ID 🔓 GRC Assessment Framework/مدقق.pdf  (144p)
- ✅ GRC Capability Model/GRC Capability Model v3.5-AR-revision-2024-11-20.pdf  (135p)

### Risk Management (6)
- ⚠ ID 64355_riskapp_a4_web.pdf  (42p)
- ✅ Enterprise Risk Management. A guide for EBMO's.pdf  (57p)
- ✅ ISO-31000.pdf  (24p)
- ✅ Risk Management Concepts and Guidance 5ed [2015].pdf  (466p)
- ✅ RiskRegisterDevelopmentandImplementation.docx17.pdf  (19p)
- ✅ The_Use_of_Bow_Tie_Analysis_to_Risk_Identification.pdf  (8p)

### SDAIA (3)
- ✅ Compliance Guide/دليل امتثال أصحاب العمل.pdf  (130p)
- ✅ Data Transfer/    أدلة نقل البيانات.pdf  (28p)
- ✅ PDPL/    أدلة PDPL.pdf  (25p)

### Saudi Regulations (10)
- ✅ NCA CCC/ccc-en.pdf  (48p)
- ✅ NCA CSCC/CSCC_Assessment_and_Compliance_Tool_v2.0.xlsx  (xlsx)
- ✅ NCA CSCC/cscc-ar.pdf  (32p)
- ✅ NCA DCC/Data-Cybersecurity-Controls-.pdf  (28p)
- ✅ NCA ECC/ECC-2-2024---NCA.pdf  (40p)
- ✅ NCA OTCC/OTCC-1-2022-Assessment-and-Compliance-Tool.xlsx  (xlsx)
- ✅ NCA OTCC/Operational-Technology-Cybersecurity-Controls-Methodogy-and-Mapping-Annex.pdf  (32p)
- ✅ NCA OTCC/otcc_en.pdf  (45p)
- ✅ SAMA Cybersecurity Framework/SAMA_EN_5888_VER1.pdf  (56p)
- ✂️ SAMA Risk Management/Print Manager.pdf  (1281p)

## Exit status
- **Unknown: 0** ✅  · **Blocked: 0** ✅
- Not yet all-Ready: 3 OCR + 1 decomposition remain → **Stage-2 Preprocessing Addendum** must complete before Stage 2 closes and extraction begins.
- Manifest reconciled to **v1.3** (`CANONICAL-MODEL.md` §5.0). This log is the rationale.
