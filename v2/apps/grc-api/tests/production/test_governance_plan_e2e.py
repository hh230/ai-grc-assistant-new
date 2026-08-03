"""End-to-end, DB-gated: the `generate_governance_plan` Mission run through the **real REST API**
(ADR 0066 §3), proving the whole chain works as one product, not just as isolated packages:

    concluded Discovery session (seeded directly, like `governance-plan-tools`' own integration
    tests do) → POST /v1/missions → POST .../run → resolve/gather/draft steps run → the mission
    pauses at the ADR 0044 human-approval gate before `finalize_plan` (the one consequential step)
    → GET /v1/approvals finds it → POST .../approve → the plan is persisted as an immutable
    snapshot (§3.1) → GET /v1/governance-plans/active returns it with its items → marking an item
    done recalculates maturity live (§5.3), and reopening it reverts that recalculation.

The production default executor is still `EchoExecutor` (the Wave 1 executor commit is separate,
tracked, unrelated work — see `tests/production/test_production_defaults.py`); this test injects a
real `ToolRegistry`-backed `RegistryExecutor` via the same `executor=` seam every other test in
this suite already uses to observe real behaviour, with a deterministic fake `GenerationProvider`
(never a live LLM call — CLAUDE.md's testing standards: "mock LLM/vector calls in unit tests").
"""

from __future__ import annotations

import uuid

import pytest

psycopg = pytest.importorskip("psycopg")

from fastapi.testclient import TestClient  # noqa: E402
from framework_library import ControlLibraryTool, FrameworkLibrary  # noqa: E402
from governance_discovery.analysis import analyze  # noqa: E402
from governance_discovery.engine import DiscoveryEngine  # noqa: E402
from governance_discovery.pack import load_bundled_packs  # noqa: E402
from governance_discovery.session import DiscoverySession  # noqa: E402
from governance_discovery.signal import Signal, SignalSet, ValueType  # noqa: E402
from governance_plan_tools.applicability_tool import OrgApplicabilityTool  # noqa: E402
from governance_plan_tools.draft_tool import PlanDraftTool  # noqa: E402
from governance_plan_tools.finalize_tool import PlanFinalizeTool  # noqa: E402
from governance_store import PostgresGovernanceStore  # noqa: E402
from governance_store.config import dsn as governance_dsn  # noqa: E402
from governance_store.schema import apply_schema as apply_governance_schema  # noqa: E402
from grc_api.app import create_app  # noqa: E402
from grc_api.composition import Storage  # noqa: E402
from pipeline_contracts import Answer  # noqa: E402
from pipeline_tool import RegistryExecutor  # noqa: E402
from tool_registry import ToolRegistry  # noqa: E402

AUTH_A = {"Authorization": "Bearer dev-tenant-a"}
AUTH_APPROVER_A = {"Authorization": "Bearer dev-approver-a"}

_SIGNALS = {
    "primary_activity": "legal_services",
    "employee_count": 15,
    "provides_saas": False,
    "has_compliance_officer": False,
    "has_board": False,
    "org_structure_state": "absent",
    "policy_state": "verbal",
    "risk_register_state": "absent",
    "internal_audit_state": "absent",
    "has_legal_team": True,
    "has_it_team": False,
    "execution_capacity": "ad_hoc",
    "handles_personal_data": True,
    "has_gov_clients": False,
}
_ENUM_KEYS = {
    "primary_activity", "org_structure_state", "policy_state", "risk_register_state",
    "internal_audit_state", "execution_capacity",
}
_BOOL_KEYS = {
    "provides_saas", "has_compliance_officer", "has_board", "has_legal_team", "has_it_team",
    "handles_personal_data", "has_gov_clients",
}


class _FakeGenerationProvider:
    """A deterministic stand-in for the LLM (no network, no live call) — proves the tools'
    orchestration/persistence is correct without depending on an API key being configured."""

    name = "fake"

    def generate(self, request):  # noqa: ANN001
        prompt = request.segments[-1].content
        if "RATIONALE:" in prompt or "OBJECTIVE:" in prompt:
            text = (
                "RATIONALE: Identified from the facts you shared.\n"
                "OBJECTIVE: Close the identified gap.\n"
                "EXPECTED_OUTCOME: The gap is closed and tracked going forward.\n"
                "RISK_IF_SKIPPED: The underlying exposure continues unmanaged."
            )
        elif "DESCRIPTION:" in prompt:
            text = (
                "DESCRIPTION: A specific control is not yet in place.\n"
                "IMPACT: Could delay detection."
            )
        else:
            text = "Early-stage governance structure. Focus first on ownership and accountability."
        return Answer(text=text, provider=self.name, model="fake-model")


def _make_signals() -> SignalSet:
    signals = {}
    for key, value in _SIGNALS.items():
        if key in _ENUM_KEYS:
            vt = ValueType.ENUM
        elif key in _BOOL_KEYS:
            vt = ValueType.BOOLEAN
        else:
            vt = ValueType.NUMERIC
        signals[key] = Signal(key=key, value_type=vt, value=value)
    return SignalSet(signals)


def _cleanup(dsn: str, tenant_id: str) -> None:
    conn = psycopg.connect(dsn, autocommit=True)
    try:
        for table in (
            "governance_plan_events", "governance_plan_items", "governance_plans",
            "organization_profiles", "discovery_answers", "discovery_sessions",
        ):
            conn.execute(f"DELETE FROM {table} WHERE tenant_id = %(t)s", {"t": tenant_id})
    finally:
        conn.close()


@pytest.fixture
def dsn() -> str:
    try:
        conn = psycopg.connect(governance_dsn(), autocommit=True, connect_timeout=3)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no reachable PostgreSQL ({exc})")
    apply_governance_schema(conn)
    conn.close()
    return governance_dsn()


@pytest.fixture
def tenant_id(dsn: str):
    # The fixed dev credential map (`grc_api.security.development_identity_provider`) resolves
    # `Bearer dev-tenant-a` to exactly `tenant_id="tenant-a"` — there is no way to mint a fresh
    # tenant per test with the dev provider, so isolation comes from per-test cleanup instead
    # (the same discipline `tests/production/conftest.py`'s throwaway *tables* give the mission
    # subsystem; the governance tables have no per-test-table seam yet, so rows are scoped by
    # tenant_id and deleted afterward).
    tid = "tenant-a"
    _cleanup(dsn, tid)
    yield tid
    _cleanup(dsn, tid)


def _seed_concluded_session(dsn: str, tenant_id: str) -> str:
    """Seed a concluded Discovery session + its `organization_profiles` baseline directly (this
    test is about Plan generation/execution, not re-driving the interview — that is
    `tests/test_discovery.py`'s job)."""
    store = PostgresGovernanceStore(dsn=dsn)
    engine = DiscoveryEngine(load_bundled_packs())
    signals = _make_signals()
    applicability = analyze(signals, engine)
    session = DiscoverySession.start(f"sess_{uuid.uuid4().hex[:8]}", tenant_id, now=1000.0)
    session = session.concluded(applicability, now=1001.0)
    active_packs = engine.active_packs(signals)
    session = session.__class__(
        **{
            **session.__dict__,
            "signals": signals,
            "active_pack_ids": tuple(p.pack_id for p in active_packs),
        }
    )
    store.save_session(session)
    store.upsert_organization_baseline(tenant_id, session.active_pack_ids, signals, now=1001.0)
    store.close()
    return session.id


def _build_client(dsn: str) -> TestClient:
    """A real `ToolRegistry`-backed executor (this suite's injection seam, not the production
    default) so the mission runs for real — the deterministic `_FakeGenerationProvider` stands in
    for the LLM. `discovery_store_factory` points every governance read/write at the same live
    Postgres database the mission's tools themselves write to."""
    engine = DiscoveryEngine(load_bundled_packs())
    registry = ToolRegistry()
    store_for_tools = PostgresGovernanceStore(dsn=dsn)
    registry.register(OrgApplicabilityTool(store_for_tools))
    registry.register(ControlLibraryTool(FrameworkLibrary.from_bundled()))
    registry.register(PlanDraftTool(store_for_tools, _FakeGenerationProvider(), now=lambda: 2000.0))
    registry.register(
        PlanFinalizeTool(
            store_for_tools, engine, new_id=lambda: uuid.uuid4().hex, now=lambda: 3000.0
        )
    )
    executor = RegistryExecutor(registry)
    return TestClient(
        create_app(
            storage=Storage.MEMORY,
            executor=executor,
            discovery_engine=engine,
            discovery_store_factory=lambda: PostgresGovernanceStore(dsn=dsn),
        )
    )


def _create_and_run(client: TestClient, session_id: str) -> str:
    created = client.post(
        "/v1/missions",
        json={"type": "generate_governance_plan", "scope": session_id, "document_ids": []},
        headers={**AUTH_A, "Idempotency-Key": uuid.uuid4().hex},
    )
    assert created.status_code == 201, created.text
    mission_id = created.json()["mission"]["id"]
    run = client.post(f"/v1/missions/{mission_id}/run", headers=AUTH_A)
    assert run.status_code == 200, run.text
    return mission_id


def _approve(client: TestClient, mission_id: str) -> None:
    decisions = client.get("/v1/approvals?status=waiting", headers=AUTH_APPROVER_A).json()["items"]
    mine = [d for d in decisions if d["mission_id"] == mission_id]
    assert mine, "the finalize step never reached the approval gate"
    approved = client.post(
        f"/v1/missions/{mission_id}/approvals/{mine[0]['decision_id']}/approve",
        headers=AUTH_APPROVER_A,
    )
    assert approved.status_code == 200, approved.text


def test_generate_governance_plan_end_to_end_through_the_real_api(dsn: str, tenant_id: str) -> None:
    session_id = _seed_concluded_session(dsn, tenant_id)
    client = _build_client(dsn)

    mission_id = _create_and_run(client, session_id)
    detail = client.get(f"/v1/missions/{mission_id}", headers=AUTH_A).json()
    assert detail["status"] == "awaiting_approval"  # paused BEFORE the consequential finalize step

    _approve(client, mission_id)

    detail = client.get(f"/v1/missions/{mission_id}", headers=AUTH_A).json()
    assert detail["status"] == "completed"

    active = client.get("/v1/governance-plans/active", headers=AUTH_A)
    assert active.status_code == 200
    body = active.json()
    assert body is not None
    assert body["plan"]["version"] == 1
    assert body["plan"]["status"] == "active"
    assert body["plan"]["executive_summary"]
    assert body["items"], "the finalized plan has no items"
    assert all(item["status"] == "not_started" for item in body["items"])
    assert all(item["rationale"] for item in body["items"])


def test_completing_an_item_recalculates_maturity_and_reopening_reverts_it(
    dsn: str, tenant_id: str
) -> None:
    session_id = _seed_concluded_session(dsn, tenant_id)
    client = _build_client(dsn)
    mission_id = _create_and_run(client, session_id)
    _approve(client, mission_id)

    before = client.get("/v1/governance-plans/maturity", headers=AUTH_A).json()
    assert before["has_baseline"] is True

    items = client.get("/v1/governance-plans/active", headers=AUTH_A).json()["items"]
    # an item whose completion resolves a signal a maturity rule reads (ADR 0066 §5.3) — the seeded
    # organization has no compliance officer, so this seed's plan item is always present.
    target = next(
        i
        for i in items
        if "compliance owner" in i["title"].lower() or "compliance" in i["objective"].lower()
    )

    completed = client.post(f"/v1/governance-plans/items/{target['id']}/complete", headers=AUTH_A)
    assert completed.status_code == 200
    assert completed.json()["status"] == "done"

    after = client.get("/v1/governance-plans/maturity", headers=AUTH_A).json()
    assert after["maturity"] != before["maturity"], "completing the item never moved the score"

    reopened = client.post(f"/v1/governance-plans/items/{target['id']}/reopen", headers=AUTH_A)
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "not_started"

    reverted = client.get("/v1/governance-plans/maturity", headers=AUTH_A).json()
    assert reverted["maturity"] == before["maturity"], "reopening never reverted the recalculation"


def test_item_events_are_readable_and_ordered(dsn: str, tenant_id: str) -> None:
    """The audit trail (Phase 3 hardening) is no longer write-only — `complete` then `reopen`
    leaves two events readable in the order they actually happened."""
    session_id = _seed_concluded_session(dsn, tenant_id)
    client = _build_client(dsn)
    mission_id = _create_and_run(client, session_id)
    _approve(client, mission_id)

    items = client.get("/v1/governance-plans/active", headers=AUTH_A).json()["items"]
    item_id = items[0]["id"]

    events_url = f"/v1/governance-plans/items/{item_id}/events"
    assert client.get(events_url, headers=AUTH_A).json()["items"] == []

    client.post(f"/v1/governance-plans/items/{item_id}/complete", headers=AUTH_A)
    client.post(f"/v1/governance-plans/items/{item_id}/reopen", headers=AUTH_A)

    events = client.get(
        f"/v1/governance-plans/items/{item_id}/events", headers=AUTH_A
    ).json()["items"]
    assert [e["event_type"] for e in events] == ["completed", "reopened"]
    assert events[0]["sequence"] < events[1]["sequence"]


def test_start_transitions_to_in_progress_and_is_idempotent(dsn: str, tenant_id: str) -> None:
    """Phase 4: the third tracked status (Not Started -> In Progress -> Completed)."""
    session_id = _seed_concluded_session(dsn, tenant_id)
    client = _build_client(dsn)
    mission_id = _create_and_run(client, session_id)
    _approve(client, mission_id)

    items = client.get("/v1/governance-plans/active", headers=AUTH_A).json()["items"]
    item_id = items[0]["id"]
    assert items[0]["status"] == "not_started"

    started = client.post(f"/v1/governance-plans/items/{item_id}/start", headers=AUTH_A)
    assert started.status_code == 200
    assert started.json()["status"] == "in_progress"

    again = client.post(f"/v1/governance-plans/items/{item_id}/start", headers=AUTH_A)
    assert again.status_code == 200
    assert again.json()["status"] == "in_progress"  # idempotent, not a conflict

    completed = client.post(f"/v1/governance-plans/items/{item_id}/complete", headers=AUTH_A)
    assert completed.status_code == 200
    assert completed.json()["status"] == "done"

    events = client.get(
        f"/v1/governance-plans/items/{item_id}/events", headers=AUTH_A
    ).json()["items"]
    assert [e["event_type"] for e in events] == ["started", "completed"]

    missing = client.get("/v1/governance-plans/items/does-not-exist/events", headers=AUTH_A)
    assert missing.status_code == 404


def test_evidence_is_always_optional_never_a_completion_gate(dsn: str, tenant_id: str) -> None:
    session_id = _seed_concluded_session(dsn, tenant_id)
    client = _build_client(dsn)
    mission_id = _create_and_run(client, session_id)
    _approve(client, mission_id)

    items = client.get("/v1/governance-plans/active", headers=AUTH_A).json()["items"]
    item_id = items[0]["id"]

    completed = client.post(f"/v1/governance-plans/items/{item_id}/complete", headers=AUTH_A)
    assert completed.status_code == 200
    assert completed.json()["is_evidence_backed"] is False  # done with no evidence at all

    with_evidence = client.post(
        f"/v1/governance-plans/items/{item_id}/evidence",
        json={"evidence_ids": ["doc-1"]},
        headers=AUTH_A,
    )
    assert with_evidence.status_code == 200
    assert with_evidence.json()["is_evidence_backed"] is True
    assert with_evidence.json()["status"] == "done"  # attaching evidence never changed completion


def test_second_plan_supersedes_the_first_and_versions_are_listed(dsn: str, tenant_id: str) -> None:
    session_id = _seed_concluded_session(dsn, tenant_id)
    client = _build_client(dsn)

    m1 = _create_and_run(client, session_id)
    _approve(client, m1)

    session_id_2 = _seed_concluded_session(dsn, tenant_id)
    m2 = _create_and_run(client, session_id_2)
    _approve(client, m2)

    versions = client.get("/v1/governance-plans/versions", headers=AUTH_A).json()["items"]
    assert [v["version"] for v in versions] == [1, 2]
    assert versions[0]["status"] == "superseded"
    assert versions[0]["maturity_at_supersession"] is not None
    assert versions[1]["status"] == "active"

    active = client.get("/v1/governance-plans/active", headers=AUTH_A).json()
    assert active["plan"]["id"] == versions[1]["id"]


def test_tenant_isolation_holds_through_the_governance_plans_api(dsn: str, tenant_id: str) -> None:
    session_id = _seed_concluded_session(dsn, tenant_id)
    client = _build_client(dsn)
    mission_id = _create_and_run(client, session_id)
    _approve(client, mission_id)

    other = client.get(
        "/v1/governance-plans/active", headers={"Authorization": "Bearer dev-tenant-b"}
    )
    assert other.status_code == 200
    assert other.json() is None  # tenant-b has no plan of its own
