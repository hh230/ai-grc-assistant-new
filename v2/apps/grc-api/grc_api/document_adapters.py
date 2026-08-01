"""The document **write side** — Upload → Ingestion → Document Projection (S4 Design rule 2).

`GET /v1/documents` reads the `document-read-model` projection directly (a query needs no service,
as S1's list did). The **upload** is the write path, and it is deliberately expressed as the three
distinct steps the contract names, even though S4 runs them in one synchronous call:

    Upload (bytes + evidence_kind)  →  Ingestion (knowledge-runtime chunks the text)
                                    →  Document Projection (record a DocumentItem)

This service is a **composition adapter** — the same role `result_adapters.py` plays for
deliverables: it wires two frozen packages together (`knowledge-runtime` ingestion +
`document-read-model` projection) and owns no business rule of its own. Chunking, tenant-scoping of
chunks, and citability all live inside the frozen `knowledge-runtime`; the projection is a single
`record`. Keeping the seam here (not fused into the read model) is what preserves CQRS: the read
model writes no chunks, and a future re-index / new-version / OCR event is a new call against this
write side, not a schema change.

`status` is honest: a Document whose ingestion produced **no retrievable chunks** (an empty or
unreadable upload), or whose ingestion raised, is projected `failed` — not silently `ready`.

*Scope note (S4): ingestion decodes the upload as text (`.txt`/`.md`/`.csv`). Binary extraction
(PDF/DOCX via the `knowledge-importer` parsers) is a follow-up — it slots in at `_extract_text`
without touching the projection, the endpoint, or the view.*
"""

from __future__ import annotations

import time
from collections.abc import Callable
from uuid import uuid4

from document_read_model import DocumentItem, DocumentReadModel, DocumentStatus
from knowledge_runtime import TenantKnowledgeBase, ingest_document
from pipeline_contracts import TenantContext


def _extract_text(data: bytes) -> str:
    """Turn uploaded bytes into text for ingestion. Text formats decode directly; `errors='replace'`
    keeps a stray byte from failing the upload. Binary parsers (PDF/DOCX) slot in here later."""
    return data.decode("utf-8", errors="replace")


class DocumentIngestionService:
    """Ingest an uploaded document and project it — the seam behind `POST /v1/documents`."""

    def __init__(
        self,
        knowledge_base: TenantKnowledgeBase,
        read_model: DocumentReadModel,
        *,
        clock: Callable[[], float] = time.time,
        new_id: Callable[[], str] = lambda: f"doc_{uuid4().hex}",
    ) -> None:
        self._kb = knowledge_base
        self._read_model = read_model
        self._clock = clock
        self._new_id = new_id

    def upload(
        self,
        tenant: TenantContext,
        *,
        filename: str,
        evidence_kind: str,
        data: bytes,
    ) -> DocumentItem:
        """Run Upload → Ingestion → Document Projection and return the projected Document.

        The `evidence_kind` is validated at the API boundary before this is called; here it is
        stored on the projection as the product's classification of the evidence."""
        document_id = self._new_id()
        uploaded_at = self._clock()
        size = len(data)

        # Ingestion: knowledge-runtime chunks the text into tenant-scoped, citable chunks. A doc
        # that yields no chunks (empty/unreadable), or an ingestion error, is an honest `failed`.
        try:
            chunks = ingest_document(
                self._kb,
                _extract_text(data),
                tenant=tenant,
                document_id=document_id,
                source_filename=filename,
            )
            status = DocumentStatus.READY if chunks else DocumentStatus.FAILED
        except Exception:
            status = DocumentStatus.FAILED

        # Document Projection: the product-owned read record the Knowledge view will show.
        item = DocumentItem(
            document_id=document_id,
            tenant_id=tenant.tenant_id,
            filename=filename,
            evidence_kind=evidence_kind,
            status=status.value,
            uploaded_at=uploaded_at,
            size=size,
        )
        self._read_model.record(item)
        return item
