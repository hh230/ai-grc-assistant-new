"""The Developer agent (read-only) — diagnoses and proposes a patch, nothing more (ADR 0061/0062).

Realizes the Agent protocol for AgentRole.DEVELOPER. Its job ends at engineering artifacts:
a diagnosis, an implementation plan, and a patch/diff — produced by an injected proposer (so it is
deterministic and infrastructure-independent). It knows NOTHING about Git: applying, committing,
pushing, and opening PRs are consequential Tools that run after the human approval gate, never agent
behavior. Read-only: the Developer proposes; it never lands anything.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from devteam_protocol import (
    AgentArtifact,
    AgentDecision,
    AgentRequest,
    AgentResult,
    AgentRole,
    AgentVerdict,
)

# Injected so the Developer is deterministic + infrastructure-independent (a real proposer is bound
# at composition; tests inject canned artifacts). It returns the engineering artifacts — diagnosis,
# plan, and, when a fix is found, a diff artifact (kind == "diff").
PatchProposer = Callable[[AgentRequest], Sequence[AgentArtifact]]

_DIFF = "diff"


class DeveloperAgent:
    role = AgentRole.DEVELOPER

    def __init__(self, propose: PatchProposer) -> None:
        self._propose = propose

    def handle(self, request: AgentRequest) -> AgentResult:
        artifacts = tuple(self._propose(request))
        diff = next((a.content for a in artifacts if a.kind == _DIFF), None)
        verdict = AgentVerdict.PROCEED if diff is not None else AgentVerdict.ABSTAIN
        rationale = "patch proposed" if diff is not None else "diagnosis only, no patch produced"
        # Carry the diff in the output inside a ```diff fence: artifacts are lossy at the engine
        # seam (ADR 0062), so the next step (apply_patch) reads the diff from prior_context (0051).
        output = f"Developer: {rationale}"
        if diff is not None:
            output = f"{output}\n```diff\n{diff}\n```"
        return AgentResult(
            # The step ran; the patch (or its absence) is carried by the artifacts + the decision.
            ok=True,
            output=output,
            artifacts=artifacts,
            decision=AgentDecision(
                verdict=verdict, by_role=AgentRole.DEVELOPER, rationale=rationale
            ),
        )
