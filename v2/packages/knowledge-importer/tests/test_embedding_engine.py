from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from knowledge_importer.embedding.checkpoint import load_checkpoint
from knowledge_importer.embedding.config import EmbeddingConfig
from knowledge_importer.embedding.engine import EmbeddingEngine
from knowledge_importer.embedding.store import read_existing_embeddings


@dataclass
class CountingProvider:
    """Records how many texts it was asked to embed, to prove skip logic avoids calls."""

    name: str = "local"
    model: str = "test-model"
    dimension: int = 4
    calls: int = 0
    embedded_texts: list[str] = field(default_factory=list)

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls += 1
        self.embedded_texts.extend(texts)
        return [[float(len(t)), 0.0, 0.0, 0.0] for t in texts]


@dataclass
class FlakyProvider:
    """Fails its first `fail_times` batch calls, then succeeds — for the retry test."""

    name: str = "local"
    model: str = "test-model"
    dimension: int = 4
    fail_times: int = 2
    _seen: int = 0

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        if self._seen < self.fail_times:
            self._seen += 1
            raise RuntimeError("transient provider error")
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


@dataclass
class AlwaysFailProvider:
    name: str = "local"
    model: str = "test-model"
    dimension: int = 4

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        raise RuntimeError("provider down")


def _write_chunk_file(chunks_dir: Path, document_id: str, chunks: list[dict]) -> None:
    chunks_dir.mkdir(parents=True, exist_ok=True)
    (chunks_dir / f"{document_id}.json").write_text(json.dumps(chunks), encoding="utf-8")


def _chunk(chunk_id: str, text: str, checksum: str, **extra) -> dict:
    base = {
        "chunk_id": chunk_id,
        "document_id": "doc1",
        "document_profile": "iso_standard",
        "structure_profile": "standard_clause",
        "parent_chunk_id": None,
        "path": ["Clause 5", "5.1"],
        "page_start": 12,
        "page_end": 13,
        "source_filename": "ISO 27001.pdf",
        "category": "ISO",
        "code": "5.1",
        "title": "Leadership",
        "content_type": "section",
        "level": 2,
        "position": 3,
        "language": "en",
        "references": [],
        "text": text,
        "checksum_sha256": checksum,
    }
    base.update(extra)
    return base


def _config(**kw) -> EmbeddingConfig:
    defaults = {
        "provider": "local",
        "model": "test-model",
        "dimension": 4,
        "batch_size": 2,
        "embedding_version": "v1",
    }
    defaults.update(kw)
    return EmbeddingConfig(**defaults)


def _engine(provider, tmp_path: Path, config: EmbeddingConfig | None = None) -> EmbeddingEngine:
    return EmbeddingEngine(
        provider=provider,
        config=config or _config(),
        chunks_dir=tmp_path / "chunks",
        embeddings_dir=tmp_path / "embeddings",
        sleep=lambda _s: None,
    )


def test_first_run_creates_all_embeddings(tmp_path: Path) -> None:
    _write_chunk_file(tmp_path / "chunks", "doc1", [_chunk("c1", "hello", "sum1"), _chunk("c2", "world", "sum2")])
    provider = CountingProvider()
    summary = _engine(provider, tmp_path).run(["doc1"])

    assert summary.created == 2
    assert summary.skipped == 0 and summary.regenerated == 0 and summary.failed == 0
    assert summary.total_embeddings == 2
    records = read_existing_embeddings(tmp_path / "embeddings", "doc1")
    assert set(records) == {"c1", "c2"}
    assert all(len(r.vector) == 4 for r in records.values())


def test_second_run_skips_unchanged(tmp_path: Path) -> None:
    _write_chunk_file(tmp_path / "chunks", "doc1", [_chunk("c1", "hello", "sum1"), _chunk("c2", "world", "sum2")])
    p1 = CountingProvider()
    _engine(p1, tmp_path).run(["doc1"])
    assert p1.calls > 0

    p2 = CountingProvider()
    summary = _engine(p2, tmp_path).run(["doc1"])
    assert summary.skipped == 2
    assert summary.created == 0 and summary.regenerated == 0
    assert p2.calls == 0  # nothing re-embedded => provider never called


def test_regenerates_when_checksum_changes(tmp_path: Path) -> None:
    _write_chunk_file(tmp_path / "chunks", "doc1", [_chunk("c1", "hello", "sum1")])
    _engine(CountingProvider(), tmp_path).run(["doc1"])

    # chunk text edited -> new checksum
    _write_chunk_file(tmp_path / "chunks", "doc1", [_chunk("c1", "hello EDITED", "sum1_NEW")])
    p2 = CountingProvider()
    summary = _engine(p2, tmp_path).run(["doc1"])
    assert summary.regenerated == 1 and summary.skipped == 0
    assert p2.calls == 1


def test_regenerates_when_model_changes(tmp_path: Path) -> None:
    _write_chunk_file(tmp_path / "chunks", "doc1", [_chunk("c1", "hello", "sum1")])
    _engine(CountingProvider(), tmp_path, _config()).run(["doc1"])

    p2 = CountingProvider(model="different-model")
    summary = _engine(p2, tmp_path, _config(model="different-model")).run(["doc1"])
    assert summary.regenerated == 1 and summary.skipped == 0


def test_regenerates_when_version_changes(tmp_path: Path) -> None:
    _write_chunk_file(tmp_path / "chunks", "doc1", [_chunk("c1", "hello", "sum1")])
    _engine(CountingProvider(), tmp_path, _config(embedding_version="v1")).run(["doc1"])

    summary = _engine(CountingProvider(), tmp_path, _config(embedding_version="v2")).run(["doc1"])
    assert summary.regenerated == 1 and summary.skipped == 0


def test_retry_recovers_then_succeeds(tmp_path: Path) -> None:
    _write_chunk_file(tmp_path / "chunks", "doc1", [_chunk("c1", "hello", "sum1")])
    provider = FlakyProvider(fail_times=2)
    summary = _engine(provider, tmp_path, _config(max_retries=3)).run(["doc1"])
    assert summary.created == 1 and summary.failed == 0


def test_exhausted_retries_records_failure_without_stopping(tmp_path: Path) -> None:
    _write_chunk_file(tmp_path / "chunks", "doc1", [_chunk("c1", "hello", "sum1"), _chunk("c2", "world", "sum2")])
    summary = _engine(AlwaysFailProvider(), tmp_path, _config(max_retries=1)).run(["doc1"])
    assert summary.failed == 2
    assert summary.created == 0
    assert summary.documents_failed == 1
    assert len(summary.failures) == 2
    # failed doc is not checkpointed => it will retry next run
    checkpoint = load_checkpoint(tmp_path / "embeddings", _config().fingerprint())
    assert not checkpoint.is_done("doc1")


def test_metadata_is_never_lost(tmp_path: Path) -> None:
    chunk = _chunk("c1", "body text", "sum1", window_index=None, chunker_version="1.0", extra_future_field="keep me")
    _write_chunk_file(tmp_path / "chunks", "doc1", [chunk])
    _engine(CountingProvider(), tmp_path).run(["doc1"])

    record = read_existing_embeddings(tmp_path / "embeddings", "doc1")["c1"]
    # required top-level fields
    assert record.document_profile == "iso_standard"
    assert record.structure_profile == "standard_clause"
    assert record.parent_chunk_id is None
    assert record.heading_path == ("Clause 5", "5.1")
    assert record.page_start == 12 and record.page_end == 13
    assert record.embedding_model == "test-model"
    assert record.embedding_dimension == 4
    assert record.embedding_version == "v1"
    assert record.embedding_created_at
    assert record.chunk_checksum == "sum1"
    # citation is complete
    assert record.citation["source_filename"] == "ISO 27001.pdf"
    assert record.citation["code"] == "5.1"
    assert record.citation["heading_path"] == ["Clause 5", "5.1"]
    # lossless: even an unknown future chunk field survives, verbatim
    assert record.chunk_metadata["extra_future_field"] == "keep me"
    assert record.chunk_metadata["content_type"] == "section"
    assert record.chunk_metadata["language"] == "en"


def test_resume_after_interruption_only_embeds_missing(tmp_path: Path) -> None:
    _write_chunk_file(tmp_path / "chunks", "doc1", [_chunk("c1", "a", "s1")])
    _write_chunk_file(tmp_path / "chunks", "doc2", [_chunk("c2", "b", "s2", document_id="doc2")])

    # first run embeds doc1 only (simulating an interruption before doc2)
    p1 = CountingProvider()
    _engine(p1, tmp_path).run(["doc1"])

    # resume over both: doc1 is skipped, only doc2 is embedded
    p2 = CountingProvider()
    summary = _engine(p2, tmp_path).run(["doc1", "doc2"])
    assert summary.skipped == 1 and summary.created == 1
    assert p2.embedded_texts == ["b"]  # only the missing document's chunk hit the provider
