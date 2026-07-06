"""Unit tests for the ``Relationship`` model and ``DomainOntology`` relationship lookups,
including the derived ``contract_type_to_clause`` edges."""

from __future__ import annotations

import pytest
from grc_knowledge_ontology import (
    ClauseCategory,
    ContractType,
    DomainOntology,
    Relationship,
    RelationshipType,
)
from grc_knowledge_ontology.models import Clause
from grc_knowledge_ontology.ontology_catalog import _derive_contract_clause_relationships


def test_relationship_rejects_an_empty_field() -> None:
    with pytest.raises(ValueError):
        Relationship(
            relationship_type=RelationshipType.RISK_TO_CONTROL,
            subject_id="",
            subject_label="x",
            object_id="y",
            object_label="y",
            description="d",
        )


def test_relationships_of_type_filters_by_type() -> None:
    requirement_edge = Relationship(
        relationship_type=RelationshipType.REQUIREMENT_TO_CONTROL,
        subject_id="requirement.x",
        subject_label="x",
        object_id="control.y",
        object_label="y",
        description="d",
    )
    risk_edge = Relationship(
        relationship_type=RelationshipType.RISK_TO_CONTROL,
        subject_id="risk.x",
        subject_label="x",
        object_id="control.y",
        object_label="y",
        description="d",
    )
    ontology = DomainOntology(relationships=(requirement_edge, risk_edge))

    assert ontology.relationships_of_type(RelationshipType.REQUIREMENT_TO_CONTROL) == (
        requirement_edge,
    )
    assert ontology.relationships_of_type(RelationshipType.RISK_TO_CONTROL) == (risk_edge,)
    assert ontology.relationships_of_type(RelationshipType.CONTROL_TO_EVIDENCE) == ()


def test_derive_contract_clause_relationships_covers_every_clause() -> None:
    contract_type = ContractType(
        contract_type_id="nda",
        name="NDA",
        description="d",
        clauses=(
            Clause(
                clause_id="c1", name="Clause One", category=ClauseCategory.REQUIRED, description="d"
            ),
            Clause(
                clause_id="c2", name="Clause Two", category=ClauseCategory.RISK, description="d"
            ),
        ),
    )

    relationships = _derive_contract_clause_relationships((contract_type,))

    assert len(relationships) == 2
    assert all(
        rel.relationship_type is RelationshipType.CONTRACT_TYPE_TO_CLAUSE for rel in relationships
    )
    assert {rel.object_id for rel in relationships} == {"clause.c1", "clause.c2"}
    assert all(rel.subject_id == "contract_type.nda" for rel in relationships)


def test_derive_contract_clause_relationships_is_empty_for_no_contract_types() -> None:
    assert _derive_contract_clause_relationships(()) == ()
