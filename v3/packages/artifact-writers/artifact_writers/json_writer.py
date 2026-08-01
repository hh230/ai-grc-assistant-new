"""JsonArtifactWriter — the first realization of the replaceable artifact format
(ADR 0057). Moved out of the NIST package once a second extractor (ISO) arrived, so it
stays source-agnostic. JSON is chosen for reviewability; it may be swapped for
Postgres/Parquet/SQLite without touching the Port or any extractor. Append-only
(§10.11): it refuses to overwrite an existing artifact.

Note — Storage ≠ Egress: this writer persists the COMPLETE artifact, including full
`description` for Licensed sources. Controlling what a user sees is the downstream Egress
Policy's job, not the writer's.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from knowledge_extraction.port import ArtifactWriter, CanonicalExtractionArtifact


class JsonArtifactWriter(ArtifactWriter):
    def __init__(self, out_dir: str | Path) -> None:
        self._out = Path(out_dir)

    def path_for(self, artifact: CanonicalExtractionArtifact) -> Path:
        ident = artifact.identity
        return self._out / f"{ident.source_id}@{ident.source_version}.json"

    def write(self, artifact: CanonicalExtractionArtifact) -> None:
        self._out.mkdir(parents=True, exist_ok=True)
        path = self.path_for(artifact)
        if path.exists():
            raise FileExistsError(f"append-only: {path} already exists (§10.11)")
        summary = artifact.summary
        payload = {
            "artifact": asdict(artifact.identity),
            "summary": {
                "entities": summary.entities,
                "structural_relationships": summary.structural_relationships,
                "warnings": summary.warnings,
                "unknown": summary.unknown,
                "counts_by_type": dict(summary.counts_by_type),
                "state": summary.state,
                "language": summary.language,
                "normalization": list(summary.normalization),
            },
            "warnings": [asdict(note) for note in artifact.warnings],
            "entities": [
                {**asdict(entity), "egress_restricted": entity.egress_restricted}
                for entity in artifact.entities
            ],
            "structural_relationships": [asdict(rel) for rel in artifact.structural_relationships],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
