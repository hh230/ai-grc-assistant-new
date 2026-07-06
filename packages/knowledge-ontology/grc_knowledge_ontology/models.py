"""Value objects for the Domain Ontology Engine (KI-P3).

Deliberately independent of any persistence/HTTP/LLM library — the same "pure core, zero
infrastructure" posture ``grc_knowledge_intelligence``/``grc_knowledge_research`` already hold
themselves to. Reuses ``grc_knowledge_intelligence.KnowledgeDomain`` rather than inventing a
second domain taxonomy — the ontology *elaborates* KI-P1's 11 domains with topics, it does not
compete with them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from grc_knowledge_intelligence import KnowledgeDomain

from .enums import ClauseCategory, RelationshipType


def _require_non_empty(value: str, field_name: str, owner: str) -> None:
    if not value.strip():
        raise ValueError(f"{owner}.{field_name} must not be empty")


@dataclass(frozen=True)
class Topic:
    """One named concept within a ``KnowledgeDomain`` — e.g. "board governance" within
    Governance — carrying enough search-preparation metadata (aliases, tags, related topics)
    for a future retrieval layer without this package implementing retrieval itself."""

    topic_id: str
    domain: KnowledgeDomain
    name: str
    description: str
    aliases: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    related_topic_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty(self.topic_id, "topic_id", "Topic")
        _require_non_empty(self.name, "name", "Topic")
        _require_non_empty(self.description, "description", "Topic")


@dataclass(frozen=True)
class Clause:
    """One clause a contract type may carry, categorized by the role it plays (required to
    exist / introduces risk / protects the organization) — the categorization missing-clause
    detection and negotiation guidance are computed from, never inferred at read time."""

    clause_id: str
    name: str
    category: ClauseCategory
    description: str
    negotiation_points: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty(self.clause_id, "clause_id", "Clause")
        _require_non_empty(self.name, "name", "Clause")
        _require_non_empty(self.description, "description", "Clause")


@dataclass(frozen=True)
class ContractType:
    """One kind of contract (NDA, vendor agreement, ...) and the clauses a professional
    reviewer expects it to carry."""

    contract_type_id: str
    name: str
    description: str
    clauses: tuple[Clause, ...]
    aliases: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty(self.contract_type_id, "contract_type_id", "ContractType")
        _require_non_empty(self.name, "name", "ContractType")
        _require_non_empty(self.description, "description", "ContractType")
        if not self.clauses:
            raise ValueError("ContractType.clauses must not be empty")
        clause_ids = [clause.clause_id for clause in self.clauses]
        if len(clause_ids) != len(set(clause_ids)):
            raise ValueError(f"ContractType {self.contract_type_id!r} has duplicate clause_id")

    def required_clauses(self) -> tuple[Clause, ...]:
        return tuple(
            clause for clause in self.clauses if clause.category is ClauseCategory.REQUIRED
        )


@dataclass(frozen=True)
class Relationship:
    """One directed edge between two GRC concepts, of a fixed ``RelationshipType``. Concepts
    are referenced by opaque, stable ids with a human-readable label alongside — this is a
    conceptual map of *what kinds of things relate to what*, not a live graph over a tenant's
    actual stored Controls/Risks/Policies (those remain the Controls/Risks/Policies bounded
    contexts' own concern)."""

    relationship_type: RelationshipType
    subject_id: str
    subject_label: str
    object_id: str
    object_label: str
    description: str

    def __post_init__(self) -> None:
        _require_non_empty(self.subject_id, "subject_id", "Relationship")
        _require_non_empty(self.subject_label, "subject_label", "Relationship")
        _require_non_empty(self.object_id, "object_id", "Relationship")
        _require_non_empty(self.object_label, "object_label", "Relationship")
        _require_non_empty(self.description, "description", "Relationship")


@dataclass(frozen=True)
class DomainOntology:
    """The full ontology: every ``Topic``, ``ContractType``, and ``Relationship`` loaded from
    ``/ontology``. Lookup helpers only — no I/O, no mutation."""

    topics: tuple[Topic, ...] = field(default_factory=tuple)
    contract_types: tuple[ContractType, ...] = field(default_factory=tuple)
    relationships: tuple[Relationship, ...] = field(default_factory=tuple)

    def topics_for_domain(self, domain: KnowledgeDomain) -> tuple[Topic, ...]:
        return tuple(topic for topic in self.topics if topic.domain is domain)

    def get_topic(self, topic_id: str) -> Topic | None:
        return next((topic for topic in self.topics if topic.topic_id == topic_id), None)

    def get_contract_type(self, contract_type_id: str) -> ContractType | None:
        return next(
            (ct for ct in self.contract_types if ct.contract_type_id == contract_type_id), None
        )

    def relationships_of_type(
        self, relationship_type: RelationshipType
    ) -> tuple[Relationship, ...]:
        return tuple(
            rel for rel in self.relationships if rel.relationship_type is relationship_type
        )
