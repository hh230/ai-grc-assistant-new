"""Concrete repository implementations of the domain repository interfaces."""

from __future__ import annotations

from .assessments import SqlAlchemyAssessmentRepository
from .audit import SqlAlchemyAuditRecordRepository
from .controls import SqlAlchemyControlRepository
from .evidence import SqlAlchemyEvidenceRepository
from .frameworks import (
    SqlAlchemyFrameworkMappingRepository,
    SqlAlchemyFrameworkRepository,
)
from .knowledge import SqlAlchemyKnowledgeSourceRepository
from .missions import SqlAlchemyMissionRepository
from .platform import (
    SqlAlchemyAgentDescriptorRepository,
    SqlAlchemyPluginDescriptorRepository,
    SqlAlchemyToolDescriptorRepository,
)
from .policies import SqlAlchemyPolicyRepository
from .reporting import SqlAlchemyReportRepository
from .risks import SqlAlchemyRiskRepository
from .tenancy import SqlAlchemyOrganizationRepository, SqlAlchemyUserRepository
from .workspace import SqlAlchemyWorkspaceRepository

__all__ = [
    "SqlAlchemyOrganizationRepository",
    "SqlAlchemyUserRepository",
    "SqlAlchemyWorkspaceRepository",
    "SqlAlchemyFrameworkRepository",
    "SqlAlchemyFrameworkMappingRepository",
    "SqlAlchemyControlRepository",
    "SqlAlchemyPolicyRepository",
    "SqlAlchemyRiskRepository",
    "SqlAlchemyAssessmentRepository",
    "SqlAlchemyEvidenceRepository",
    "SqlAlchemyKnowledgeSourceRepository",
    "SqlAlchemyReportRepository",
    "SqlAlchemyToolDescriptorRepository",
    "SqlAlchemyAgentDescriptorRepository",
    "SqlAlchemyPluginDescriptorRepository",
    "SqlAlchemyMissionRepository",
    "SqlAlchemyAuditRecordRepository",
]
