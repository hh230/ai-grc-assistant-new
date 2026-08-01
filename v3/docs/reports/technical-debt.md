# V3 Technical Debt & Fail-Open Pipeline Protocol

> Subordinate to [`CANONICAL-MODEL.md`](../knowledge/CANONICAL-MODEL.md) and the Stage-2 readiness
> report. Records the owner ruling (2026-07-25): **an un-extractable source or part does not stop the
> project** — it is recorded as **Technical Debt / Pending**, and the pipeline continues.

---

## 1. Protocol — the pipeline does not stop

```
Extraction
    │
    ▼
Artifact
    ├── Success ──▶ pipeline continues (Artifact Store → Graph → Supabase → Embeddings → AI)
    └── Failure ──▶ Technical Debt (recorded, honest) ──▶ pipeline continues
```

- **Reference Guarantees ≠ Production Gate.** The Reference Guarantees prove *design* quality. A
  guarantee left unproven because of a **bad rendition** (not an architecture flaw) is **debt**, not a
  freeze. This achieves both goals at once: **quality is not compromised or hidden**, and **the project
  is not frozen by one isolated case.**
- **Fail-open for production, fail-honest for the record.** A failure is never silently dropped and
  never algorithmically "fixed" — it is *described* (an `ExtractionNote` / a debt entry) and skipped.
- **Incremental upsert — no full rebuild.** When a debt source is later resolved (e.g. a clean ECC
  rendition arrives), it flows `Extract → Upsert → Embed (that source only)`. The system is **not**
  re-run end to end.

```
117 Sources → Extraction ──(113 Success / 4-5 Pending)──▶ Artifact Store → Graph Builder
            → Supabase → Embeddings → AI
                                   … later: ECC(clean) → Extract → Upsert → Embed(ECC only)
```

---

## 2. Debt register

| Source | Debt | Status | Reason (rendition/quality, not architecture) | Resolution |
|---|---|---|---|---|
| `NCA-ECC` | `IDENTITY_FIDELITY` | Pending / **Skip** | This rendition reverses multi-digit identifier components (RTL): `1-10`→`1-01`, `12↔21` silently ambiguous — **Identity-degraded rendition** (Source stays Canonical). | Acquire clean (born-digital/LTR) rendition → Extract → Upsert → Embed(ECC only). |
| `ISO-42001` | `CANONICAL_RENDITION` | Missing | Present file is an image-only scan (§5.0). | Born-digital licensed copy → Extract → Upsert. |
| `ISO-22301` | `CANONICAL_RENDITION` | Missing | Image-only scan (§5.0). | Born-digital copy → Extract → Upsert. |
| `SAMA-RISK` | `NON_AUTHORITATIVE` | Rejected | Derived print bundle of `rulebook.sama.gov.sa` (§5.0). | Acquire the real SAMA Rulebook documents (new Source IDs). |
| `EX-POL-TRAVEL` | `LOW_VALUE_SCAN` | Rejected | Low-value scanned sample (§5.0). | None planned (dropped); OCR only if ever needed. |

**Rule:** each debt entry is honest (cause named, not hidden), the Source identity is unchanged, and
nothing is invented or heuristically repaired. The pipeline proceeds on the extractable sources.

---

## 3. Effect on the Reference Guarantees

The three ECC-tied guarantees (**#6 Variable Depth · #7 Regulatory Controls · #8 Identity Fidelity**)
remain **unproven — carried as debt `IDENTITY_FIDELITY`**, *not* a production gate. The
[Reference Guarantees baseline](stage-2-extraction-readiness.md) stays 5/8 proven; the missing three
are demonstrated the moment a clean ECC (or another identity-preserving Regulatory-Controls source)
extracts successfully, then upserted incrementally. **Design maturity is not blocked; only the formal
demonstration is deferred, and it is tracked openly.**
