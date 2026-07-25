"""Tests for the Graph Builder (Stage 4) + the append-only Knowledge Graph.

Proves the ADR 0058 stage contract: **Independent** (no extractor imported), **Idempotent**
(re-ingest = no-op), **Incremental** (fold one source in, no rebuild), and **Append-only**
(a conflicting redefinition raises, never silently mutates).
"""
from __future__ import annotations

import glob
from dataclasses import replace
from pathlib import Path

import pytest

from knowledge_extraction.port import (
    KnowledgeEntity,
    Provenance,
    ResolvedSource,
    SourceFacets,
    assemble_artifact,
)
from graph_builder import GraphBuilder, GraphError, KnowledgeGraph


def _src(source_id: str, version: str = "1") -> ResolvedSource:
    return ResolvedSource(
        source_id=source_id, version=version, language="EN", variant="Official",
        physical_path="/x", sha256="x",
        facets=SourceFacets(authority="Normative", license="Public-Domain",
                            stability="Stable", genre="Framework", grc_domains=("ISEC",)),
    )


def _entity(src: ResolvedSource, suffix: str, etype: str, parent: str | None = None) -> KnowledgeEntity:
    return KnowledgeEntity(
        source_id=src.source_id, version=src.version,
        entity_id=f"{src.source_id}@{src.version}::{suffix}",
        parent=(f"{src.source_id}@{src.version}::{parent}" if parent else None),
        type=etype, name=suffix, number=suffix, description="d", language="EN",
        authority=src.facets.authority, license=src.facets.license,
        stability=src.facets.stability, confidence="100%",
        provenance=Provenance(src.source_id, src.version, suffix), native_node_type=etype,
    )


def _artifact(source_id: str, version: str = "1"):
    s = _src(source_id, version)
    entities = (
        _entity(s, "D", "Domain"),
        _entity(s, "D.1", "Category", "D"),
        _entity(s, "D.1.1", "Control", "D.1"),
    )  # 3 nodes, 2 `contains` edges
    return assemble_artifact(
        source=s, entities=entities, extractor_version="1",
        protocol_version="1", contract_version="1.3",
    )


def test_build_appends_nodes_and_edges() -> None:
    graph = GraphBuilder().build([_artifact("A"), _artifact("B")])
    assert graph.node_count() == 6            # 3 per source
    assert graph.edge_count() == 4            # 2 `contains` per source
    assert graph.sources() == {"A", "B"}
    assert graph.counts_by_type() == {"Domain": 2, "Category": 2, "Control": 2}


def test_ingestion_is_idempotent() -> None:
    art = _artifact("A")
    graph = GraphBuilder().build([art, art, art])   # same artifact three times
    assert graph.node_count() == 3 and graph.edge_count() == 2
    assert len(graph.ingested_artifacts()) == 1


def test_incremental_append_no_rebuild() -> None:
    builder, graph = GraphBuilder(), KnowledgeGraph()
    builder.append(graph, _artifact("A"))
    assert graph.node_count() == 3
    builder.append(graph, _artifact("B"))           # B folded in; A retained
    assert graph.node_count() == 6 and graph.sources() == {"A", "B"}


def test_append_only_violation_on_conflicting_redefinition() -> None:
    s = _src("A")
    entity = _entity(s, "X", "Control")
    a1 = assemble_artifact(source=s, entities=(entity,), extractor_version="1",
                           protocol_version="1", contract_version="1.3")
    conflicting = replace(entity, description="DIFFERENT content for the same entity_id")
    a2 = assemble_artifact(source=s, entities=(conflicting,), extractor_version="2",
                           protocol_version="1", contract_version="1.3")
    graph = GraphBuilder().build([a1])
    with pytest.raises(GraphError):
        GraphBuilder().append(graph, a2)            # append-only: cannot mutate a node in place


def test_children_of_reflects_structural_edges() -> None:
    graph = GraphBuilder().build([_artifact("A")])
    assert graph.children_of("A@1::D") == ("A@1::D.1",)
    assert graph.children_of("A@1::D.1") == ("A@1::D.1.1",)


# --- Integration: the three real artifacts on disk (skips if absent) --------
def _entities_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "knowledge" / "entities"


def _real_artifacts() -> list[Path]:
    names = ["NIST-CSF@2.0.json", "ISO-27001@2022.json", "KSA-PDPL-LAW@2023.json"]
    return [_entities_dir() / n for n in names if (_entities_dir() / n).exists()]


@pytest.mark.skipif(len(_real_artifacts()) < 3, reason="the 3 real artifacts are not all present")
def test_graph_over_three_real_sources() -> None:
    from artifact_writers import JsonArtifactReader

    reader = JsonArtifactReader()
    artifacts = [reader.read(p) for p in _real_artifacts()]
    graph = GraphBuilder().build(artifacts)
    assert graph.node_count() == 134 + 97 + 156     # NIST + ISO + PDPL = 387
    assert graph.edge_count() == 128 + 93 + 113      # contains edges = 334
    assert graph.sources() == {"NIST-CSF", "ISO-27001", "KSA-PDPL-LAW"}
    # idempotent: re-appending all three changes nothing
    again = GraphBuilder().build(artifacts + artifacts)
    assert again.node_count() == graph.node_count()
    assert again.edge_count() == graph.edge_count()
