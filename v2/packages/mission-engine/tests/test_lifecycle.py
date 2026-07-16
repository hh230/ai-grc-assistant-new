"""The lifecycle state machine (ADR 0042 §7): the happy path is legal, states cannot be
skipped, and terminal states are immutable except for archival."""

from mission_engine.lifecycle import (
    TERMINAL_STATES,
    can_transition,
    is_terminal,
)
from mission_engine.lifecycle import (
    MissionStatus as S,
)


def test_happy_path_is_legal():
    assert can_transition(S.CREATED, S.PLANNED)
    assert can_transition(S.PLANNED, S.EXECUTING)
    assert can_transition(S.EXECUTING, S.COMPLETED)


def test_states_cannot_be_skipped():
    assert not can_transition(S.CREATED, S.EXECUTING)
    assert not can_transition(S.CREATED, S.COMPLETED)
    assert not can_transition(S.PLANNED, S.COMPLETED)


def test_gate_and_replan_paths_are_present_though_unexercised():
    assert can_transition(S.EXECUTING, S.AWAITING_APPROVAL)
    assert can_transition(S.AWAITING_APPROVAL, S.RESUMED)
    assert can_transition(S.RESUMED, S.PLANNED)
    assert can_transition(S.RESUMED, S.EXECUTING)


def test_fail_safe_is_reachable_from_every_active_state():
    for state in (S.CREATED, S.PLANNED, S.EXECUTING, S.AWAITING_APPROVAL, S.RESUMED):
        assert can_transition(state, S.CANCELLED)
        assert can_transition(state, S.FAILED)


def test_terminal_states_only_archive():
    for terminal in (S.COMPLETED, S.FAILED, S.CANCELLED):
        assert is_terminal(terminal)
        assert can_transition(terminal, S.ARCHIVED)
        assert not can_transition(terminal, S.EXECUTING)
        assert not can_transition(terminal, S.PLANNED)


def test_archived_is_a_dead_end():
    assert is_terminal(S.ARCHIVED)
    assert not can_transition(S.ARCHIVED, S.ARCHIVED)
    assert not can_transition(S.ARCHIVED, S.EXECUTING)


def test_terminal_set_is_exactly_the_four_end_states():
    assert frozenset(
        {S.COMPLETED, S.FAILED, S.CANCELLED, S.ARCHIVED}
    ) == TERMINAL_STATES
