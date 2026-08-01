"""The pipeline itself: discover files under a library root, fold each one through the
configured stages, and return every resulting manifest. Adding a stage (text extraction,
chunking, embedding) means adding it to the `stages` sequence passed to
`KnowledgeImportPipeline` — this module's control flow never changes."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from knowledge_importer.chunking.profiles import ProfileCatalog, load_profile_catalog
from knowledge_importer.config import DEFAULT_CHUNKS_DIR, DEFAULT_IMPORTS_DIR, DEFAULT_PROFILES_CATALOG
from knowledge_importer.discovery import discover_library
from knowledge_importer.models import DocumentManifest, document_id_for
from knowledge_importer.stages import ChunkingStage, IntakeStage, ParsingStage, PipelineStage, ProfileAssignmentStage


@dataclass(frozen=True)
class ImportRun:
    manifests: tuple[DocumentManifest, ...]


class KnowledgeImportPipeline:
    def __init__(self, stages: Sequence[PipelineStage]) -> None:
        self._stages = tuple(stages)

    def run(self, library_root: Path) -> ImportRun:
        discovered_at = datetime.now(tz=timezone.utc).isoformat()
        manifests: list[DocumentManifest] = []
        for discovered in discover_library(library_root):
            manifest = DocumentManifest.seed(
                document_id=document_id_for(discovered.relative_path),
                filename=discovered.path.name,
                extension=discovered.path.suffix.lower(),
                category=discovered.category,
                relative_path=discovered.relative_path,
                discovered_at=discovered_at,
            )
            for stage in self._stages:
                manifest = stage.run(manifest, discovered.path)
            manifests.append(manifest)
        return ImportRun(manifests=tuple(manifests))


def build_pipeline(
    imports_dir: Path | None = None,
    chunks_dir: Path | None = None,
    profile_catalog: ProfileCatalog | None = None,
) -> KnowledgeImportPipeline:
    """The pipeline this package ships today: discovery, `IntakeStage`, `ParsingStage`,
    `ProfileAssignmentStage`, `ChunkingStage`. A future stage (embedding) is added to
    this list."""
    catalog = profile_catalog or load_profile_catalog(DEFAULT_PROFILES_CATALOG)
    return KnowledgeImportPipeline(
        stages=[
            IntakeStage(),
            ParsingStage(imports_dir=imports_dir or DEFAULT_IMPORTS_DIR),
            ProfileAssignmentStage(catalog=catalog),
            ChunkingStage(
                imports_dir=imports_dir or DEFAULT_IMPORTS_DIR,
                chunks_dir=chunks_dir or DEFAULT_CHUNKS_DIR,
                catalog=catalog,
            ),
        ]
    )
