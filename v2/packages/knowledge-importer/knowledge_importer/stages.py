"""Pipeline stages. A stage takes a manifest and the document's real path on disk, and
returns a new manifest with its own fields filled in. Later stages (text extraction,
chunking, embedding) are added the same way — implement the `PipelineStage` protocol and
append to the stage list passed into `KnowledgeImportPipeline` — without changing this
module or the pipeline's control flow."""

from __future__ import annotations

import dataclasses
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from knowledge_importer.chunking.engine import chunk_document
from knowledge_importer.chunking.profiles import ProfileCatalog
from knowledge_importer.chunks_store import write_chunks
from knowledge_importer.imports_store import write_extracted_text
from knowledge_importer.models import DocumentManifest
from knowledge_importer.parsers.base import ParseAttempt, ParseError
from knowledge_importer.parsers.registry import get_parser

_CHECKSUM_CHUNK_SIZE = 1024 * 1024


class PipelineStage(Protocol):
    name: str

    def run(self, manifest: DocumentManifest, source_path: Path) -> DocumentManifest: ...


def _compute_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(_CHECKSUM_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@dataclasses.dataclass
class IntakeStage:
    """Fills in the structural file-system facts: size, last-modified time, and a
    SHA-256 checksum. This is the only stage this version of the pipeline runs."""

    name: str = "intake"

    def run(self, manifest: DocumentManifest, source_path: Path) -> DocumentManifest:
        stat = source_path.stat()
        return dataclasses.replace(
            manifest,
            size_bytes=stat.st_size,
            last_modified=_iso(stat.st_mtime),
            checksum_sha256=_compute_checksum(source_path),
            stages_completed=(*manifest.stages_completed, self.name),
            status="discovered",
        )


@dataclasses.dataclass
class ParsingStage:
    """Extracts readable text via the format-specific `Parser` registered for the
    document's extension (see `parsers/registry.py`), and writes it to
    `imports_dir/{document_id}.txt`. A parser may try several backends in order (the PDF
    parser tries pypdf, then pypdfium2); the manifest records which engine produced the
    text, whether a fallback was needed, every attempt, and — only when every backend
    failed — a failure reason. A total failure is recorded rather than raised: one bad
    document must never stop the rest of the library from being processed."""

    imports_dir: Path
    name: str = "parsing"

    def run(self, manifest: DocumentManifest, source_path: Path) -> DocumentManifest:
        parser = get_parser(manifest.extension)
        if parser is None:
            reason = f"no parser registered for extension {manifest.extension!r}"
            return dataclasses.replace(
                manifest,
                parsed=False,
                failure_reason=reason,
                parser_attempts=(),
                parsed_at=_now_iso(),
                error=reason,
                status="parse_failed",
                stages_completed=(*manifest.stages_completed, self.name),
            )

        started = time.perf_counter()
        try:
            result = parser.parse(source_path)
        except ParseError as exc:
            # Every backend the parser tried failed — record the full attempt trail.
            reason = str(exc)
            return dataclasses.replace(
                manifest,
                parsed=False,
                parser=parser.name,
                parser_attempts=tuple(a.to_json_dict() for a in exc.attempts),
                failure_reason=reason,
                extraction_duration=time.perf_counter() - started,
                parsed_at=_now_iso(),
                error=reason,
                status="parse_failed",
                stages_completed=(*manifest.stages_completed, self.name),
            )
        except Exception as exc:  # noqa: BLE001 - a single-backend parser raised; record it as one failed attempt
            reason = f"{type(exc).__name__}: {exc}"
            return dataclasses.replace(
                manifest,
                parsed=False,
                parser=parser.name,
                parser_attempts=(ParseAttempt(parser.name, ok=False, error=reason).to_json_dict(),),
                failure_reason=reason,
                extraction_duration=time.perf_counter() - started,
                parsed_at=_now_iso(),
                error=reason,
                status="parse_failed",
                stages_completed=(*manifest.stages_completed, self.name),
            )

        duration = time.perf_counter() - started
        write_extracted_text(self.imports_dir, manifest.document_id, result.text)
        return dataclasses.replace(
            manifest,
            parsed=True,
            parser=parser.name,
            parser_used=result.parser_used,
            parser_fallback=result.fallback,
            parser_attempts=tuple(a.to_json_dict() for a in result.attempts),
            failure_reason=None,
            page_count=result.page_count,
            character_count=len(result.text),
            extraction_duration=duration,
            parsed_at=_now_iso(),
            error=None,
            status="parsed",
            stages_completed=(*manifest.stages_completed, self.name),
        )


@dataclasses.dataclass
class ProfileAssignmentStage:
    """Assigns a Document Profile (architecture doc §2, §2.1) using Phase 1's
    `category`/`extension`/`document_id` — no parsed text needed, so this stage would
    work immediately after `IntakeStage` too; it sits after `ParsingStage` only to keep
    the pipeline's stage order matching its conceptual order."""

    catalog: ProfileCatalog
    name: str = "profile_assignment"

    def run(self, manifest: DocumentManifest, source_path: Path) -> DocumentManifest:
        assignment = self.catalog.resolve(
            document_id=manifest.document_id, category=manifest.category, extension=manifest.extension
        )
        return dataclasses.replace(
            manifest,
            document_profile=assignment.profile_id,
            profile_assignment_source=assignment.source,
            stages_completed=(*manifest.stages_completed, self.name),
        )


@dataclasses.dataclass
class ChunkingStage:
    """Segments Phase 2's extracted text into structure-preserving chunks (architecture
    doc, full document). Reads `imports_dir/{document_id}.txt` — never `source_path`,
    the original file — continuing the layering discipline `ParsingStage` established:
    each stage consumes only the previous stage's artifact. A document that Phase 2
    failed to parse, or a chunking failure itself, is recorded on the manifest and never
    stops the rest of the library from being processed."""

    imports_dir: Path
    chunks_dir: Path
    catalog: ProfileCatalog
    name: str = "chunking"

    def run(self, manifest: DocumentManifest, source_path: Path) -> DocumentManifest:
        if not manifest.parsed:
            return dataclasses.replace(
                manifest,
                chunked=False,
                chunking_error="document was not successfully parsed",
                chunked_at=_now_iso(),
                stages_completed=(*manifest.stages_completed, self.name),
            )

        text_path = self.imports_dir / f"{manifest.document_id}.txt"
        if not text_path.exists():
            return dataclasses.replace(
                manifest,
                chunked=False,
                chunking_error="extracted text file not found",
                chunked_at=_now_iso(),
                stages_completed=(*manifest.stages_completed, self.name),
            )

        profile_id = manifest.document_profile
        document_profile = (
            self.catalog.get(profile_id) if profile_id and profile_id in self.catalog.profiles else None
        )
        full_text = text_path.read_text(encoding="utf-8")

        started = time.perf_counter()
        try:
            result = chunk_document(
                full_text=full_text,
                document_id=manifest.document_id,
                source_filename=manifest.filename,
                category=manifest.category,
                page_count=manifest.page_count,
                document_profile=document_profile,
                profile_id=profile_id,
            )
        except Exception as exc:  # noqa: BLE001 - a chunking failure must not halt the pipeline
            return dataclasses.replace(
                manifest,
                chunked=False,
                chunking_duration=time.perf_counter() - started,
                chunking_error=f"{type(exc).__name__}: {exc}",
                chunked_at=_now_iso(),
                stages_completed=(*manifest.stages_completed, self.name),
            )
        duration = time.perf_counter() - started

        write_chunks(self.chunks_dir, manifest.document_id, result.chunks)

        return dataclasses.replace(
            manifest,
            chunked=True,
            chunk_count=len(result.chunks),
            structure_profile_used=result.structure_profile_used,
            recognizer_confidence=result.recognizer_confidence,
            chunking_duration=duration,
            chunked_at=_now_iso(),
            chunking_error=None,
            stages_completed=(*manifest.stages_completed, self.name),
        )
