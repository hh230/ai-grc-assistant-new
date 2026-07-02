"""The task an agent is asked to perform and the result it returns.

Results carry the agent, its confidence, the model/usage (for audit, CLAUDE.md §19), any citation
keys, and a ``requires_human_approval`` flag — agents *propose*; a human decides on consequential
output (CLAUDE.md §1, §11).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from grc_llm import TokenUsage


class AgentRole(str, Enum):
    """The specialized agent roster (CLAUDE.md §11)."""

    KNOWLEDGE = "knowledge"
    COMPLIANCE = "compliance"
    RISK = "risk"
    POLICY = "policy"
    REPORT = "report"
    WORKFLOW = "workflow"


@dataclass(frozen=True)
class AgentTask:
    """A unit of work handed to an agent: a goal plus optional named context inputs."""

    goal: str
    inputs: tuple[tuple[str, str], ...] = ()
    max_output_tokens: int = 512

    def __post_init__(self) -> None:
        if not self.goal.strip():
            raise ValueError("AgentTask goal must not be empty")
        if self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be > 0")


@dataclass(frozen=True)
class AgentResult:
    """What an agent produced: its output, grounding, confidence, and approval status."""

    agent: str
    role: AgentRole
    output: str
    confidence: float
    requires_human_approval: bool
    citations: tuple[str, ...] = ()
    model: str = ""
    usage: TokenUsage = field(default_factory=TokenUsage)
