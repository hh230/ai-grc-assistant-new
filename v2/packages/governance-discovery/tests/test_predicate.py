import pytest

from governance_discovery.predicate import evaluate, references_signal
from tests.helpers import make_signals


def test_none_predicate_always_true() -> None:
    assert evaluate(None, make_signals()) is True


def test_missing_signal_is_false() -> None:
    assert evaluate({"signal": "handles_personal_data", "op": "eq", "value": True}, make_signals()) is False


def test_eq_neq_in() -> None:
    signals = make_signals(primary_activity="technology")
    assert evaluate({"signal": "primary_activity", "op": "eq", "value": "technology"}, signals)
    assert not evaluate({"signal": "primary_activity", "op": "neq", "value": "technology"}, signals)
    assert evaluate({"signal": "primary_activity", "op": "in", "value": ["technology", "legal_services"]}, signals)


def test_numeric_gte_lte_between() -> None:
    signals = make_signals(employee_count=15)
    assert evaluate({"signal": "employee_count", "op": "gte", "value": 11}, signals)
    assert not evaluate({"signal": "employee_count", "op": "gte", "value": 16}, signals)
    assert evaluate({"signal": "employee_count", "op": "lte", "value": 20}, signals)
    assert evaluate({"signal": "employee_count", "op": "between", "value": [10, 20]}, signals)
    assert not evaluate({"signal": "employee_count", "op": "between", "value": [16, 20]}, signals)


def test_enum_ordinal_gte_lte_on_default_maturity_scale() -> None:
    signals = make_signals(policy_state="approved")
    assert evaluate({"signal": "policy_state", "op": "gte", "value": "documented_unapproved"}, signals)
    assert not evaluate({"signal": "policy_state", "op": "gte", "value": "reviewed_periodically"}, signals)
    assert evaluate({"signal": "policy_state", "op": "lte", "value": "reviewed_periodically"}, signals)
    assert not evaluate({"signal": "policy_state", "op": "lte", "value": "verbal"}, signals)


def test_all_and_any_combinators() -> None:
    signals = make_signals(handles_personal_data=True, policy_state="absent")
    both = {
        "all": [
            {"signal": "handles_personal_data", "op": "eq", "value": True},
            {"signal": "policy_state", "op": "lte", "value": "verbal"},
        ]
    }
    assert evaluate(both, signals)

    either = {
        "any": [
            {"signal": "handles_personal_data", "op": "eq", "value": False},
            {"signal": "policy_state", "op": "eq", "value": "absent"},
        ]
    }
    assert evaluate(either, signals)


def test_unknown_op_raises() -> None:
    with pytest.raises(ValueError):
        evaluate({"signal": "x", "op": "nonsense", "value": 1}, make_signals(x=1))


def test_references_signal_walks_the_tree() -> None:
    expr = {"any": [{"signal": "a", "op": "eq", "value": 1}, {"signal": "b", "op": "eq", "value": 2}]}
    assert references_signal(expr, "a")
    assert references_signal(expr, "b")
    assert not references_signal(expr, "c")
    assert not references_signal(None, "a")
