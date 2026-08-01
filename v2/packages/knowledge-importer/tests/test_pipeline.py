from __future__ import annotations

import hashlib
import json
from pathlib import Path

from knowledge_importer.cli import build_pipeline
from knowledge_importer.manifest_store import write_index, write_manifests
from knowledge_importer.models import document_id_for


def _make_library(root: Path) -> None:
    (root / "iso").mkdir(parents=True)
    (root / "iso" / "iso-27001.txt").write_text("ISO 27001 summary")
    (root / "iso" / "nested").mkdir()
    (root / "iso" / "nested" / "annex-a.md").write_text("# Annex A")
    (root / "saudi-regulations").mkdir()
    (root / "saudi-regulations" / "nca-ecc.txt").write_text("NCA ECC controls")
    (root / "saudi-regulations" / "logo.png").write_bytes(b"\x89PNG\r\n")


def test_pipeline_discovers_only_supported_files(tmp_path: Path) -> None:
    library_root = tmp_path / "library"
    _make_library(library_root)

    run = build_pipeline(imports_dir=tmp_path / "imports", chunks_dir=tmp_path / "chunks").run(library_root)

    relative_paths = {m.relative_path for m in run.manifests}
    assert relative_paths == {
        "iso/iso-27001.txt",
        "iso/nested/annex-a.md",
        "saudi-regulations/nca-ecc.txt",
    }


def test_manifest_fields_match_source_file(tmp_path: Path) -> None:
    library_root = tmp_path / "library"
    _make_library(library_root)

    run = build_pipeline(imports_dir=tmp_path / "imports", chunks_dir=tmp_path / "chunks").run(library_root)
    manifest = next(m for m in run.manifests if m.relative_path == "iso/iso-27001.txt")

    source_bytes = (library_root / "iso" / "iso-27001.txt").read_bytes()
    assert manifest.checksum_sha256 == hashlib.sha256(source_bytes).hexdigest()
    assert manifest.category == "iso"
    assert manifest.extension == ".txt"
    assert manifest.size_bytes == len(source_bytes)
    assert manifest.document_id == document_id_for("iso/iso-27001.txt")
    assert manifest.stages_completed == ("intake", "parsing", "profile_assignment", "chunking")
    assert manifest.status == "parsed"
    assert manifest.parsed is True


def test_write_manifests_and_index(tmp_path: Path) -> None:
    library_root = tmp_path / "library"
    manifests_dir = tmp_path / "manifests"
    _make_library(library_root)

    run = build_pipeline(imports_dir=tmp_path / "imports", chunks_dir=tmp_path / "chunks").run(library_root)
    write_manifests(manifests_dir, run.manifests)
    index_path = write_index(manifests_dir, run.manifests)

    index = json.loads(index_path.read_text())
    assert index["document_count"] == 3
    assert len(index["documents"]) == 3
    for manifest in run.manifests:
        assert (manifests_dir / f"{manifest.document_id}.json").exists()


def test_rerun_is_idempotent_and_prunes_removed_documents(tmp_path: Path) -> None:
    library_root = tmp_path / "library"
    manifests_dir = tmp_path / "manifests"
    imports_dir = tmp_path / "imports"
    _make_library(library_root)

    pipeline = build_pipeline(imports_dir=imports_dir, chunks_dir=tmp_path / "chunks")
    first_run = pipeline.run(library_root)
    write_manifests(manifests_dir, first_run.manifests)
    write_index(manifests_dir, first_run.manifests)

    second_run = pipeline.run(library_root)
    assert {m.checksum_sha256 for m in first_run.manifests} == {m.checksum_sha256 for m in second_run.manifests}

    removed = library_root / "iso" / "iso-27001.txt"
    stale_manifest_path = manifests_dir / f"{document_id_for('iso/iso-27001.txt')}.json"
    removed.unlink()

    third_run = pipeline.run(library_root)
    write_manifests(manifests_dir, third_run.manifests)
    write_index(manifests_dir, third_run.manifests)

    assert not stale_manifest_path.exists()
    assert len(third_run.manifests) == 2
