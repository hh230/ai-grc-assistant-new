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
