from __future__ import annotations

import json
from pathlib import Path

from knowledge_importer.chunking.engine import chunk_document
from knowledge_importer.chunking.profiles import load_profile_catalog
from knowledge_importer.chunking.text_lines import split_into_lines
from knowledge_importer.config import DEFAULT_PROFILES_CATALOG
from knowledge_importer.pipeline import build_pipeline


def _real_catalog():
    return load_profile_catalog(DEFAULT_PROFILES_CATALOG)


def test_chunk_document_iso_style_produces_full_tree() -> None:
    catalog = _real_catalog()
    profile = catalog.get("iso_standard")
    text = (
        "4 Context of the organization\n"
        "4.1 Understanding the organization\n"
        "Body one.\n"
        "4.2 Understanding needs\n"
        "Body two.\n"
        "5 Leadership\n"
        "Body three.\n"
    )
    result = chunk_document(
        full_text=text,
        document_id="doc-iso",
        source_filename="doc.pdf",
        category="ISO",
        page_count=1,
        document_profile=profile,
        profile_id="iso_standard",
    )
    assert result.structure_profile_used == "standard_clause"
    assert result.recognizer_confidence > 0
    codes = [c.code for c in result.chunks]
    assert codes == ["4", "4.1", "4.2", "5"]
    for chunk in result.chunks:
        assert chunk.document_profile == "iso_standard"
        assert chunk.source_filename == "doc.pdf"
        assert chunk.category == "ISO"


def test_chunk_document_falls_back_to_window_when_no_structure() -> None:
    catalog = _real_catalog()
    profile = catalog.get("corporate_policy")
    text = "just plain prose with absolutely no headings or numbering at all. " * 30
    result = chunk_document(
        full_text=text,
        document_id="doc-flat",
        source_filename="doc.txt",
        category="Governance",
        page_count=1,
        document_profile=profile,
        profile_id="corporate_policy",
    )
    assert result.structure_profile_used == "fallback_window"
    assert all(c.content_type == "window" for c in result.chunks)


def test_chunk_document_spreadsheet_dispatches_to_tabular() -> None:
    catalog = _real_catalog()
    profile = catalog.get("spreadsheet")
    header = "Control ID\tDescription"
    rows = [f"AC-{i}\tDescription {i}" for i in range(5)]
    text = "\n".join([header, *rows])
    result = chunk_document(
        full_text=text,
        document_id="doc-xlsx",
        source_filename="doc.xlsx",
        category="Risk Management",
        page_count=1,
        document_profile=profile,
        profile_id="spreadsheet",
    )
    assert result.structure_profile_used == "tabular"
    assert result.chunks[0].content_type == "heading_only"
    assert result.chunks[1].content_type == "table"


def test_no_content_is_lost_across_structure_aware_chunks() -> None:
    """The core fidelity invariant: every non-blank line of the original text appears
    in exactly one chunk's text when there is no windowing overlap involved."""
    catalog = _real_catalog()
    profile = catalog.get("iso_standard")
    text = "1 Scope\nScope body line.\n2 References\nReferences body line.\n2.1 Sub reference\nSub body line.\n"
    result = chunk_document(
        full_text=text,
        document_id="doc-fidelity",
        source_filename="doc.txt",
        category="ISO",
        page_count=1,
        document_profile=profile,
        profile_id="iso_standard",
    )
    assert not any(c.content_type == "window" for c in result.chunks)

    original_lines = {line.strip() for line in text.splitlines() if line.strip()}
    reconstructed_lines: set[str] = set()
    for chunk in result.chunks:
        for line in chunk.text.splitlines():
            if line.strip():
                reconstructed_lines.add(line.strip())
    assert reconstructed_lines == original_lines


def test_chunk_text_is_only_whitespace_normalized_never_rewritten() -> None:
    catalog = _real_catalog()
    profile = catalog.get("iso_standard")
    text = "4 Context\nThe quick brown FOX jumps over 123 lazy dogs — exactly as written.\n5 Leadership\nBody.\n"
    result = chunk_document(
        full_text=text,
        document_id="doc-verbatim",
        source_filename="doc.txt",
        category="ISO",
        page_count=1,
        document_profile=profile,
        profile_id="iso_standard",
    )
    context_chunk = next(c for c in result.chunks if c.code == "4")
    assert "The quick brown FOX jumps over 123 lazy dogs — exactly as written." in context_chunk.text


def test_full_pipeline_writes_chunk_files_and_stamps_manifest(tmp_path: Path) -> None:
    library_root = tmp_path / "library"
    (library_root / "ISO").mkdir(parents=True)
    (library_root / "ISO" / "sample.txt").write_text(
        "4 Context of the organization\n4.1 Understanding\nBody text here that is real.\n5 Leadership\nBody.\n"
    )

    pipeline = build_pipeline(
        imports_dir=tmp_path / "imports",
        chunks_dir=tmp_path / "chunks",
        profile_catalog=_real_catalog(),
    )
    run = pipeline.run(library_root)
    manifest = run.manifests[0]

    assert manifest.document_profile == "iso_standard"
    assert manifest.profile_assignment_source == "category_default"
    assert manifest.chunked is True
    assert manifest.chunk_count and manifest.chunk_count > 0
    assert manifest.structure_profile_used == "standard_clause"
    assert manifest.chunking_error is None
    assert manifest.stages_completed == ("intake", "parsing", "profile_assignment", "chunking")

    chunk_file = tmp_path / "chunks" / f"{manifest.document_id}.json"
    assert chunk_file.exists()
    payload = json.loads(chunk_file.read_text(encoding="utf-8"))
    assert len(payload) == manifest.chunk_count
    assert payload[0]["document_id"] == manifest.document_id


def test_chunking_skips_gracefully_when_parsing_failed(tmp_path: Path) -> None:
    library_root = tmp_path / "library"
    (library_root / "ISO").mkdir(parents=True)
    (library_root / "ISO" / "broken.pdf").write_bytes(b"not a real pdf")

    pipeline = build_pipeline(
        imports_dir=tmp_path / "imports",
        chunks_dir=tmp_path / "chunks",
        profile_catalog=_real_catalog(),
    )
    run = pipeline.run(library_root)
    manifest = run.manifests[0]

    assert manifest.parsed is False
    assert manifest.chunked is False
    assert manifest.chunking_error == "document was not successfully parsed"
    assert not (tmp_path / "chunks" / f"{manifest.document_id}.json").exists()


def test_chunk_ids_are_deterministic_across_reruns(tmp_path: Path) -> None:
    library_root = tmp_path / "library"
    (library_root / "ISO").mkdir(parents=True)
    (library_root / "ISO" / "sample.txt").write_text("4 Context\nBody.\n5 Leadership\nBody.\n")

    pipeline = build_pipeline(
        imports_dir=tmp_path / "imports",
        chunks_dir=tmp_path / "chunks",
        profile_catalog=_real_catalog(),
    )
    first = pipeline.run(library_root)
    second = pipeline.run(library_root)

    first_ids = json.loads((tmp_path / "chunks" / f"{first.manifests[0].document_id}.json").read_text(encoding="utf-8"))
    second_ids = json.loads((tmp_path / "chunks" / f"{second.manifests[0].document_id}.json").read_text(encoding="utf-8"))
    assert [c["chunk_id"] for c in first_ids] == [c["chunk_id"] for c in second_ids]
    assert [c["checksum_sha256"] for c in first_ids] == [c["checksum_sha256"] for c in second_ids]


def test_split_into_lines_consumes_page_markers() -> None:
    lines = split_into_lines("page one line\fpage two line")
    assert lines == [(1, "page one line"), (2, "page two line")]
