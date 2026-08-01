"""Autonomous Platform Dev Team — the agents (realizations of the Agent protocol, ADR 0062/0063).

Each agent realizes devteam_protocol.Agent and runs behind an AgentTool through the one Tool
execution path (ADR 0062/0063): the Mission Engine resolves a step to a Tool via the Tool Registry;
an AgentTool resolves the capability to an agent (CapabilityResolver) and invokes it. New agents are
added by writing a realization and mapping a capability to it — no Core change (§17).
"""

from devteam_agents.agent_tool import AgentTool, build_agent_registry
from devteam_agents.analysis_proposer import AnalysisProposer
from devteam_agents.developer import DeveloperAgent, PatchProposer
from devteam_agents.foreman import Foreman
from devteam_agents.monitor import MonitorAgent
from devteam_agents.qa import QaAgent, SuiteRunner
from devteam_agents.resolver import MapCapabilityResolver
from devteam_agents.reviewer import ReviewerAgent
from devteam_agents.security import SecurityAgent

__all__ = [
    "AgentTool",
    "AnalysisProposer",
    "DeveloperAgent",
    "Foreman",
    "MapCapabilityResolver",
    "MonitorAgent",
    "PatchProposer",
    "QaAgent",
    "ReviewerAgent",
    "SecurityAgent",
    "SuiteRunner",
    "build_agent_registry",
]
