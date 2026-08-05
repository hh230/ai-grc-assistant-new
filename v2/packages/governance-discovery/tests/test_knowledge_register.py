"""The register must describe the packs as they ARE — and must fail when it does not.

A check that can only pass proves nothing, so most of this file makes the register wrong on
purpose and asserts each way is caught. Without the negative cases, a bug that made
`verify_register` always return clean would be invisible.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from governance_discovery.knowledge_register import (
    REGISTER,
    DecisionEffect,
    RegisterEntry,
    WhenUnanswered,
    register_as_rows,
    signals_that_drive_decisions,
    verify_bundled,
    verify_register,
)
from governance_discovery.pack import load_bundled_packs


@pytest.fixture
def packs():
    return load_bundled_packs()


def test_register_matches_the_packs_we_ship():
    report = verify_bundled()
    assert report.ok, report.render()
    assert report.checked == 23


def test_every_question_asked_is_registered(packs):
    asked = {question.id for pack in packs.values() for question in pack.questions}
    assert asked == set(REGISTER), (
        "a question is asked without a licence, or licensed without being asked"
    )


def test_a_dead_question_claiming_impact_is_caught(packs):
    """The failure this whole file exists for: a question stops mattering and nobody notices."""
    register = dict(REGISTER)
    register["q:has_legal_team"] = replace(
        register["q:has_legal_team"], decision_effect=(DecisionEffect.SEEDS_TASK,), inert_reason=""
    )
    report = verify_register(register, packs)
    assert not report.ok
    assert "dead question" in report.violations[0].problem


def test_a_new_question_without_a_register_entry_is_caught(packs):
    register = {k: v for k, v in REGISTER.items() if k != "q:policy_state"}
    report = verify_register(register, packs)
    assert not report.ok
    assert "absent from the register" in report.violations[0].problem


def test_a_live_question_wrongly_declared_inert_is_caught(packs):
    """The register must not understate a question either — that would hide a real dependency."""
    register = dict(REGISTER)
    register["q:policy_state"] = replace(
        register["q:policy_state"],
        decision_effect=(DecisionEffect.NONE,),
        inert_reason="pretend",
    )
    report = verify_register(register, packs)
    assert not report.ok
    assert "understates it" in report.violations[0].problem


def test_a_stale_entry_for_a_removed_question_is_caught(packs):
    register = dict(REGISTER)
    register["q:no_longer_asked"] = RegisterEntry(
        question_id="q:no_longer_asked",
        purpose="p",
        regulatory_basis="b",
        when_unanswered=WhenUnanswered.NO_EFFECT,
        decision_effect=(DecisionEffect.SEEDS_TASK,),
    )
    report = verify_register(register, packs)
    assert not report.ok
    assert "no pack asks it" in report.violations[0].problem


def test_declaring_a_question_inert_requires_a_reason():
    """`NONE` is legal, but only as a deliberate, argued choice — never as a shrug."""
    with pytest.raises(ValueError, match="must say why"):
        RegisterEntry(
            question_id="q:x",
            purpose="p",
            regulatory_basis="b",
            when_unanswered=WhenUnanswered.NO_EFFECT,
            decision_effect=(DecisionEffect.NONE,),
        )


def test_every_entry_states_a_purpose_and_a_basis():
    for entry in REGISTER.values():
        assert entry.purpose.strip(), f"{entry.question_id} has no stated purpose"
        assert entry.regulatory_basis.strip(), f"{entry.question_id} has no regulatory basis"


def test_inert_questions_are_the_known_backlog_and_no_more():
    """If this list grows a dead question shipped; if it shrinks an item was fixed."""
    inert = {
        entry.question_id
        for entry in REGISTER.values()
        if entry.decision_effect == (DecisionEffect.NONE,)
    }
    assert inert == {
        "q:has_legal_team",
        "q:held_licenses",
        "q:last_policy_review_date",
        "q:additional_context_note",
    }


def test_driving_signals_are_read_from_activation_predicates_too(packs):
    """`has_it_team` seeds no task; it decides which packs open. That still counts as driving."""
    driving = signals_that_drive_decisions(packs)
    assert "has_it_team" in driving
    assert "policy_state" in driving
    assert "has_legal_team" not in driving


def test_rows_render_for_a_document_or_a_ui():
    rows = register_as_rows()
    assert len(rows) == len(REGISTER)
    assert set(rows[0]) == {
        "question",
        "purpose",
        "regulatory_basis",
        "when_unanswered",
        "decision_effect",
        "inert_reason",
    }
