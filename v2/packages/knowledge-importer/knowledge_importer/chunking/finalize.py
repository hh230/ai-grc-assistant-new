"""Chunk finalization — the one place a `Chunk` is actually constructed.

Every chunk producer (the boundary/tree assembler in `text_lines.py`, the tabular builder
in `tabular.py`, and any future one) funnels through `finalize_chunk`, so normalization,
checksum generation, language detection, metadata stamping, and reference extraction
behave identically no matter which path produced the content. There is exactly one
implementation of these stamps.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from knowledge_importer.chunking.chunk_models import Chunk
from knowledge_importer.chunking.references import detect_references, resolve_scopes
from knowledge_importer.chunking.text_utils import detect_language, normalize_whitespace, slugify


@dataclass(frozen=True)
class ChunkContext:
    """The per-document invariants every chunk of one chunking run shares."""

    document_id: str
    source_filename: str
    category: str
    document_profile: str
    structure_profile: str
    recognizer_confidence: float
    chunked_at: str
    window_chars: int
    overlap_chars: int


def make_chunk_id(document_id: str, slug_source: str, position: int) -> str:
    return f"{document_id}::{slugify(slug_source)}--{position:04d}"


def finalize_chunk(
    ctx: ChunkContext,
    *,
    chunk_id: str,
    position: int,
    content_type: str,
    code: str | None,
    title: str | None,
    path: tuple[str, ...],
    level: int,
    parent_chunk_id: str | None,
    raw_text: str,
    page_start: int | None,
    page_end: int | None,
    window_index: int | None = None,
    window_of_total: int | None = None,
    known_codes: frozenset[str] = frozenset(),
) -> Chunk:
    """Normalize the text, extract references, detect language, checksum, stamp the
    context metadata, and build the final `Chunk`."""
    text = normalize_whitespace(raw_text)
    references = resolve_scopes(detect_references(text), known_codes)
    return Chunk(
        chunk_id=chunk_id,
        document_id=ctx.document_id,
        source_filename=ctx.source_filename,
        category=ctx.category,
        document_profile=ctx.document_profile,
        structure_profile=ctx.structure_profile,
        content_type=content_type,
        code=code,
        title=title,
        path=path,
        level=level,
        parent_chunk_id=parent_chunk_id,
        position=position,
        text=text,
        character_count=len(text),
        page_start=page_start,
        page_end=page_end,
        window_index=window_index,
        window_of_total=window_of_total,
        references=references,
        language=detect_language(text),
        recognizer_confidence=ctx.recognizer_confidence,
        chunked_at=ctx.chunked_at,
        checksum_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )
