"""The Chunk model. Every field here exists to answer one question from the approved
architecture (`v2/docs/architecture/chunking-engine.md` §9): given only this chunk, can
Rasheed always reconstruct exactly where it came from? `text` is the one field this
engine is forbidden from rewriting, summarizing, translating, merging, or simplifying —
only whitespace-normalized (see `text_utils.normalize_whitespace`)."""

from __future__ import annotations

from dataclasses import dataclass

CHUNKER_VERSION = "1.0"


@dataclass(frozen=True)
class ChunkReference:
    """A candidate in-text cross-reference mention, detected but never resolved (§8 of
    the architecture doc) — raw material for a future resolution stage, not itself an
    authoritative claim."""

    raw_text: str
    target_code: str
    scope: str  # "internal" | "external"
    confidence: float

    def to_json_dict(self) -> dict[str, object]:
        return {
            "raw_text": self.raw_text,
            "target_code": self.target_code,
            "scope": self.scope,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    source_filename: str
    category: str
    document_profile: str
    structure_profile: str
    content_type: str  # "section" | "table" | "window" | "definition" | "heading_only"
    code: str | None
    title: str | None
    path: tuple[str, ...]
    level: int
    parent_chunk_id: str | None
    position: int
    text: str
    character_count: int
    page_start: int | None
    page_end: int | None
    window_index: int | None
    window_of_total: int | None
    references: tuple[ChunkReference, ...]
    language: str
    recognizer_confidence: float
    chunked_at: str
    checksum_sha256: str
    chunker_version: str = CHUNKER_VERSION

    def to_json_dict(self) -> dict[str, object]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "source_filename": self.source_filename,
            "category": self.category,
            "document_profile": self.document_profile,
            "structure_profile": self.structure_profile,
            "content_type": self.content_type,
            "code": self.code,
            "title": self.title,
            "path": list(self.path),
            "level": self.level,
            "parent_chunk_id": self.parent_chunk_id,
            "position": self.position,
            "text": self.text,
            "character_count": self.character_count,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "window_index": self.window_index,
            "window_of_total": self.window_of_total,
            "references": [r.to_json_dict() for r in self.references],
            "language": self.language,
            "recognizer_confidence": self.recognizer_confidence,
            "chunker_version": self.chunker_version,
            "chunked_at": self.chunked_at,
            "checksum_sha256": self.checksum_sha256,
        }
