"""End-to-end runtime VALIDATION of the observability layer (regression guard for the validation
run documented in docs/devteam/OBSERVABILITY-VALIDATION.md).

Real missions on the real MissionEngine with real agents and a real on-disk journal. Scenario A is
the real quality-review mission (QA -> Reviewer). Scenario B drives the REAL ContinuousMonitor over
a REAL ChainDriver that opens a REAL gated fix-it mission — only the GitHub HTTP layer is canned (a
CommandRunner returning a red run). Nothing in the observability path is mocked.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from devteam_chain import AttemptStore, ChainAttempt
from devteam_ci import PackageResult
from devteam_contracts import platform_tenant
from devteam_github import GitHubActions, WorkflowRun
from devteam_observability import (
    AgentStarted,
    AgentStatus,
    DevTeamObservability,
    JournalingObserver,
    RuntimeEvent,
    RuntimeStateView,
    SessionStatus,
    agent_id_for,
    devteam_view_from_journal,
)
from devteam_protocol import AgentArtifact, AgentRequest, AgentRole
from devteam_runtime import ChainDriver, ChainStatus, ContinuousMonitor, FixItRuntime
from devteam_runtime.agent_runtime import AgentMissionRuntime
from devteam_tools import CommandResult
from mission_engine.adapters import InMemoryMissionStore
from mission_engine.lifecycle import MissionStatus, is_terminal
from mission_engine.mission import Mission

QA = agent_id_for(AgentRole.QA)
REVIEWER = agent_id_for(AgentRole.REVIEWER)
DEVELOPER = agent_id_for(AgentRole.DEVELOPER)


class _Probe:
    """Wired as a downstream AFTER the registry: when it sees an AgentStarted the registry has
    already folded it, so the view reporting WORKING proves a real-time update."""

    def __init__(self) -> None:
        self.view: RuntimeStateView | None = None
        self.working: dict[str, bool] = {}

    def observe(self, event: RuntimeEvent) -> None:
        if isinstance(event, AgentStarted) and event.agent is not None and self.view is not None:
            dto = self.view.agent(event.agent)
            if dto is not None:
                self.working[event.agent.key] = dto["status"] == AgentStatus.WORKING.value


def _green() -> list[PackageResult]:
    return [PackageResult("event-bus", 0, "35 passed"), PackageResult("tool-registry", 0, "ok")]


# --- Scenario A: real quality-review mission -----------------------------------------------------


def test_scenario_a_sessions_tree_and_lifecycle(tmp_path: Path) -> None:
    obs = DevTeamObservability(downstreams=[JournalingObserver(tmp_path / "a.jsonl")])
    mission = AgentMissionRuntime(_green, observability=obs).run_quality_review()

    sessions = obs.registry.sessions_for_mission(mission.id)
    # C1 — sessions created correctly: QA then Reviewer, both sealed, Reviewer carries its verdict.
    assert [s.agent_id for s in sessions] == [QA, REVIEWER]
    assert all(s.status is SessionStatus.COMPLETED and s.duration_ms is not None for s in sessions)
    assert sessions[1].decision is not None and sessions[1].decision.verdict == "approve"

    # C5 — ownership + session tree consistent (bidirectional links; the relay is a parent->child).
    qa_session, reviewer_session = sessions
    mission_state = obs.registry.mission_state(mission.id)
    assert mission_state is not None and mission_state.owner == QA
    assert qa_session.parent_session_id is None
    assert reviewer_session.parent_session_id == qa_session.session_id
    assert qa_session.child_session_ids == (reviewer_session.session_id,)

    # C6 — mission & agent lifecycle synchronized: terminal mission, actors idle, nothing active.
    assert mission.status is MissionStatus.COMPLETED
    for agent_id in (QA, REVIEWER):
        state = obs.registry.state_for(agent_id)
        assert state is not None and state.status is AgentStatus.IDLE
        assert state.active_session_id is None
    assert obs.registry.active_sessions() == []


def test_scenario_a_realtime_and_exact_reconstruction(tmp_path: Path) -> None:
    journal = tmp_path / "a.jsonl"
    probe = _Probe()
    obs = DevTeamObservability(downstreams=[JournalingObserver(journal), probe])
    probe.view = obs.view
    mission = AgentMissionRuntime(_green, observability=obs).run_quality_review()

    # C2 — the view reported WORKING at the instant each agent started (real-time).
    assert probe.working.get(QA.key) is True
    assert probe.working.get(REVIEWER.key) is True

    # C3 — journal records written correctly (present, versioned, typed).
    records = [json.loads(ln) for ln in journal.read_text().splitlines() if ln.strip()]
    assert records and all(r["schema_version"] == 1 and "kind" in r["event"] for r in records)

    # C4 — JournalReader reconstructs the EXACT view (byte-identical state), through the view.
    live, replayed = obs.view, devteam_view_from_journal(journal)
    assert replayed.agents() == live.agents()
    assert replayed.ownership() == live.ownership()
    assert replayed.mission_sessions(mission.id) == live.mission_sessions(mission.id)
    assert replayed.mission_flow(mission.id) == live.mission_flow(mission.id)


# --- Scenario B: real ContinuousMonitor -> real gated fix-it mission ------------------------------

_RED = json.dumps(
    {"workflow_runs": [{"id": 7, "name": "CI", "status": "completed", "conclusion": "failure",
                        "head_branch": "fixme", "display_title": "t", "html_url": "u"}]}
)
_PULLS = json.dumps([{"number": 1, "head": {"ref": "fixme"}, "title": "PR 1", "html_url": "u/1"}])


class _RoutingRunner:
    def run(self, args: Sequence[str], *, cwd: Path, stdin: str | None = None) -> CommandResult:
        url = args[-1]
        if "/pulls" in url:
            return CommandResult(0, _PULLS, "")
        if "branch=fixme&" in url:
            return CommandResult(0, _RED, "")
        return CommandResult(0, json.dumps({"workflow_runs": []}), "")


def _diff_proposer(request: AgentRequest) -> list[AgentArtifact]:
    diff = "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"
    return [AgentArtifact(kind="diff", title="fix.patch", content=diff)]


def _run_real_monitor(obs: DevTeamObservability, repo_root: Path) -> tuple[ChainStatus, str]:
    runner = _RoutingRunner()
    github = GitHubActions(runner, "owner/repo", token="t")
    missions = InMemoryMissionStore()

    def opener(run: WorkflowRun, ref: str, number: int) -> Mission | None:
        fix = FixItRuntime(
            propose=_diff_proposer, runner=runner, repo_root=repo_root,
            observability=obs, store=missions,
        )
        return fix.open_fix_it(f"tests fail [{ref}: attempt {number}]")

    def is_finished(attempt: ChainAttempt) -> bool:
        current = missions.get(attempt.mission_id, platform_tenant())
        return current is None or is_terminal(current.status)

    driver = ChainDriver(github, AttemptStore(), opener, is_finished=is_finished)
    monitor = ContinuousMonitor(github, driver, on_alert=lambda a: None, sleep=lambda s: None)
    outcome = monitor.tick()[0]
    return outcome.status, outcome.mission.id if outcome.mission is not None else ""


def test_scenario_b_real_monitor_drives_a_gated_fix_it_mission(tmp_path: Path) -> None:
    journal = tmp_path / "b.jsonl"
    probe = _Probe()
    obs = DevTeamObservability(downstreams=[JournalingObserver(journal), probe])
    probe.view = obs.view

    status, mission_id = _run_real_monitor(obs, tmp_path / "repo")

    # The real monitor opened a real mission that paused at the human gate.
    assert status is ChainStatus.OPENED and mission_id
    mission_state = obs.registry.mission_state(mission_id)
    assert mission_state is not None

    sessions = obs.registry.sessions_for_mission(mission_id)
    # C1 — one Developer session, sealed, with its PROCEED verdict and the diff artifact.
    assert [s.agent_id for s in sessions] == [DEVELOPER]
    dev_session = sessions[0]
    assert dev_session.status is SessionStatus.COMPLETED
    assert dev_session.decision is not None and dev_session.decision.verdict == "proceed"
    assert any(a.kind == "diff" for a in dev_session.artifacts)

    # C2 — real-time; C5 — single root session (no children); C6 — lifecycle sync at the gate.
    assert probe.working.get(DEVELOPER.key) is True
    assert dev_session.parent_session_id is None and dev_session.child_session_ids == ()
    dev_state = obs.registry.state_for(DEVELOPER)
    assert dev_state is not None
    # The Developer finished its step (session COMPLETED, agent IDLE); the pending gate is a HUMAN
    # one on a non-agent Git step — so no agent is left WORKING while the mission awaits approval.
    assert dev_state.status is AgentStatus.IDLE and dev_state.active_session_id is None

    # C3 / C4 — journal written + exact reconstruction.
    records = [json.loads(ln) for ln in journal.read_text().splitlines() if ln.strip()]
    assert records and all(r["schema_version"] == 1 for r in records)
    replayed = devteam_view_from_journal(journal)
    assert replayed.mission_sessions(mission_id) == obs.view.mission_sessions(mission_id)
    assert replayed.agents() == obs.view.agents()
