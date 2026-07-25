"""Tests for the Knowledge Extraction Port — proving the ADR 0056/0057 guarantees
at the boundary, with NO document library in sight (a realization needs none)."""
from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from knowledge_extraction.port import (
    EntityType,
    ExtractionError,
    ExtractorRegistry,
    KnowledgeEntity,
    KnowledgeExtractionPort,
    Provenance,
    ResolvedSource,
    SourceFacets,
    assemble_artifact,
)

PROTOCOL = "1"
CONTRACT = "1.3"


def _iso_source() -> ResolvedSource:
    return ResolvedSource(
        source_id="ISO-27001", version="2022", language="EN", variant="Official",
        physical_path="/opaque/iso27001.pdf", sha256="deadbeef",
        facets=SourceFacets(
            authority="Normative", license="Licensed", stability="Stable",
            genre="International-Standard", grc_domains=("ISEC", "CYB"),
        ),
    )


def _entity(
    source: ResolvedSource, suffix: str, etype: EntityType, native: str,
    number: str | None, confidence: str = "100%",
) -> KnowledgeEntity:
    return KnowledgeEntity(
        source_id=source.source_id, version=source.version,
        entity_id=f"{source.source_id}@{source.version}::{suffix}",
        parent=None, type=etype, name=f"name-{suffix}", number=number,
        description="desc", language=source.language,
        authority=source.facets.authority, license=source.facets.license,
        stability=source.facets.stability, confidence=confidence,
        provenance=Provenance(source.source_id, source.version, f"loc-{suffix}"),
        native_node_type=native,
    )


# --- Owner constraint: the boundary is tooling-agnostic --------------------
def test_port_module_imports_no_document_library() -> None:
    """Parse the real import statements (AST — ignores docstrings/comments) and
    assert the boundary depends on no document/format library."""
    src = (Path(__file__).resolve().parents[1] / "knowledge_extraction" / "port.py").read_text(
        encoding="utf-8"
    )
    imported: set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    forbidden = {"fitz", "openpyxl", "pypdf", "docx", "pandas", "numpy"}
    assert not (imported & forbidden), f"boundary must not import: {imported & forbidden}"


# --- Artifact assembly + summary -------------------------------------------
def test_assemble_computes_summary_and_identity() -> None:
    s = _iso_source()
    entities = (
        _entity(s, "A.5.1", "Control", "Control", "5.1"),
        _entity(s, "A.5.2", "Control", "Control", "5.2"),
        _entity(s, "3.1", "Definition", "Term", "3.1", confidence="Unknown"),
    )
    art = assemble_artifact(
        source=s, entities=entities, extractor_version="1",
        protocol_version=PROTOCOL, contract_version=CONTRACT,
    )
    assert art.summary.entities == 3
    assert art.summary.counts_by_type == {"Control": 2, "Definition": 1}
    assert art.summary.unknown == 1
    assert art.summary.structural_relationships == 0  # these entities have no parent
    assert art.identity.contract_version == "1.3"
    assert art.identity.artifact_id.startswith("ISO-27001@2022~x1~p1~c1.3~")


def test_structural_relationships_materialize_parents() -> None:
    s = _iso_source()
    parent = _entity(s, "A.5", "Control", "Theme", "5")
    child = replace(
        _entity(s, "A.5.1", "Control", "Control", "5.1"), parent="ISO-27001@2022::A.5"
    )
    art = assemble_artifact(
        source=s, entities=(parent, child), extractor_version="1",
        protocol_version=PROTOCOL, contract_version=CONTRACT,
    )
    assert art.summary.structural_relationships == 1
    rel = art.structural_relationships[0]
    assert (rel.type, rel.source, rel.target) == (
        "contains", "ISO-27001@2022::A.5", "ISO-27001@2022::A.5.1"
    )


def test_rejects_dangling_parent() -> None:
    s = _iso_source()
    orphan = replace(
        _entity(s, "A.5.1", "Control", "Control", "5.1"), parent="ISO-27001@2022::A.9"
    )
    with pytest.raises(ExtractionError):
        assemble_artifact(
            source=s, entities=(orphan,), extractor_version="1",
            protocol_version=PROTOCOL, contract_version=CONTRACT,
        )


# --- Reproducibility: generated_at excluded from hash/id -------------------
def test_reproducible_hash_excludes_generated_at() -> None:
    s = _iso_source()
    entities = (_entity(s, "A.5.1", "Control", "Control", "5.1"),)
    a1 = assemble_artifact(
        source=s, entities=entities, extractor_version="1", protocol_version=PROTOCOL,
        contract_version=CONTRACT, generated_at="2026-01-01T00:00:00+00:00",
    )
    a2 = assemble_artifact(
        source=s, entities=entities, extractor_version="1", protocol_version=PROTOCOL,
        contract_version=CONTRACT, generated_at="2027-12-31T23:59:59+00:00",
    )
    assert a1.identity.content_hash == a2.identity.content_hash
    assert a1.identity.artifact_id == a2.identity.artifact_id
    assert a1.identity.generated_at != a2.identity.generated_at


# --- Attributable diffs: extractor vs source -------------------------------
def test_diff_attributable_to_extractor_vs_source() -> None:
    s = _iso_source()
    base_entities = (_entity(s, "A.5.1", "Control", "Control", "5.1"),)
    base = assemble_artifact(
        source=s, entities=base_entities, extractor_version="1",
        protocol_version=PROTOCOL, contract_version=CONTRACT,
    )
    # Extractor evolved, same entities -> same content, different artifact id.
    evolved = assemble_artifact(
        source=s, entities=base_entities, extractor_version="2",
        protocol_version=PROTOCOL, contract_version=CONTRACT,
    )
    assert evolved.identity.content_hash == base.identity.content_hash
    assert evolved.identity.artifact_id != base.identity.artifact_id
    # Source content changed -> different content hash.
    changed = assemble_artifact(
        source=s,
        entities=base_entities + (_entity(s, "A.5.2", "Control", "Control", "5.2"),),
        extractor_version="1", protocol_version=PROTOCOL, contract_version=CONTRACT,
    )
    assert changed.identity.content_hash != base.identity.content_hash


# --- Guardrails at the boundary --------------------------------------------
def test_rejects_non_version_pinned_entity_id() -> None:
    s = _iso_source()
    bad = replace(_entity(s, "A.5.1", "Control", "Control", "5.1"), entity_id="A.5.1")
    with pytest.raises(ExtractionError):
        assemble_artifact(
            source=s, entities=(bad,), extractor_version="1",
            protocol_version=PROTOCOL, contract_version=CONTRACT,
        )


def test_rejects_non_inherited_facets() -> None:
    s = _iso_source()
    tampered = replace(_entity(s, "A.5.1", "Control", "Control", "5.1"), authority="Reference")
    with pytest.raises(ExtractionError):
        assemble_artifact(
            source=s, entities=(tampered,), extractor_version="1",
            protocol_version=PROTOCOL, contract_version=CONTRACT,
        )


def test_rejects_missing_native_node_type() -> None:
    s = _iso_source()
    no_native = replace(_entity(s, "A.5.1", "Control", "Control", "5.1"), native_node_type="")
    with pytest.raises(ExtractionError):
        assemble_artifact(
            source=s, entities=(no_native,), extractor_version="1",
            protocol_version=PROTOCOL, contract_version=CONTRACT,
        )


def test_extract_requires_verified_source() -> None:
    """Terminal verification (PROTO-EXT-3): a non-`Ready` source is a caller
    contract violation — the extractor never re-validates, it refuses."""
    s = replace(_iso_source(), state="Missing")
    with pytest.raises(ExtractionError):
        assemble_artifact(
            source=s, entities=(_entity(s, "A.5.1", "Control", "Control", "5.1"),),
            extractor_version="1", protocol_version=PROTOCOL, contract_version=CONTRACT,
        )


def test_egress_restricted_follows_license() -> None:
    e = _entity(_iso_source(), "A.5.1", "Control", "Control", "5.1")
    assert e.egress_restricted is True  # Licensed
    assert replace(e, license="Public-Domain").egress_restricted is False


# --- Registry + a realization that needs no document library ---------------
class _FakeIsoKnowledgeExtractor(KnowledgeExtractionPort):
    extractor_version = "1"

    def accepts(self, source: ResolvedSource) -> bool:
        return source.source_id.startswith("ISO-")

    def extract(self, source: ResolvedSource):
        entities = (_entity(source, "A.5.1", "Control", "Control", "5.1"),)
        return assemble_artifact(
            source=source, entities=entities, extractor_version=self.extractor_version,
            protocol_version=PROTOCOL, contract_version=CONTRACT,
        )


def test_registry_dispatches_to_realization() -> None:
    registry = ExtractorRegistry()
    registry.register(["ISO-27001", "ISO-27002"], _FakeIsoKnowledgeExtractor())
    art = registry.extract(_iso_source())
    assert art.entities[0].entity_id == "ISO-27001@2022::A.5.1"


def test_registry_rejects_duplicate_and_unknown() -> None:
    registry = ExtractorRegistry()
    registry.register(["ISO-27001"], _FakeIsoKnowledgeExtractor())
    with pytest.raises(ExtractionError):
        registry.register(["ISO-27001"], _FakeIsoKnowledgeExtractor())
    with pytest.raises(ExtractionError):
        registry.resolve("NOPE")


def test_registry_rejects_mis_registration_via_accepts() -> None:
    """The `accepts` cross-check catches an extractor registered for the wrong family."""
    registry = ExtractorRegistry()
    registry.register(["SAMA-CSF"], _FakeIsoKnowledgeExtractor())  # wrong family
    with pytest.raises(ExtractionError):
        registry.extract(replace(_iso_source(), source_id="SAMA-CSF"))
