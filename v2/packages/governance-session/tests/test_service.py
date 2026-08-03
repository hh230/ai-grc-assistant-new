import pytest
from governance_discovery.analysis import Applicability
from governance_discovery.engine import DiscoveryEngine
from governance_discovery.pack import load_bundled_packs
from governance_session.errors import (
    InvalidAnswer,
    SessionAlreadyConcluded,
    SessionNotFound,
)
from governance_session.service import DiscoverySessionService

from tests.fake_store import FakeGovernanceStore


def _service() -> tuple[DiscoverySessionService, FakeGovernanceStore]:
    counter = {"id": 0, "clock": 1000.0}

    def new_id() -> str:
        counter["id"] += 1
        return f"id_{counter['id']}"

    def now() -> float:
        counter["clock"] += 1.0
        return counter["clock"]

    store = FakeGovernanceStore()
    engine = DiscoveryEngine(load_bundled_packs())
    return DiscoverySessionService(engine, store, new_id=new_id, now=now), store


def test_start_returns_the_primary_activity_question_first() -> None:
    service, _ = _service()
    session, question = service.start("tenant_a")
    assert session.status == "in_progress"
    assert question is not None
    assert question.id == "q:primary_activity"


def test_answering_the_opening_question_activates_technology_pack() -> None:
    service, _ = _service()
    session, question = service.start("tenant_a")
    outcome = service.answer(session.id, "tenant_a", question.id, "technology")
    assert not outcome.concluded
    assert "pack:technology" in outcome.session.active_pack_ids


def test_invalid_answer_type_is_rejected() -> None:
    service, _ = _service()
    session, question = service.start("tenant_a")
    with pytest.raises(InvalidAnswer):
        service.answer(session.id, "tenant_a", question.id, 12345)  # enum expects a string option


def test_answering_after_conclusion_is_rejected() -> None:
    service, store = _service()
    session, question = service.start("tenant_a")
    # Drive straight to a low-confidence conclusion with a single sparse answer isn't possible
    # (primary_activity alone won't conclude); simulate a concluded session directly instead.
    concluded = session.concluded(
        Applicability(
            frameworks=(), maturity={}, maturity_vision={}, capacity={}, gaps=(), plan_items=(),
            confidence_score=1.0, confidence="normal",
        ),
        now=2000.0,
    )
    store.save_session(concluded)
    with pytest.raises(SessionAlreadyConcluded):
        service.answer(session.id, "tenant_a", question.id, "technology")


def test_unknown_session_raises() -> None:
    service, _ = _service()
    with pytest.raises(SessionNotFound):
        service.get("does-not-exist", "tenant_a")


def test_resume_finds_the_in_progress_session_and_its_next_question() -> None:
    service, _ = _service()
    started, _ = service.start("tenant_a")
    resumed = service.resume("tenant_a")
    assert resumed is not None
    session, question = resumed
    assert session.id == started.id
    assert question is not None


def test_resume_returns_none_when_no_session_exists() -> None:
    service, _ = _service()
    assert service.resume("tenant_with_no_sessions") is None


def test_skip_advances_without_writing_a_signal() -> None:
    service, store = _service()
    session, q1 = service.start("tenant_a")
    outcome = service.answer(session.id, "tenant_a", q1.id, "technology")
    # drive to the optional held_licenses question directly (order-independent for this test)
    outcome2 = service.skip(outcome.session.id, "tenant_a", "q:held_licenses")
    assert not outcome2.session.signals.has("held_licenses")
    assert "q:held_licenses" in outcome2.session.answered_question_ids


def test_required_questions_cannot_be_skipped() -> None:
    service, _ = _service()
    session, q1 = service.start("tenant_a")
    with pytest.raises(InvalidAnswer):
        service.skip(session.id, "tenant_a", q1.id)


def test_go_back_returns_the_most_recent_in_scope_answer_for_editing() -> None:
    service, _ = _service()
    session, question = service.start("tenant_a")
    outcome = service.answer(session.id, "tenant_a", question.id, "technology")
    target = service.go_back(outcome.session.id, "tenant_a")
    assert target.question.id == "q:primary_activity"
    assert target.previous_answer == "technology"


def test_go_back_quietly_skips_a_question_no_longer_produced_by_any_active_pack() -> None:
    """The core 'quiet reroute' requirement: a stale answer that no longer belongs to any
    currently-active pack (e.g. a question from a pack version that has since changed) is never
    offered back for editing — go_back silently skips past it to the next in-scope answer,
    without any error or user-visible fuss."""
    service, store = _service()
    session, q1 = service.start("tenant_a")
    outcome = service.answer(session.id, "tenant_a", q1.id, "technology")

    # A later, still-in-scope core answer.
    outcome2 = service.answer(outcome.session.id, "tenant_a", "q:employee_count", 15)

    # Simulate a stale answer landing AFTER it for a question id that belongs to no loaded pack
    # at all (as if a pack version changed and dropped a question) — a defensive edge case.
    store.append_answer(
        answer_id="stale_1",
        session_id=outcome2.session.id,
        tenant_id="tenant_a",
        sequence=store.next_sequence(outcome2.session.id),
        question_id="q:no_longer_exists",
        question_version="0.9",
        raw_answer="whatever",
        resolved_signal_key="retired_signal",
        resolved_signal_value="whatever",
        normalized_by="direct",
        llm_model_version=None,
        llm_confidence=None,
        created_at=9999.0,
    )

    target = service.go_back(outcome2.session.id, "tenant_a")
    assert target.question.id == "q:employee_count"  # skipped the stale, unrecognized entry
