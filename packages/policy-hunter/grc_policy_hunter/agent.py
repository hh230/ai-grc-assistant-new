"""``PolicyHunterAgent`` — the Policy Intelligence roster's read-only coverage-gap agent
(CLAUDE.md §11: a specialized, governed reasoning unit that acts only through registered
Tools). It never performs a side effect directly; both of its Tools are ``READ_ONLY`` and
there is no code path here that writes anything.
"""

from __future__ import annotations

from grc_tools import ToolContext, ToolRegistry

from .tools import (
    LIST_APPLICABLE_OBLIGATIONS_TOOL_NAME,
    LIST_APPLICABLE_OBLIGATIONS_TOOL_VERSION,
    SCAN_POLICY_COVERAGE_GAPS_TOOL_NAME,
    SCAN_POLICY_COVERAGE_GAPS_TOOL_VERSION,
    ListApplicableObligationsOutput,
    ScanPolicyCoverageGapsOutput,
)

AGENT_NAME = "policy_hunter_agent"


class PolicyHunterAgent:
    """Reads confirmed regulatory obligations and a tenant's policies, and reports coverage
    gaps — entirely by invoking its two Tools through the Tool Registry, so every call is
    authorized, validated, and unconditionally audited (CLAUDE.md §19), exactly like any
    other Tool invocation. Never proposes or applies a policy change.
    """

    name = AGENT_NAME

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    async def list_applicable_obligations(
        self, *, control_domain: str | None, context: ToolContext
    ) -> ListApplicableObligationsOutput:
        output = await self._registry.invoke(
            LIST_APPLICABLE_OBLIGATIONS_TOOL_NAME,
            LIST_APPLICABLE_OBLIGATIONS_TOOL_VERSION,
            {"control_domain": control_domain},
            context,
        )
        assert isinstance(output, ListApplicableObligationsOutput)
        return output

    async def scan_policy_coverage_gaps(
        self, *, tenant_id: str, control_domain: str | None, context: ToolContext
    ) -> ScanPolicyCoverageGapsOutput:
        output = await self._registry.invoke(
            SCAN_POLICY_COVERAGE_GAPS_TOOL_NAME,
            SCAN_POLICY_COVERAGE_GAPS_TOOL_VERSION,
            {"tenant_id": tenant_id, "control_domain": control_domain},
            context,
        )
        assert isinstance(output, ScanPolicyCoverageGapsOutput)
        return output
