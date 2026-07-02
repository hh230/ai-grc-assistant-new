"""The standard agent roster (CLAUDE.md §11).

The Knowledge agent is the grounding specialist — it answers from retrieved, cited knowledge via
the RAG pipeline (read-only). The others are reasoning agents; ``Policy`` and ``Workflow`` produce
consequential output (a policy draft, a process action) and so flag for human approval.
"""
from __future__ import annotations

from grc_llm import ChatModel
from grc_rag import RagPipeline

from .base import Agent, LLMAgent
from .tasks import AgentResult, AgentRole, AgentTask


class KnowledgeAgent(Agent):
    """Answers 'what do we know?' from grounded, cited retrieval. Read-only."""

    def __init__(self, pipeline: RagPipeline, *, name: str = "knowledge_agent") -> None:
        self._pipeline = pipeline
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def role(self) -> AgentRole:
        return AgentRole.KNOWLEDGE

    async def run(self, task: AgentTask) -> AgentResult:
        answer = await self._pipeline.answer(task.goal)
        return AgentResult(
            agent=self._name,
            role=AgentRole.KNOWLEDGE,
            output=answer.answer,
            confidence=answer.confidence,
            requires_human_approval=False,
            citations=tuple(str(citation.object_id) for citation in answer.citations),
            model=answer.model,
            usage=answer.usage,
        )


class ComplianceAgent(LLMAgent):
    def __init__(self, chat: ChatModel) -> None:
        super().__init__(AgentRole.COMPLIANCE, chat, name="compliance_agent")


class RiskAgent(LLMAgent):
    def __init__(self, chat: ChatModel) -> None:
        super().__init__(AgentRole.RISK, chat, name="risk_agent")


class ReportAgent(LLMAgent):
    def __init__(self, chat: ChatModel) -> None:
        super().__init__(AgentRole.REPORT, chat, name="report_agent")


class PolicyAgent(LLMAgent):
    """Drafting/altering a policy is consequential — output is held for human sign-off."""

    def __init__(self, chat: ChatModel) -> None:
        super().__init__(AgentRole.POLICY, chat, name="policy_agent", consequential=True)


class WorkflowAgent(LLMAgent):
    """Coordinating approvals/process changes is consequential — held for human sign-off."""

    def __init__(self, chat: ChatModel) -> None:
        super().__init__(AgentRole.WORKFLOW, chat, name="workflow_agent", consequential=True)
