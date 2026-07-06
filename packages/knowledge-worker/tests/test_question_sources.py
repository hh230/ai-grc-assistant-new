"""Unit tests for combine_question_sources: merges the curated catalog with ontology-generated
questions, and raises on an id collision between the two sources rather than silently dropping
or overwriting a question."""

from __future__ import annotations

from pathlib import Path

import pytest
from grc_knowledge_intelligence import KnowledgeDomain, KnowledgeQuestion, build_catalog
from grc_knowledge_ontology import (
    ClauseCategory,
    ContractType,
    DomainOntology,
    Topic,
    build_ontology,
    generate_ontology_questions,
)
from grc_knowledge_ontology.models import Clause
from grc_knowledge_worker import combine_question_sources

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ONTOLOGY_DIR = _REPO_ROOT / "ontology"
_KNOWLEDGE_CATALOG_DIR = _REPO_ROOT / "knowledge-catalog"

_TOPIC = Topic(
    topic_id="board_governance",
    domain=KnowledgeDomain.GOVERNANCE,
    name="board governance",
    description="d",
)

_CONTRACT_TYPE = ContractType(
    contract_type_id="nda",
    name="NDA",
    description="d",
    clauses=(Clause(clause_id="c1", name="n1", category=ClauseCategory.REQUIRED, description="d"),),
)

_CATALOG_QUESTION = KnowledgeQuestion(
    question_id="vendor_management.contract_clauses",
    question="What clauses should exist in a vendor contract?",
    domain=KnowledgeDomain.VENDOR_MANAGEMENT,
    category="contract_requirements",
)


def _real_topic_files() -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(_ONTOLOGY_DIR.glob("*.json"))
        if path.name not in {"contracts.json", "relationships.json"}
    )


def test_combines_catalog_and_ontology_questions() -> None:
    ontology = DomainOntology(topics=(_TOPIC,), contract_types=(_CONTRACT_TYPE,), relationships=())

    combined = combine_question_sources(catalog_questions=(_CATALOG_QUESTION,), ontology=ontology)

    assert _CATALOG_QUESTION in combined
    ids = {question.question_id for question in combined}
    assert "governance.board_governance.q1" in ids
    assert "contracts.nda.q1" in ids
    assert len(combined) == 1 + 2 + 4  # catalog question + 2 topic questions + 4 contract ones


def test_raises_on_a_duplicate_question_id_between_sources() -> None:
    ontology = DomainOntology(topics=(_TOPIC,), contract_types=(), relationships=())
    colliding_catalog_question = KnowledgeQuestion(
        question_id="governance.board_governance.q1",
        question="A hand-curated question that happens to collide.",
        domain=KnowledgeDomain.GOVERNANCE,
        category="board_governance",
    )

    with pytest.raises(ValueError, match="duplicate question_id"):
        combine_question_sources(catalog_questions=(colliding_catalog_question,), ontology=ontology)


def test_the_real_catalog_and_ontology_combine_without_collision() -> None:
    ontology = build_ontology(
        topic_files=_real_topic_files(),
        contract_type_files=(_ONTOLOGY_DIR / "contracts.json",),
        relationship_files=(_ONTOLOGY_DIR / "relationships.json",),
    )
    catalog = build_catalog(sorted(_KNOWLEDGE_CATALOG_DIR.glob("*.json")))

    combined = combine_question_sources(catalog_questions=catalog, ontology=ontology)

    generated = generate_ontology_questions(ontology)
    assert len(combined) == len(catalog) + len(generated)
    ids = [question.question_id for question in combined]
    assert len(ids) == len(set(ids))
    assert len(combined) > len(catalog)
