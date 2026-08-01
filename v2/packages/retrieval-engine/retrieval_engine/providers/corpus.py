"""The in-memory corpus — the temporary data source both in-memory providers share. It
loads the generated chunk artifacts (`v2/knowledge/chunks/*.json`) into `CorpusChunk`
objects (text + structured metadata). Vectors are loaded separately by the vector provider
from the embedding artifacts. This whole module is what `PgVectorProvider` + a real store
will replace next phase — the engine above it does not change.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pipeline_contracts import KnowledgeScope, RetrievalScope

from retrieval_engine.providers.interfaces import CorpusChunk, Filter


def in_scope(chunk: CorpusChunk, scope: RetrievalScope | None) -> bool:
    """The two-library rule (ADR 0040 §2), applied to one chunk:

    - no scope, or a GLOBAL scope → only GLOBAL chunks (fail-safe: never another tenant's data);
    - an ORGANIZATION scope → GLOBAL chunks ∪ chunks owned by that organization.

    Cross-organization is impossible by construction: an organization chunk passes only when its
    `organization_id` equals the scope's tenant."""
    if scope is None or scope.kind is KnowledgeScope.GLOBAL:
        return chunk.scope_kind is KnowledgeScope.GLOBAL
    if chunk.scope_kind is KnowledgeScope.GLOBAL:
        return True
    return chunk.organization_id == scope.tenant_id


def passes_filter(chunk: CorpusChunk, f: Filter) -> bool:
    """A chunk passes when it is *in scope* (always enforced) and satisfies every *set* metadata
    facet (unset = matches). `codes` matches by exact code or code-prefix ('A.5' matches
    'A.5.15'). Scope is checked first and unconditionally — it is not a metadata facet."""
    if not in_scope(chunk, f.scope):
        return False
    if f.document_profiles and chunk.document_profile not in f.document_profiles:
        return False
    if f.categories and chunk.category not in f.categories:
        return False
    if f.structure_profiles and chunk.structure_profile not in f.structure_profiles:
        return False
    if f.languages and chunk.language not in f.languages:
        return False
    if f.document_ids and chunk.document_id not in f.document_ids:
        return False
    if f.codes:
        code = chunk.code or ""
        if not any(code == c or code.startswith(c) for c in f.codes):
            return False
    return True


def _chunk_from_record(record: dict[str, object]) -> CorpusChunk:
    return CorpusChunk(
        chunk_id=str(record["chunk_id"]),
        document_id=str(record["document_id"]),
        text=str(record.get("text", "")),
        document_profile=record.get("document_profile"),  # type: ignore[arg-type]
        structure_profile=str(record.get("structure_profile", "")),
        category=str(record.get("category", "")).strip(),
        language=str(record.get("language", "en")),
        code=record.get("code"),  # type: ignore[arg-type]
        title=record.get("title"),  # type: ignore[arg-type]
        heading_path=tuple(record.get("path") or []),  # type: ignore[arg-type]
        page_start=record.get("page_start"),  # type: ignore[arg-type]
        page_end=record.get("page_end"),  # type: ignore[arg-type]
        source_filename=str(record.get("source_filename", "")),
        checksum=str(record.get("checksum_sha256", "")),
        content_type=str(record.get("content_type", "")),
        scope_kind=(
            KnowledgeScope.ORGANIZATION
            if str(record.get("scope_kind", "global")) == "organization"
            else KnowledgeScope.GLOBAL
        ),
        organization_id=record.get("organization_id"),  # type: ignore[arg-type]
    )


@dataclass
class InMemoryCorpus:
    chunks: list[CorpusChunk]

    def __post_init__(self) -> None:
        self.by_id: dict[str, CorpusChunk] = {c.chunk_id: c for c in self.chunks}

    def filter(self, f: Filter) -> list[CorpusChunk]:
        # No is_empty() short-circuit: the tenant scope is always enforced, even when the
        # metadata predicate is empty (ADR 0040 §4).
        return [c for c in self.chunks if passes_filter(c, f)]

    @classmethod
    def from_chunks(cls, chunks: list[CorpusChunk]) -> InMemoryCorpus:
        return cls(chunks=list(chunks))

    @classmethod
    def load(cls, chunks_dir: Path) -> InMemoryCorpus:
        chunks: list[CorpusChunk] = []
        for path in sorted(chunks_dir.glob("*.json")):
            records = json.loads(path.read_text(encoding="utf-8"))
            chunks.extend(_chunk_from_record(r) for r in records)
        return cls(chunks=chunks)
