"""``StepCapture`` — the one-slot courier between the agent boundary and the executor boundary.

The tool boundary drops the mission ids (the ``AgentTool`` builds an ``AgentRequest`` without them)
and folds the rich ``AgentResult`` to a plain ``StepResult`` — so neither boundary sees BOTH the
mission context AND the agent's work-product. This bridges it: the ``ResultCourier`` (at the agent
boundary) drops the just-run agent's whole ``AgentResult`` here, and the ``ObservingExecutor`` (at
the mission-bound step boundary) takes it to build the session — decision, declared handoff,
artifacts, and output summary.

One slot is enough because the DevTeam runtime is single-threaded and runs one step at a time;
``clear`` before a step and ``take`` after guarantee a non-agent step never reads a stale result.
"""

from __future__ import annotations

from dataclasses import dataclass

from devteam_protocol import AgentResult


@dataclass
class StepCapture:
    """A single ``AgentResult`` slot handed between the two boundaries of one step."""

    result: AgentResult | None = None

    def put(self, result: AgentResult) -> None:
        self.result = result

    def take(self) -> AgentResult | None:
        """Read and clear the slot — so the next step starts empty."""
        result = self.result
        self.result = None
        return result

    def clear(self) -> None:
        self.result = None
