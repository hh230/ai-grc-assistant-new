"""CLI entrypoint: run the pipeline against a Knowledge Library root and write manifests
into the V2 project. The library root is always an explicit runtime argument
(`--library-dir`) — its default (see `config.py`) points at the external Knowledge
Library for local development, but nothing here hardcodes that path into the pipeline or
falls back to it silently; pass `--library-dir` to point at any other location, on any
machine, in any future deployment."""

from __future__ import annotations

import argparse
from pathlib import Path

from knowledge_importer.chunking.profiles import load_profile_catalog
from knowledge_importer.chunks_store import prune_chunk_files
from knowledge_importer.config import (
    DEFAULT_CHUNKS_DIR,
    DEFAULT_IMPORTS_DIR,
    DEFAULT_LIBRARY_DIR,
    DEFAULT_MANIFESTS_DIR,
    DEFAULT_PROFILES_CATALOG,
)
from knowledge_importer.manifest_store import write_index, write_manifests
from knowledge_importer.pipeline import build_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rasheed V2 Knowledge Importer — discovery, parsing & chunking")
    parser.add_argument(
        "--library-dir",
        type=Path,
        default=DEFAULT_LIBRARY_DIR,
        help="Root of the Knowledge Library to scan (default: the configured external library path).",
    )
    parser.add_argument(
        "--manifests-dir",
        type=Path,
        default=DEFAULT_MANIFESTS_DIR,
        help="Where to write generated manifests (default: v2/knowledge/manifests).",
    )
    parser.add_argument(
        "--imports-dir",
        type=Path,
        default=DEFAULT_IMPORTS_DIR,
        help="Where to write extracted document text (default: v2/knowledge/imports).",
    )
    parser.add_argument(
        "--chunks-dir",
        type=Path,
        default=DEFAULT_CHUNKS_DIR,
        help="Where to write generated chunks (default: v2/knowledge/chunks).",
    )
    parser.add_argument(
        "--profiles-catalog",
        type=Path,
        default=DEFAULT_PROFILES_CATALOG,
        help="Document Profile catalog JSON (default: v2/knowledge/profiles/document_profiles.json).",
    )
    args = parser.parse_args(argv)

    catalog = load_profile_catalog(args.profiles_catalog)
    pipeline = build_pipeline(imports_dir=args.imports_dir, chunks_dir=args.chunks_dir, profile_catalog=catalog)
    run = pipeline.run(args.library_dir)
    write_manifests(args.manifests_dir, run.manifests)
    index_path = write_index(args.manifests_dir, run.manifests)
    prune_chunk_files(args.chunks_dir, {m.document_id for m in run.manifests})

    parsed_count = sum(1 for m in run.manifests if m.parsed)
    failed_count = len(run.manifests) - parsed_count
    chunked_count = sum(1 for m in run.manifests if m.chunked)
    total_chunks = sum(m.chunk_count or 0 for m in run.manifests if m.chunked)

    print(f"Discovered {len(run.manifests)} document(s) under {args.library_dir}")
    print(f"Parsed {parsed_count} document(s), {failed_count} failed")
    print(f"Chunked {chunked_count} document(s) into {total_chunks} chunk(s)")
    print(f"Wrote {len(run.manifests)} manifest(s) and index to {index_path}")
    print(f"Wrote chunks to {args.chunks_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
