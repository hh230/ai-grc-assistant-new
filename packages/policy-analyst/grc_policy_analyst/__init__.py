"""grc_policy_analyst — Policy Analyst (Policy Intelligence PI-P4): a read-only agent that
analyzes an existing policy's completeness, regulatory alignment, internal consistency, and
freshness, and reports findings with evidence. See README.md.
"""

from __future__ import annotations

from .agent import AGENT_NAME, PolicyAnalystAgent
from .enums import FindingType, Severity
from .exceptions import PolicyAnalystError, PolicyNotFoundError
from .models import PolicyDocument, PolicyQualityReport, QualityFinding, RelatedObligation
from .ports import (
    ObligationRecord,
    ObligationStore,
    PolicyRecord,
    PolicyStore,
    RawDocumentRecord,
    RawDocumentStore,
)
from .quality_engine import review_policy
from .tools import (
    REVIEW_POLICY_QUALITY_TOOL_NAME,
    REVIEW_POLICY_QUALITY_TOOL_VERSION,
    QualityFindingEvidence,
    ReviewPolicyQualityInput,
    ReviewPolicyQualityOutput,
    ReviewPolicyQualityTool,
)

__all__ = [
    "AGENT_NAME",
    "REVIEW_POLICY_QUALITY_TOOL_NAME",
    "REVIEW_POLICY_QUALITY_TOOL_VERSION",
    "FindingType",
    "ObligationRecord",
    "ObligationStore",
    "PolicyAnalystAgent",
    "PolicyAnalystError",
    "PolicyDocument",
    "PolicyNotFoundError",
    "PolicyQualityReport",
    "PolicyRecord",
    "PolicyStore",
    "QualityFinding",
    "QualityFindingEvidence",
    "RawDocumentRecord",
    "RawDocumentStore",
    "RelatedObligation",
    "ReviewPolicyQualityInput",
    "ReviewPolicyQualityOutput",
    "ReviewPolicyQualityTool",
    "Severity",
    "review_policy",
]
