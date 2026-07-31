"""Reading the inbox — how an organization agent sees the work handed to it (ADR 0051/0062).

Each stage runs behind an ``AgentTool``, which folds the prior step's output onto the request's
``inbox`` (a handoff carrying a ``prior_step`` artifact). These helpers read that inbox so a
downstream agent (the CTO reading the CEO's strategy, the DevTeam reading everyone) works from real
upstream context — never re-derives it, never invents it.
"""

from __future__ import annotations

from devteam_protocol import AgentRequest


def inbox_text(request: AgentRequest) -> str:
    """The concatenated content of everything handed to this agent, or "" for the first stage."""
    if request.inbox is None:
        return ""
    return "\n\n".join(artifact.content for artifact in request.inbox.artifacts if artifact.content)


def has_shortfall(text: str) -> bool:
    """Whether upstream context reports a blocking shortfall a later stage must not paper over: a
    security BLOCK, a requested change, an escalation, or QA reporting fewer green suites than run.
    Read from the real handoff text (the agents write these markers into their output)."""
    lowered = text.lower()
    if any(marker in lowered for marker in ("blocked", "request_changes", "escalate")):
        return True
    return _qa_shortfall(lowered)


def _qa_shortfall(lowered_text: str) -> bool:
    """QA writes "N/M suites green"; N < M is a real shortfall signal carried across the handoff."""
    import re

    match = re.search(r"(\d+)/(\d+) suites green", lowered_text)
    return match is not None and int(match.group(1)) < int(match.group(2))
