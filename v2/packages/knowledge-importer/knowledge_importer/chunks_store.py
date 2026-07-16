"""Persists one document's chunks to `knowledge/chunks/{document_id}.json` — a flat list
where every entry carries its own `parent_chunk_id` (architecture doc §6). Written
immediately per document from `ChunkingStage` (mirrors `imports_store.py`); pruning of
chunk files for documents no longer in the library runs once per pipeline invocation
(mirrors `manifest_store.py`'s prune step)."""

from __future__ import annotations

import json
from pathlib import Path

from knowledge_importer.chunking.chunk_models import Chunk


def chunk_filename(document_id: str) -> str:
    return f"{document_id}.json"


def write_chunks(chunks_dir: Path, document_id: str, chunks: tuple[Chunk, ...]) -> Path:
    chunks_dir.mkdir(parents=True, exist_ok=True)
    target = chunks_dir / chunk_filename(document_id)
    payload = [c.to_json_dict() for c in chunks]
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def prune_chunk_files(chunks_dir: Path, current_document_ids: set[str]) -> None:
    if not chunks_dir.is_dir():
        return
    keep = {chunk_filename(document_id) for document_id in current_document_ids}
    for existing in chunks_dir.glob("*.json"):
        if existing.name not in keep:
            existing.unlink()
