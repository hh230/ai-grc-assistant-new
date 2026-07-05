"""The classification vocabulary for regulatory obligations.

These are stable, cross-framework classification *categories* — not any single framework's
own domain/control structure. No framework name is ever hardcoded into this vocabulary
(CLAUDE.md §13): a NIST CSF requirement and an NCA ECC control classify into the same
``ControlDomain`` bucket, which is what lets Policy Hunter reason across frameworks later.
"""

from __future__ import annotations

from enum import Enum


class ObligationType(str, Enum):
    """What kind of regulatory duty an obligation expresses."""

    REQUIREMENT = "requirement"
    PROHIBITION = "prohibition"
    PERMISSION = "permission"
    REPORTING = "reporting"
    DISCLOSURE = "disclosure"
    RECORD_KEEPING = "record_keeping"
    NOTIFICATION = "notification"
    OTHER = "other"


class ControlDomain(str, Enum):
    """The cross-framework control domain an obligation most relates to."""

    GOVERNANCE = "governance"
    RISK_MANAGEMENT = "risk_management"
    ACCESS_CONTROL = "access_control"
    DATA_PROTECTION = "data_protection"
    ASSET_MANAGEMENT = "asset_management"
    PHYSICAL_SECURITY = "physical_security"
    HUMAN_RESOURCES_SECURITY = "human_resources_security"
    INCIDENT_MANAGEMENT = "incident_management"
    BUSINESS_CONTINUITY = "business_continuity"
    THIRD_PARTY_MANAGEMENT = "third_party_management"
    COMPLIANCE_MONITORING = "compliance_monitoring"
    OTHER = "other"


class Severity(str, Enum):
    """How consequential non-compliance with an obligation is."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class ClassificationStatus(str, Enum):
    """The human-review lifecycle of one classified obligation (CLAUDE.md §1: human-in-the-loop).

    Every obligation is created ``PENDING_REVIEW``; only a future human-gated review action
    moves it to ``CONFIRMED`` or ``REJECTED`` — Regulatory Intelligence never sets either of
    those itself.
    """

    PENDING_REVIEW = "pending_review"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
