"""GraphBuilder — **Stage 4** of the V3 pipeline (ADR 0058).

**Independent** — runs on *any* artifact(s), needs no extractor (it never imports one).
**Idempotent** — re-running on the same input is a no-op (the append-only graph skips an
already-ingested `content_hash`). **Incremental** — folds one source's artifact into an
existing graph without rebuilding.
"""
from __future__ import annotations

from collections.abc import Iterable

from knowledge_extraction.port import CanonicalExtractionArtifact
from graph_builder.graph import KnowledgeGraph


class GraphBuilder:
    def build(
        self,
        artifacts: Iterable[CanonicalExtractionArtifact],
        into: KnowledgeGraph | None = None,
    ) -> KnowledgeGraph:
        """Append many artifacts into a (new or existing) append-only Knowledge Graph."""
        graph = into if into is not None else KnowledgeGraph()
        for artifact in artifacts:
            graph.append_artifact(artifact)
        return graph

    def append(
        self, graph: KnowledgeGraph, artifact: CanonicalExtractionArtifact
    ) -> KnowledgeGraph:
        """Incremental: fold one source's artifact into an existing graph (no rebuild)."""
        return graph.append_artifact(artifact)
