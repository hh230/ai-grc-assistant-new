"""Retrieval contracts — the ports and value objects the retrieval stage is built on.

Engines depend only on these abstractions — never on a concrete provider, and never on
where vectors or keywords actually live (in-memory array, pgvector, anything else).
Swapping providers is a wiring change; nothing that consumes these shapes changes.

`Citation` and its helpers (`is_citable`, `format_citation`, `build_citation`) are defined
in `pipeline_contracts.citations` — the one canonical home for citation rules — and
re-exported here, where the retrieval stage has always reached for them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from pipeline_contracts.citations import (
    Citation,
    build_citation,
    format_citation,
    is_citable,
)
from pipeline_contracts.serialization import dataclass_dict
from pipeline_contracts.tenancy import KnowledgeScope, RetrievalScope

__all__ = [
    "Filter", "RetrievalFilter", "CorpusChunk", "ScoredHit", "FusedHit", "Citation",
    "RetrievedChunk", "RetrievedContext", "RetrievalQuery", "DEFAULT_TOP_K",
    "VectorSearchProvider", "KeywordSearchProvider", "RetrievalScope",
    "is_citable", "format_citation", "build_citation",
]


# ── Filter (the metadata predicate) ───────────────────────────────────────────
@dataclass(frozen=True)
class Filter:
    """A metadata predicate applied *inside* each provider before scoring (never as a
    post-hoc filter that would wreck recall). The metadata fields are optional; an unset field
    matches everything.

    `scope` is the tenant boundary (ADR 0040 §2/§4), a first-class `RetrievalScope` rather than
    a bare tenant id — so future scope dimensions are added without touching `Filter`. It is
    applied *inside* each provider as part of the store query. `scope=None` means **no
    organization is in scope** and the provider is fail-safe: it returns GLOBAL knowledge only,
    never another tenant's data. The pipeline always sets an organization scope from the run's
    tenant; a bare `Filter()` seeing only global data is the safe default."""

    document_profiles: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    structure_profiles: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    document_ids: tuple[str, ...] = ()
    codes: tuple[str, ...] = ()
    scope: RetrievalScope | None = None

    def is_empty(self) -> bool:
        """Whether the *metadata* predicate is empty. The tenant `scope` is orthogonal and is
        always applied by the provider regardless of this."""
        return not any(
            (self.document_profiles, self.categories, self.structure_profiles,
             self.languages, self.document_ids, self.codes)
        )


# Canonical pipeline-wide name; `Filter` is kept as the original (and still primary)
# spelling used across the engines.
RetrievalFilter = Filter


# ── The chunk payload (carries everything downstream needs) ───────────────────
@dataclass(frozen=True)
class CorpusChunk:
    """One retrievable unit: text plus the structured GRC metadata the pipeline preserved.
    This is the payload every provider returns and every later stage consumes."""

    chunk_id: str
    document_id: str
    text: str
    document_profile: str | None
    structure_profile: str
    category: str
    language: str
    code: str | None
    title: str | None
    heading_path: tuple[str, ...]
    page_start: int | None
    page_end: int | None
    source_filename: str
    checksum: str
    content_type: str
    # Tenancy classification (ADR 0040 §2). `scope_kind` is GLOBAL (shared frameworks/laws) or
    # ORGANIZATION (a tenant's own data); `organization_id` names the owner for ORGANIZATION
    # rows and is **None** for GLOBAL (never an empty string). Defaulted so existing corpus rows
    # and constructions are GLOBAL until tagged; the provider populates them from the store row
    # and the engine re-verifies scope at its boundary.
    scope_kind: KnowledgeScope = KnowledgeScope.GLOBAL
    organization_id: str | None = None


@dataclass(frozen=True)
class ScoredHit:
    """A single provider's result: a chunk with that provider's score and a source tag
    ('vector' | 'keyword' | ...)."""

    chunk: CorpusChunk
    score: float
    source: str


@dataclass(frozen=True)
class FusedHit:
    """A fused candidate: the chunk, the fused score, and the per-source rank/score trail
    for full explainability."""

    chunk: CorpusChunk
    fused_score: float
    source_scores: dict[str, float]
    source_ranks: dict[str, int]


# ── Output ────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    document_id: str
    text: str
    citation: Citation
    document_profile: str | None
    structure_profile: str
    page_start: int | None
    page_end: int | None
    scores: dict[str, float]
    confidence: float

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)


@dataclass(frozen=True)
class RetrievedContext:
    """The retrieval stage's output — a structured, cited context bundle. Not generation,
    not an answer: the ranked, validated, citable chunks a later phase grounds on."""

    query: str
    results: list[RetrievedChunk]
    total_candidates: int
    applied_filter: Filter
    overall_confidence: float
    warnings: list[str] = field(default_factory=list)
    timings_ms: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        # applied_filter keeps its historic raw-__dict__ shape (tuple values untouched)
        return dataclass_dict(
            self, exclude=("applied_filter",),
            extra={"applied_filter": self.applied_filter.__dict__},
        )


# ── The query value object ────────────────────────────────────────────────────
DEFAULT_TOP_K = 8


@dataclass(frozen=True)
class RetrievalQuery:
    text: str
    filter: Filter = field(default_factory=Filter)
    top_k: int = DEFAULT_TOP_K
    language: str | None = None
    codes: tuple[str, ...] = ()
    weights: dict[str, float] | None = None


# ── The ports ─────────────────────────────────────────────────────────────────
class VectorSearchProvider(Protocol):
    """Turns a text query into vector-ranked candidates. How it embeds and where the
    vectors live is entirely the adapter's business — the engine never knows."""

    def search(self, query: str, filter: Filter, top_k: int) -> list[ScoredHit]: ...


class KeywordSearchProvider(Protocol):
    """Turns a text query into keyword/BM25-ranked candidates."""

    def search(self, query: str, filter: Filter, top_k: int) -> list[ScoredHit]: ...
