"""MapCapabilityResolver — the composition-root map from capability to agent (ADR 0063).

The concrete CapabilityResolver: a {AgentCapability: Agent} map built at wiring time. Adding or
reassigning a capability is a map edit — the Foreman (which plans in capabilities) and the executor
(which depends only on the CapabilityResolver port) never change.
"""

from __future__ import annotations

from collections.abc import Mapping

from devteam_protocol import Agent, AgentCapability


class MapCapabilityResolver:
    """A CapabilityResolver backed by an explicit {capability: agent} map. Realizes the port
    structurally. An unprovided capability raises loudly rather than silently doing nothing."""

    def __init__(self, agents: Mapping[AgentCapability, Agent]) -> None:
        self._agents = dict(agents)

    def resolve(self, capability: AgentCapability) -> Agent:
        agent = self._agents.get(capability)
        if agent is None:
            raise KeyError(f"no agent provides capability {capability.value!r}")
        return agent
