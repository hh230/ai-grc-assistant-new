"""Enumerations for the Audit bounded context."""
from __future__ import annotations

from enum import Enum


class AuditCategory(str, Enum):
    """High-level category of an audited action."""

    AI_DECISION = "ai_decision"
    HUMAN_APPROVAL = "human_approval"
    STATE_CHANGE = "state_change"
    ACCESS = "access"
    INGESTION = "ingestion"
    TENANCY = "tenancy"
