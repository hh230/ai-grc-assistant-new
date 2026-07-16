"""The embedding record — one per chunk. It is a **superset** of the chunk's metadata:
every required citation/structure field is promoted to the top level, the complete chunk
metadata block is carried verbatim so nothing the Knowledge Pipeline produced is ever
lost, and the vector plus its provenance are added. The only chunk field intentionally
not duplicated here is the raw `text` body, which remains authoritative in
`chunks/{document_id}.json` and is re-linkable by `chunk_id` and verifiable by
`chunk_checksum` — text is content, not metadata, and copying it would double storage
for no gain."""

from __future__ import annotations

from dataclasses import dataclass

# Chunk fields that this record promotes to the top level and therefore need not be
# repeated inside the carried-over `chunk_metadata` block. `text` is excluded on purpose
# (see module docstring).
_PROMOTED_OR_EXCLUDED = frozenset(
    {
        "text",
        "chunk_id",
        "document_id",
        "document_profile",
        "structure_profile",
        "parent_chunk_id",
        "path",
        "page_start",
        "page_end",
        "checksum_sha256",
    }
)


def build_citation(chunk: dict[str, object]) -> dict[str, object]:
    """Everything a later phase needs to render a source citation — without the chunk
    text itself. e.g. "ISO/IEC 27001 — A.5.15 Access control policy — pp. 12–13"."""
    return {
        "source_filename": chunk.get("source_filename"),
        "category": chunk.get("category"),
        "document_profile": chunk.get("document_profile"),
        "structure_profile": chunk.get("structure_profile"),
        "code": chunk.get("code"),
        "title": chunk.get("title"),
        "heading_path": list(chunk.get("path") or []),
        "page_start": chunk.get("page_start"),
        "page_end": chunk.get("page_end"),
    }


@dataclass(frozen=True)
class EmbeddingRecord:
    chunk_id: str
    document_id: str
    document_profile: str | None
    structure_profile: str | None
    parent_chunk_id: str | None
    heading_path: tuple[str, ...]
    page_start: int | None
    page_end: int | None
    citation: dict[str, object]
    chunk_checksum: str  # links back to the exact chunk text; drives the regenerate-on-change rule
    chunk_metadata: dict[str, object]  # every remaining chunk field, verbatim — lossless
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    embedding_version: str
    embedding_created_at: str
    vector: list[float]

    @classmethod
    def from_chunk(
        cls,
        chunk: dict[str, object],
        *,
        vector: list[float],
        provider: str,
        model: str,
        dimension: int,
        version: str,
        created_at: str,
    ) -> EmbeddingRecord:
        carried = {k: v for k, v in chunk.items() if k not in _PROMOTED_OR_EXCLUDED}
        return cls(
            chunk_id=str(chunk["chunk_id"]),
            document_id=str(chunk["document_id"]),
            document_profile=chunk.get("document_profile"),  # type: ignore[arg-type]
            structure_profile=chunk.get("structure_profile"),  # type: ignore[arg-type]
            parent_chunk_id=chunk.get("parent_chunk_id"),  # type: ignore[arg-type]
            heading_path=tuple(chunk.get("path") or []),  # type: ignore[arg-type]
            page_start=chunk.get("page_start"),  # type: ignore[arg-type]
            page_end=chunk.get("page_end"),  # type: ignore[arg-type]
            citation=build_citation(chunk),
            chunk_checksum=str(chunk.get("checksum_sha256", "")),
            chunk_metadata=carried,
            embedding_provider=provider,
            embedding_model=model,
            embedding_dimension=dimension,
            embedding_version=version,
            embedding_created_at=created_at,
            vector=vector,
        )

    def to_json_dict(self) -> dict[str, object]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_profile": self.document_profile,
            "structure_profile": self.structure_profile,
            "parent_chunk_id": self.parent_chunk_id,
            "heading_path": list(self.heading_path),
            "page_start": self.page_start,
            "page_end": self.page_end,
            "citation": self.citation,
            "chunk_checksum": self.chunk_checksum,
            "chunk_metadata": self.chunk_metadata,
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model,
            "embedding_dimension": self.embedding_dimension,
            "embedding_version": self.embedding_version,
            "embedding_created_at": self.embedding_created_at,
            "vector": self.vector,
        }

    @classmethod
    def from_json_dict(cls, data: dict[str, object]) -> EmbeddingRecord:
        return cls(
            chunk_id=str(data["chunk_id"]),
            document_id=str(data["document_id"]),
            document_profile=data.get("document_profile"),  # type: ignore[arg-type]
            structure_profile=data.get("structure_profile"),  # type: ignore[arg-type]
            parent_chunk_id=data.get("parent_chunk_id"),  # type: ignore[arg-type]
            heading_path=tuple(data.get("heading_path") or []),  # type: ignore[arg-type]
            page_start=data.get("page_start"),  # type: ignore[arg-type]
            page_end=data.get("page_end"),  # type: ignore[arg-type]
            citation=dict(data.get("citation") or {}),  # type: ignore[arg-type]
            chunk_checksum=str(data.get("chunk_checksum", "")),
            chunk_metadata=dict(data.get("chunk_metadata") or {}),  # type: ignore[arg-type]
            embedding_provider=str(data.get("embedding_provider", "")),
            embedding_model=str(data.get("embedding_model", "")),
            embedding_dimension=int(data.get("embedding_dimension", 0)),  # type: ignore[arg-type]
            embedding_version=str(data.get("embedding_version", "")),
            embedding_created_at=str(data.get("embedding_created_at", "")),
            vector=list(data.get("vector") or []),  # type: ignore[arg-type]
        )
