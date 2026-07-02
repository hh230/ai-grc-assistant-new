"""Errors for the multi-agent layer and the orchestrator."""
from __future__ import annotations


class AgentError(Exception):
    """Base class for agent-layer errors."""


class NoAgentForRoleError(AgentError):
    """Raised when the orchestrator has no agent registered for a required role."""
