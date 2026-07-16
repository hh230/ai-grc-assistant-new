"""Normalization — the entry stage that turns the Retrieval Engine's `RetrievedContext`
into the builder's working unit, `ContextBlock`.

This is a pure translation: one `RetrievedChunk` → one `ContextBlock`, carrying the citation
through untouched, deriving the GRC role from the document profile, and stamping a content
hash for later dedup. No ordering, no budgeting, no loss — those are later stages.
"""

from __future__ import annotations

from context_builder.deduplicate import content_hash
from context_builder.models import ContextBlock, role_for_profile
from pipeline_contracts.retrieval import RetrievedChunk, RetrievedContext


def _block_from_chunk(chunk: RetrievedChunk) -> ContextBlock:
    citation = chunk.citation
    return ContextBlock(
        block_id=chunk.chunk_id,
        document_id=chunk.document_id,
        role=role_for_profile(chunk.document_profile),
        text=chunk.text,
        citation=citation,
        heading_path=citation.heading_path,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        code=citation.code,
        document_profile=chunk.document_profile,
        # `final` is the post-ranking score the engine sorts on; fall back to confidence.
        score=float(chunk.scores.get("final", chunk.confidence)),
        confidence=chunk.confidence,
        source_chunk_ids=(chunk.chunk_id,),
        content_hash=content_hash(chunk.text),
    )


def blocks_from_context(context: RetrievedContext) -> list[ContextBlock]:
    """Flatten a RetrievedContext's results into working ContextBlocks (retrieval order)."""
    return [_block_from_chunk(chunk) for chunk in context.results]
