"""Reads chunk files and reads/writes embedding files. One embedding file per document —
`embeddings/{document_id}.json`, a list of per-chunk embedding records — mirroring the
`chunks/{document_id}.json` layout so promotion into a vector DB later is a straight load,
and so a completed document's embeddings are a durable checkpoint (see `checkpoint.py`)."""

from __future__ import annotations

import json
from pathlib import Path

from knowledge_importer.embedding.models import EmbeddingRecord


def embedding_filename(document_id: str) -> str:
    return f"{document_id}.json"


def read_chunks(chunks_dir: Path, document_id: str) -> list[dict[str, object]]:
    path = chunks_dir / f"{document_id}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def read_existing_embeddings(embeddings_dir: Path, document_id: str) -> dict[str, EmbeddingRecord]:
    """Existing embeddings for a document, indexed by chunk_id. Empty when the document
    has never been embedded. Used by the skip/regenerate decision and by resume."""
    path = embeddings_dir / embedding_filename(document_id)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}  # a partially-written file from a hard kill: treat as absent, re-embed
    return {str(r["chunk_id"]): EmbeddingRecord.from_json_dict(r) for r in raw}


def write_embeddings(embeddings_dir: Path, document_id: str, records: list[EmbeddingRecord]) -> Path:
    embeddings_dir.mkdir(parents=True, exist_ok=True)
    target = embeddings_dir / embedding_filename(document_id)
    payload = [r.to_json_dict() for r in records]
    # Write to a temp file then rename, so a crash mid-write never leaves a half-written
    # embedding file that a resume would misread.
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(target)
    return target


def prune_embedding_files(embeddings_dir: Path, current_document_ids: set[str]) -> None:
    if not embeddings_dir.is_dir():
        return
    keep = {embedding_filename(d) for d in current_document_ids}
    reserved = {"embedding_manifest.json", "_checkpoint.json"}
    for existing in embeddings_dir.glob("*.json"):
        if existing.name not in keep and existing.name not in reserved:
            existing.unlink()
