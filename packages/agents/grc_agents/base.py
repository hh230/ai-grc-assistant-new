"""The Agent abstraction and the LLM-backed reasoning base.

An agent is a focused reasoning unit (CLAUDE.md §11). ``LLMAgent`` builds a role-specific prompt,
calls the provider-agnostic ``ChatModel`` in JSON mode, and validates the (untrusted) output. An
agent only **proposes**: consequential roles flag their output for human approval — they never
self-authorize a side effect (CLAUDE.md §1, §9).
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Mapping

from grc_llm import ChatMessage, ChatModel, ChatRequest

from .prompts import prompt_version, system_prompt
from .tasks import AgentResult, AgentRole, AgentTask


class Agent(ABC):
    """A specialized, governed reasoning unit. Concrete agents act only by proposing results."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def role(self) -> AgentRole: ...

    @abstractmethod
    async def run(self, task: AgentTask) -> AgentResult: ...


class LLMAgent(Agent):
    """A reasoning agent backed by a chat model, returning a validated structured result."""

    def __init__(
        self,
        role: AgentRole,
        chat: ChatModel,
        *,
        name: str | None = None,
        consequential: bool = False,
    ) -> None:
        self._role = role
        self._chat = chat
        self._name = name or f"{role.value}_agent"
        self._consequential = consequential

    @property
    def name(self) -> str:
        return self._name

    @property
    def role(self) -> AgentRole:
        return self._role

    @property
    def consequential(self) -> bool:
        return self._consequential

    async def run(self, task: AgentTask) -> AgentResult:
        request = ChatRequest(
            messages=(
                ChatMessage.system(system_prompt(self._role)),
                ChatMessage.user(_render_task(task)),
            ),
            max_output_tokens=task.max_output_tokens,
            temperature=0.0,
            json_object=True,
            prompt_version=prompt_version(self._role),
        )
        result = await self._chat.complete(request)
        output, confidence = _parse_output(result.text)
        return AgentResult(
            agent=self._name,
            role=self._role,
            output=output,
            confidence=confidence,
            requires_human_approval=self._consequential,
            model=result.model,
            usage=result.usage,
        )


def _render_task(task: AgentTask) -> str:
    lines = [f"Goal: {task.goal}"]
    lines.extend(f"{key}: {value}" for key, value in task.inputs)
    lines.append("Respond with the JSON object only.")
    return "\n".join(lines)


def _parse_output(raw_text: str) -> tuple[str, float]:
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        return ("", 0.0)
    if not isinstance(data, Mapping):
        return ("", 0.0)
    output = str(data.get("output", "")).strip()
    confidence = data.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        return (output, 0.0)
    return (output, max(0.0, min(1.0, float(confidence))))
