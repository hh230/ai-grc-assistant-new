"""AgentTool — every agent executable through the one Tool contract (ADR 0062/0063).

Instead of a dedicated agent executor + branching routing, an agent runs behind a Tool adapter: the
Mission Engine's existing tool-execution path resolves a step to this Tool via the Tool Registry and
invokes it; the Tool resolves the capability to an Agent via the CapabilityResolver and invokes it.
One execution path, one registry, one model. The agent stays a pure reasoning realization; Git and
every other consequential Tool sit on the same path.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from devteam_protocol import (
    Agent,
    AgentArtifact,
    AgentCapability,
    AgentHandoff,
    AgentRequest,
    AgentRole,
    CapabilityResolver,
)
from pipeline_contracts import TenantContext
from tool_registry import ToolRegistry
from tool_registry.result import PAYLOAD_INSTRUCTION, PAYLOAD_PRIOR_CONTEXT, ToolStepResult
from tool_registry.spec import SideEffectProfile, ToolSpec
from tool_registry.tool import Tool

from devteam_agents.resolver import MapCapabilityResolver


class AgentTool:
    """A Tool that invokes the agent for a capability, registered under the capability's value.
    A plan routing PlanStep.tool = capability runs it through the one tool path. Read-only: the
    agent reasons and produces artifacts; consequential work is other Tools (Git, etc.)."""

    def __init__(self, capability: AgentCapability, resolver: CapabilityResolver) -> None:
        self._capability = capability
        self._resolver = resolver

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self._capability.value,
            version=1,
            description=f"Runs the {self._capability.value} agent.",
            side_effect=SideEffectProfile.READ_ONLY,
        )

    def invoke(self, payload: dict[str, object], tenant: TenantContext) -> dict[str, object]:
        agent = self._resolver.resolve(self._capability)
        prior = str(payload.get(PAYLOAD_PRIOR_CONTEXT, ""))
        inbox = _inbox_from_prior(prior, agent.role) if prior.strip() else None
        request = AgentRequest(
            role=agent.role,
            intent=str(payload.get(PAYLOAD_INSTRUCTION, "")),
            tenant=tenant,
            inbox=inbox,
        )
        result = agent.handle(request)
        return ToolStepResult(
            ok=result.ok,
            output=result.output,
            source_ids=result.source_ids,
            confidence=result.confidence,
            warnings=result.warnings,
        ).as_payload()


def _inbox_from_prior(prior: str, to_role: AgentRole) -> AgentHandoff:
    """Wrap the prior-step output (ADR 0051, carried on PAYLOAD_PRIOR_CONTEXT) into an inbox handoff
    the receiving agent reads. from_role is the receiving role, a seam placeholder."""
    return AgentHandoff(
        from_role=to_role,
        to_role=to_role,
        reason="prior step output",
        artifacts=(AgentArtifact(kind="prior_step", title="prior", content=prior),),
    )


def build_agent_registry(
    agents: Mapping[AgentCapability, Agent], *, extra_tools: Iterable[Tool] = ()
) -> ToolRegistry:
    """Build the one Tool Registry the dev team executes through: an AgentTool per capability (so a
    capability-routed plan resolves to its agent) plus any extra Tools — check_repo_health and the
    consequential Git Tools. One CapabilityResolver backs every AgentTool."""
    resolver = MapCapabilityResolver(agents)
    registry = ToolRegistry()
    for capability in agents:
        registry.register(AgentTool(capability, resolver))
    for tool in extra_tools:
        registry.register(tool)
    return registry
