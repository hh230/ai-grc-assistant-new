"""Autonomous Platform Dev Team — the agent collaboration protocol (ADR 0062/0063).

The BOUNDARY between agents: the messages they exchange, the single-method ``Agent`` protocol, the
step-level ``AgentCapability`` vocabulary, and the ``CapabilityResolver`` that maps a capability to
the agent providing it. Agents are realizations of this protocol (built after review), never the
other way round.
"""

from devteam_contracts import AgentFinding, FindingSeverity  # the one finding concept, reused

from devteam_protocol.agent import Agent
from devteam_protocol.capabilities import AgentCapability, CapabilityResolver
from devteam_protocol.mapping import agent_request_from_step, agent_result_to_step
from devteam_protocol.messages import (
    AgentArtifact,
    AgentDecision,
    AgentHandoff,
    AgentRequest,
    AgentResult,
    AgentVerdict,
)
from devteam_protocol.roles import AgentRole

__all__ = [
    "Agent",
    "AgentArtifact",
    "AgentCapability",
    "AgentDecision",
    "AgentFinding",
    "AgentHandoff",
    "AgentRequest",
    "AgentResult",
    "AgentRole",
    "AgentVerdict",
    "CapabilityResolver",
    "FindingSeverity",
    "agent_request_from_step",
    "agent_result_to_step",
]
