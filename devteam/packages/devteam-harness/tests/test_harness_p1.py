"""P1 tests — the harness must itself be trustworthy before it can judge the product."""

from __future__ import annotations

from devteam_harness import (
    InMemoryGovernanceStore,
    Posture,
    generate_organization,
    generate_organizations,
    run_discovery,
)

# --- determinism: the property the whole "reproduce from a seed" promise rests on -----------


def test_same_seed_yields_an_identical_organization() -> None:
    assert generate_organization(42) == generate_organization(42)


def test_different_seeds_yield_different_tenants() -> None:
    orgs = generate_organizations(50)
    assert len({o.tenant_id for o in orgs}) == 50


def test_same_seed_replays_an_identical_transcript() -> None:
    """A failure is only reproducible if the seed alone rebuilds the exact same run."""
    first = run_discovery(generate_organization(7))
    second = run_discovery(generate_organization(7))
    assert first.concluded and second.concluded
    assert [(t.question_id, t.answer, t.skipped) for t in first.turns] == [
        (t.question_id, t.answer, t.skipped) for t in second.turns
    ]


# --- the core capability --------------------------------------------------------------------


def test_a_scenario_runs_to_conclusion() -> None:
    result = run_discovery(generate_organization(1))
    assert result.ok, result.error
    assert result.concluded
    assert result.turn_count > 0


def test_conclusion_writes_the_organization_baseline() -> None:
    """The exact step the grc-api test-local store could not do — its absence is why that store
    can never finish an interview."""
    org = generate_organization(3)
    store = InMemoryGovernanceStore()
    result = run_discovery(org, store=store)
    assert result.concluded
    assert org.tenant_id in store.organization_baselines


def test_every_posture_concludes() -> None:
    """Each posture drives a different branch of the tree; none may dead-end."""
    seen: set[Posture] = set()
    for seed in range(40):
        org = generate_organization(seed)
        seen.add(org.posture)
        result = run_discovery(org)
        assert result.ok, f"{org.label}: {result.error}"
    assert seen == set(Posture)


# --- adaptivity: the reason answers are a strategy and not a recorded script -----------------


def test_no_question_is_asked_twice_in_one_interview() -> None:
    result = run_discovery(generate_organization(11))
    asked = [t.question_id for t in result.turns]
    assert len(asked) == len(set(asked)), f"repeated question in {asked}"


def test_required_questions_are_never_skipped() -> None:
    for seed in range(15):
        result = run_discovery(generate_organization(seed))
        assert not any(t.skipped and t.required for t in result.turns)


def test_optional_questions_do_get_skipped_somewhere() -> None:
    """Guards the skip path from silently going uncovered."""
    assert any(
        t.skipped for seed in range(30) for t in run_discovery(generate_organization(seed)).turns
    )


# --- tenant isolation -----------------------------------------------------------------------


def test_a_shared_store_keeps_tenants_separate() -> None:
    """Even when two scenarios share one store, neither may see the other's session."""
    store = InMemoryGovernanceStore()
    a = run_discovery(generate_organization(101), store=store)
    b = run_discovery(generate_organization(202), store=store)
    assert a.session_id is not None and b.session_id is not None
    assert store.get_session(a.session_id, b.organization.tenant_id) is None
    assert store.get_session(b.session_id, a.organization.tenant_id) is None


# --- failures are data, never crashes -------------------------------------------------------


def test_a_non_terminating_interview_is_reported_not_raised() -> None:
    result = run_discovery(generate_organization(5), max_turns=1)
    assert not result.ok
    assert result.error_type == "NonTermination"
    assert "did not conclude" in (result.error or "")
