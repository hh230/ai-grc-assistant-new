"""The Embedding Engine: the provider-agnostic core that decides what to embed, batches
it, retries transient failures, writes per-document embedding files, and aggregates the
run summary. It knows nothing about any vendor — it only holds an `EmbeddingProvider`.

Skip / regenerate rule (exactly as specified): an existing embedding is reused unless the
chunk's checksum changed, the embedding model changed, or the embedding version changed.
Everything else is idempotent, which is also what makes an interrupted run resume
automatically: rerunning re-embeds only what's missing or stale."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from knowledge_importer.embedding.checkpoint import load_checkpoint, save_checkpoint
from knowledge_importer.embedding.config import EmbeddingConfig
from knowledge_importer.embedding.manifest import EmbeddingRunSummary
from knowledge_importer.embedding.models import EmbeddingRecord
from knowledge_importer.embedding.providers.base import EmbeddingProvider
from knowledge_importer.embedding.store import read_chunks, read_existing_embeddings, write_embeddings


@dataclass
class _ChunkDecision:
    chunk: dict[str, object]
    reason: str  # "new" | "checksum_changed" | "model_changed" | "version_changed"


@dataclass
class DocumentResult:
    document_id: str
    total_chunks: int = 0
    created: int = 0
    regenerated: int = 0
    skipped: int = 0
    failed: int = 0
    failures: list[dict[str, object]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.failed == 0


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _text_for_embedding(chunk: dict[str, object]) -> str:
    """The text sent to the provider. Falls back to a synthesized label for structural
    chunks whose own `text` is empty (e.g. a heading-only parent), so every chunk gets a
    vector and providers that reject empty input (OpenAI does) never fail on them."""
    text = str(chunk.get("text") or "")
    if text.strip():
        return text
    parts = [
        str(chunk.get("code") or ""),
        str(chunk.get("title") or ""),
        " > ".join(str(p) for p in (chunk.get("path") or [])),
    ]
    synthesized = " / ".join(p for p in parts if p)
    return synthesized or "(no text)"


def _decide(chunk: dict[str, object], existing: EmbeddingRecord | None, config: EmbeddingConfig) -> str | None:
    """Return the regeneration reason, or None if the existing embedding can be reused."""
    if existing is None:
        return "new"
    if existing.chunk_checksum != str(chunk.get("checksum_sha256", "")):
        return "checksum_changed"
    if existing.embedding_model != config.model:
        return "model_changed"
    if existing.embedding_version != config.embedding_version:
        return "version_changed"
    return None


def _batched(items: list[_ChunkDecision], size: int) -> list[list[_ChunkDecision]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


class EmbeddingEngine:
    def __init__(
        self,
        *,
        provider: EmbeddingProvider,
        config: EmbeddingConfig,
        chunks_dir: Path,
        embeddings_dir: Path,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._provider = provider
        self._config = config
        self._chunks_dir = chunks_dir
        self._embeddings_dir = embeddings_dir
        self._sleep = sleep or time.sleep

    def _embed_with_retry(self, texts: list[str]) -> list[list[float]]:
        last_exc: Exception | None = None
        for attempt in range(self._config.max_retries + 1):
            try:
                return self._provider.embed_batch(texts)
            except Exception as exc:  # noqa: BLE001 - retry any provider error, then surface it
                last_exc = exc
                if attempt < self._config.max_retries:
                    self._sleep(self._config.retry_base_delay * (2**attempt))
        assert last_exc is not None
        raise last_exc

    def embed_document(self, document_id: str) -> DocumentResult:
        chunks = read_chunks(self._chunks_dir, document_id)
        existing = read_existing_embeddings(self._embeddings_dir, document_id)
        result = DocumentResult(document_id=document_id, total_chunks=len(chunks))

        # Records to write for this document, keyed by chunk_id, so we can reuse valid
        # existing ones and slot new ones in while preserving chunk order at the end.
        records: dict[str, EmbeddingRecord] = {}
        to_embed: list[_ChunkDecision] = []

        for chunk in chunks:
            chunk_id = str(chunk["chunk_id"])
            reason = _decide(chunk, existing.get(chunk_id), self._config)
            if reason is None:
                records[chunk_id] = existing[chunk_id]  # reuse verbatim, no provider call
                result.skipped += 1
            else:
                to_embed.append(_ChunkDecision(chunk=chunk, reason=reason))

        for batch in _batched(to_embed, self._config.batch_size):
            texts = [_text_for_embedding(d.chunk) for d in batch]
            try:
                vectors = self._embed_with_retry(texts)
            except Exception as exc:  # noqa: BLE001 - record failures, keep going with other batches
                for decision in batch:
                    result.failed += 1
                    result.failures.append(
                        {"chunk_id": str(decision.chunk["chunk_id"]), "reason": f"{type(exc).__name__}: {exc}"}
                    )
                continue

            created_at = _now_iso()
            for decision, vector in zip(batch, vectors):
                record = EmbeddingRecord.from_chunk(
                    decision.chunk,
                    vector=vector,
                    provider=self._provider.name,
                    model=self._config.model,
                    dimension=self._config.dimension,
                    version=self._config.embedding_version,
                    created_at=created_at,
                )
                records[record.chunk_id] = record
                if decision.reason == "new":
                    result.created += 1
                else:
                    result.regenerated += 1

        # Write in chunk order; failed chunks simply have no record and are retried next run.
        ordered = [records[str(c["chunk_id"])] for c in chunks if str(c["chunk_id"]) in records]
        write_embeddings(self._embeddings_dir, document_id, ordered)
        return result

    def run(self, document_ids: list[str]) -> EmbeddingRunSummary:
        started = time.perf_counter()
        summary = EmbeddingRunSummary(
            provider=self._provider.name,
            model=self._config.model,
            dimension=self._config.dimension,
            embedding_version=self._config.embedding_version,
            documents_total=len(document_ids),
            generated_at=_now_iso(),
        )
        checkpoint = load_checkpoint(self._embeddings_dir, self._config.fingerprint())

        for document_id in document_ids:
            result = self.embed_document(document_id)
            summary.documents_processed += 1
            summary.total_chunks += result.total_chunks
            summary.created += result.created
            summary.regenerated += result.regenerated
            summary.skipped += result.skipped
            summary.failed += result.failed
            summary.total_embeddings += result.created + result.regenerated + result.skipped
            summary.failures.extend(result.failures)
            if not result.ok:
                summary.documents_failed += 1
            else:
                checkpoint.mark_done(document_id)
                save_checkpoint(self._embeddings_dir, checkpoint)

        summary.duration_seconds = time.perf_counter() - started
        return summary
