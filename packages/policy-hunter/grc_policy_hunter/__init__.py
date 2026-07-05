"""grc_policy_hunter — Policy Hunter (Policy Intelligence PI-P3): a read-only agent that
compares confirmed regulatory obligations against tenant policies and reports coverage gaps
with evidence. See README.md.
"""

from __future__ import annotations

from .agent import AGENT_NAME, PolicyHunterAgent
from .enums import GapCategory
from .matching import scan_coverage
from .models import CoverageScanResult, GapFinding, ObligationSummary, PolicySummary
from .ports import (
    ObligationRecord,
    ObligationStore,
    PolicyRecord,
    PolicyStore,
    RawDocumentRecord,
    RawDocumentStore,
)
from .tools import (
    LIST_APPLICABLE_OBLIGATIONS_TOOL_NAME,
    LIST_APPLICABLE_OBLIGATIONS_TOOL_VERSION,
    SCAN_POLICY_COVERAGE_GAPS_TOOL_NAME,
    SCAN_POLICY_COVERAGE_GAPS_TOOL_VERSION,
    GapFindingEvidence,
    ListApplicableObligationsInput,
    ListApplicableObligationsOutput,
    ListApplicableObligationsTool,
    ObligationEvidence,
    ScanPolicyCoverageGapsInput,
    ScanPolicyCoverageGapsOutput,
    ScanPolicyCoverageGapsTool,
)

__all__ = [
    "AGENT_NAME",
    "LIST_APPLICABLE_OBLIGATIONS_TOOL_NAME",
    "LIST_APPLICABLE_OBLIGATIONS_TOOL_VERSION",
    "SCAN_POLICY_COVERAGE_GAPS_TOOL_NAME",
    "SCAN_POLICY_COVERAGE_GAPS_TOOL_VERSION",
    "CoverageScanResult",
    "GapCategory",
    "GapFinding",
    "GapFindingEvidence",
    "ListApplicableObligationsInput",
    "ListApplicableObligationsOutput",
    "ListApplicableObligationsTool",
    "ObligationEvidence",
    "ObligationRecord",
    "ObligationStore",
    "ObligationSummary",
    "PolicyHunterAgent",
    "PolicyRecord",
    "PolicyStore",
    "PolicySummary",
    "RawDocumentRecord",
    "RawDocumentStore",
    "ScanPolicyCoverageGapsInput",
    "ScanPolicyCoverageGapsOutput",
    "ScanPolicyCoverageGapsTool",
    "scan_coverage",
]
