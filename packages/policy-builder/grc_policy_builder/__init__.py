"""grc_policy_builder — Policy Builder (Policy Intelligence PI-P7): a read-only agent that
drafts a starter policy from one confirmed regulatory obligation, for human review. See
README.md.
"""

from __future__ import annotations

from .agent import AGENT_NAME, PolicyBuilderAgent
from .drafting import draft_policy
from .exceptions import ObligationNotFoundError, PolicyBuilderError
from .models import ObligationForDrafting, PolicyDraft
from .ports import (
    ObligationRecord,
    ObligationStore,
    RawDocumentRecord,
    RawDocumentStore,
)
from .tools import (
    DRAFT_POLICY_FROM_OBLIGATION_TOOL_NAME,
    DRAFT_POLICY_FROM_OBLIGATION_TOOL_VERSION,
    DraftPolicyFromObligationInput,
    DraftPolicyFromObligationOutput,
    DraftPolicyFromObligationTool,
    PolicyDraftEvidence,
)

__all__ = [
    "AGENT_NAME",
    "DRAFT_POLICY_FROM_OBLIGATION_TOOL_NAME",
    "DRAFT_POLICY_FROM_OBLIGATION_TOOL_VERSION",
    "DraftPolicyFromObligationInput",
    "DraftPolicyFromObligationOutput",
    "DraftPolicyFromObligationTool",
    "ObligationForDrafting",
    "ObligationNotFoundError",
    "ObligationRecord",
    "ObligationStore",
    "PolicyBuilderAgent",
    "PolicyBuilderError",
    "PolicyDraft",
    "PolicyDraftEvidence",
    "RawDocumentRecord",
    "RawDocumentStore",
    "draft_policy",
]
