# document-read-model

The product-side **read model behind the Knowledge view** (Domain-Model §3 gap; V1 Execution Slice
**S4**). It answers one question — *"what evidence do we have?"* — for one tenant, fail-closed.

## Why it exists

The frozen Core stores **no Document**. `knowledge-runtime` ingests an uploaded file into retrievable,
tenant-scoped **chunks** — but nothing records that *"a document exists, of this evidence kind, with this
ingestion status."* That record is a §3 gap. This package fills it as a **CQRS read model** (the same
pattern as `mission-read-model`): a projection written *after* ingestion, read by the Knowledge view. It
writes no chunks and exposes no chunk / embedding / pgvector detail.

## The two product rules it encodes

1. **Knowledge = Evidence Collections, not a File Manager.** The unit is the **collection**, not the file.
   `list_collections` returns each `evidence_kind` present plus its `count`, in the product's display order
   (`KIND_ORDER`) — the overview the view lists first (`Policies (12)`). Opening one calls
   `list_documents(..., evidence_kind=…)`.
2. **Upload is an event; a Document is an entity.** `record` is the **Document Projection** step of
   `Upload → Ingestion → Document Projection → Evidence Collection`. `status` (`ingesting·ready·failed`)
   models the *ingestion lifecycle of a Document*, so a re-record advances it (`ingesting → ready`) by
   idempotent upsert on `document_id` — never a second row.

`evidence_kind` (not `*_type`: "type" is overloaded) and `size` are first-class Document fields
(REST_API_CONTRACT_V1 §2, S4 footnote).

## Surface

- `DocumentItem` · `EvidenceCollection` — the read-side data the view renders.
- `EvidenceKind` · `DocumentStatus` · `KIND_ORDER` · `is_known_kind` — the product vocabulary.
- `DocumentReadModel` — the port (`record` · `get` · `list_documents` · `list_collections`), all
  tenant-scoped, fail-closed.
- `InMemoryDocumentReadModel` — driver-free adapter (tests / local).
- `PostgresDocumentReadModel` — durable adapter (same port; lazy psycopg, loaded only on instantiation).
- `create_table_sql` — the read-model table DDL (ADR 0053).

## Test

```bash
uv run pytest
```

Postgres-adapter integration auto-skips unless `DOCUMENT_READ_MODEL_TEST_DSN` points at a reachable
database; the in-memory acceptance suite is the executable S4 spec the Postgres adapter must match.
