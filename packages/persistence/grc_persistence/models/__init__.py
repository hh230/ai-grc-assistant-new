"""SQLAlchemy ORM models — the relational shape of the domain.

Models carry *no* behavior and *no* translation logic: they are plain mapped tables.
Importing this package registers every table on :data:`Base.metadata`, which is what both
``create_all`` (tests) and Alembic (production) build from.
"""

from __future__ import annotations

from ..db.base import Base
from .assessments import AssessmentModel
from .audit import AuditRecordModel
from .controls import ControlModel
from .evidence import EvidenceModel
from .frameworks import FrameworkMappingSetModel, FrameworkModel
from .knowledge import KnowledgeSourceModel
from .missions import MissionApprovalGateModel, MissionModel, MissionStepModel
from .outbox import OutboxMessageModel
from .platform import AgentDescriptorModel, PluginDescriptorModel, ToolDescriptorModel
from .policies import PolicyModel
from .reporting import ReportModel
from .risks import RiskModel
from .tenancy import OrganizationModel, UserModel
from .workspace import WorkspaceModel

__all__ = [
    "Base",
    "OrganizationModel",
    "UserModel",
    "WorkspaceModel",
    "FrameworkModel",
    "FrameworkMappingSetModel",
    "ControlModel",
    "PolicyModel",
    "RiskModel",
    "AssessmentModel",
    "EvidenceModel",
    "KnowledgeSourceModel",
    "ReportModel",
    "ToolDescriptorModel",
    "AgentDescriptorModel",
    "PluginDescriptorModel",
    "MissionModel",
    "MissionStepModel",
    "MissionApprovalGateModel",
    "AuditRecordModel",
    "OutboxMessageModel",
]
