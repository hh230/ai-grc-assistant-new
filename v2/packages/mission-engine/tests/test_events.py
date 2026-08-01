"""Mission events (ADR 0042 §2.7, §12.2): every event is mission- and tenant-stamped, threads
the trace id, and serializes to a plain summary."""

from mission_engine.events import (
    MissionAwaitingApproval,
    MissionCancelled,
    MissionCompleted,
    MissionCreated,
    MissionFailed,
    MissionPlanned,
    MissionResumed,
    MissionStepCompleted,
)

_ALL_EVENT_TYPES = (
    MissionCreated,
    MissionPlanned,
    MissionStepCompleted,
    MissionAwaitingApproval,
    MissionResumed,
    MissionCompleted,
    MissionFailed,
    MissionCancelled,
)


def test_created_event_carries_the_full_stamp():
    event = MissionCreated(
        trace_id="trc_1", mission_id="mis_1", tenant_id="org_acme", goal="assess MFA"
    )
    data = event.to_dict()
    assert data["name"] == "mission.created"
    assert data["trace_id"] == "trc_1"
    assert data["mission_id"] == "mis_1"
    assert data["tenant_id"] == "org_acme"
    assert data["goal"] == "assess MFA"


def test_step_completed_summarizes_source_ids_not_output():
    event = MissionStepCompleted(
        trace_id="t", mission_id="m", tenant_id="o", step_id="stp_1", source_ids=("a", "b")
    )
    data = event.to_dict()
    assert data["step_id"] == "stp_1"
    assert data["source_ids"] == ["a", "b"]
    assert "output" not in data  # events stay summaries, never the payload


def test_every_event_type_is_mission_and_tenant_stamped():
    for event_type in _ALL_EVENT_TYPES:
        event = event_type(trace_id="t", mission_id="m", tenant_id="o")
        data = event.to_dict()
        assert data["mission_id"] == "m"
        assert data["tenant_id"] == "o"
        assert data["trace_id"] == "t"


def test_event_names_are_stable_and_distinct():
    names = [event_type.name for event_type in _ALL_EVENT_TYPES]
    assert len(names) == len(set(names))  # no collisions
    assert all(name.startswith("mission.") for name in names)
