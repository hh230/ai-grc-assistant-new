"""The interview must offer more than yes/no: dropdown, buttons (incl. tri-state), number, date,
multi-select, and short free text — each is a real `ui_hint`/`value_type` combination in the
bundled packs, not just infrastructure nobody uses."""

from governance_discovery.pack import load_bundled_packs
from governance_discovery.signal import ValueType


def _question(question_id: str):
    for pack in load_bundled_packs().values():
        for question in pack.questions:
            if question.id == question_id:
                return question
    raise AssertionError(f"question not found: {question_id}")


def test_dropdown_for_the_opening_sector_question() -> None:
    q = _question("q:primary_activity")
    assert q.ui_hint == "dropdown"
    assert q.value_type == ValueType.ENUM
    assert len(q.options) > 5


def test_tri_state_buttons_not_a_flat_yes_no() -> None:
    q = _question("q:cloud_data_residency_controlled")
    assert q.ui_hint == "buttons"
    assert q.options == ("no", "partially", "yes")


def test_numeric_employee_count_is_a_real_number_not_a_band() -> None:
    q = _question("q:employee_count")
    assert q.value_type == ValueType.NUMERIC
    assert q.ui_hint == "number"
    assert q.options is None


def test_date_input_for_last_policy_review() -> None:
    q = _question("q:last_policy_review_date")
    assert q.value_type == ValueType.DATE
    assert q.ui_hint == "date"


def test_multi_select_for_held_licenses_and_marked_optional() -> None:
    q = _question("q:held_licenses")
    assert q.allow_multiple is True
    assert q.ui_hint == "chips"
    assert q.required is False


def test_short_free_text_for_additional_context() -> None:
    q = _question("q:additional_context_note")
    assert q.value_type == ValueType.TEXT
    assert q.ui_hint == "short_text"
    assert q.required is False
