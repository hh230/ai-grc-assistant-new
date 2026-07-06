"""Unit tests for the ontology loaders: schema validation for topics/contract types, and —
mirroring ``grc_knowledge_intelligence/tests/test_question_catalog.py`` and
``grc_knowledge_research_adapters/tests/test_trusted_source_catalog.py`` — that the real
``/ontology`` directory shipped with the repo loads cleanly and is internally consistent."""

from __future__ import annotations

from pathlib import Path

import pytest
from grc_knowledge_intelligence import KnowledgeDomain
from grc_knowledge_ontology import (
    ClauseCategory,
    build_ontology,
    load_contract_types,
    load_relationships,
    load_topics,
)
from grc_knowledge_ontology.enums import RelationshipType

_ONTOLOGY_DIR = Path(__file__).resolve().parents[3] / "ontology"

_VALID_TOPIC_FILE = {
    "domain": "governance",
    "topics": [
        {
            "topic_id": "board_governance",
            "name": "board governance",
            "description": "How the board oversees strategy and performance.",
            "aliases": ["board oversight"],
            "tags": ["governance"],
            "related_topic_ids": ["committees"],
        }
    ],
}

_VALID_CONTRACT_TYPES_FILE = {
    "contract_types": [
        {
            "contract_type_id": "nda",
            "name": "NDA",
            "description": "Non-disclosure agreement.",
            "clauses": [
                {
                    "clause_id": "definition_of_confidential_information",
                    "name": "Definition of Confidential Information",
                    "category": "required",
                    "description": "Defines confidential information.",
                }
            ],
        }
    ]
}

_VALID_RELATIONSHIPS_FILE = {
    "relationships": [
        {
            "relationship_type": "requirement_to_control",
            "subject_id": "requirement.x",
            "subject_label": "X requirement",
            "object_id": "control.y",
            "object_label": "Y control",
            "description": "X is satisfied by Y.",
        }
    ]
}


def test_load_topics_builds_topics_tagged_with_their_domain() -> None:
    topics = load_topics(_VALID_TOPIC_FILE)

    assert len(topics) == 1
    assert topics[0].topic_id == "board_governance"
    assert topics[0].domain is KnowledgeDomain.GOVERNANCE
    assert topics[0].aliases == ("board oversight",)
    assert topics[0].related_topic_ids == ("committees",)


def test_load_topics_rejects_a_duplicate_topic_id() -> None:
    data = {
        "domain": "governance",
        "topics": [
            {"topic_id": "x", "name": "x", "description": "d"},
            {"topic_id": "x", "name": "x again", "description": "d"},
        ],
    }

    with pytest.raises(ValueError, match="duplicate topic_id"):
        load_topics(data)


def test_load_topics_rejects_an_empty_topics_list() -> None:
    with pytest.raises(ValueError, match="topics"):
        load_topics({"domain": "governance", "topics": []})


def test_load_contract_types_builds_clauses_with_categories() -> None:
    contract_types = load_contract_types(_VALID_CONTRACT_TYPES_FILE)

    assert len(contract_types) == 1
    nda = contract_types[0]
    assert nda.contract_type_id == "nda"
    assert len(nda.clauses) == 1
    assert nda.clauses[0].category is ClauseCategory.REQUIRED


def test_load_contract_types_rejects_a_duplicate_clause_id_within_one_contract_type() -> None:
    data = {
        "contract_types": [
            {
                "contract_type_id": "nda",
                "name": "NDA",
                "description": "d",
                "clauses": [
                    {"clause_id": "c1", "name": "n1", "category": "required", "description": "d"},
                    {"clause_id": "c1", "name": "n2", "category": "risk", "description": "d"},
                ],
            }
        ]
    }

    with pytest.raises(ValueError, match="duplicate clause_id"):
        load_contract_types(data)


def test_load_contract_types_rejects_an_unclassified_clause_category() -> None:
    data = {
        "contract_types": [
            {
                "contract_type_id": "nda",
                "name": "NDA",
                "description": "d",
                "clauses": [
                    {"clause_id": "c1", "name": "n1", "category": "made_up", "description": "d"}
                ],
            }
        ]
    }

    with pytest.raises(ValueError):
        load_contract_types(data)


def test_load_relationships_builds_typed_relationships() -> None:
    relationships = load_relationships(_VALID_RELATIONSHIPS_FILE)

    assert len(relationships) == 1
    assert relationships[0].relationship_type is RelationshipType.REQUIREMENT_TO_CONTROL


def test_build_ontology_derives_contract_type_to_clause_relationships(tmp_path: Path) -> None:
    import json

    contract_file = tmp_path / "contracts.json"
    contract_file.write_text(json.dumps(_VALID_CONTRACT_TYPES_FILE))

    ontology = build_ontology(contract_type_files=(contract_file,))

    derived = ontology.relationships_of_type(RelationshipType.CONTRACT_TYPE_TO_CLAUSE)
    assert len(derived) == 1
    assert derived[0].subject_id == "contract_type.nda"
    assert derived[0].object_id == "clause.definition_of_confidential_information"


def test_build_ontology_rejects_a_duplicate_topic_id_across_files(tmp_path: Path) -> None:
    import json

    first = tmp_path / "a.json"
    first.write_text(json.dumps(_VALID_TOPIC_FILE))
    second = tmp_path / "b.json"
    second.write_text(json.dumps(_VALID_TOPIC_FILE))

    with pytest.raises(ValueError, match="duplicate topic_id"):
        build_ontology(topic_files=(first, second))


# ---------------------------------------------------------------------------
# The real /ontology directory shipped with the repo.
# ---------------------------------------------------------------------------

_EXPECTED_TOPIC_DOMAINS = {
    KnowledgeDomain.GOVERNANCE,
    KnowledgeDomain.RISK_MANAGEMENT,
    KnowledgeDomain.COMPLIANCE,
    KnowledgeDomain.INTERNAL_CONTROLS,
    KnowledgeDomain.AUDIT,
    KnowledgeDomain.DATA_PROTECTION,
    KnowledgeDomain.CYBERSECURITY_GOVERNANCE,
}


def _topic_files() -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(_ONTOLOGY_DIR.glob("*.json"))
        if path.name not in {"contracts.json", "relationships.json"}
    )


def test_the_real_ontology_directory_loads_cleanly() -> None:
    ontology = build_ontology(
        topic_files=_topic_files(),
        contract_type_files=(_ONTOLOGY_DIR / "contracts.json",),
        relationship_files=(_ONTOLOGY_DIR / "relationships.json",),
    )

    assert {topic.domain for topic in ontology.topics} == _EXPECTED_TOPIC_DOMAINS
    assert len(ontology.contract_types) == 6
    # Every relationship type named in ADR-0027 is represented at least once.
    for relationship_type in RelationshipType:
        assert ontology.relationships_of_type(relationship_type), relationship_type


def test_every_topic_id_is_unique_across_the_real_ontology() -> None:
    ontology = build_ontology(topic_files=_topic_files())
    ids = [topic.topic_id for topic in ontology.topics]
    assert len(ids) == len(set(ids))


def test_every_related_topic_id_resolves_to_a_real_topic() -> None:
    """Search-preparation data ("related concepts") is only useful if it actually resolves —
    a dangling related_topic_id would silently break a future retrieval layer."""
    ontology = build_ontology(topic_files=_topic_files())
    known_ids = {topic.topic_id for topic in ontology.topics}

    for topic in ontology.topics:
        for related_id in topic.related_topic_ids:
            assert related_id in known_ids, f"{topic.topic_id} references unknown {related_id!r}"


def test_every_contract_type_has_at_least_one_required_clause() -> None:
    ontology = build_ontology(contract_type_files=(_ONTOLOGY_DIR / "contracts.json",))

    for contract_type in ontology.contract_types:
        assert contract_type.required_clauses(), contract_type.contract_type_id
