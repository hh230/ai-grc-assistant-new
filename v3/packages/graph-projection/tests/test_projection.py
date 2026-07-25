"""Tests for the Graph Projection layer (ADR 0059).

Proves: request-scoped projection (source/delta/snapshot, no whole-graph load), the
`GraphProjector` is **target-agnostic** (no store import, no SQL), the `ProjectionPackage`
is **immutable**, and the `MemoryProjectionTarget` reference realization applies it
**idempotently**.
"""
from __future__ import annotations

import ast
import dataclasses
import glob
from pathlib import Path

import pytest

from knowledge_extraction.port import (
    KnowledgeEntity,
    Provenance,
    ResolvedSource,
    SourceFacets,
    assemble_artifact,
)
from graph_builder import GraphBuilder
from graph_projection import (
    GraphProjector,
    MemoryProjectionTarget,
    ProjectionPackage,
    ProjectSnapshot,
    ProjectSource,
)


def _src(source_id: str, version: str = "1") -> ResolvedSource:
    return ResolvedSource(
        source_id=source_id, version=version, language="EN", variant="Official",
        physical_path="/x", sha256="x",
        facets=SourceFacets(authority="Normative", license="Public-Domain",
                            stability="Stable", genre="Framework", grc_domains=("ISEC",)),
    )


def _entity(src, suffix, etype, parent=None):
    return KnowledgeEntity(
        source_id=src.source_id, version=src.version,
        entity_id=f"{src.source_id}@{src.version}::{suffix}",
        parent=(f"{src.source_id}@{src.version}::{parent}" if parent else None),
        type=etype, name=suffix, number=suffix, description="d", language="EN",
        authority=src.facets.authority, license=src.facets.license,
        stability=src.facets.stability, confidence="100%",
        provenance=Provenance(src.source_id, src.version, suffix), native_node_type=etype,
    )


def _artifact(source_id: str):
    s = _src(source_id)
    entities = (_entity(s, "D", "Domain"), _entity(s, "D.1", "Category", "D"),
                _entity(s, "D.1.1", "Control", "D.1"))     # 3 nodes, 2 edges
    return assemble_artifact(source=s, entities=entities, extractor_version="1",
                             protocol_version="1", contract_version="1.3")


def _graph():
    return GraphBuilder().build([_artifact("A"), _artifact("B")])


def test_project_source_is_request_scoped() -> None:
    pkg = GraphProjector().project(_graph(), ProjectSource("A", "1"))
    assert {n.source_id for n in pkg.nodes} == {"A"}        # only A, not the whole graph
    assert len(pkg.nodes) == 3 and len(pkg.relationships) == 2
    kinds = [op.kind for op in pkg.operations]
    assert kinds.count("upsert_node") == 3 and kinds.count("upsert_edge") == 2


def test_project_snapshot_covers_everything() -> None:
    pkg = GraphProjector().project(_graph(), ProjectSnapshot())
    assert len(pkg.nodes) == 6 and len(pkg.relationships) == 4


def test_package_is_immutable() -> None:
    pkg = GraphProjector().project(_graph(), ProjectSnapshot())
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        pkg.nodes = ()          # type: ignore[misc]  # ADR 0059: no one may mutate a package


def test_projector_and_package_are_target_agnostic() -> None:
    root = Path(__file__).resolve().parents[1] / "graph_projection"
    forbidden = {"supabase", "psycopg", "psycopg2", "asyncpg", "sqlalchemy",
                 "sqlite3", "neo4j", "rdflib"}
    for module in ("projector.py", "package.py", "request.py"):
        tree = ast.parse((root / module).read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert not (imported & forbidden), f"{module} imports a store: {imported & forbidden}"


def test_memory_target_applies_and_is_idempotent() -> None:
    graph = _graph()
    pkg = GraphProjector().project(graph, ProjectSource("A", "1"))
    target = MemoryProjectionTarget()
    result = target.apply(pkg)
    assert result.upserted_nodes == 3 and result.upserted_edges == 2
    assert target.node_count() == 3 and target.edge_count() == 2
    target.apply(pkg)                                       # re-apply the same package
    assert target.node_count() == 3 and target.edge_count() == 2   # idempotent


# --- Integration: project from the real 3-source graph ----------------------
def _entities_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "knowledge" / "entities"


def _real_present() -> bool:
    names = ["NIST-CSF@2.0.json", "ISO-27001@2022.json", "KSA-PDPL-LAW@2023.json"]
    return all((_entities_dir() / n).exists() for n in names)


@pytest.mark.skipif(not _real_present(), reason="the 3 real artifacts are not all present")
def test_project_one_source_from_the_real_graph() -> None:
    from artifact_writers import JsonArtifactReader

    reader = JsonArtifactReader()
    names = ["NIST-CSF@2.0.json", "ISO-27001@2022.json", "KSA-PDPL-LAW@2023.json"]
    graph = GraphBuilder().build([reader.read(_entities_dir() / n) for n in names])

    # project ONLY ISO-27001 → the serving view holds just that source's subgraph
    iso = GraphProjector().project(graph, ProjectSource("ISO-27001", "2022"))
    target = MemoryProjectionTarget()
    target.apply(iso)
    assert target.node_count() == 97 and target.edge_count() == 93   # 4 Category + 93 Control

    # a full snapshot projects the whole graph
    snapshot = GraphProjector().project(graph, ProjectSnapshot())
    assert len(snapshot.nodes) == 387 and len(snapshot.relationships) == 334
