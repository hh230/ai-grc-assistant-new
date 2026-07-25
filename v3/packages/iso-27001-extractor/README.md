# iso-27001-extractor

A `*KnowledgeExtractor` behind [`KnowledgeExtractionPort`](../knowledge-extraction/). The first
**Licensed, multi-structure** source — it proves three properties beyond NIST:

1. **Native ≠ Canonical** — native `Theme` → canonical `Category`; native `Control` → `Control`.
2. **Storage ≠ Egress** — ISO is Licensed: the full control text is **stored**; every entity is
   `egress_restricted`; a downstream Egress Policy decides what a user sees.
3. **The Extractor describes reality, it does not complete it.**

## What it extracts (and what it honestly refuses to)

- **Annex A — fully**: 4 Themes → **93 Controls** (`A.5.1 … A.8.34`; the `A.` prefix disambiguates
  from clause `5.1`). Deterministic, zero invention.
- **Management Clauses (4–10) — NOT extracted.** This rendition (`rm.pdf`) puts clause numbers and
  titles in separate, out-of-order layout blocks; deterministic recovery would require heuristic
  layout guessing. The extractor records a **formal `ExtractionNote`** instead:

  ```
  subject: Management Clauses (4-10)
  status:  Partial
  reason:  rendition not structurally recoverable without heuristic layout interpretation …
  recommended_action: Acquire a higher-quality (born-digital) rendition of the same source
  ```

  This is a **Rendition-quality** matter — `Source ≠ Rendition` — *not* a Missing/Rejected Source and
  *not* Knowledge Acquisition. The Source identity is unchanged; only the physical copy is
  insufficient. Extraction never fails, invents, or waits.

## Run

```bash
cd v3/packages/iso-27001-extractor && PYTHONPATH=../knowledge-extraction python -m pytest -q
```

The integration test asserts real-document **counts only, never Licensed content**.
