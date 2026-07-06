"""Unit tests for deterministic, template-based question generation: well-formed output, no
LLM, and — critically — no collision with the hand-curated ``/knowledge-catalog`` questions
this generated set is meant to sit alongside."""

from __future__ import annotations

from pathlib import Path

from grc_knowledge_intelligence import KnowledgeDomain, build_catalog
from grc_knowledge_ontology import (
    ClauseCategory,
    ContractType,
    DomainOntology,
    Topic,
    build_ontology,
    generate_contract_type_questions,
    generate_ontology_questions,
    generate_topic_questions,
)
from grc_knowledge_ontology.models import Clause

_ONTOLOGY_DIR = Path(__file__).resolve().parents[3] / "ontology"
_KNOWLEDGE_CATALOG_DIR = Path(__file__).resolve().parents[3] / "knowledge-catalog"

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


def test_generate_topic_questions_uses_the_domains_templates() -> None:
    questions = generate_topic_questions(_TOPIC)

    assert len(questions) == 2  # governance has two templates
    assert all(question.domain is KnowledgeDomain.GOVERNANCE for question in questions)
    assert all(question.category == "board_governance" for question in questions)
    assert all("board governance" in question.question for question in questions)


def test_generate_topic_questions_produces_stable_namespaced_ids() -> None:
    questions = generate_topic_questions(_TOPIC)

    assert questions[0].question_id == "governance.board_governance.q1"
    assert questions[1].question_id == "governance.board_governance.q2"


def test_generate_topic_questions_is_empty_for_a_domain_with_no_templates() -> None:
    topic = Topic(
        topic_id="vendor_onboarding",
        domain=KnowledgeDomain.VENDOR_MANAGEMENT,
        name="vendor onboarding",
        description="d",
    )

    assert generate_topic_questions(topic) == ()


def test_generate_contract_type_questions_applies_all_four_templates() -> None:
    questions = generate_contract_type_questions(_CONTRACT_TYPE)

    assert len(questions) == 4
    assert all(question.domain is KnowledgeDomain.CONTRACTS for question in questions)
    assert questions[0].question == "What clauses should exist in a NDA contract?"
    assert questions[0].question_id == "contracts.nda.q1"


def test_generate_ontology_questions_combines_topics_and_contract_types() -> None:
    ontology = DomainOntology(topics=(_TOPIC,), contract_types=(_CONTRACT_TYPE,), relationships=())

    questions = generate_ontology_questions(ontology)

    assert len(questions) == 6  # 2 from the topic + 4 from the contract type
    ids = [question.question_id for question in questions]
    assert len(ids) == len(set(ids))


def _real_topic_files() -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(_ONTOLOGY_DIR.glob("*.json"))
        if path.name not in {"contracts.json", "relationships.json"}
    )


def test_generated_questions_never_collide_with_the_curated_catalog() -> None:
    ontology = build_ontology(
        topic_files=_real_topic_files(),
        contract_type_files=(_ONTOLOGY_DIR / "contracts.json",),
        relationship_files=(_ONTOLOGY_DIR / "relationships.json",),
    )
    generated = generate_ontology_questions(ontology)
    curated = build_catalog(sorted(_KNOWLEDGE_CATALOG_DIR.glob("*.json")))

    generated_ids = {question.question_id for question in generated}
    curated_ids = {question.question_id for question in curated}

    assert generated_ids.isdisjoint(curated_ids)
    assert len(generated) > 0
