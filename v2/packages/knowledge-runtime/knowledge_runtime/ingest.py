"""Runtime, per-tenant document ingestion (product roadmap P1).

`ingest_document` turns a customer document's text into tenant-scoped, retrievable chunks and adds
them to a `TenantKnowledgeBase` — so the platform's retrieval/search find the **customer's own
data**, not just the shared global library. It **consumes** the frozen `knowledge-importer` chunker
(`chunk_document`, fallback windowing for arbitrary documents) and maps each `Chunk` to the
`retrieval-engine` `CorpusChunk` shape. Nothing about parsing/chunking/retrieval is re-implemented.

Two boundary concerns are handled here:

- **Tenant scope** — every chunk is stamped `ORGANIZATION` / `organization_id=<tenant>` (ADR 0040),
  so it is only ever retrievable within that tenant.
- **Citability** — the retrieval citation gate (`is_citable`) drops any chunk without a source file
  and a hard locator (code or page). Ingested chunks always get a source filename and, when the
  document has no page/code locator (e.g. plain text), a stable position locator (`§N`) — so a
  customer's uploaded content is actually retrievable and honestly cited to its place in the file.
"""

from __future__ import annotations

from knowledge_importer.chunking.chunk_models import Chunk
from knowledge_importer.chunking.engine import chunk_document
from pipeline_contracts import KnowledgeScope, TenantContext
from retrieval_engine.providers.interfaces import CorpusChunk

from knowledge_runtime.tenant_kb import TenantKnowledgeBase

DEFAULT_CATEGORY = "customer_documents"


def _to_corpus_chunk(chunk: Chunk, *, tenant_id: str) -> CorpusChunk:
    # A hard locator so the chunk survives the retrieval citation gate: the source's own code/page
    # when present, else a stable position locator into the document.
    code = chunk.code or f"§{chunk.position + 1}"
    return CorpusChunk(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        text=chunk.text,
        document_profile=chunk.document_profile or None,
        structure_profile=chunk.structure_profile,
        category=chunk.category,
        language=chunk.language,
        code=code,
        title=chunk.title,
        heading_path=chunk.path,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        source_filename=chunk.source_filename,
        checksum=chunk.checksum_sha256,
        content_type=chunk.content_type,
        scope_kind=KnowledgeScope.ORGANIZATION,
        organization_id=tenant_id,
    )


def ingest_document(
    kb: TenantKnowledgeBase,
    text: str,
    *,
    tenant: TenantContext,
    document_id: str,
    source_filename: str,
    category: str = DEFAULT_CATEGORY,
    page_count: int | None = None,
) -> tuple[CorpusChunk, ...]:
    """Chunk `text` and add the chunks — tenant-scoped and citable — to `kb`. Returns the chunks
    added. `document_profile` is left unassigned so the chunker uses robust fallback windowing,
    which handles any customer document shape."""
    result = chunk_document(
        full_text=text,
        document_id=document_id,
        source_filename=source_filename,
        category=category,
        page_count=page_count,
        document_profile=None,
        profile_id=None,
    )
    chunks = tuple(_to_corpus_chunk(c, tenant_id=tenant.tenant_id) for c in result.chunks)
    kb.add(chunks)
    return chunks
