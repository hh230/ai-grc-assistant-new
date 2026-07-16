"""Checkpoint for resumable embedding runs. The authoritative resume mechanism is the
per-chunk skip decision (an already-embedded chunk whose checksum, model, and version all
match is never re-embedded), which makes every run idempotent. This checkpoint file is a
fast-path on top of that: it records which documents are fully done under the current
config so a resumed run can skip reloading and re-deciding them, and it gives progress
visibility. If the config fingerprint changes, the checkpoint is ignored."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

CHECKPOINT_FILENAME = "_checkpoint.json"


@dataclass
class Checkpoint:
    fingerprint: dict[str, object]
    completed_document_ids: set[str] = field(default_factory=set)

    def mark_done(self, document_id: str) -> None:
        self.completed_document_ids.add(document_id)

    def is_done(self, document_id: str) -> bool:
        return document_id in self.completed_document_ids

    def to_json_dict(self) -> dict[str, object]:
        return {
            "fingerprint": self.fingerprint,
            "completed_document_ids": sorted(self.completed_document_ids),
        }


def load_checkpoint(embeddings_dir: Path, fingerprint: dict[str, object]) -> Checkpoint:
    """Load the checkpoint if present AND its config fingerprint matches the current run;
    otherwise start fresh (a config change invalidates prior progress fast-path)."""
    path = embeddings_dir / CHECKPOINT_FILENAME
    if not path.exists():
        return Checkpoint(fingerprint=fingerprint)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return Checkpoint(fingerprint=fingerprint)
    if raw.get("fingerprint") != fingerprint:
        return Checkpoint(fingerprint=fingerprint)
    return Checkpoint(fingerprint=fingerprint, completed_document_ids=set(raw.get("completed_document_ids", [])))


def save_checkpoint(embeddings_dir: Path, checkpoint: Checkpoint) -> None:
    embeddings_dir.mkdir(parents=True, exist_ok=True)
    path = embeddings_dir / CHECKPOINT_FILENAME
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(checkpoint.to_json_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
