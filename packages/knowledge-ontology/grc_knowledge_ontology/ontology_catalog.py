"""Read the Domain Ontology from local JSON config files (mirrors
``grc_knowledge_intelligence.question_catalog``'s role for questions and
``grc_regulatory_intelligence.source_config``'s role for regulatory sources — CLAUDE.md §13:
configuration, not code). Topics and contract types live under ``/ontology/<domain>.json``;
cross-cutting relationships live under ``/ontology/relationships.json``.

Only the standard library (``json``, ``pathlib``) plus ``grc_knowledge_intelligence`` (itself
dependency-free) are used, and this module never assumes a repo layout — the caller resolves
and passes in the files to load, the same contract every sibling catalog loader in this repo
already holds itself to.

Canonical topic file schema (a parsed mapping)::

    {
      "domain": "governance",
      "topics": [
        {
          "topic_id": "board_governance",
          "name": "board governance",
          "description": "How the board oversees strategy, risk, and management performance.",
          "aliases": ["board oversight"],
          "tags": ["governance", "board"],
          "related_topic_ids": ["committees"]
        }
      ]
    }

Canonical contract-types file schema (``/ontology/contracts.json``)::

    {
      "domain": "contracts",
      "contract_types": [
        {
          "contract_type_id": "nda",
          "name": "NDA",
          "description": "...",
          "aliases": ["non-disclosure agreement"],
          "tags": ["confidentiality"],
          "clauses": [
            {
              "clause_id": "definition_of_confidential_information",
              "name": "Definition of Confidential Information",
              "category": "required",
              "description": "...",
              "negotiation_points": ["scope of what counts as confidential"]
            }
          ]
        }
      ]
    }

Canonical relationships file schema (``/ontology/relationships.json``)::

    {
      "relationships": [
        {
          "relationship_type": "requirement_to_control",
          "subject_id": "requirement.least_privilege_access",
          "subject_label": "Least privilege access requirement",
          "object_id": "control.role_based_access_control",
          "object_label": "Role-based access control",
          "description": "..."
        }
      ]
    }
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from grc_knowledge_intelligence import KnowledgeDomain

from .enums import ClauseCategory, RelationshipType
from .models import Clause, ContractType, DomainOntology, Relationship, Topic


def _require_str(data: Mapping[str, object], key: str, *, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}: missing or empty required field {key!r}")
    return value


def _optional_str_tuple(data: Mapping[str, object], key: str, *, context: str) -> tuple[str, ...]:
    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{context}: {key!r} must be a list of strings")
    return tuple(value)


def _require_objects(
    data: Mapping[str, object], key: str, *, context: str
) -> Sequence[Mapping[str, object]]:
    value = data.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"{context}: {key!r} must be a non-empty list")
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError(f"{context}: each entry in {key!r} must be an object")
    return value


def load_topics(data: Mapping[str, object]) -> tuple[Topic, ...]:
    """Validate and translate one parsed topic file into its ``Topic``s."""
    domain = KnowledgeDomain(_require_str(data, "domain", context="topic file"))
    raw_topics = _require_objects(data, "topics", context=f"topic file for {domain.value}")
    topics = tuple(
        Topic(
            topic_id=_require_str(raw, "topic_id", context=domain.value),
            domain=domain,
            name=_require_str(raw, "name", context=domain.value),
            description=_require_str(raw, "description", context=domain.value),
            aliases=_optional_str_tuple(raw, "aliases", context=domain.value),
            tags=_optional_str_tuple(raw, "tags", context=domain.value),
            related_topic_ids=_optional_str_tuple(raw, "related_topic_ids", context=domain.value),
        )
        for raw in raw_topics
    )
    ids = [topic.topic_id for topic in topics]
    if len(ids) != len(set(ids)):
        raise ValueError(f"topic file for {domain.value} has a duplicate topic_id")
    return topics


def load_topics_file(path: Path) -> tuple[Topic, ...]:
    return load_topics(_read_json_object(path))


def _load_clause(raw: Mapping[str, object], *, context: str) -> Clause:
    return Clause(
        clause_id=_require_str(raw, "clause_id", context=context),
        name=_require_str(raw, "name", context=context),
        category=ClauseCategory(_require_str(raw, "category", context=context)),
        description=_require_str(raw, "description", context=context),
        negotiation_points=_optional_str_tuple(raw, "negotiation_points", context=context),
    )


def load_contract_types(data: Mapping[str, object]) -> tuple[ContractType, ...]:
    """Validate and translate the parsed ``/ontology/contracts.json`` file into its
    ``ContractType``s."""
    raw_contract_types = _require_objects(data, "contract_types", context="contract types file")
    contract_types = []
    for raw in raw_contract_types:
        contract_type_id = _require_str(raw, "contract_type_id", context="contract type")
        raw_clauses = _require_objects(raw, "clauses", context=contract_type_id)
        contract_types.append(
            ContractType(
                contract_type_id=contract_type_id,
                name=_require_str(raw, "name", context=contract_type_id),
                description=_require_str(raw, "description", context=contract_type_id),
                aliases=_optional_str_tuple(raw, "aliases", context=contract_type_id),
                tags=_optional_str_tuple(raw, "tags", context=contract_type_id),
                clauses=tuple(_load_clause(c, context=contract_type_id) for c in raw_clauses),
            )
        )
    ids = [ct.contract_type_id for ct in contract_types]
    if len(ids) != len(set(ids)):
        raise ValueError("contract types file has a duplicate contract_type_id")
    return tuple(contract_types)


def load_contract_types_file(path: Path) -> tuple[ContractType, ...]:
    return load_contract_types(_read_json_object(path))


def load_relationships(data: Mapping[str, object]) -> tuple[Relationship, ...]:
    """Validate and translate the parsed ``/ontology/relationships.json`` file into its
    ``Relationship``s."""
    raw_relationships = _require_objects(data, "relationships", context="relationships file")
    return tuple(
        Relationship(
            relationship_type=RelationshipType(
                _require_str(raw, "relationship_type", context="relationship")
            ),
            subject_id=_require_str(raw, "subject_id", context="relationship"),
            subject_label=_require_str(raw, "subject_label", context="relationship"),
            object_id=_require_str(raw, "object_id", context="relationship"),
            object_label=_require_str(raw, "object_label", context="relationship"),
            description=_require_str(raw, "description", context="relationship"),
        )
        for raw in raw_relationships
    )


def load_relationships_file(path: Path) -> tuple[Relationship, ...]:
    return load_relationships(_read_json_object(path))


def _read_json_object(path: Path) -> Mapping[str, object]:
    if path.suffix.lower() != ".json":
        raise ValueError(
            f"Unsupported ontology file format {path.suffix!r} for {path}; expected '.json'"
        )
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, Mapping):
        raise ValueError(f"{path} must contain an object at the top level")
    return parsed


def _derive_contract_clause_relationships(
    contract_types: Sequence[ContractType],
) -> tuple[Relationship, ...]:
    """``Contract Type -> Clause`` edges are never hand-authored in ``relationships.json`` —
    they are derived directly from the loaded contract types, so they can never drift out of
    sync with the clauses actually modeled."""
    return tuple(
        Relationship(
            relationship_type=RelationshipType.CONTRACT_TYPE_TO_CLAUSE,
            subject_id=f"contract_type.{contract_type.contract_type_id}",
            subject_label=contract_type.name,
            object_id=f"clause.{clause.clause_id}",
            object_label=clause.name,
            description=(
                f"A {contract_type.name} contract is expected to carry a "
                f"{clause.category.value} '{clause.name}' clause."
            ),
        )
        for contract_type in contract_types
        for clause in contract_type.clauses
    )


def build_ontology(
    *,
    topic_files: Iterable[Path] = (),
    contract_type_files: Iterable[Path] = (),
    relationship_files: Iterable[Path] = (),
) -> DomainOntology:
    """Build the full ``DomainOntology`` by loading every given file. Raises ``ValueError`` on
    a duplicate ``topic_id``/``contract_type_id`` across files — both are append-only keys,
    never shared between two entries."""
    topics: list[Topic] = []
    seen_topic_ids: set[str] = set()
    for path in topic_files:
        for topic in load_topics_file(path):
            if topic.topic_id in seen_topic_ids:
                raise ValueError(f"duplicate topic_id: {topic.topic_id!r}")
            seen_topic_ids.add(topic.topic_id)
            topics.append(topic)

    contract_types: list[ContractType] = []
    seen_contract_type_ids: set[str] = set()
    for path in contract_type_files:
        for contract_type in load_contract_types_file(path):
            if contract_type.contract_type_id in seen_contract_type_ids:
                raise ValueError(f"duplicate contract_type_id: {contract_type.contract_type_id!r}")
            seen_contract_type_ids.add(contract_type.contract_type_id)
            contract_types.append(contract_type)

    relationships: list[Relationship] = []
    for path in relationship_files:
        relationships.extend(load_relationships_file(path))
    relationships.extend(_derive_contract_clause_relationships(contract_types))

    return DomainOntology(
        topics=tuple(topics),
        contract_types=tuple(contract_types),
        relationships=tuple(relationships),
    )
