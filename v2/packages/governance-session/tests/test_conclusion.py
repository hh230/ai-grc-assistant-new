"""ADR 0066 §5.7: concluding a session must copy its final signals/active packs into
`organization_profiles` — the baseline `effective_signals()` (Plan Execution) builds on. Drives a
real interview to full, realistic conclusion (not a hand-constructed 'concluded' session) to prove
the whole path end to end."""

from governance_discovery.engine import DiscoveryEngine
from governance_discovery.pack import load_bundled_packs
from governance_session.service import DiscoverySessionService

from tests.fake_store import FakeGovernanceStore

_ANSWERS = {
    "q:primary_activity": "legal_services",
    "q:organization_language": "ar",
    "q:employee_count": 15,
    "q:provides_saas": False,
    "q:has_compliance_officer": True,
    "q:has_board": True,
    "q:org_structure_state": "approved",
    "q:policy_state": "approved",
    "q:risk_register_state": "approved",
    "q:internal_audit_state": "approved",
    "q:has_legal_team": True,
    "q:has_it_team": True,
    "q:execution_capacity": "dedicated_budget",
    "q:handles_personal_data": False,
    "q:has_gov_clients": False,
    "q:last_policy_review_date": "2026-01-15",
    "q:ownership_type": "private",
    "q:outsources_critical_functions": False,
    # `has_it_team` is True above, so data location is in scope for this organization.
    "q:data_geography": "ksa_only",
    # Optional, and previously never reached: the interview used to conclude before them because
    # no required question remained. Now that required questions exist in a LATER stage, these
    # earlier optional ones get their turn first.
    "q:held_licenses": ["none"],
    "q:additional_context_note": "no further context",
    # `has_it_team` also activates the technology and cloud packs.
    "q:tech_team_maturity": "approved",
    "q:cloud_data_residency_controlled": "yes",
    "q:operates_critical_infrastructure": False,
}


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


def _drive_to_conclusion(service: DiscoverySessionService, tenant_id: str):
    session, question = service.start(tenant_id)
    outcome = None
    guard = 0
    while question is not None and guard < 50:
        guard += 1
        value = _ANSWERS[question.id]
        outcome = service.answer(session.id, tenant_id, question.id, value)
        session = outcome.session
        question = outcome.next_question
        if outcome.concluded:
            break
    return outcome


def test_concluding_writes_the_organization_baseline() -> None:
    service, store = _service()
    outcome = _drive_to_conclusion(service, "tenant_a")
    assert outcome is not None
    assert outcome.concluded is True

    assert "tenant_a" in store.organization_baselines
    active_packs, signals = store.organization_baselines["tenant_a"]
    assert "pack:core" in active_packs
    assert signals.value("employee_count") == 15
    assert signals.value("org_structure_state") == "approved"


def test_baseline_active_packs_match_the_concluded_sessions_active_packs() -> None:
    service, store = _service()
    outcome = _drive_to_conclusion(service, "tenant_b")
    assert outcome is not None
    active_packs, _ = store.organization_baselines["tenant_b"]
    assert set(active_packs) == set(outcome.session.active_pack_ids)


# --- ADR 0068: the concluded analysis is recorded as version 1, here and nowhere else -----------


def test_concluding_records_applicability_version_one() -> None:
    """v1 is written where the analysis is COMPUTED.

    An earlier draft let the sector conclusion create a missing v1 on demand. That made two write
    paths for one fact, and left every session that never had a sector interview — the majority —
    with no version at all.
    """
    service, store = _service()
    outcome = _drive_to_conclusion(service, "tenant_a")
    assert outcome is not None and outcome.concluded is True

    assert len(store.applicability_versions) == 1
    version = store.applicability_versions[0]
    assert version["version"] == 1
    assert version["source"] == "core_conclusion"
    assert version["session_id"] == outcome.session.id
    assert version["tenant_id"] == "tenant_a"
    assert version["conflicts"] == []
    assert "assessment_id" not in version, "a core version names no assessment"


def test_the_recorded_version_is_the_analysis_the_session_concluded_with() -> None:
    """Recorded, not recomputed — the row and the session must agree byte for byte."""
    from governance_store.codec import applicability_to_dict

    service, store = _service()
    outcome = _drive_to_conclusion(service, "tenant_a")
    assert outcome is not None

    recorded = store.applicability_versions[0]["applicability"]
    assert recorded == applicability_to_dict(outcome.session.applicability)


def test_the_version_carries_the_pack_versions_that_ruled() -> None:
    """Without this, reproducing an old decision means guessing which packs were installed."""
    service, store = _service()
    outcome = _drive_to_conclusion(service, "tenant_a")
    assert outcome is not None

    assert store.applicability_versions[0]["engine_pack_versions"] == dict(
        outcome.session.pack_versions
    )


def test_a_session_that_has_not_concluded_records_no_version() -> None:
    service, store = _service()
    session, question = service.start("tenant_a")
    service.answer(session.id, "tenant_a", question.id, _ANSWERS[question.id])

    assert store.applicability_versions == []


# The atomicity of a conclusion is NOT tested here. This store has no transactions, so a test
# against it could only assert the ORDER of calls — and an audit found exactly that: a test whose
# name promised "the conclusion is stopped" while it proved something weaker. The real property
# lives in `grc-api/tests/production/test_stored_applicability_is_authoritative.py`, which fails
# the version write against a real Postgres and asserts that no session, version or baseline
# survives.
