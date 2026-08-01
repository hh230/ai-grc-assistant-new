"""Rasheed V3 — Knowledge Extraction Port (ADR 0056 + ADR 0057).

The format- and tooling-agnostic boundary of Stage-2 extraction. Public API is
the boundary and its canonical types only; realizations (`*KnowledgeExtractor`)
live in their own packages behind this Port.
"""
from knowledge_extraction.port import (
    ArtifactIdentity,
    ArtifactSummary,
    ArtifactWriter,
    Authority,
    CanonicalExtractionArtifact,
    Confidence,
    EntityType,
    ExtractionError,
    ExtractionNote,
    ExtractorRegistry,
    KnowledgeEntity,
    KnowledgeExtractionPort,
    Language,
    License,
    Provenance,
    ResolvedSource,
    SourceFacets,
    Stability,
    StructuralRelationship,
    assemble_artifact,
    compute_content_hash,
)

__all__ = [
    "ArtifactIdentity",
    "ArtifactSummary",
    "ArtifactWriter",
    "Authority",
    "CanonicalExtractionArtifact",
    "Confidence",
    "EntityType",
    "ExtractionError",
    "ExtractionNote",
    "ExtractorRegistry",
    "KnowledgeEntity",
    "KnowledgeExtractionPort",
    "Language",
    "License",
    "Provenance",
    "ResolvedSource",
    "SourceFacets",
    "Stability",
    "StructuralRelationship",
    "assemble_artifact",
    "compute_content_hash",
]
