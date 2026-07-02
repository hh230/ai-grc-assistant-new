"""Enumerations for the Tenancy/Identity bounded context."""
from __future__ import annotations

from enum import Enum


class OrganizationStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class UserStatus(str, Enum):
    INVITED = "invited"
    ACTIVE = "active"
    DEACTIVATED = "deactivated"


class UserRole(str, Enum):
    """Coarse RBAC roles. Fine-grained permissions are enforced at the application layer."""

    OWNER = "owner"
    ADMIN = "admin"
    COMPLIANCE_MANAGER = "compliance_manager"
    RISK_MANAGER = "risk_manager"
    ANALYST = "analyst"
    AUDITOR = "auditor"
    VIEWER = "viewer"
