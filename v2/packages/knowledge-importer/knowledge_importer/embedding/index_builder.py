"""Builds a compact per-document embedding index — `embeddings/embedding_index.json`,
a `{document_id: embedding_count}` map. This is what the Knowledge Center (and any other
consumer) reads to show per-document embedding counts without loading the full
half-a-gigabyte of vectors. It is authoritative: it counts the actual records on disk.

Run standalone (`python -m knowledge_importer.embedding.index_builder`) or via the
embedding CLI, which refreshes it after every run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from knowledge_importer.config import DEFAULT_EMBEDDINGS_DIR

INDEX_FILENAME = "embedding_index.json"
_RESERVED = {"embedding_manifest.json", "_checkpoint.json", INDEX_FILENAME}


def build_index(embeddings_dir: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not embeddings_dir.is_dir():
        return counts
    for path in sorted(embeddings_dir.glob("*.json")):
        if path.name in _RESERVED:
            continue
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        counts[path.stem] = len(records)
    return counts


def write_index(embeddings_dir: Path) -> Path:
    counts = build_index(embeddings_dir)
    target = embeddings_dir / INDEX_FILENAME
    payload = {"document_count": len(counts), "total_embeddings": sum(counts.values()), "counts": counts}
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the per-document embedding index")
    parser.add_argument("--embeddings-dir", type=Path, default=DEFAULT_EMBEDDINGS_DIR)
    args = parser.parse_args(argv)
    path = write_index(args.embeddings_dir)
    data = json.loads(path.read_text(encoding="utf-8"))
    print(f"Wrote embedding index: {data['document_count']} documents, {data['total_embeddings']} embeddings -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
