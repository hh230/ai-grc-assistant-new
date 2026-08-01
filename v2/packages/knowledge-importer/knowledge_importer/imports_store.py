"""Persists a document's extracted text to `knowledge/imports/{document_id}.txt`."""

from __future__ import annotations

from pathlib import Path


def write_extracted_text(imports_dir: Path, document_id: str, text: str) -> Path:
    imports_dir.mkdir(parents=True, exist_ok=True)
    target = imports_dir / f"{document_id}.txt"
    target.write_text(text, encoding="utf-8")
    return target
