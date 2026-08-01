# knowledge-extraction — the Stage-2 boundary (Port)

Rasheed **V3**'s first code package. It is the **boundary** of Stage-2 extraction, per
[ADR 0056](../../../docs/adr/0056-v3-knowledge-extraction-port.md) and
[ADR 0057](../../../docs/adr/0057-v3-extraction-output-artifact.md), conforming to
[CANONICAL-MODEL.md](../../docs/knowledge/CANONICAL-MODEL.md) v1.3.

## What this is (and is not)

- **The Port** — `KnowledgeExtractionPort` — speaks only `Source → CanonicalExtractionArtifact`.
- It is **format- and tooling-agnostic**: it knows nothing of PDF/DOCX/XLSX, `fitz`, or `openpyxl`.
  It is **pure stdlib with zero dependencies** — it *cannot* import a document library because it
  does not depend on one. That is enforced by a test.
- Every source family is a **`*KnowledgeExtractor`** realization *behind* this Port
  (`IsoKnowledgeExtractor`, `NistCsfKnowledgeExtractor`, `KsaLawKnowledgeExtractor`, …), living in
  its own package. **They are built *after* this boundary — never before it.**
- **Single responsibility:** an extractor turns a **Verified** source into an artifact —
  `accepts(source) → extract(source) → Artifact`. It **never** re-validates OCR/encryption/missing/
  rejected; verification is terminal (PROTO-EXT-3). The Port asserts `state == "Ready"`.

## The shape it guarantees

- `CanonicalExtractionArtifact` = `ArtifactIdentity` + `ExtractionManifest` + `KnowledgeEntity[]`.
- **`ArtifactIdentity`** (distinct from entity provenance) carries `artifact_id`, the four version
  axes (`source`/`extractor`/`protocol`/`contract`), a reproducibility `content_hash`, and a
  metadata-only `generated_at` (excluded from the hash and id). A future diff is therefore
  **attributable** to *document changed* vs *extractor evolved*.
- **`KnowledgeEntity`** = the 14 ratified fields + the retained `native_node_type` — the source's own
  node name (ADR 0056 guarantee 7): canonical `Requirement` ↔ native `Clause`; `Control` ↔
  `Enhancement`. `egress_restricted` is derived from `license` (§10.6).
- `assemble_artifact(...)` is the single factory all realizations return through, so guarantees
  (identity spine §2.2, inherited facets §3, valid §3.5 types, reproducible hashing) are enforced
  **at the boundary**, not per-extractor. It fails loud (§16).
- **Format is replaceable** (`ArtifactWriter`): JSON is only the first writer; swappable for
  Postgres/Parquet/SQLite without touching the Port or any extractor.

## Test

```bash
cd v3/packages/knowledge-extraction && python3 -m pytest -q
```

## Position in the V3 boundary chain

```
Source → KnowledgeExtractionPort → Canonical Extraction Artifact
  → Knowledge Graph Builder → Knowledge Graph → Embeddings → AI
```

Boundaries, not implementations.
