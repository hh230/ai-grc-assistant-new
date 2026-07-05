"""``PolicyBuilderAgent`` — the Policy Intelligence roster's read-only drafting agent
(CLAUDE.md §11: a specialized, governed reasoning unit that acts only through registered
Tools). It never performs a side effect directly; its one Tool is ``READ_ONLY`` and there is
no code path here that creates, edits, or approves a policy.
"""

from __future__ import annotations

from grc_tools import ToolContext, ToolRegistry

from .tools import (
    DRAFT_POLICY_FROM_OBLIGATION_TOOL_NAME,
    DRAFT_POLICY_FROM_OBLIGATION_TOOL_VERSION,
    DraftPolicyFromObligationOutput,
)

AGENT_NAME = "policy_builder_agent"


class PolicyBuilderAgent:
    """Drafts a starter policy for one confirmed obligation — entirely by invoking its Tool
    through the Tool Registry, so every call is authorized, validated, and unconditionally
    audited (CLAUDE.md §19), exactly like any other Tool invocation. Never proposes or applies
    a policy change: the draft it returns is not persisted anywhere until a human explicitly
    saves it through the existing policy-authoring workflow (ADR-0024).
    """

    name = AGENT_NAME

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    async def draft_policy_from_obligation(
        self, *, obligation_id: str, context: ToolContext
    ) -> DraftPolicyFromObligationOutput:
        output = await self._registry.invoke(
            DRAFT_POLICY_FROM_OBLIGATION_TOOL_NAME,
            DRAFT_POLICY_FROM_OBLIGATION_TOOL_VERSION,
            {"obligation_id": obligation_id},
            context,
        )
        assert isinstance(output, DraftPolicyFromObligationOutput)
        return output
