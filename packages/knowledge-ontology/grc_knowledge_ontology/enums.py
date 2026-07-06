"""Enums for the Domain Ontology Engine (KI-P3)."""

from __future__ import annotations

from enum import Enum


class ClauseCategory(str, Enum):
    """The role one contract clause plays, for missing-clause detection and negotiation
    guidance. A clause is exactly one of these — never inferred, always curated."""

    REQUIRED = "required"
    RISK = "risk"
    PROTECTIVE = "protective"


class RelationshipType(str, Enum):
    """The fixed vocabulary of edges the ontology can express between GRC concepts. Deliberately
    a closed enum, not a free-text string — "what kinds of relationships exist in this domain"
    is a curated, reviewable decision, the same posture ADR-0025 already took for
    ``TrustedSourceType``."""

    REQUIREMENT_TO_CONTROL = "requirement_to_control"
    CONTROL_TO_EVIDENCE = "control_to_evidence"
    RISK_TO_CONTROL = "risk_to_control"
    CONTRACT_TYPE_TO_CLAUSE = "contract_type_to_clause"
    REGULATION_TO_OBLIGATION = "regulation_to_obligation"
    POLICY_TO_REQUIREMENT = "policy_to_requirement"
