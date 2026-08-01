"""FixItRuntime — the gated fix-it mission end to end, in-memory (ADR 0061/0044/0048).

Composition only (no new abstractions): the Foreman plans the fix-it mission (the Developer
diagnoses and proposes a diff, then the Git Tools land it), and the frozen MissionEngine drives it
over the one Tool path. Because the plan places a SINGLE consequential gate (apply_patch), the
engine pauses once at AWAITING_APPROVAL before any repository side effect; after a human approves it
runs apply -> commit -> push -> open_pr automatically (ADR 0044). Reasoning (the Developer) and
execution (the Git Tools) are injected — a PatchProposer and a CommandRunner — so this is
deterministic and DB-free. The durable path (Postgres store) swaps in later; plan and tools stay.
"""

from __future__ import annotations

from pathlib import Path

from devteam_agents import DeveloperAgent, Foreman, PatchProposer, build_agent_registry
from devteam_contracts import platform_tenant
from devteam_observability import DevTeamObservability
from devteam_protocol import AgentCapability
from devteam_tools import (
    ApplyPatchTool,
    CommandRunner,
    CommitChangesTool,
    OpenPrTool,
    PushBranchTool,
)
from event_bus import ALL_EVENTS, InProcessEventBus
from mission_engine import MissionEngine
from mission_engine.adapters import InMemoryMissionStore
from mission_engine.lifecycle import MissionStatus
from mission_engine.mission import Mission
from mission_engine.ports import ExecutionPort, MissionStorePort
from mission_integration.audit import MissionAuditSink

from devteam_runtime.executor import DevToolExecutor

_DIFF_FENCE = "```diff"
# When the Developer produces no patch there is nothing to apply — and so nothing for a human to
# approve. The mission ends fail-safe with this reason instead of presenting a meaningless gate.
NO_PATCH_REASON = "human intervention required: the Developer produced no patch"


def _has_patch(mission: Mission) -> bool:
    """True if a step carries a diff. The Developer puts its patch in a ```diff fence (artifacts are
    lossy at the engine seam, ADR 0062), so that fence in a step's output is the signal."""
    return any(_DIFF_FENCE in result.output for result in mission.step_results)


class FixItRuntime:
    """In-memory composition that runs the gated fix-it mission. Inject the PatchProposer (the
    Developer's reasoning) and the CommandRunner (git/gh execution). ``open_fix_it`` drives the
    mission to the approval gate; ``approve_and_resume`` lands the patch; ``reject`` cancels it."""

    def __init__(
        self,
        *,
        propose: PatchProposer,
        runner: CommandRunner,
        repo_root: Path | str,
        foreman: Foreman | None = None,
        store: MissionStorePort | None = None,
        observability: DevTeamObservability | None = None,
    ) -> None:
        self._events = InProcessEventBus()
        self._audit = MissionAuditSink()
        self._events.subscribe(ALL_EVENTS, self._audit.record)
        self._observability = observability
        # Opt-in observability (see AgentMissionRuntime): courier-wrap the Developer and wrap the
        # executor when injected; the daemon injects nothing, so its behavior is unchanged. The Git
        # tools are not agents, so the ObservingExecutor passes their steps straight through.
        agents = {AgentCapability.IMPLEMENTATION: DeveloperAgent(propose)}
        registry = build_agent_registry(
            observability.observe_agents(agents) if observability is not None else agents,
            extra_tools=(
                ApplyPatchTool(repo_root, runner),
                CommitChangesTool(repo_root, runner),
                PushBranchTool(repo_root, runner),
                OpenPrTool(repo_root, runner),
            ),
        )
        executor: ExecutionPort = DevToolExecutor(
            registry, default_tool=AgentCapability.IMPLEMENTATION.value
        )
        if observability is not None:
            executor = observability.observe_executor(executor)
            observability.subscribe(self._events)
        # A shared store lets one chain's attempts read each other's LIVE status (the ChainDriver's
        # is_finished); the default isolated in-memory store leaves a lone fix-it mission unchanged.
        self._engine = MissionEngine(
            store if store is not None else InMemoryMissionStore(),
            executor,
            events=self._events,
        )
        self._foreman = foreman or Foreman()

    @property
    def audit(self) -> MissionAuditSink:
        return self._audit

    @property
    def observability(self) -> DevTeamObservability | None:
        """The injected observability layer (if any) — read its ``view`` for live agent state."""
        return self._observability

    def open_fix_it(self, issue: str, *, principal_id: str = "devteam-foreman") -> Mission:
        """Create, plan (Foreman.plan_fix_it), and execute the mission up to the human gate: the
        Developer step runs, then it pauses in AWAITING_APPROVAL before apply_patch — UNLESS the
        Developer produced no patch, when there is nothing to approve and it ends fail-safe
        (human intervention required) rather than presenting a meaningless gate."""
        tenant = platform_tenant(principal_id)
        mission = self._engine.create(f"fix: {issue}", tenant)
        self._engine.plan(mission, self._foreman.plan_fix_it(issue))
        mission = self._engine.execute(mission)
        if mission.status is MissionStatus.AWAITING_APPROVAL and not _has_patch(mission):
            return self._engine.cancel(mission, NO_PATCH_REASON)
        return mission

    def approve_and_resume(
        self, mission: Mission, *, principal_id: str = "devteam-approver"
    ) -> Mission:
        """Approve the paused mission and resume it: one approval lands the whole sequence — apply,
        commit, push, open_pr — then the mission completes (ADR 0044)."""
        approver = platform_tenant(principal_id)
        self._engine.approve(mission, approver)
        return self._engine.resume(mission)

    def reject(self, mission: Mission, *, principal_id: str = "devteam-approver") -> Mission:
        """Reject the paused mission: it stops fail-safe as CANCELLED, no repository side effect."""
        return self._engine.reject(mission, platform_tenant(principal_id))
