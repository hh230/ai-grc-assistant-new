"""Pure round-trip tests for the DiscoverySession <-> row translation — no database needed,
mirrors `mission_store/tests/test_codec.py`'s discipline."""

from __future__ import annotations

from governance_discovery.analysis import Applicability
from governance_discovery.session import DiscoverySession
from governance_discovery.signal import Signal, SignalSet, ValueType
from governance_discovery.plan import PlanItem
from governance_store.codec import (
    answer_to_row,
    plan_item_from_row,
    plan_item_to_row,
    session_from_row,
    session_to_row,
)


def _session(**overrides) -> DiscoverySession:
    base = DiscoverySession.start("sess_1", "tenant_1", now=1000.0)
    return base if not overrides else base.__class__(**{**base.__dict__, **overrides})


def test_round_trip_preserves_typed_signals() -> None:
    session = _session(
        signals=SignalSet().with_signal(
            Signal(key="employee_count", value_type=ValueType.NUMERIC, value=15)
        ).with_signal(
            Signal(key="policy_state", value_type=ValueType.ENUM, value="approved", confidence=0.9)
        ),
        answered_question_ids=frozenset({"q:employee_count", "q:policy_state"}),
    )
    row = session_to_row(session)
    restored = session_from_row(row, answered_question_ids=session.answered_question_ids)

    assert restored.signals.value("employee_count") == 15
    assert restored.signals.get("employee_count").value_type == ValueType.NUMERIC
    assert restored.signals.get("policy_state").value_type == ValueType.ENUM
    assert restored.signals.get("policy_state").confidence == 0.9


def test_round_trip_preserves_applicability_when_concluded() -> None:
    applicability = Applicability(
        frameworks=(
            {"framework_id": "framework:iso_27001", "confidence": 0.6, "rationale_key": "x"},
        ),
        maturity={"governance": {"score": 2, "stars": 1, "label": "limited"}},
        maturity_vision={"governance": {"score": 8, "stars": 4, "label": "established"}},
        capacity={"score": 24.0, "tier": "mid", "per_period_budget": {"week_1": 5}},
        gaps=(),
        plan_items=({"id": "seed:a", "timeframe_bucket": "week_1"},),
        confidence_score=1.0,
        confidence="normal",
    )
    session = _session(status="concluded", applicability=applicability, concluded_at=2000.0)
    row = session_to_row(session)
    restored = session_from_row(row, answered_question_ids=frozenset())

    assert restored.status == "concluded"
    assert restored.applicability is not None
    assert restored.applicability.frameworks[0]["framework_id"] == "framework:iso_27001"
    assert restored.applicability.plan_items[0]["timeframe_bucket"] == "week_1"
    assert restored.applicability.maturity_vision["governance"]["stars"] == 4
    assert restored.concluded_at == 2000.0


def test_skipped_answer_row_carries_a_null_raw_answer_not_a_missing_key() -> None:
    """A skipped optional question must be representable as a real NULL in the nullable
    `raw_answer` column — not silently coerced into some other sentinel — matching the schema
    (ADR 0066 §2, discovery_answers)."""
    row = answer_to_row(
        answer_id="a1",
        session_id="s1",
        tenant_id="t1",
        sequence=1,
        question_id="q:held_licenses",
        question_version="1.0",
        raw_answer=None,
        resolved_signal_key=None,
        resolved_signal_value=None,
        normalized_by="skipped",
        llm_model_version=None,
        llm_confidence=None,
        created_at=1000.0,
    )
    assert row["raw_answer"] is None
    assert row["normalized_by"] == "skipped"


def test_round_trip_of_a_fresh_session_has_no_applicability() -> None:
    session = _session()
    row = session_to_row(session)
    restored = session_from_row(row, answered_question_ids=frozenset())
    assert restored.applicability is None
    assert restored.status == "in_progress"


def _plan_item(**overrides) -> PlanItem:
    base = dict(
        id="itm_1", plan_id="pln_1", tenant_id="t1", pillar="risk",
        title="Establish Risk Register", objective="Close the identified gap.",
        expected_outcome="A maintained register.", rationale="Identified during the assessment.",
        timeframe_bucket="week_1", priority="high", effort_size="medium",
        depends_on_item_ids=(), status="not_started", source_signal_keys=(),
        source_framework_refs=(), created_at=1.0, updated_at=1.0,
    )
    base.update(overrides)
    return PlanItem(**base)


def test_a_plan_item_carries_its_i18n_keys_through_the_round_trip() -> None:
    """The keys are what let a title render in a second language without re-running the model. A
    codec that drops them turns a translatable field back into a monolingual one — which is exactly
    how the titles became English-only in the first place."""
    item = _plan_item(
        title_key="plan.seed.establish_risk_register.title",
        objective_key="plan.seed.establish_risk_register.objective",
    )
    row = plan_item_to_row(item)
    assert row["title_key"] == "plan.seed.establish_risk_register.title"
    assert plan_item_from_row(row).title_key == item.title_key
    assert plan_item_from_row(row).objective_key == item.objective_key


def test_a_row_written_before_the_key_columns_existed_still_decodes() -> None:
    """Why the columns default to empty rather than being required: every plan drafted before today
    has no key, and must keep rendering from the text that WAS stored."""
    row = plan_item_to_row(_plan_item())
    del row["title_key"], row["objective_key"]
    decoded = plan_item_from_row(row)
    assert decoded.title_key == ""
    assert decoded.title == "Establish Risk Register"
