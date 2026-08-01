"""Document Read Model — the read model behind the Knowledge view (Domain-Model §3; S4).

The Knowledge view asks one question: *"what evidence do we have?"* The frozen Core stores **no**
Document at all — `knowledge-runtime` ingests a file into retrievable **chunks**, but nothing
records that "a document exists, of this evidence kind, with this ingestion status". This package
fills that gap as a **CQRS read model**: a tenant-scoped, fail-closed projection of Documents that
also groups them into **Evidence Collections** (by `evidence_kind`) — the unit the product is built
around (S4 Design rule 1). It writes no chunks; ingestion stays `knowledge-runtime`'s job, behind
the projection (Design rule 2: *Upload → Ingestion → Document Projection → Evidence Collection*).

Public surface:
- `DocumentItem` / `EvidenceCollection` — the read-side data the Knowledge view renders.
- `EvidenceKind` / `DocumentStatus` / `KIND_ORDER` / `is_known_kind` — the product vocabulary.
- `DocumentReadModel` — the port the API reads through.
- `InMemoryDocumentReadModel` — the driver-free adapter (tests / local).
- `PostgresDocumentReadModel` — the durable adapter (deployment), same port; import triggers a lazy
  psycopg load only when instantiated.
- `create_table_sql` — the read-model table DDL (ADR 0053).
"""

from __future__ import annotations

from document_read_model.kinds import (
    KIND_ORDER,
    DocumentStatus,
    EvidenceKind,
    is_known_kind,
)
from document_read_model.memory import InMemoryDocumentReadModel
from document_read_model.models import DocumentItem, EvidenceCollection
from document_read_model.ports import DocumentReadModel
from document_read_model.postgres import PostgresDocumentReadModel
from document_read_model.schema import DEFAULT_TABLE, create_table_sql

__all__ = [
    "DEFAULT_TABLE",
    "KIND_ORDER",
    "DocumentItem",
    "DocumentReadModel",
    "DocumentStatus",
    "EvidenceCollection",
    "EvidenceKind",
    "InMemoryDocumentReadModel",
    "PostgresDocumentReadModel",
    "create_table_sql",
    "is_known_kind",
]
