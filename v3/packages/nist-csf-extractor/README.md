# nist-csf-extractor — the Reference Realization

The first `*KnowledgeExtractor` behind
[`KnowledgeExtractionPort`](../knowledge-extraction/) (ADR 0056). It turns a **Verified**
`NIST-CSF@2.0` source into a Canonical Extraction Artifact — deterministically, with **zero
runtime human decisions** and **zero invented knowledge**.

## Why NIST first

To prove the boundary is **source-independent**: NIST CSF has no "Clause" — it is
`Function → Category → Subcategory`. If the same Port produces a valid artifact here, then
for ISO (Clause), then for a KSA law (Article), the boundary is confirmed independent of
source structure. NIST is first for *that* reason, not because it is Public-Domain.

## Definition of Done (proof, not count)

- ✅ conforms to the Port (`accepts` + `extract`)
- ✅ the artifact fully satisfies the contract (`assemble_artifact` validates it)
- ✅ re-runnable → identical `content_hash`
- ✅ no human decision at runtime (pure deterministic parse)
- ✅ no invented knowledge (every entity's code appears in the source; the hierarchy is
  *read* from NIST's own identifier scheme — `GV.OC-01 ∈ GV.OC ∈ GV`)

## What it extracts

`GOVERN (GV): …` → **Function** · `• Organizational Context (GV.OC): …` → **Category** ·
`o GV.OC-01: …` → **Subcategory**. On the real document: **6 Functions · 22 Categories ·
106 Subcategories = 134 entities**, 0 unknown, 0 difficulties.

The artifact is the four-part canonical shape (`artifact · summary · entities ·
structural_relationships`): the extractor also emits **128 `contains` structural relationships** —
the parent hierarchy it *read* (Structure, not Tier-2 Semantics; those come later from the Graph
Builder).

`fitz` is imported **lazily** inside `_read_text`, so `parse_nist_csf(text)` and the whole
`extract_from_text` path are testable with no document library.

## Run

```bash
cd v3/packages/nist-csf-extractor && PYTHONPATH=../knowledge-extraction python -m pytest -q
```

The first realization of the replaceable artifact format (`JsonArtifactWriter`, ADR 0057)
lives here for now; it is source-agnostic and will move to a shared writers package when the
second extractor arrives.
