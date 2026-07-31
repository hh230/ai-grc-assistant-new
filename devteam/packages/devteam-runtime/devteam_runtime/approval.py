"""ApprovalGateway — the human approval path that closes a chain's attempt cycle (ADR 0044/0061).

The consequential half of a fix-it mission, over the SAME mission store the ChainDriver reads. A
chain's attempt opens a mission paused at the human gate (AWAITING_APPROVAL); approving it here
resumes the mission — apply -> commit -> push -> open_pr, one gate (ADR 0044) — to COMPLETED, and
rejecting cancels it fail-safe. Either way the mission becomes terminal, so on the next poll the
ChainDriver's is_finished sees the attempt finished and the next attempt can open (or CI goes
green). No agent self-approves a consequential action: this gateway is the seam a human operator
drives (today) or a UI/API drives later.

It reuses FixItRuntime for the resume machinery (the Git Tools). The Developer already ran BEFORE
the gate, so the proposer here is never invoked — resume runs only the already-approved
consequential steps. Approving/rejecting is by mission id, so it works after a Worker restart: the
mission is read from the (shared) store, never from Driver memory.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from devteam_contracts import platform_tenant
from devteam_protocol import AgentArtifact, AgentRequest
from devteam_tools import CommandRunner
from mission_engine.mission import Mission
from mission_engine.ports import MissionStorePort

from devteam_runtime.fix_it_runtime import FixItRuntime


class ApprovalError(RuntimeError):
    """No mission to decide on under the given id — already resolved, or never opened."""


def _no_developer_needed(_request: AgentRequest) -> Sequence[AgentArtifact]:
    # The Developer ran before the gate; resume runs only the Git steps, so this is never invoked.
    return ()


class ApprovalGateway:
    """Approve or reject a chain's gated fix-it mission, BY ID, over the shared mission store — the
    human decision that lands (or cancels) an attempt and lets the chain move on. Stateless beyond
    the store: it reads the mission fresh each time, so a restart loses nothing."""

    def __init__(
        self, store: MissionStorePort, *, repo_root: Path | str, git_runner: CommandRunner
    ) -> None:
        self._store = store
        self._runtime = FixItRuntime(
            propose=_no_developer_needed, runner=git_runner, repo_root=repo_root, store=store
        )

    def pending(self, mission_id: str) -> Mission | None:
        """The mission for review before deciding — its Developer proposal is step_results[0]."""
        return self._store.get(mission_id, platform_tenant())

    def approve(self, mission_id: str, *, principal_id: str = "devteam-approver") -> Mission:
        """Approve the paused mission and land the patch: one approval resumes apply -> commit ->
        push -> open_pr to COMPLETED (ADR 0044). Raises ApprovalError if there is no such."""
        mission = self._require(mission_id)
        return self._runtime.approve_and_resume(mission, principal_id=principal_id)

    def reject(self, mission_id: str, *, principal_id: str = "devteam-approver") -> Mission:
        """Reject the paused mission: it stops fail-safe as CANCELLED, no repository side effect."""
        mission = self._require(mission_id)
        return self._runtime.reject(mission, principal_id=principal_id)

    def _require(self, mission_id: str) -> Mission:
        mission = self._store.get(mission_id, platform_tenant())
        if mission is None:
            raise ApprovalError(f"no mission {mission_id!r} to decide on")
        return mission
