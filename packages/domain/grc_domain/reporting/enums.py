"""Enumerations for the Reporting bounded context."""
from __future__ import annotations

from enum import Enum


class ReportType(str, Enum):
    GAP_ANALYSIS = "gap_analysis"
    EXECUTIVE_SUMMARY = "executive_summary"
    EVIDENCE_PACK = "evidence_pack"
    ATTESTATION = "attestation"
    RISK_REGISTER = "risk_register"


class ReportStatus(str, Enum):
    REQUESTED = "requested"
    GENERATED = "generated"
    FINALIZED = "finalized"
    PUBLISHED = "published"
