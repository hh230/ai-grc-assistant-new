"""The read-model port — the single seam the API layer reads the Knowledge view through.

Four methods, all tenant-scoped:

- **`record`** projects a Document into the read model (upsert by `document_id`). This is the
  **Document Projection** step of `Upload → Ingestion → Document Projection → Evidence Collection`
  (S4 Design rule 2): the product layer calls it *after* `knowledge-runtime` has ingested the file.
  It is idempotent — recording the same `document_id` again updates the row (e.g. `ingesting →
  ready`), never duplicates it.
- **`get`** returns one document's projection, scoped to the caller's tenant (fail-closed).
- **`list_documents`** answers the Knowledge query for *one tenant only*, optionally narrowed to a
  single `evidence_kind` (opening a collection). Newest-first.
- **`list_collections`** returns the tenant's **Evidence Collections** (each `evidence_kind` + its
  count), in the product's display order — the overview the Knowledge view lists first.

Tenant isolation is **fail-closed by construction** (ADR 0040 §5): the caller's `TenantContext` is
the only tenant whose rows can be returned — no parameter can widen the scope, so another tenant's
documents (or collections) cannot appear even by mistake.

CQRS read side: this port never ingests or mutates evidence content. `knowledge-runtime` owns
ingestion; this is a product projection built beside it (Domain-Model §3 read-model gap).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pipeline_contracts import TenantContext

from document_read_model.models import DocumentItem, EvidenceCollection


@runtime_checkable
class DocumentReadModel(Protocol):
    """The Knowledge read seam. An in-memory adapter backs tests and local runs; a Postgres adapter
    backs deployment — both implement exactly this, so the API layer never changes."""

    def record(self, item: DocumentItem) -> None:
        """Project one Document (idempotent upsert by `document_id`). Called after ingestion."""
        ...

    def get(self, document_id: str, tenant: TenantContext) -> DocumentItem | None:
        """One document's projection, scoped to the caller's tenant — or `None` if absent or owned
        by another tenant (fail-closed)."""
        ...

    def list_documents(
        self,
        tenant: TenantContext,
        *,
        evidence_kind: str | None = None,
    ) -> tuple[DocumentItem, ...]:
        """This tenant's documents, newest first, optionally narrowed to one `evidence_kind` (the
        contents of one Evidence Collection). Never returns another tenant's rows."""
        ...

    def list_collections(self, tenant: TenantContext) -> tuple[EvidenceCollection, ...]:
        """This tenant's Evidence Collections — each `evidence_kind` present plus its document count
        — in the product's display order (`KIND_ORDER`, unknown kinds last). Empty when the tenant
        has no documents. Never counts another tenant's documents."""
        ...
