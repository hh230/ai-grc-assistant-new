"""Enums for the Autonomous Knowledge Engine (KI-P1, ADR-0025)."""

from __future__ import annotations

from enum import Enum


class KnowledgeDomain(str, Enum):
    """The GRC/legal domains the Knowledge Question Generator covers."""

    GOVERNANCE = "governance"
    RISK_MANAGEMENT = "risk_management"
    COMPLIANCE = "compliance"
    INTERNAL_CONTROLS = "internal_controls"
    AUDIT = "audit"
    CONTRACTS = "contracts"
    VENDOR_MANAGEMENT = "vendor_management"
    DATA_PROTECTION = "data_protection"
    CYBERSECURITY_GOVERNANCE = "cybersecurity_governance"
    POLICIES_PROCEDURES = "policies_procedures"
    REGULATORY_OBLIGATIONS = "regulatory_obligations"


class TrustedSourceType(str, Enum):
    """The only source types the Knowledge Engine is allowed to research from ("Do not use
    random blogs" — ADR-0025). A source that cannot be classified as one of these is not a
    valid ``TrustedSource`` at all; this is structural enforcement, not a docstring promise."""

    GOVERNMENT_REGULATOR = "government_regulator"
    OFFICIAL_FRAMEWORK = "official_framework"
    STANDARDS_BODY = "standards_body"
    LAW_REGULATION = "law_regulation"
    OFFICIAL_GUIDANCE = "official_guidance"


class VerificationStatus(str, Enum):
    """Knowledge is never absolute (ADR-0025 §6). Every ``KnowledgeItem`` starts
    ``DISCOVERED`` and only a human decision moves it to ``VERIFIED`` — the same
    never-auto-confirm posture ``grc_regulatory_intelligence``'s ``ClassificationStatus``
    already established for regulatory obligations."""

    DISCOVERED = "discovered"
    VERIFIED = "verified"
    NEEDS_REVIEW = "needs_review"
    OUTDATED = "outdated"


class GapStatus(str, Enum):
    """What the Knowledge Gap Detector found when it checked one question against the
    knowledge repository."""

    MISSING = "missing"
    OUTDATED = "outdated"
    WEAK_CONFIDENCE = "weak_confidence"
    ANSWERED = "answered"
