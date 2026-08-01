"""Orchestrates the Recognizer selection cascade (architecture doc §3) and dispatches
to the right chunk-building path for a document's assigned Document Profile (§2, §2.1).
This is the only module that decides *which* recognizer's output to keep — recognizers
themselves only detect boundaries, `text_lines`/`tabular` only build trees/chunks from
whatever boundaries they're given."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from knowledge_importer.chunking.chunk_models import Chunk
from knowledge_importer.chunking.profiles import DocumentProfile
from knowledge_importer.chunking.recognizers import policy_procedure
from knowledge_importer.chunking.recognizers.base import Boundary, score_confidence
from knowledge_importer.chunking.recognizers.registry import get_line_boundary_recognizer
from knowledge_importer.chunking.tabular import build_tabular_chunks
from knowledge_importer.chunking.text_lines import ChunkContext, assemble_chunks, build_fallback_chunks, split_into_lines

CONFIDENCE_THRESHOLD = 0.5
DEFAULT_WINDOW_CHARS = 1200
DEFAULT_OVERLAP_CHARS = 150


@dataclass(frozen=True)
class ChunkingResult:
    chunks: tuple[Chunk, ...]
    structure_profile_used: str
    recognizer_confidence: float


def _detect(name: str, lines: list[tuple[int, str]], policy_mode: str) -> list[Boundary]:
    if name == "policy_procedure":
        return policy_procedure.detect_boundaries(lines, mode=policy_mode)
    detector = get_line_boundary_recognizer(name)
    return detector(lines) if detector else []


def chunk_document(
    *,
    full_text: str,
    document_id: str,
    source_filename: str,
    category: str,
    page_count: int | None,
    document_profile: DocumentProfile | None,
    profile_id: str | None,
) -> ChunkingResult:
    chunked_at = datetime.now(tz=timezone.utc).isoformat()
    lines = split_into_lines(full_text)

    window_chars = document_profile.fallback_windowing.get("window_chars", DEFAULT_WINDOW_CHARS) if document_profile else DEFAULT_WINDOW_CHARS
    overlap_chars = document_profile.fallback_windowing.get("overlap_chars", DEFAULT_OVERLAP_CHARS) if document_profile else DEFAULT_OVERLAP_CHARS

    if profile_id == "spreadsheet":
        ctx = ChunkContext(
            document_id=document_id,
            source_filename=source_filename,
            category=category,
            document_profile=profile_id,
            structure_profile="tabular",
            recognizer_confidence=1.0,
            chunked_at=chunked_at,
            window_chars=window_chars,
            overlap_chars=overlap_chars,
        )
        chunks = build_tabular_chunks(full_text, ctx)
        return ChunkingResult(chunks=tuple(chunks), structure_profile_used="tabular", recognizer_confidence=1.0)

    policy_mode = "policy"
    if document_profile is not None and document_profile.recognizer == "policy_procedure":
        policy_mode = str(document_profile.skeleton.get("mode", "policy"))

    candidates: list[str] = []
    if document_profile is not None:
        candidates.append(document_profile.recognizer)
    for generic in ("standard_clause", "policy_procedure"):
        if generic not in candidates:
            candidates.append(generic)

    best_name: str | None = None
    best_boundaries: list[Boundary] = []
    best_confidence = 0.0

    for name in candidates:
        boundaries = _detect(name, lines, policy_mode)
        confidence = score_confidence(len(boundaries), page_count, len(lines))
        if confidence > best_confidence or best_name is None:
            best_name, best_boundaries, best_confidence = name, boundaries, confidence
        if confidence >= CONFIDENCE_THRESHOLD:
            break

    if not best_boundaries or best_confidence < CONFIDENCE_THRESHOLD:
        ctx = ChunkContext(
            document_id=document_id,
            source_filename=source_filename,
            category=category,
            document_profile=profile_id or "unmapped",
            structure_profile="fallback_window",
            recognizer_confidence=best_confidence,
            chunked_at=chunked_at,
            window_chars=window_chars,
            overlap_chars=overlap_chars,
        )
        chunks = build_fallback_chunks(lines, ctx)
        return ChunkingResult(chunks=tuple(chunks), structure_profile_used="fallback_window", recognizer_confidence=best_confidence)

    ctx = ChunkContext(
        document_id=document_id,
        source_filename=source_filename,
        category=category,
        document_profile=profile_id or "unmapped",
        structure_profile=best_name,
        recognizer_confidence=best_confidence,
        chunked_at=chunked_at,
        window_chars=window_chars,
        overlap_chars=overlap_chars,
    )
    chunks = assemble_chunks(lines, best_boundaries, ctx)
    return ChunkingResult(chunks=tuple(chunks), structure_profile_used=best_name, recognizer_confidence=best_confidence)
