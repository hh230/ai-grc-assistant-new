# Knowledge Library (V2) — directory scaffold

**Scaffold only.** This tree holds no data, code, or documents yet — it is the folder
structure the [Knowledge Library architecture](../docs/architecture/knowledge-library.md)
and [Knowledge Catalog](../docs/knowledge-catalog.md) will be populated into, one source at a
time, per that catalog's roadmap. No importing, parsing, chunking, embedding, or RAG logic
exists yet — this is deliberately structure before content, and content before code.

V2-only: nothing here is read by, or affects, the production (V1) application.

## Layout

```
knowledge/
├── library/        # the source-of-truth documents, one folder per knowledge category
├── imports/         # raw intake — files as fetched/uploaded, before any processing
├── chunks/          # parsed, structure-aware segments of a library document (§6 of the
│                     # architecture doc) — populated once ingestion is implemented
├── embeddings/       # vector representations of chunks — populated once embedding
│                     # generation is implemented
└── manifests/        # per-source ingestion manifests (what was fetched, when, what
                       # version/hash) — the audit trail for what's in library/
```

`imports/` → `chunks/` → `embeddings/` mirrors the ingestion pipeline's own stages
(intake → segment → embed) described in the architecture document — each directory is where
that stage's output will eventually land, kept separate so a re-embedding or re-chunking run
never has to touch the original imported source.

## `library/` categories

Folder names are lowercase-kebab-case, matching this repository's existing convention for
data directories (`/frameworks`, `/ontology`, `/knowledge-catalog`, `/regulatory-sources`,
`/trusted-sources`). Mapping to the Knowledge Catalog's own category names:

| Folder | Catalog category |
|---|---|
| `iso/` | International Standards — ISO family (ISO-27001, ISO-31000, ...) |
| `nist/` | International Standards — NIST family (NIST-CSF, NIST-AI-RMF, ...) |
| `saudi-regulations/` | Saudi Regulations (NCA-ECC, NCA-CCC, NCA-OTCC, SAMA-*, ...) |
| `governance/` | Governance |
| `compliance/` | Compliance |
| `risk-management/` | Risk Management |
| `internal-audit/` | Internal Audit |
| `cobit/` | International Standards — COBIT |
| `coso/` | International Standards — COSO (ERM and Internal Control) |
| `oceg/` | Reference Books — OCEG GRC Capability Model |
| `sdaia/` | AI Governance — SDAIA AI Ethics Principles |
| `cma/` | Saudi Regulations — CMA |
| `corporate-policies/` | Policy Templates (and, later, tenant-authored policies promoted for reuse) |
| `contract-templates/` | Contract Templates |

Categories not yet given their own `library/` subfolder (Cybersecurity, Privacy & Data
Protection, Business Continuity, Quality Management, Procedures, Checklists, Best Practices,
Vendor & Third-Party Risk Management — see the Knowledge Catalog) will get one when the first
source in that category is actually added, rather than pre-creating empty folders for
categories with no near-term content — this list grows with the catalog's roadmap, not ahead
of it.

## Adding a source (once ingestion is built — not yet)

A new source will land in `library/<category>/<knowledge-id>/`, get a manifest in
`manifests/`, and only then flow through `imports/` → `chunks/` → `embeddings/` — the
Knowledge Catalog's `Status` column is what tracks a source's progress through that flow. No
step in that pipeline is implemented today; this directory exists so the structure is ready
before that work starts.
