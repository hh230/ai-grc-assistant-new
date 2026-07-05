"""``PolicyAnalystAgent`` — the Policy Intelligence roster's read-only policy-quality agent
(CLAUDE.md §11: a specialized, governed reasoning unit that acts only through registered
Tools). It never performs a side effect directly; its one Tool is ``READ_ONLY`` and there is
no code path here that edits, creates, or approves a policy.
"""

from __future__ import annotations

from grc_tools import ToolContext, ToolRegistry

from .tools import (
    REVIEW_POLICY_QUALITY_TOOL_NAME,
    REVIEW_POLICY_QUALITY_TOOL_VERSION,
    ReviewPolicyQualityOutput,
)

AGENT_NAME = "policy_analyst_agent"


class PolicyAnalystAgent:
    """Reviews one tenant policy's quality — entirely by invoking its Tool through the Tool
    Registry, so every call is authorized, validated, and unconditionally audited (CLAUDE.md
    §19), exactly like any other Tool invocation. Never proposes or applies a policy change.
    """

    name = AGENT_NAME

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    async def review_policy_quality(
        self, *, tenant_id: str, policy_id: str, context: ToolContext
    ) -> ReviewPolicyQualityOutput:
        output = await self._registry.invoke(
            REVIEW_POLICY_QUALITY_TOOL_NAME,
            REVIEW_POLICY_QUALITY_TOOL_VERSION,
            {"tenant_id": tenant_id, "policy_id": policy_id},
            context,
        )
        assert isinstance(output, ReviewPolicyQualityOutput)
        return output
