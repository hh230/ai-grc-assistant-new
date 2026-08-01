"""`EmbeddingStage` — the `PipelineStage` adapter around `EmbeddingEngine`, so embedding
can be composed into a pipeline exactly like intake/parsing/profile-assignment/chunking.
It embeds one document's chunks (reading `chunks/{document_id}.json`, writing
`embeddings/{document_id}.json`) and returns the manifest unchanged — the embedding
phase's own artifacts are the embedding files and the embedding manifest, so it never
rewrites the parse/chunk manifests.

Per-document results are accumulated on the stage so a driver can build the run summary.
The standalone embedding CLI drives `EmbeddingEngine` directly (cleaner for checkpointing
and the run manifest); this adapter exists for pipeline composition and parity with the
other stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from knowledge_importer.embedding.engine import DocumentResult, EmbeddingEngine
from knowledge_importer.models import DocumentManifest


@dataclass
class EmbeddingStage:
    engine: EmbeddingEngine
    name: str = "embedding"
    results: list[DocumentResult] = field(default_factory=list)

    def run(self, manifest: DocumentManifest, source_path: Path) -> DocumentManifest:
        # source_path is unused: embedding consumes the chunk artifact, not the original
        # file — the same layering discipline every post-parse stage follows.
        if manifest.chunked:
            self.results.append(self.engine.embed_document(manifest.document_id))
        return manifest
