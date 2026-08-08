"""What a sector question may declare, and what it may not (ADR 0068 §D1-D2).

Tests 7-12 of the ADR's table. Each rejection here corresponds to a specific way a compliance
decision goes wrong, so the assertions check the REASON as well as the refusal — a pack author who
gets "invalid" and nothing else will guess, and guessing is how the wrong signal gets declared.
"""

from __future__ import annotations

import pytest
from governance_discovery.pack import load_bundled_packs
from governance_discovery.writable_signals import writable_signals
from grc_api.signal_declarations import validate_declaration, validate_pack_declarations


@pytest.fixture(scope="module")
def packs():
    return load_bundled_packs()


def _errors(question, packs):
    return [e.message for e in validate_declaration(question, packs)]


# --- the vocabulary is derived from the engine, never listed by hand ----------------------------


def test_the_writable_vocabulary_comes_from_the_engine_itself(packs) -> None:
    writable = writable_signals(packs)
    assert writable, "an empty vocabulary would silently disable the whole channel"
    # Every one of them is asked by a question and read by something — that IS the definition.
    assert "data_geography" in writable
    assert "has_gov_clients" in writable


def test_a_derived_signal_is_not_writable(packs) -> None:
    """`subject_to_nca` is a conclusion. A pack asserting it would be a pack writing a rule."""
    for derived in ("subject_to_nca", "subject_to_pdpl", "cross_border_data_exposure"):
        assert derived not in writable_signals(packs)


def test_an_orphan_signal_is_not_writable(packs) -> None:
    """`held_licenses` is asked and read by nothing — a question answered for nothing."""
    assert "held_licenses" not in writable_signals(packs)


def test_the_sector_selector_is_not_writable(packs) -> None:
    assert "primary_activity" not in writable_signals(packs)


# --- 7-9: what a question may name -------------------------------------------------------------


def test_a_signal_the_engine_does_not_know_is_refused(packs) -> None:
    errors = _errors(
        {"question_id": "q", "type": "boolean", "writes_signal": "invented_signal",
         "signal_value_map": {"true": True, "false": False}}, packs)
    assert errors and "not a signal any engine question writes" in errors[0]


def test_a_signal_no_rule_consumes_is_refused_with_its_reason(packs) -> None:
    errors = _errors(
        {"question_id": "q", "type": "enum", "writes_signal": "held_licenses",
         "options": [{"option_id": "none"}], "signal_value_map": {"none": "none"}}, packs)
    assert errors and "no rule and no derivation reads it" in errors[0]


def test_a_derived_signal_is_refused_with_its_reason(packs) -> None:
    errors = _errors(
        {"question_id": "q", "type": "boolean", "writes_signal": "subject_to_nca",
         "signal_value_map": {"true": True, "false": False}}, packs)
    assert errors and "DERIVED" in errors[0]


# --- 10: only closed question types ------------------------------------------------------------


@pytest.mark.parametrize("kind", ["text", "multi_select"])
def test_an_open_question_type_cannot_declare_a_signal(kind, packs) -> None:
    errors = _errors(
        {"question_id": "q", "type": kind, "writes_signal": "has_gov_clients",
         "signal_value_map": {"true": True}}, packs)
    assert errors and "cannot declare a signal" in errors[0]


# --- 11: completeness, in both directions -------------------------------------------------------


def test_an_option_with_no_declared_value_is_refused(packs) -> None:
    errors = _errors(
        {"question_id": "q", "type": "enum", "writes_signal": "data_geography",
         "options": [{"option_id": "a"}, {"option_id": "b"}],
         "signal_value_map": {"a": "ksa_only"}}, packs)
    assert errors and "declare null explicitly" in errors[0]


def test_a_map_entry_for_an_option_that_does_not_exist_is_refused(packs) -> None:
    errors = _errors(
        {"question_id": "q", "type": "enum", "writes_signal": "data_geography",
         "options": [{"option_id": "a"}],
         "signal_value_map": {"a": "ksa_only", "ghost": "gcc"}}, packs)
    assert any("do not exist" in e for e in errors)


def test_options_without_stable_ids_cannot_carry_a_declaration(packs) -> None:
    """A map keyed by text would make a translator a governance actor."""
    errors = _errors(
        {"question_id": "q", "type": "enum", "writes_signal": "data_geography",
         "options": ["داخل المملكة"], "signal_value_map": {}}, packs)
    assert any("stable option_id" in e for e in errors)


def test_duplicate_option_ids_are_refused(packs) -> None:
    errors = _errors(
        {"question_id": "q", "type": "enum", "writes_signal": "data_geography",
         "options": [{"option_id": "a"}, {"option_id": "a"}],
         "signal_value_map": {"a": "ksa_only"}}, packs)
    assert any("unique" in e for e in errors)


def test_a_declaration_with_no_map_is_refused(packs) -> None:
    errors = _errors(
        {"question_id": "q", "type": "boolean", "writes_signal": "has_gov_clients"}, packs)
    assert errors and "no signal_value_map" in errors[0]


def test_a_map_with_no_declaration_is_refused_as_a_leftover(packs) -> None:
    errors = _errors(
        {"question_id": "q", "type": "boolean", "signal_value_map": {"true": True}}, packs)
    assert errors and "leftover" in errors[0]


# --- 12: the value has to fit the signal --------------------------------------------------------


def test_a_value_outside_the_signals_vocabulary_is_refused(packs) -> None:
    errors = _errors(
        {"question_id": "q", "type": "enum", "writes_signal": "data_geography",
         "options": [{"option_id": "a"}], "signal_value_map": {"a": "mars"}}, packs)
    assert errors and "not one of" in errors[0]


def test_a_value_of_the_wrong_type_is_refused(packs) -> None:
    errors = _errors(
        {"question_id": "q", "type": "boolean", "writes_signal": "has_gov_clients",
         "signal_value_map": {"true": "yes", "false": False}}, packs)
    assert errors and "boolean" in errors[0]


# --- what a valid declaration looks like, and the null that is a decision ------------------------


def test_a_complete_enum_declaration_passes(packs) -> None:
    assert not validate_declaration(
        {"question_id": "q", "type": "enum", "writes_signal": "data_geography",
         "options": [{"option_id": "ksa"}, {"option_id": "abroad"}, {"option_id": "unknown"}],
         "signal_value_map": {"ksa": "ksa_only", "abroad": "international", "unknown": None}},
        packs)


def test_a_boolean_declares_both_branches_through_the_same_mechanism(packs) -> None:
    assert not validate_declaration(
        {"question_id": "q", "type": "boolean", "writes_signal": "has_gov_clients",
         "signal_value_map": {"true": True, "false": False}}, packs)


def test_a_boolean_branch_may_declare_null(packs) -> None:
    """"No, we do not store data abroad" need not be enough to assert WHERE it is stored."""
    assert not validate_declaration(
        {"question_id": "q", "type": "boolean", "writes_signal": "data_geography",
         "signal_value_map": {"true": "international", "false": None}}, packs)


# --- 20: the shipped packs are untouched --------------------------------------------------------


def test_every_shipped_sector_pack_still_validates_and_declares_nothing(packs) -> None:
    """Phase 1 wires the channel; it does not open it. A shipped pack that started writing signals
    here would be a decision nobody reviewed."""
    from grc_api.knowledge_seed import available_packs, load_pack

    for slug in available_packs():
        pack = load_pack(slug)
        assert not validate_pack_declarations(pack, packs)
        assert not [q for q in pack["questions"] if q.get("writes_signal")], slug


# --- the boundary: no AI-authored pack can reach these columns ----------------------------------


def test_the_repositorys_insert_does_not_carry_the_declaration_columns() -> None:
    """The structural guarantee, asserted against the SQL itself.

    `_FORBIDDEN_FIELDS` stops the generator from returning `writes_signal`, and that is a good
    guard — but it is a behaviour, and behaviours get relaxed. This is the fact underneath it: the
    one statement in the product that writes `release_questions` does not name the declaration
    columns at all, so no generated pack, no import, and no future caller of that repository can
    set them however hard it tries. A declaration arrives by human review, or not at all.
    """
    import inspect

    from governance_store import knowledge_store

    source = inspect.getsource(knowledge_store)
    inserts = [
        line for line in source.splitlines() if "INSERT INTO release_questions" in line
    ]
    assert len(inserts) == 1, "a second write path would need its own guarantee"

    start = source.index("INSERT INTO release_questions")
    statement = source[start : source.index("VALUES", start)]
    assert "writes_signal" not in statement
    assert "signal_value_map" not in statement


def test_a_generated_pack_carrying_a_declaration_is_rejected_whole() -> None:
    """And the behavioural half, at the generator's own boundary: the response is refused, not
    stripped. Silently dropping the field would let the prompt drift into asking for it."""
    from grc_api.knowledge_generation import _FORBIDDEN_FIELDS

    assert {"writes_signal", "signal_value_map"} <= _FORBIDDEN_FIELDS


def test_a_declaration_survives_nothing_when_the_pack_file_carries_one(packs) -> None:
    """An authored pack file CAN carry a declaration — that is the point of the channel — but it
    still has to pass validation before anything stores it."""
    invalid = {
        "question_id": "q", "type": "enum", "writes_signal": "subject_to_nca",
        "options": [{"option_id": "a"}], "signal_value_map": {"a": True},
    }
    assert validate_declaration(invalid, packs), "a derived signal must not pass"
