"""The Embedding Manifest — a single summary of an embedding run, written to
`embeddings/embedding_manifest.json`. Counts are accumulated by the engine as it
processes documents."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

MANIFEST_FILENAME = "embedding_manifest.json"


@dataclass
class EmbeddingRunSummary:
    provider: str
    model: str
    dimension: int
    embedding_version: str
    documents_total: int = 0
    documents_processed: int = 0
    documents_failed: int = 0
    total_chunks: int = 0
    total_embeddings: int = 0  # records present after the run (created + regenerated + skipped)
    created: int = 0  # embedded for the first time
    regenerated: int = 0  # re-embedded because checksum / model / version changed
    skipped: int = 0  # reused an existing valid embedding, no provider call
    failed: int = 0  # embedding attempt failed
    duration_seconds: float = 0.0
    generated_at: str = ""
    failures: list[dict[str, object]] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model,
            "dimensions": self.dimension,
            "embedding_version": self.embedding_version,
            "documents_total": self.documents_total,
            "documents_processed": self.documents_processed,
            "documents_failed": self.documents_failed,
            "total_chunks": self.total_chunks,
            "total_embeddings": self.total_embeddings,
            "created": self.created,
            "regenerated": self.regenerated,
            "skipped": self.skipped,
            "failed": self.failed,
            "duration_seconds": round(self.duration_seconds, 3),
            "generated_at": self.generated_at,
            "failures": self.failures,
        }


def write_manifest(embeddings_dir: Path, summary: EmbeddingRunSummary) -> Path:
    embeddings_dir.mkdir(parents=True, exist_ok=True)
    path = embeddings_dir / MANIFEST_FILENAME
    path.write_text(json.dumps(summary.to_json_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
