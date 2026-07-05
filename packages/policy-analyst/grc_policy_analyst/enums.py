"""The finding taxonomy Policy Analyst reports issues in — one enum member per concrete,
deterministic check in ``quality_engine.py``, grouped by the four analysis dimensions
CLAUDE.md-aligned GRC review covers: completeness, regulatory alignment, internal
consistency, and freshness.
"""

from __future__ import annotations

from enum import Enum


class FindingType(str, Enum):
    # --- completeness ---
    MISSING_REQUIRED_SECTION = "missing_required_section"

    # --- regulatory alignment ---
    MISSING_CLAUSE = "missing_clause"
    WEAK_REGULATORY_COVERAGE = "weak_regulatory_coverage"
    OUTDATED_REFERENCE = "outdated_reference"

    # --- internal consistency ---
    CONFLICTING_REQUIREMENTS = "conflicting_requirements"
    UNCLEAR_OWNERSHIP = "unclear_ownership"
    AMBIGUOUS_LANGUAGE = "ambiguous_language"

    # --- freshness ---
    STALE_POLICY = "stale_policy"
    POLICY_OLDER_THAN_REGULATION = "policy_older_than_regulation"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"
