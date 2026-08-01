# artifact-writers — the replaceable artifact FORMAT (ADR 0057)

Realizations of `ArtifactWriter` (the Port boundary). **Source-agnostic** and shared by every
`*KnowledgeExtractor`. Split out of the NIST package the moment a **second** extractor (ISO) arrived,
so no extractor owns the format.

- **`JsonArtifactWriter`** — the first realization. Writes the four-part canonical artifact
  (`artifact · summary · entities · structural_relationships` + `warnings`) as append-only JSON under
  `v3/knowledge/entities/<SOURCE_ID>@<version>.json`. Swappable for Postgres/Parquet/SQLite **without
  touching the Port or any extractor** — that is the whole point of ADR 0057.

**Storage ≠ Egress:** the writer persists the **complete** artifact, including full `description` for
Licensed sources; what a user is shown is the downstream **Egress Policy**'s concern, never the
writer's.

```bash
cd v3/packages/artifact-writers && PYTHONPATH=../knowledge-extraction python -m pytest -q
```
