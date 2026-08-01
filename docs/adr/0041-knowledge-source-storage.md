# ADR 0041 — Knowledge Source Storage

- **Status:** Proposed — draft (proposal only; not yet decided, not implemented)
- **Date:** 2026-07-16
- **CLAUDE.md pillars:** §5 (system architecture), §12 (RAG / ingestion), §19 (auditability), §20 (multi-tenancy & data residency)
- **Supersedes/relates:** 0035 (V2 — Knowledge library), 0036–0039 (V2 pipeline)

> This is a **proposal**, deliberately without an implementation. Its job is to frame the
> long-term decision about where original source documents live, and to settle whether the
> `knowledge/imports/` directory is a temporary cache or a permanent source-of-truth. A
> follow-up ADR will record the accepted decision before any code is written.

## Context

The V2 knowledge pipeline is a strict, one-directional flow, produced entirely by the
`knowledge-importer` package:

```
library/<category>/<doc>   →   imports/<id>.txt   →   chunks/<id>.json   →   embeddings/<id>.json   →   Postgres/pgvector
   (original PDF/DOCX/XLSX)     (extracted text)       (segments)             (vectors)                 (runtime query surface)
```

At the Platform Baseline commit, the reality on disk is:

- **`library/`** — the *declared* source-of-truth — is **empty** in git (only `.gitkeep`
  scaffolding). The original documents (PDF/DOCX/XLSX) exist only on the operator's machine
  and are **not version-controlled anywhere**.
- **`imports/`** (~27 MB) — the extracted plain text — is therefore the **only representation
  of the source content that exists in the repository**. Kept in the baseline.
- **`chunks/` + `embeddings/`** (~584 MB) — deterministically regenerable build cache —
  are now git-ignored (see ADR-adjacent `.gitignore` change; embeddings are placeholder
  `local-deterministic-hash-v1` vectors, rebuildable bit-for-bit).

This exposes the open question: **the true source of truth (the original binary documents)
has no defined, durable home.** `imports/` is currently standing in for it by accident, not
by design.

## Problem statement

1. **Where do original source documents live long-term** — in git, in Git LFS, or in
   tenant-scoped object storage — given they are large, binary, potentially copyrighted,
   and (for tenant uploads) sensitive?
2. **Is `imports/` a temporary cache or a permanent source-of-truth?** Today it is
   ambiguously both. The pipeline treats it as derived (regenerable from `library/`), yet the
   repository treats it as source (nothing else survives a fresh clone).

## Options (to be evaluated in the deciding ADR)

- **A — Commit original documents to git.** Simple, self-contained; but bloats history
  permanently with large binaries, and cannot hold tenant-private or license-restricted
  documents. Rejected as the general solution; acceptable only for small, redistributable
  reference standards.
- **B — Git LFS for shared reference documents.** Keeps the repo lean while versioning the
  canonical public/reference corpus (ISO, NIST, COBIT, public Saudi regulations). Good for
  the shared library; still unsuitable for tenant-private data.
- **C — Tenant-scoped object storage (recommended direction).** Original documents live in
  an object store (e.g. S3-compatible), keyed by `tenant_id` + document id, with region-aware
  buckets for data residency (§20). The `manifests/` records the pointer, hash, version, and
  provenance; the pipeline fetches on demand. This is the only option that satisfies
  multi-tenancy, residency, and license constraints simultaneously.
- **D — Hybrid (likely outcome):** shared **reference** corpus in Git LFS (option B) for
  reproducible platform builds; **tenant** documents in object storage (option C). The
  Framework/knowledge library is public and reproducible; customer evidence is isolated and
  residency-bound.

## Proposed position on `imports/`

Declare `imports/` **derived and temporary — a rebuildable cache, not source-of-truth** —
*once* a durable home for original documents exists (option C/D). Until then, it is retained
in version control as a **stopgap** because it is the only surviving copy of the source text.
The deciding ADR should:

1. Establish the durable document store (C/D) and make `manifests/` the authoritative,
   version-controlled **index/provenance** record (source URI, content hash, version,
   ingested-at) — small, auditable, tenant-scoped.
2. Once (1) exists, add `v2/knowledge/imports/` to `.gitignore` alongside `chunks/` and
   `embeddings/`, so the entire `imports → chunks → embeddings` chain becomes pure cache and
   the repo carries only code + manifests.
3. Guarantee a **rebuild path**: `manifests/` + the document store must be sufficient to
   regenerate `imports → chunks → embeddings → Postgres` end-to-end with no manual step.

## Consequences

- **Positive:** repository stays code-sized; original documents get a residency-aware,
  tenant-isolated, auditable home; the full pipeline becomes reproducible from
  `manifests/` + object store; license/privacy exposure from committing raw documents is
  eliminated.
- **Negative / cost:** requires standing up object storage, a fetch/caching layer in
  `knowledge-importer`, and manifest provenance fields; a fresh clone can no longer run
  retrieval offline without first hydrating the document store.
- **Until decided:** `imports/` stays committed and is treated as source-of-truth by
  necessity; `chunks/` and `embeddings/` remain git-ignored regenerable cache.

## Not in scope for this proposal

Implementation, schema, bucket layout, connector interfaces, and migration of the existing
local documents — all deferred to the deciding ADR and its follow-up work. No code changes
accompany this proposal beyond the `.gitignore` exclusion of `chunks/` and `embeddings/`.
