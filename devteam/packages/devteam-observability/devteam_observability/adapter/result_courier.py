"""``ResultCourier`` — carries an agent's full result to the executor without changing the agent.

A structural realization of ``devteam_protocol.Agent`` (a ``role`` and a ``handle``) that WRAPS a
real dev-team agent. ``handle`` runs the wrapped agent unchanged, drops its whole ``AgentResult``
into the shared ``StepCapture``, and returns it untouched — so the agent behaves exactly as before
(the mission still gets the same result), while the ``ObservingExecutor`` gains the decision, the
declared handoff, the artifacts, and the output the tool boundary would otherwise fold away. This is
how the session's rich fields are captured with zero change to Foreman, QA, Developer, Reviewer,
Security, or Monitor.
"""

from __future__ import annotations

from devteam_protocol import Agent, AgentRequest, AgentResult, AgentRole

from devteam_observability.adapter.capture import StepCapture


class ResultCourier:
    """Wraps a dev-team agent to courier its result to the executor boundary. Read-through:
    ``handle`` returns exactly what the wrapped agent returns."""

    def __init__(self, agent: Agent, capture: StepCapture) -> None:
        self._agent = agent
        self._capture = capture

    @property
    def role(self) -> AgentRole:
        return self._agent.role

    def handle(self, request: AgentRequest) -> AgentResult:
        result = self._agent.handle(request)
        self._capture.put(result)
        return result
