"""The ``Agent`` protocol — the collaboration boundary itself (ADR 0061).

This is the architecture: a single-method boundary every specialist realizes, exactly as every
extractor realizes the Extraction Port (ADR 0056) and every target realizes the Projection Port
(ADR 0059). An agent declares its ``role`` and ``handle``s an ``AgentRequest`` into an
``AgentResult``. The rest of the system depends on this protocol — never on a concrete agent — so
Foreman, QA, Monitor, Security, Developer, and Reviewer are merely realizations added at the edge
without changing the Core (§17).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from devteam_protocol.messages import AgentRequest, AgentResult
from devteam_protocol.roles import AgentRole


@runtime_checkable
class Agent(Protocol):
    """A dev-team agent: it declares which role it plays and turns a request into a result. Pure
    boundary — it says nothing about how the agent reasons, what tools it uses, or how it is hosted;
    those are the realization's concern."""

    @property
    def role(self) -> AgentRole: ...

    def handle(self, request: AgentRequest) -> AgentResult: ...
