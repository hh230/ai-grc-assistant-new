"""End-to-end: the AI Organization is visible in the SAME journal-backed view the Dashboard reads.

This is the acceptance proof. The runtime journals every fact; the Dashboard's ``/api/agents``
reads ``devteam_view_from_journal`` — so reconstructing that exact view here proves the organization
appears in the existing Dashboard (roster, timeline, decisions) with no UI change. One journal,
one view type — no duplicate runtime, dashboard, or state model.
"""

from __future__ import annotations

from pathlib import Path

from devteam_agents import SuiteRunner
from devteam_observability import (
    DevTeamObservability,
    JournalingObserver,
    agent_id_for,
    devteam_view_from_journal,
)
from devteam_organization import OrganizationRuntime
from devteam_protocol import AgentRole

_FULL_GOAL = "Implement encryption and map ISO 27001 controls, with tests"
_CHAIN = [
    "platform:ceo",
    "platform:cto",
    "platform:ciso",
    "platform:grc_expert",
    "platform:qa",
    "platform:devteam",
]
_ORG = {
    "platform:ceo",
    "platform:cto",
    "platform:ciso",
    "platform:grc_expert",
    "platform:devteam",
    "platform:supervisor",
}
_SQUAD = {"platform:foreman", "platform:qa", "platform:developer", "platform:reviewer"}


def _agent_key(item: dict[str, object]) -> str:
    agent = item.get("agent")
    if isinstance(agent, dict):
        key = agent.get("key")
        if isinstance(key, str):
            return key
    return ""


def test_the_organization_is_visible_in_the_dashboard_view(
    tmp_path: Path, green_runner: SuiteRunner
) -> None:
    journal = tmp_path / "runtime.jsonl"
    observability = DevTeamObservability(downstreams=[JournalingObserver(journal)])
    runtime = OrganizationRuntime(green_runner, observability=observability)

    mission = runtime.run_mission(_FULL_GOAL)
    runtime.run_health_check()

    # Rebuild the Dashboard's view from the journal alone (never the file directly).
    view = devteam_view_from_journal(journal)
    keys = {_agent_key(dto) for dto in view.agents()}
    assert keys >= _ORG  # the whole AI Organization is visible
    assert keys >= _SQUAD  # the engineering squad is untouched

    # The mission timeline is replayable in order — the Live Pipeline / Mission Timeline surface.
    chain = [_agent_key(session) for session in view.mission_sessions(mission.id)]
    assert chain == _CHAIN


def test_decisions_and_supervisor_activity_are_recorded(
    tmp_path: Path, green_runner: SuiteRunner
) -> None:
    journal = tmp_path / "runtime.jsonl"
    observability = DevTeamObservability(downstreams=[JournalingObserver(journal)])
    runtime = OrganizationRuntime(green_runner, observability=observability)
    runtime.run_mission(_FULL_GOAL)
    runtime.run_health_check()

    view = devteam_view_from_journal(journal)
    ceo = view.agent(agent_id_for(AgentRole.CEO))
    assert ceo is not None
    history = ceo["decision_history"]
    assert isinstance(history, list) and len(history) >= 1  # the CEO's verdict is in the log

    supervisor = view.agent(agent_id_for(AgentRole.SUPERVISOR))
    assert supervisor is not None
    completed = supervisor["completed_missions"]
    assert isinstance(completed, int) and completed >= 1  # a real health mission ran
