from __future__ import annotations

import json
from pathlib import Path

from knowledge_importer.embedding.config import EmbeddingConfig
from knowledge_importer.embedding.engine import EmbeddingEngine
from knowledge_importer.embedding.providers.local import LocalDeterministicProvider
from knowledge_importer.embedding.stage import EmbeddingStage
from knowledge_importer.models import DocumentManifest


def _seed_manifest(document_id: str, *, chunked: bool) -> DocumentManifest:
    m = DocumentManifest.seed(
        document_id=document_id,
        filename="x.pdf",
        extension=".pdf",
        category="ISO",
        relative_path="ISO/x.pdf",
        discovered_at="2026-01-01T00:00:00",
    )
    import dataclasses

    return dataclasses.replace(m, chunked=chunked, chunk_count=1 if chunked else 0)


def _engine(tmp_path: Path) -> EmbeddingEngine:
    return EmbeddingEngine(
        provider=LocalDeterministicProvider(dimension=8),
        config=EmbeddingConfig(provider="local", model="local-deterministic-hash-v1", dimension=8),
        chunks_dir=tmp_path / "chunks",
        embeddings_dir=tmp_path / "embeddings",
        sleep=lambda _s: None,
    )


def test_stage_embeds_chunked_document_and_returns_manifest_unchanged(tmp_path: Path) -> None:
    (tmp_path / "chunks").mkdir(parents=True)
    (tmp_path / "chunks" / "doc1.json").write_text(
        json.dumps([{"chunk_id": "c1", "document_id": "doc1", "text": "hello", "checksum_sha256": "s1", "path": []}]),
        encoding="utf-8",
    )
    stage = EmbeddingStage(engine=_engine(tmp_path))
    manifest = _seed_manifest("doc1", chunked=True)

    returned = stage.run(manifest, Path("ignored"))
    assert returned is manifest  # embedding phase does not rewrite the document manifest
    assert len(stage.results) == 1 and stage.results[0].created == 1
    assert (tmp_path / "embeddings" / "doc1.json").exists()


def test_stage_skips_unchunked_document(tmp_path: Path) -> None:
    stage = EmbeddingStage(engine=_engine(tmp_path))
    manifest = _seed_manifest("failed_doc", chunked=False)

    stage.run(manifest, Path("ignored"))
    assert stage.results == []
    assert not (tmp_path / "embeddings" / "failed_doc.json").exists()
