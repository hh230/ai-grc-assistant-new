"""The AI Orchestrator — the brain (CLAUDE.md §7).

It owns **routing** (deterministic; the LLM may reason inside an agent but does not decide control
flow), records a **decision trail** for audit, and enforces the **human gate**: an agent's
consequential output is surfaced for approval, never auto-applied. State that mutates the platform
only ever happens through Tools behind these gates — agents here propose, they do not act.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .base import Agent
from .exceptions import NoAgentForRoleError
from .tasks import AgentResult, AgentRole, AgentTask

# Deterministic routing rules, owned by the orchestrator (first match wins).
_ROUTING_RULES: tuple[tuple[str, AgentRole], ...] = (
    ("risk", AgentRole.RISK),
    ("policy", AgentRole.POLICY),
    ("report", AgentRole.REPORT),
    ("summary", AgentRole.REPORT),
    ("workflow", AgentRole.WORKFLOW),
    ("schedule", AgentRole.WORKFLOW),
    ("approval", AgentRole.WORKFLOW),
    ("gap", AgentRole.COMPLIANCE),
    ("control", AgentRole.COMPLIANCE),
    ("coverage", AgentRole.COMPLIANCE),
    ("comply", AgentRole.COMPLIANCE),
)


@dataclass(frozen=True)
class OrchestratorDecision:
    """One recorded step in the orchestrator's decision trail (auditable)."""

    step: str
    agent: str
    detail: str


@dataclass(frozen=True)
class MissionOutcome:
    """The result of handling a goal: the route taken, the agent result, the trail, the gate."""

    goal: str
    route: AgentRole
    result: AgentResult
    decisions: tuple[OrchestratorDecision, ...]
    awaiting_approval: bool


class Orchestrator:
    """Routes a goal to a governed agent, records the decision trail, and enforces human gates."""

    def __init__(self, agents: Sequence[Agent]) -> None:
        self._by_role: dict[AgentRole, Agent] = {agent.role: agent for agent in agents}

    @property
    def roles(self) -> frozenset[AgentRole]:
        return frozenset(self._by_role)

    def plan(self, goal: str) -> AgentRole:
        """Pick the agent role for a goal (deterministic; defaults to Knowledge grounding)."""
        lowered = goal.lower()
        for keyword, role in _ROUTING_RULES:
            if keyword in lowered and role in self._by_role:
                return role
        if AgentRole.KNOWLEDGE in self._by_role:
            return AgentRole.KNOWLEDGE
        raise NoAgentForRoleError("no agent available to handle the goal")

    async def run(self, goal: str, *, role: AgentRole | None = None) -> MissionOutcome:
        if not goal.strip():
            raise ValueError("goal must not be empty")
        chosen = role if role is not None else self.plan(goal)
        agent = self._by_role.get(chosen)
        if agent is None:
            raise NoAgentForRoleError(f"no agent registered for role {chosen.value}")

        decisions = [
            OrchestratorDecision(step="plan", agent=agent.name, detail=f"routed to {chosen.value}")
        ]
        result = await agent.run(AgentTask(goal=goal))
        decisions.append(
            OrchestratorDecision(step="execute", agent=agent.name, detail="agent produced a result")
        )
        if result.requires_human_approval:
            decisions.append(
                OrchestratorDecision(
                    step="human_gate",
                    agent=agent.name,
                    detail="consequential output held for human approval",
                )
            )
        return MissionOutcome(
            goal=goal,
            route=chosen,
            result=result,
            decisions=tuple(decisions),
            awaiting_approval=result.requires_human_approval,
        )
