"""The manifest model — the sole artifact this pipeline stage produces.

A `DocumentManifest` accumulates fields as it passes through each configured
`PipelineStage` (see `stages.py`): this version only runs `IntakeStage`, which fills in
the structural/file-system facts. A later stage (text extraction, chunking, embedding)
reads the manifest a prior stage produced, adds its own fields, and appends its own name
to `stages_completed` — it never needs to touch what an earlier stage already recorded.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MANIFEST_SCHEMA_VERSION = "1.3"


def document_id_for(relative_path: str) -> str:
    """A stable, deterministic id derived from a document's path under `library/`.
    Two runs over an unchanged tree always produce the same id for the same file, which
    is what makes manifest regeneration idempotent (CLAUDE.md §6 — ingestion is
    idempotent and safe to retry) rather than accumulating duplicates on every re-run."""
    return relative_path.replace("/", "--").lower()


@dataclass(frozen=True)
class DocumentManifest:
    """One discovered document's metadata. Immutable — a stage never mutates a manifest
    in place, it returns a new one (`dataclasses.replace`) with its own fields filled in,
    so the pipeline's history of "what did stage N see" is never silently lost."""

    manifest_version: str
    document_id: str
    filename: str
    extension: str
    category: str
    relative_path: str
    size_bytes: int
    last_modified: str
    checksum_sha256: str
    discovered_at: str
    stages_completed: tuple[str, ...] = field(default_factory=tuple)
    status: str = "pending"
    parsed: bool = False
    parser: str | None = None
    parser_used: str | None = None
    parser_fallback: bool = False
    parser_attempts: tuple[dict[str, object], ...] = field(default_factory=tuple)
    failure_reason: str | None = None
    page_count: int | None = None
    character_count: int | None = None
    extraction_duration: float | None = None
    parsed_at: str | None = None
    error: str | None = None
    document_profile: str | None = None
    profile_assignment_source: str | None = None
    chunked: bool = False
    chunk_count: int | None = None
    structure_profile_used: str | None = None
    recognizer_confidence: float | None = None
    chunking_duration: float | None = None
    chunked_at: str | None = None
    chunking_error: str | None = None

    @classmethod
    def seed(
        cls,
        *,
        document_id: str,
        filename: str,
        extension: str,
        category: str,
        relative_path: str,
        discovered_at: str,
    ) -> DocumentManifest:
        """The scaffold every pipeline run starts from, before any stage has run."""
        return cls(
            manifest_version=MANIFEST_SCHEMA_VERSION,
            document_id=document_id,
            filename=filename,
            extension=extension,
            category=category,
            relative_path=relative_path,
            size_bytes=0,
            last_modified="",
            checksum_sha256="",
            discovered_at=discovered_at,
            stages_completed=(),
            status="pending",
        )

    def to_json_dict(self) -> dict[str, object]:
        return {
            "manifest_version": self.manifest_version,
            "document_id": self.document_id,
            "filename": self.filename,
            "extension": self.extension,
            "category": self.category,
            "relative_path": self.relative_path,
            "size_bytes": self.size_bytes,
            "last_modified": self.last_modified,
            "checksum_sha256": self.checksum_sha256,
            "discovered_at": self.discovered_at,
            "stages_completed": list(self.stages_completed),
            "status": self.status,
            "parsed": self.parsed,
            "parser": self.parser,
            "parser_used": self.parser_used,
            "parser_fallback": self.parser_fallback,
            "parser_attempts": list(self.parser_attempts),
            "failure_reason": self.failure_reason,
            "page_count": self.page_count,
            "character_count": self.character_count,
            "extraction_duration": self.extraction_duration,
            "parsed_at": self.parsed_at,
            "error": self.error,
            "document_profile": self.document_profile,
            "profile_assignment_source": self.profile_assignment_source,
            "chunked": self.chunked,
            "chunk_count": self.chunk_count,
            "structure_profile_used": self.structure_profile_used,
            "recognizer_confidence": self.recognizer_confidence,
            "chunking_duration": self.chunking_duration,
            "chunked_at": self.chunked_at,
            "chunking_error": self.chunking_error,
        }
