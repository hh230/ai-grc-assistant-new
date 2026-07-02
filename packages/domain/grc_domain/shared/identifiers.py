"""Typed identifier value objects (shared kernel).

All entity identifiers live here so cross-context references use IDs only — never
imports of other aggregates — which keeps the bounded contexts free of cycles.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class EntityId:
    """Base identifier value object. Identity is the wrapped, non-empty string value."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise ValueError("EntityId value must be a non-empty string")

    @classmethod
    def generate(cls) -> EntityId:
        """Generate a new random identifier (UUID4)."""
        return cls(str(uuid.uuid4()))

    def __str__(self) -> str:
        return self.value


# --- Tenancy / identity ---
class OrganizationId(EntityId):
    """Identifies a tenant organization."""


class UserId(EntityId):
    """Identifies a user within an organization."""


# --- Workspace ---
class WorkspaceId(EntityId):
    """Identifies a workspace."""


# --- Frameworks (stable, human-meaningful ids, e.g. 'framework:nca_ecc') ---
class FrameworkId(EntityId):
    """Stable framework identifier. Frameworks are data; ids are not random UUIDs."""


class FrameworkControlId(EntityId):
    """Identifies a control/requirement node inside a framework definition."""


class FrameworkMappingId(EntityId):
    """Identifies a cross-framework mapping set."""


# --- Controls / policies / risks / evidence / assessments / reporting ---
class ControlId(EntityId):
    """Identifies a customer control implementation."""


class PolicyId(EntityId):
    """Identifies a policy."""


class RiskId(EntityId):
    """Identifies a risk."""


class AssessmentId(EntityId):
    """Identifies an assessment."""


class EvidenceId(EntityId):
    """Identifies an evidence artifact."""


class ReportId(EntityId):
    """Identifies a report."""


# --- Knowledge (the canonical structured-knowledge bounded context) ---
class KnowledgeSourceId(EntityId):
    """Identifies a knowledge source: the stable logical work (a law, standard, policy...)."""


class KnowledgeSourceVersionId(EntityId):
    """Identifies one immutable, effective-dated version of a knowledge source."""


class KnowledgeDocumentId(EntityId):
    """Identifies a physical manifestation (one language/format) of a source version."""


class KnowledgeSectionId(EntityId):
    """Identifies a structural unit (article/clause/section) within a document."""


class CanonicalKnowledgeObjectId(EntityId):
    """Identifies the stable lineage identity that groups a knowledge object's revisions."""


class KnowledgeObjectId(EntityId):
    """Identifies one immutable, version-pinned revision of an extracted knowledge object."""


class KnowledgeRelationshipId(EntityId):
    """Identifies a typed relationship (graph edge) between knowledge objects/sections."""


class ExtractionRunId(EntityId):
    """Identifies a run of the Knowledge Extraction Engine (for provenance/lineage)."""


class StageExecutionId(EntityId):
    """Identifies one execution of a single stage within an extraction run."""


# --- Platform: tools / agents / plugins ---
class ToolId(EntityId):
    """Identifies a registered tool."""


class AgentId(EntityId):
    """Identifies a registered agent."""


class PluginId(EntityId):
    """Identifies an installed plugin."""


# --- Missions ---
class MissionId(EntityId):
    """Identifies a mission."""


class MissionStepId(EntityId):
    """Identifies a step within a mission plan."""


class ApprovalGateId(EntityId):
    """Identifies a human approval gate within a mission."""


# --- Audit ---
class AuditRecordId(EntityId):
    """Identifies an append-only audit record."""
