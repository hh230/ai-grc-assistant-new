"""Tests for the Decision Verifier — the layer that asks whether the plan makes SENSE.

Every rule is tested against a plan that is technically perfect and still bad advice. That is the
whole point of this layer: none of these failures are reachable by a type checker, a schema check,
an HTTP sweep or a browser.
"""

from __future__ import annotations

from devteam_harness.decisions import (
    DecisionFinding,
    PlanContext,
    a_plan_fits_what_the_organization_can_execute,
    an_immature_organization_gets_a_plan,
    high_risk_never_gets_low_priority,
    no_action_on_something_that_does_not_exist,
    no_duplicate_tasks,
    no_step_before_its_prerequisite,
    verify_decision,
)


def _item(
    seed: str,
    *,
    bucket: str = "week_1",
    priority: str = "high",
    resolves: tuple[str, object] | None = None,
    sources: tuple[str, ...] = (),
    depends_on: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "id": f"seed:{seed}",
        "timeframe_bucket": bucket,
        "priority": priority,
        "resolves_signal": {"signal": resolves[0], "value": resolves[1]} if resolves else {},
        "source_signal_keys": list(sources),
        "depends_on_item_ids": list(depends_on),
    }


def _context(**overrides: object) -> PlanContext:
    base: dict[str, object] = {
        "signals": {},
        "plan_items": [],
        "gaps": [],
        "maturity": {},
        "capacity": {},
    }
    base.update(overrides)
    return PlanContext(**base)  # type: ignore[arg-type]


# --- "review the security policy" when there is no policy --------------------------------------


def test_it_catches_asking_to_review_something_that_does_not_exist() -> None:
    """The owner's example, exactly: the organization says it has no policies and the plan says
    "review the security policy". Nothing technical is wrong — there is simply nothing to review."""
    context = _context(
        signals={"policy_state": "absent"},
        plan_items=[_item("review_security_policy", sources=("policy_state",))],
    )
    findings = no_action_on_something_that_does_not_exist(context)
    assert findings, "reviewing a non-existent policy must be reported"
    assert "nothing in the plan creates it" in findings[0].detail


def test_verbal_does_not_count_as_existing() -> None:
    """"We talk about it" is not a document anyone can review or approve."""
    context = _context(
        signals={"policy_state": "verbal"},
        plan_items=[_item("approve_policy", sources=("policy_state",))],
    )
    assert no_action_on_something_that_does_not_exist(context)


def test_creating_it_first_makes_the_action_coherent() -> None:
    """"Draft the policy, then approve it" is a sensible plan; "approve it" alone is not."""
    context = _context(
        signals={"policy_state": "absent"},
        plan_items=[
            _item("draft_policy", bucket="week_1", resolves=("policy_state", "approved")),
            _item("review_policy", bucket="month_3", sources=("policy_state",)),
        ],
    )
    assert not no_action_on_something_that_does_not_exist(context)


def test_creating_it_afterwards_does_not() -> None:
    """Order matters: being told to approve in week 1 what gets drafted in month 3 is incoherent."""
    context = _context(
        signals={"policy_state": "absent"},
        plan_items=[
            _item("draft_policy", bucket="month_3", resolves=("policy_state", "approved")),
            _item("approve_policy", bucket="week_1", sources=("policy_state",)),
        ],
    )
    findings = no_action_on_something_that_does_not_exist(context)
    assert findings and "before the item that creates it" in findings[0].detail


def test_an_action_on_something_that_exists_is_fine() -> None:
    """The rule must not fire on good advice — reviewing an approved policy is exactly right."""
    context = _context(
        signals={"policy_state": "approved"},
        plan_items=[_item("review_policy", sources=("policy_state",))],
    )
    assert not no_action_on_something_that_does_not_exist(context)


def test_creating_something_absent_is_never_flagged() -> None:
    """"Draft a policy" when there is no policy is the correct advice, not a defect."""
    context = _context(
        signals={"policy_state": "absent"},
        plan_items=[_item("draft_policy", sources=("policy_state",))],
    )
    assert not no_action_on_something_that_does_not_exist(context)


# --- ordering ----------------------------------------------------------------------------------


def test_it_catches_a_task_scheduled_before_its_prerequisite() -> None:
    context = _context(
        plan_items=[
            _item("formalize_structure", bucket="month_3"),
            _item("draft_policies", bucket="week_1", depends_on=("seed:formalize_structure",)),
        ]
    )
    findings = no_step_before_its_prerequisite(context)
    assert findings and "depends on" in findings[0].detail


def test_a_missing_dependency_is_left_to_the_invariant() -> None:
    """Separation of concerns: `plan_dependencies_exist` owns "is it present". This rule owns
    "does the order make sense". Reporting both would double-count one defect."""
    context = _context(plan_items=[_item("a", depends_on=("seed:ghost",))])
    assert not no_step_before_its_prerequisite(context)


# --- priority ----------------------------------------------------------------------------------


def test_a_high_severity_gap_answered_with_a_low_priority_task_is_reported() -> None:
    """Mis-prioritising is worse than omitting: an organization that trusts the ordering does the
    low-priority item last and believes it is being systematic while the worst exposure stays open.
    """
    context = _context(
        gaps=[{"id": "gap:1", "severity": "critical", "source_signal_keys": ["risk_state"]}],
        plan_items=[_item("establish_risk_register", priority="low", sources=("risk_state",))],
    )
    findings = high_risk_never_gets_low_priority(context)
    assert findings and "only low" in findings[0].detail


def test_a_gap_urgently_addressed_is_fine_even_if_a_RELATED_task_is_medium() -> None:
    """The strict reading ("every related task must be urgent") produced 3,250 false positives the
    moment gaps gained provenance: a critical gap properly answered by a critical task was
    condemned because a secondary task sharing one signal was medium."""
    context = _context(
        gaps=[{"gap_id": "gap:1", "severity": "critical", "source_signal_keys": ["has_officer"]}],
        plan_items=[
            _item("designate_compliance_owner", priority="critical", sources=("has_officer",)),
            _item("establish_oversight_body", priority="medium", sources=("has_officer",)),
        ],
    )
    assert high_risk_never_gets_low_priority(context) == []


def test_a_high_severity_gap_answered_with_a_high_priority_task_is_fine() -> None:
    context = _context(
        gaps=[{"id": "gap:1", "severity": "critical", "source_signal_keys": ["risk_state"]}],
        plan_items=[_item("establish_risk_register", priority="critical", sources=("risk_state",))],
    )
    assert not high_risk_never_gets_low_priority(context)


# --- duplication -------------------------------------------------------------------------------


def test_two_tasks_moving_the_same_signal_to_the_same_state_are_duplicates() -> None:
    """Duplication inflates the plan, makes the organization do work twice, and destroys trust in
    the plan's length as a signal of effort."""
    context = _context(
        plan_items=[
            _item("draft_policies", resolves=("policy_state", "approved")),
            _item("write_policy_documents", resolves=("policy_state", "approved")),
        ]
    )
    findings = no_duplicate_tasks(context)
    assert findings and "both move policy_state" in findings[0].detail


def test_two_tasks_moving_the_same_signal_to_DIFFERENT_states_are_not_duplicates() -> None:
    """A ladder is not a duplicate: draft-then-approve legitimately touches one signal twice."""
    context = _context(
        plan_items=[
            _item("draft_policies", resolves=("policy_state", "documented_unapproved")),
            _item("approve_policies", resolves=("policy_state", "approved")),
        ]
    )
    assert not no_duplicate_tasks(context)


# --- the most damaging output ------------------------------------------------------------------


def test_an_organization_scoring_zero_must_never_get_an_empty_plan() -> None:
    """The worst possible output: the organization least equipped to know what to do is told there
    is nothing to do, and reads it as reassurance."""
    context = _context(
        plan_items=[],
        maturity={"governance": {"stars": 0}, "risk": {"stars": 0}, "leadership": {"stars": 4}},
    )
    findings = an_immature_organization_gets_a_plan(context)
    assert findings and "governance" in findings[0].detail


def test_a_mature_organization_may_legitimately_have_an_empty_plan() -> None:
    """Nothing to do is a valid answer when there is genuinely nothing to do."""
    context = _context(plan_items=[], maturity={"governance": {"stars": 5}})
    assert not an_immature_organization_gets_a_plan(context)


# --- executability -----------------------------------------------------------------------------


def test_a_plan_larger_than_the_organization_can_execute_is_reported() -> None:
    """Measured against the product's OWN capacity model, not an invented number — an unexecutable
    plan is abandoned rather than partially followed."""
    context = _context(
        plan_items=[_item(f"task_{n}") for n in range(30)],
        capacity={"tier": "micro", "per_period_budget": {"week_1": 1, "week_2": 1, "month_1": 2}},
    )
    findings = a_plan_fits_what_the_organization_can_execute(context)
    assert findings and "whole-horizon budget is 4" in findings[0].detail


def test_a_plan_within_budget_is_fine() -> None:
    context = _context(
        plan_items=[_item("a"), _item("b")],
        capacity={"tier": "micro", "per_period_budget": {"week_1": 2, "week_2": 2}},
    )
    assert not a_plan_fits_what_the_organization_can_execute(context)


# --- the suite ---------------------------------------------------------------------------------


def test_a_good_plan_produces_no_findings() -> None:
    """The rules must not fire on sound advice, or nobody will read them."""
    context = _context(
        signals={"policy_state": "absent", "risk_register_state": "absent"},
        plan_items=[
            _item("draft_policies", bucket="week_1", resolves=("policy_state", "approved")),
            _item(
                "establish_risk_register",
                bucket="week_2",
                resolves=("risk_register_state", "approved"),
            ),
        ],
        maturity={"governance": {"stars": 0}},
        capacity={"tier": "small", "per_period_budget": {"week_1": 4, "week_2": 4}},
    )
    assert verify_decision(context) == []


def test_every_rule_is_wired_into_the_suite() -> None:
    """A rule that exists but is never run is worse than no rule: it reads as coverage."""
    from devteam_harness.decisions import RULES

    assert len(RULES) == 8
    assert all(callable(rule) for rule in RULES)


def test_findings_are_typed_not_strings() -> None:
    context = _context(
        plan_items=[], maturity={"governance": {"stars": 0}}
    )
    findings = verify_decision(context)
    assert findings and all(isinstance(f, DecisionFinding) for f in findings)


# --- gaps ---------------------------------------------------------------------------------------


def test_a_critical_gap_with_no_matching_task_is_reported() -> None:
    context = _context(
        gaps=[{"gap_id": "gap:x", "severity": "critical", "source_signal_keys": ["has_dpo"]}],
        plan_items=[_item("draft_policies", sources=("policy_state",))],
    )
    from devteam_harness.decisions import every_critical_gap_has_a_task

    findings = every_critical_gap_has_a_task(context)
    assert findings and "no plan item addresses" in findings[0].detail


def test_a_critical_gap_that_IS_addressed_is_not_reported() -> None:
    """The false positive that nearly shipped: seed 7 flags
    gap:gov_client_without_compliance_officer AND contains seed:designate_compliance_owner, which
    addresses it exactly. Reporting that would be crying wolf about correct behaviour."""
    context = _context(
        gaps=[{"gap_id": "gap:x", "severity": "critical", "source_signal_keys": ["has_officer"]}],
        plan_items=[_item("designate_compliance_owner", sources=("has_officer",))],
    )
    from devteam_harness.decisions import every_critical_gap_has_a_task

    assert every_critical_gap_has_a_task(context) == []


def test_an_untraceable_gap_is_a_TRACEABILITY_finding_not_an_unaddressed_one() -> None:
    """The two are deliberately different claims: one says the advice is wrong, the other says the
    advice cannot be checked. Conflating them produced 78 false positives on 300 organizations."""
    from devteam_harness.decisions import every_critical_gap_has_a_task, gaps_are_traceable_to_tasks

    context = _context(
        gaps=[{"gap_id": "gap:x", "severity": "critical"}],  # no source_signal_keys at all
        plan_items=[_item("designate_compliance_owner", sources=("has_officer",))],
    )
    assert every_critical_gap_has_a_task(context) == [], "must not claim it is unaddressed"
    findings = gaps_are_traceable_to_tasks(context)
    assert findings and "no source signals" in findings[0].detail


# --- every task the engine can emit must be presentable ----------------------------------------


def test_every_seed_the_packs_can_emit_has_a_label_in_BOTH_languages() -> None:
    """A task with no title renders as a raw key. This caught a PRE-EXISTING defect:
    `establish_governance_oversight_body` fired in real plans and had no label in either language,
    so a customer saw an untitled item. Bilingual is not optional — Arabic is a first-class
    surface for the KSA frameworks this product targets."""
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[4]
    packs = root / "v2/packages/governance-discovery/governance_discovery/packs"
    messages = root / "apps/web/messages"
    if not packs.is_dir() or not messages.is_dir():  # pragma: no cover - outside the monorepo
        return

    seeds = {"confirm_basics_with_advisor"}  # the code-level fallback in analysis.py
    for pack in packs.glob("*.json"):
        for rule in json.loads(pack.read_text(encoding="utf-8")).get("rules", []):
            seed = (rule.get("effect") or {}).get("plan_seed")
            if seed:
                seeds.add(str(seed["id"]).removeprefix("seed:"))

    for language in ("en", "ar"):
        labels = json.loads((messages / f"{language}.json").read_text(encoding="utf-8"))
        present = labels["plan"]["seed"]
        missing = sorted(seeds - set(present))
        assert not missing, f"{language}: plan tasks with no label: {missing}"
        for key in seeds:
            assert present[key].get("title"), f"{language}: {key} has an empty title"
            assert present[key].get("rationale"), f"{language}: {key} has no rationale"
