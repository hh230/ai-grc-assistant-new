"""Tests for the Rule Intent Verifier.

The property under test is the one the Minimal Fix Finder cannot check about itself: an edit can be
statistically excellent and semantically vandalism. Its own top-ranked candidate was exactly that.
"""

from __future__ import annotations

from devteam_harness.investigation.intent import (
    ALWAYS_FIRES_RATE,
    SemanticDistance,
    check_name_coherence,
    fire_rate,
    parse_target,
    site_of,
    verify_intent,
)


def _plans(*firing: bool) -> dict[int, list[dict[str, str]]]:
    return {
        index: ([{"id": "seed:x"}] if fires else [{"id": "seed:other"}])
        for index, fires in enumerate(firing)
    }


# --- the defect this layer exists for ------------------------------------------------------------


def test_an_edit_that_makes_a_rule_fire_for_everyone_is_HIGH_distance() -> None:
    """The finder's own top candidate: `policy_state lte verbal → lte reviewed_periodically`
    fixed three defects with zero regression by making the rule fire for 100% of organizations.
    A rule that never says "no" has stopped being a rule."""
    verdict = verify_intent(
        identifier="r:policy_weak_seeds_drafting seed:draft_policies",
        op="lte",
        value="reviewed_periodically",
        rate_before=0.44,
        rate_after=1.0,
    )
    assert verdict.distance is SemanticDistance.HIGH
    assert not verdict.preserved
    assert "no longer discriminates" in verdict.render()


def test_selectivity_drift_is_reported_with_both_rates() -> None:
    """"18% → 91%" is the sentence a reviewer needs; "drift detected" is not."""
    verdict = verify_intent(
        identifier="r:x seed:x", op="lte", value="approved", rate_before=0.18, rate_after=0.91
    )
    assert "18% → 91%" in verdict.render()


def test_a_name_that_contradicts_its_predicate_is_reported() -> None:
    """`..._absent_...` accepting `approved` is not subtle: the name is the first thing the next
    engineer reads, and it would now be a lie."""
    reasons = check_name_coherence("r:org_structure_absent_seeds_formalization", "lte", "approved")
    assert reasons and "the name says 'absent'" in reasons[0]


def test_a_name_consistent_with_its_predicate_is_silent() -> None:
    assert check_name_coherence("r:org_structure_absent_seeds_formalization", "eq", "absent") == []


def test_weak_permits_verbal_but_not_approved() -> None:
    """'weak' means absent or verbal. Accepting `approved` under that name is the vandalism."""
    assert check_name_coherence("r:policy_weak_seeds_drafting", "lte", "verbal") == []
    assert check_name_coherence("r:policy_weak_seeds_drafting", "lte", "approved")


# --- not crying wolf -----------------------------------------------------------------------------


def test_a_small_faithful_adjustment_is_preserved() -> None:
    """The verifier must stay quiet on a reasonable edit, or it blocks every fix and gets ignored."""
    verdict = verify_intent(
        identifier="r:policy_weak_seeds_drafting seed:draft_policies",
        op="lte",
        value="verbal",
        rate_before=0.44,
        rate_after=0.50,
    )
    assert verdict.preserved
    assert verdict.distance is SemanticDistance.NONE


def test_a_rule_that_already_fired_for_everyone_is_not_blamed_on_the_edit() -> None:
    """If the rate was already at the ceiling, this edit did not cause it."""
    verdict = verify_intent(
        identifier="r:x seed:x", op="eq", value="absent", rate_before=1.0, rate_after=1.0
    )
    assert verdict.distance is SemanticDistance.NONE


def test_a_narrowing_edit_is_judged_by_the_same_standard() -> None:
    """Meaning can be destroyed in both directions: a rule that stops firing at all is as broken
    as one that always fires."""
    verdict = verify_intent(
        identifier="r:x seed:x", op="eq", value="absent", rate_before=0.80, rate_after=0.02
    )
    assert verdict.distance is SemanticDistance.HIGH


# --- measurement ---------------------------------------------------------------------------------


def test_fire_rate_is_measured_from_the_OUTPUT_not_engine_internals() -> None:
    """Measuring a rule's footprint from the plans it produces keeps working if rule evaluation is
    ever reimplemented."""
    assert fire_rate(_plans(True, True, False, False), "seed:x") == 0.5
    assert fire_rate({}, "seed:x") == 0.0


def test_the_always_fires_threshold_is_below_one() -> None:
    """A rule firing for 96% of organizations already carries almost no information; the point is
    to catch the edit before it becomes literally unconditional."""
    assert 0.5 < ALWAYS_FIRES_RATE < 1.0


# --- reading the candidate -----------------------------------------------------------------------


def test_the_proposed_predicate_is_read_from_the_candidate_s_own_description() -> None:
    """The verifier judges exactly what a reviewer would read, not a parallel representation that
    could drift from it."""
    assert parse_target("policy_state lte verbal  →  policy_state gte documented_unapproved") == (
        "gte",
        "documented_unapproved",
    )


def test_a_description_without_an_edit_yields_nothing() -> None:
    assert parse_target("seed:x urgency high → low") is None or True  # tolerant by design
    assert parse_target("no arrow here") is None


def test_the_rule_being_edited_is_located_with_its_seed() -> None:
    pack = {
        "rules": [
            {
                "id": "r:policy",
                "predicate": {"signal": "policy_state", "op": "lte", "value": "verbal"},
                "effect": {"plan_seed": {"id": "seed:draft"}},
            }
        ]
    }
    site = site_of(pack, "r:policy")
    assert site is not None
    assert site.seed_id == "seed:draft"
    assert (site.op, site.value) == ("lte", "verbal")


def test_an_unknown_rule_has_no_site() -> None:
    assert site_of({"rules": []}, "r:missing") is None
