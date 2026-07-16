"""Persists an `ImportRun`'s manifests to `knowledge/manifests/`: one JSON file per
document plus a combined `index.json`. Re-running the pipeline over an unchanged tree
reproduces identical output; removing a document from `library/` prunes its stale
manifest on the next run."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from knowledge_importer.models import MANIFEST_SCHEMA_VERSION, DocumentManifest

INDEX_FILENAME = "index.json"


def manifest_filename(document_id: str) -> str:
    return f"{document_id}.json"


def write_manifests(manifests_dir: Path, manifests: tuple[DocumentManifest, ...]) -> None:
    manifests_dir.mkdir(parents=True, exist_ok=True)
    written_filenames = {manifest_filename(m.document_id) for m in manifests}
    for manifest in manifests:
        target = manifests_dir / manifest_filename(manifest.document_id)
        target.write_text(json.dumps(manifest.to_json_dict(), indent=2, ensure_ascii=False) + "\n")

    keep = written_filenames | {INDEX_FILENAME}
    for existing in manifests_dir.glob("*.json"):
        if existing.name not in keep:
            existing.unlink()


def write_index(manifests_dir: Path, manifests: tuple[DocumentManifest, ...]) -> Path:
    manifests_dir.mkdir(parents=True, exist_ok=True)
    ordered = sorted(manifests, key=lambda m: (m.category, m.relative_path))
    index = {
        "manifest_version": MANIFEST_SCHEMA_VERSION,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "document_count": len(ordered),
        "documents": [
            {
                "document_id": m.document_id,
                "filename": m.filename,
                "category": m.category,
                "extension": m.extension,
                "status": m.status,
                "checksum_sha256": m.checksum_sha256,
                "manifest_path": manifest_filename(m.document_id),
            }
            for m in ordered
        ],
    }
    index_path = manifests_dir / INDEX_FILENAME
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n")
    return index_path
