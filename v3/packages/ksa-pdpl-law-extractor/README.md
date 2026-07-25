# ksa-pdpl-law-extractor

The first **Arabic** `*KnowledgeExtractor` behind [`KnowledgeExtractionPort`](../knowledge-extraction/).
It proves:

1. **Language does not change the Port** — an Arabic source flows through the *same* boundary and
   yields a contract-conforming artifact, with **no exception in the Port**.
2. **Canonical type follows legal FUNCTION, not node name** — every numbered sub-item is natively a
   `Provision`, but maps to canonical **`Definition`** *or* **`Requirement`** by what it does. A
   structural **definitions detector** (items shaped `term: meaning`) decides — **never** the article
   number (some laws start definitions at Article 2 or 3).
3. **The Extractor describes reality — including when it's fine.** It would record a content-fidelity
   `ExtractionNote` if the body were degraded; for this rendition, content was verified clean (0
   reversed spans across all entities), so it attaches **none** — it invents no problem.

## What it extracts

`Article → Provision` (contract §6.1). Articles numbered by **document order** (Nth header = Article N
— no ordinal table). On the real document: **43 articles**, **19 definitions** (Article 1), the rest
Provisions → **137 Requirement + 19 Definition = 156 entities**, 113 `contains` edges. PDPL is
Public-Domain, so `egress_restricted=false`.

- **NFKC** normalization is a **STEP** applied on read (`PROTO-EXT-1`), recorded in
  `summary.normalization` — never business logic.
- `fitz` is imported lazily, so `parse_pdpl(text)` is testable without a document library.

```bash
cd v3/packages/ksa-pdpl-law-extractor && PYTHONPATH=../knowledge-extraction python -m pytest -q
```
