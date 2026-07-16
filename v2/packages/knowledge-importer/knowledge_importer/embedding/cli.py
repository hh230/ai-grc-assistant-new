"""CLI entrypoint for the embedding phase: `python -m knowledge_importer.embedding.cli`.

Embedding is a separate phase from parse/chunk on purpose — it needs a provider (and, for
a real vendor, credentials), so it isn't wired into the credential-free
discovery→parse→chunk pipeline. This runner reads the document list from the chunk
manifests' index, builds the configured provider, and embeds every chunked document,
writing per-document embedding files, a checkpoint, and the run manifest.

Provider selection is entirely environment-driven (see `embedding/config.py`); it defaults
to the local deterministic provider so the phase runs with no credentials. Switch to a
real vendor with e.g. `EMBEDDING_PROVIDER=openai` (plus `OPENAI_API_KEY`)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from knowledge_importer.config import DEFAULT_CHUNKS_DIR, DEFAULT_EMBEDDINGS_DIR, DEFAULT_MANIFESTS_DIR
from knowledge_importer.embedding.config import config_from_env
from knowledge_importer.embedding.engine import EmbeddingEngine
from knowledge_importer.embedding.index_builder import write_index
from knowledge_importer.embedding.manifest import write_manifest
from knowledge_importer.embedding.providers.registry import build_provider
from knowledge_importer.embedding.store import prune_embedding_files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rasheed V2 Knowledge Importer — embedding phase")
    parser.add_argument("--manifests-dir", type=Path, default=DEFAULT_MANIFESTS_DIR)
    parser.add_argument("--chunks-dir", type=Path, default=DEFAULT_CHUNKS_DIR)
    parser.add_argument("--embeddings-dir", type=Path, default=DEFAULT_EMBEDDINGS_DIR)
    args = parser.parse_args(argv)

    config = config_from_env()
    provider = build_provider(config.provider, config.model, config.dimension)

    index = json.loads((args.manifests_dir / "index.json").read_text(encoding="utf-8"))
    document_ids = [
        e["document_id"]
        for e in index["documents"]
        if (args.chunks_dir / f"{e['document_id']}.json").exists()
    ]

    engine = EmbeddingEngine(
        provider=provider,
        config=config,
        chunks_dir=args.chunks_dir,
        embeddings_dir=args.embeddings_dir,
    )
    summary = engine.run(document_ids)
    prune_embedding_files(args.embeddings_dir, set(document_ids))
    manifest_path = write_manifest(args.embeddings_dir, summary)
    write_index(args.embeddings_dir)  # refresh the per-document index the dashboard reads

    print(f"Provider {summary.provider} / model {summary.model} / {summary.dimension} dims")
    print(f"Documents: {summary.documents_processed} processed, {summary.documents_failed} failed")
    print(
        f"Chunks: {summary.total_embeddings} embeddings "
        f"({summary.created} created, {summary.regenerated} regenerated, {summary.skipped} skipped, {summary.failed} failed)"
    )
    print(f"Duration: {summary.duration_seconds:.1f}s")
    print(f"Wrote embeddings to {args.embeddings_dir} and manifest to {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
