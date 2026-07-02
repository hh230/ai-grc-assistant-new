"""Enumerations for the Knowledge bounded context.

These describe the *canonical structured-knowledge* model — not RAG/ingestion state.
Document parsing, chunking, embedding, and retrieval are infrastructure concerns that live
outside the domain and are deliberately absent here.
"""
from __future__ import annotations

from enum import Enum


class KnowledgeScopeKind(str, Enum):
    """Whether knowledge is platform-global (shared) or isolated to one tenant."""

    GLOBAL = "global"
    ORGANIZATION = "organization"


class KnowledgeDomain(str, Enum):
    """The high-level category a source belongs to (a facet, not a rigid tree)."""

    LEGAL_REGULATORY = "legal_regulatory"
    STANDARDS_FRAMEWORKS = "standards_frameworks"
    GOVERNANCE = "governance"
    ORGANIZATIONAL = "organizational"
    OPERATIONAL = "operational"


class DocumentType(str, Enum):
    """The kind of document a source is (controlled vocabulary, extensible)."""

    LAW = "law"
    EXECUTIVE_REGULATION = "executive_regulation"
    GOVERNMENT_GUIDE = "government_guide"
    STANDARD = "standard"
    FRAMEWORK = "framework"
    POLICY = "policy"
    PROCEDURE = "procedure"
    TEMPLATE = "template"
    CONTRACT = "contract"
    INTERNAL_DOCUMENT = "internal_document"
    OTHER = "other"


class DocumentFormat(str, Enum):
    """Physical file format of a document manifestation."""

    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    HTML = "html"
    MARKDOWN = "markdown"
    TXT = "txt"


class SectionType(str, Enum):
    """The structural role of a section — the basis of a stable citation anchor."""

    PART = "part"
    CHAPTER = "chapter"
    ARTICLE = "article"
    CLAUSE = "clause"
    SECTION = "section"
    SUBSECTION = "subsection"
    ANNEX = "annex"
    SCHEDULE = "schedule"
    APPENDIX = "appendix"


class VersionStatus(str, Enum):
    """Governance lifecycle of a source version (NOT ingestion/processing state)."""

    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"
    ARCHIVED = "archived"
    REJECTED = "rejected"


class KnowledgeObjectType(str, Enum):
    """The type of an extracted knowledge object (the ontology of facts)."""

    DEFINITION = "definition"
    REQUIREMENT = "requirement"
    CONTROL = "control"
    OBLIGATION = "obligation"
    PROHIBITION = "prohibition"
    RIGHT = "right"
    RISK = "risk"
    ROLE = "role"
    PROCESS = "process"
    PENALTY = "penalty"
    EVIDENCE_EXPECTATION = "evidence_expectation"
    METRIC = "metric"
    CONDITION = "condition"
    REFERENCE = "reference"
    TERM_DATE = "term_date"


class NormativeStrength(str, Enum):
    """How binding a statement is (derived from deontic/modal cues — shall/should/may)."""

    MANDATORY = "mandatory"
    RECOMMENDED = "recommended"
    PERMITTED = "permitted"
    INFORMATIVE = "informative"


class CurationStatus(str, Enum):
    """Curation lifecycle shared by knowledge objects and relationships.

    Captures the human-in-the-loop gate: extracted facts are reviewed before they are
    published, and superseded (not edited) when knowledge changes.
    """

    EXTRACTED = "extracted"
    IN_REVIEW = "in_review"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class RelationshipPredicate(str, Enum):
    """The typed edge vocabulary that turns isolated facts into a knowledge graph."""

    SATISFIED_BY = "satisfied_by"
    IMPLEMENTS = "implements"
    MAPPED_TO = "mapped_to"
    IMPOSED_ON = "imposed_on"
    ARISES_FROM = "arises_from"
    USED_BY = "used_by"
    REFERENCES = "references"
    MITIGATED_BY = "mitigated_by"
    FULFILLS = "fulfills"
    PERFORMED_BY = "performed_by"
    EXECUTES = "executes"
    APPLIES_TO = "applies_to"
    PARENT_OF = "parent_of"
    CITED_FROM = "cited_from"


class RelationshipEndpointKind(str, Enum):
    """What a relationship endpoint points at."""

    KNOWLEDGE_OBJECT = "knowledge_object"
    SECTION = "section"
    FRAMEWORK_CONTROL = "framework_control"


class DerivationMethod(str, Enum):
    """How a fact/relationship was derived (for provenance and trust)."""

    AUTOMATIC = "automatic"
    CURATED = "curated"
    MANUAL = "manual"
