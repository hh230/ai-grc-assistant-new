"""grc_agents — the multi-agent layer and the AI Orchestrator (Handbook §8 milestone 12).

A roster of specialized, governed agents (Knowledge, Compliance, Risk, Policy, Report, Workflow)
that reason via the provider-agnostic ``ChatModel`` and the RAG pipeline, under an Orchestrator that
owns routing, the decision trail, and human gates. Agents only propose; consequential output is held
for human approval (CLAUDE.md §7, §11). Depends on ``grc_llm`` and ``grc_rag``.
"""
from __future__ import annotations

from .base import Agent, LLMAgent
from .exceptions import AgentError, NoAgentForRoleError
from .orchestrator import MissionOutcome, Orchestrator, OrchestratorDecision
from .roster import (
    ComplianceAgent,
    KnowledgeAgent,
    PolicyAgent,
    ReportAgent,
    RiskAgent,
    WorkflowAgent,
)
from .tasks import AgentResult, AgentRole, AgentTask

__all__ = [
    # base
    "Agent",
    "LLMAgent",
    "AgentTask",
    "AgentResult",
    "AgentRole",
    # roster
    "KnowledgeAgent",
    "ComplianceAgent",
    "RiskAgent",
    "PolicyAgent",
    "ReportAgent",
    "WorkflowAgent",
    # orchestrator
    "Orchestrator",
    "MissionOutcome",
    "OrchestratorDecision",
    # exceptions
    "AgentError",
    "NoAgentForRoleError",
]
