"""JsonArtifactReader — the inverse of JsonArtifactWriter. Reads a persisted artifact
from the append-only archive back into a `CanonicalExtractionArtifact`, so any downstream
stage (Graph Builder, …) can run on the archive **independently** of the extractors
(ADR 0058 rule 5). `egress_restricted` is a derived property and is not reconstructed.
"""
from __future__ import annotations

import json
from pathlib import Path

from knowledge_extraction.port import (
    ArtifactIdentity,
    ArtifactSummary,
    CanonicalExtractionArtifact,
    ExtractionNote,
    KnowledgeEntity,
    Provenance,
    StructuralRelationship,
)


class JsonArtifactReader:
    def read(self, path: str | Path) -> CanonicalExtractionArtifact:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        identity = ArtifactIdentity(**doc["artifact"])
        s = doc["summary"]
        summary = ArtifactSummary(
            entities=s["entities"],
            structural_relationships=s["structural_relationships"],
            warnings=s["warnings"],
            unknown=s["unknown"],
            counts_by_type=dict(s["counts_by_type"]),
            state=s["state"],
            language=s["language"],
            normalization=tuple(s["normalization"]),
        )
        entities = tuple(
            KnowledgeEntity(
                source_id=e["source_id"], version=e["version"], entity_id=e["entity_id"],
                parent=e["parent"], type=e["type"], name=e["name"], number=e["number"],
                description=e["description"], language=e["language"], authority=e["authority"],
                license=e["license"], stability=e["stability"], confidence=e["confidence"],
                provenance=Provenance(**e["provenance"]), native_node_type=e["native_node_type"],
            )
            for e in doc["entities"]
        )
        relationships = tuple(
            StructuralRelationship(type=r["type"], source=r["source"], target=r["target"])
            for r in doc["structural_relationships"]
        )
        warnings = tuple(ExtractionNote(**n) for n in doc["warnings"])
        return CanonicalExtractionArtifact(
            identity=identity, summary=summary, entities=entities,
            structural_relationships=relationships, warnings=warnings,
        )
