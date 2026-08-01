"""Tests for JsonArtifactWriter — round-trips the four-part canonical shape,
serializes structured warnings, and is append-only."""
from __future__ import annotations

import json

import pytest

from artifact_writers import JsonArtifactReader, JsonArtifactWriter
from knowledge_extraction.port import (
    ExtractionNote,
    KnowledgeEntity,
    Provenance,
    ResolvedSource,
    SourceFacets,
    assemble_artifact,
)


def _artifact():
    source = ResolvedSource(
        source_id="ISO-27001", version="2022", language="EN", variant="Official",
        physical_path="/opaque.pdf", sha256="x",
        facets=SourceFacets(authority="Normative", license="Licensed",
                            stability="Stable", genre="International-Standard",
                            grc_domains=("ISEC",)),
    )
    parent = KnowledgeEntity(
        source_id="ISO-27001", version="2022", entity_id="ISO-27001@2022::A.5",
        parent=None, type="Category", name="Organizational", number="A.5",
        description="theme", language="EN", authority="Normative", license="Licensed",
        stability="Stable", confidence="100%",
        provenance=Provenance("ISO-27001", "2022", "Theme A.5"), native_node_type="Theme",
    )
    child = KnowledgeEntity(
        source_id="ISO-27001", version="2022", entity_id="ISO-27001@2022::A.5.1",
        parent="ISO-27001@2022::A.5", type="Control", name="Policies", number="A.5.1",
        description="full licensed text stored here", language="EN", authority="Normative",
        license="Licensed", stability="Stable", confidence="100%",
        provenance=Provenance("ISO-27001", "2022", "Control A.5.1"), native_node_type="Control",
    )
    note = ExtractionNote(
        subject="Management Clauses", status="Partial",
        reason="rendition not deterministically recoverable",
        recommended_action="Acquire higher-quality rendition",
    )
    return assemble_artifact(
        source=source, entities=(parent, child), extractor_version="1",
        protocol_version="1", contract_version="1.3", warnings=(note,),
    )


def test_writes_four_part_shape_and_structured_warnings(tmp_path) -> None:
    writer = JsonArtifactWriter(tmp_path)
    art = _artifact()
    writer.write(art)
    doc = json.loads(writer.path_for(art).read_text(encoding="utf-8"))
    assert list(doc.keys()) == [
        "artifact", "summary", "warnings", "entities", "structural_relationships"
    ]
    assert doc["summary"]["entities"] == 2
    assert doc["summary"]["structural_relationships"] == 1
    assert doc["summary"]["warnings"] == 1
    assert doc["warnings"][0] == {
        "subject": "Management Clauses", "status": "Partial",
        "reason": "rendition not deterministically recoverable",
        "recommended_action": "Acquire higher-quality rendition",
    }
    # Storage ≠ Egress: full licensed description is stored; egress flagged.
    control = next(e for e in doc["entities"] if e["type"] == "Control")
    assert control["description"] == "full licensed text stored here"
    assert control["egress_restricted"] is True


def test_append_only_refuses_overwrite(tmp_path) -> None:
    writer = JsonArtifactWriter(tmp_path)
    art = _artifact()
    writer.write(art)
    with pytest.raises(FileExistsError):
        writer.write(art)


def test_writer_reader_round_trip(tmp_path) -> None:
    writer, reader = JsonArtifactWriter(tmp_path), JsonArtifactReader()
    original = _artifact()
    writer.write(original)
    restored = reader.read(writer.path_for(original))
    assert restored == original  # identity + summary + entities + rels + warnings all round-trip
