"""grc_knowledge_ontology — the Domain Ontology Engine (KI-P3): a structured
GRC/Compliance/Governance/Risk/Legal/Contracts taxonomy (topics, contract types and clauses,
cross-cutting relationships), missing-clause detection, and deterministic, template-based
question generation that expands the KI-P1 question catalog. See README.md.
"""

from __future__ import annotations

from .contracts import detect_missing_clauses
from .enums import ClauseCategory, RelationshipType
from .models import Clause, ContractType, DomainOntology, Relationship, Topic
from .ontology_catalog import (
    build_ontology,
    load_contract_types,
    load_contract_types_file,
    load_relationships,
    load_relationships_file,
    load_topics,
    load_topics_file,
)
from .question_generation import (
    generate_contract_type_questions,
    generate_ontology_questions,
    generate_topic_questions,
)

__all__ = [
    "Clause",
    "ClauseCategory",
    "ContractType",
    "DomainOntology",
    "Relationship",
    "RelationshipType",
    "Topic",
    "build_ontology",
    "detect_missing_clauses",
    "generate_contract_type_questions",
    "generate_ontology_questions",
    "generate_topic_questions",
    "load_contract_types",
    "load_contract_types_file",
    "load_relationships",
    "load_relationships_file",
    "load_topics",
    "load_topics_file",
]
