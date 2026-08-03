"""End-to-end, DB-gated tests for the three Governance Plan tools (ADR 0066 §3): resolve →
draft → finalize, against real Postgres. Skips cleanly when no database is reachable. A fake
`GenerationProvider` stands in for the LLM (no live call, no network) — the tools' own
orchestration/persistence logic is what's under test.
"""

from __future__ import annotations

import json
import uuid

import pytest

psycopg = pytest.importorskip("psycopg")

from governance_discovery.analysis import analyze  # noqa: E402
from governance_discovery.engine import DiscoveryEngine  # noqa: E402
from governance_discovery.pack import load_bundled_packs  # noqa: E402
from governance_discovery.session import DiscoverySession  # noqa: E402
from pipeline_contracts import TenantContext  # noqa: E402
from tool_registry import PAYLOAD_INSTRUCTION, PAYLOAD_PRIOR_CONTEXT  # noqa: E402

from governance_plan_tools.applicability_tool import OrgApplicabilityTool  # noqa: E402
from governance_plan_tools.draft_tool import PlanDraftTool  # noqa: E402
from governance_plan_tools.finalize_tool import PlanFinalizeTool  # noqa: E402
from governance_store import PostgresGovernanceStore  # noqa: E402
from governance_store.config import dsn  # noqa: E402

from tests.fake_provider import FakeGenerationProvider  # noqa: E402

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


def _connect():
    try:
        return psycopg.connect(dsn(), autocommit=True, connect_timeout=3)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no reachable PostgreSQL ({exc})")


def _tenant() -> str:
    return f"it_tools_{uuid.uuid4().hex[:8]}"


def _make_signals():
    from governance_discovery.signal import Signal, SignalSet, ValueType

    enum_keys = {
        "primary_activity", "org_structure_state", "policy_state", "risk_register_state",
        "internal_audit_state", "execution_capacity",
    }
    bool_keys = {
        "provides_saas", "has_compliance_officer", "has_board", "has_legal_team", "has_it_team",
        "handles_personal_data", "has_gov_clients",
    }
    signals = {}
    for key, value in _SIGNALS.items():
        if key in enum_keys:
            vt = ValueType.ENUM
        elif key in bool_keys:
            vt = ValueType.BOOLEAN
        else:
            vt = ValueType.NUMERIC
        signals[key] = Signal(key=key, value_type=vt, value=value)
    return SignalSet(signals)


@pytest.fixture
def conn():
    c = _connect()
    from governance_store.schema import apply_schema

    apply_schema(c)
    yield c
    c.close()


def _cleanup(conn, tenant_id: str) -> None:
    conn.execute("DELETE FROM governance_plan_events WHERE tenant_id = %(t)s", {"t": tenant_id})
    conn.execute("DELETE FROM governance_plan_items WHERE tenant_id = %(t)s", {"t": tenant_id})
    conn.execute("DELETE FROM governance_plans WHERE tenant_id = %(t)s", {"t": tenant_id})
    conn.execute("DELETE FROM organization_profiles WHERE tenant_id = %(t)s", {"t": tenant_id})
    conn.execute("DELETE FROM discovery_answers WHERE tenant_id = %(t)s", {"t": tenant_id})
    conn.execute("DELETE FROM discovery_sessions WHERE tenant_id = %(t)s", {"t": tenant_id})


def _concluded_session(store: PostgresGovernanceStore, tenant_id: str, engine: DiscoveryEngine) -> DiscoverySession:
    signals = _make_signals()
    applicability = analyze(signals, engine)
    session = DiscoverySession.start(f"sess_{uuid.uuid4().hex[:8]}", tenant_id, now=1000.0)
    session = session.concluded(applicability, now=1001.0)
    active_packs = engine.active_packs(signals)
    session = session.__class__(**{**session.__dict__, "signals": signals, "active_pack_ids": tuple(p.pack_id for p in active_packs)})
    store.save_session(session)
    store.upsert_organization_baseline(tenant_id, session.active_pack_ids, signals, now=1001.0)
    return session


def test_full_resolve_draft_finalize_flow(conn) -> None:
    tenant_id = _tenant()
    tenant = TenantContext(tenant_id=tenant_id, principal_id="user_1", roles=("owner",))
    try:
        store = PostgresGovernanceStore(connection=conn)
        engine = DiscoveryEngine(load_bundled_packs())
        session = _concluded_session(store, tenant_id, engine)

        # Step 1: resolve_applicability
        applicability_tool = OrgApplicabilityTool(store)
        step1_result = applicability_tool.invoke({PAYLOAD_INSTRUCTION: session.id}, tenant)
        assert step1_result["ok"] is True

        # Step 3: draft_plan (step 2 / control library omitted — not needed for this test's
        # assertions, and draft_tool reads the session directly rather than depending on it)
        provider = FakeGenerationProvider()
        draft_tool = PlanDraftTool(store, provider, now=lambda: 2000.0)
        step3_result = draft_tool.invoke({PAYLOAD_INSTRUCTION: session.id}, tenant)
        assert step3_result["ok"] is True
        draft = json.loads(step3_result["output"])
        assert draft["items"]
        assert draft["executive_summary"]
        assert all(item["rationale"] for item in draft["items"])
        assert all(item["due_at"] is not None for item in draft["items"])

        # Step 4: finalize_plan (consequential) — prior_context mirrors the executor's exact
        # rendering (ADR 0051): "[Step N]\n<output>" blocks, joined by a blank line.
        prior_context = f"[Step 1]\n{step1_result['output']}\n\n[Step 3]\n{step3_result['output']}"
        finalize_tool = PlanFinalizeTool(store, engine, new_id=lambda: f"plan_{uuid.uuid4().hex[:8]}", now=lambda: 3000.0)
        step4_result = finalize_tool.invoke(
            {PAYLOAD_PRIOR_CONTEXT: prior_context, "mission_id": "mission_1"}, tenant
        )
        assert step4_result["ok"] is True
        finalized = json.loads(step4_result["output"])
        assert finalized["version"] == 1

        plan = store.get_plan(finalized["plan_id"], tenant_id)
        assert plan is not None
        assert plan.status == "active"
        assert plan.executive_summary

        items = store.list_plan_items(plan.id, tenant_id)
        assert len(items) == len(draft["items"])
        assert all(item.status == "not_started" for item in items)
        assert all(item.rationale for item in items)

        # Dependency ids were correctly remapped to the persisted, plan-scoped item ids.
        dependent = next((i for i in items if i.depends_on_item_ids), None)
        if dependent is not None:
            dep_ids = {i.id for i in items}
            assert all(dep in dep_ids for dep in dependent.depends_on_item_ids)
    finally:
        _cleanup(conn, tenant_id)


def test_finalizing_a_second_plan_supersedes_the_first(conn) -> None:
    tenant_id = _tenant()
    tenant = TenantContext(tenant_id=tenant_id, principal_id="user_1", roles=("owner",))
    try:
        store = PostgresGovernanceStore(connection=conn)
        engine = DiscoveryEngine(load_bundled_packs())
        session = _concluded_session(store, tenant_id, engine)
        provider = FakeGenerationProvider()

        def run_to_finalize(plan_id: str, now: float):
            draft_tool = PlanDraftTool(store, provider, now=lambda: now)
            step3 = draft_tool.invoke({PAYLOAD_INSTRUCTION: session.id}, tenant)
            prior_context = f"[Step 3]\n{step3['output']}"
            finalize_tool = PlanFinalizeTool(store, engine, new_id=lambda: plan_id, now=lambda: now)
            return finalize_tool.invoke({PAYLOAD_PRIOR_CONTEXT: prior_context, "mission_id": "m1"}, tenant)

        run_to_finalize("plan_v1", 2000.0)
        run_to_finalize("plan_v2", 3000.0)

        versions = store.list_plan_versions(tenant_id)
        assert [p.version for p in versions] == [1, 2]
        assert versions[0].status == "superseded"
        assert versions[0].maturity_at_supersession is not None
        assert versions[1].status == "active"
        assert versions[1].previous_plan_id == "plan_v1"
        assert store.get_active_plan(tenant_id).id == "plan_v2"
    finally:
        _cleanup(conn, tenant_id)


def test_draft_falls_back_gracefully_when_generation_fails(conn) -> None:
    tenant_id = _tenant()
    tenant = TenantContext(tenant_id=tenant_id, principal_id="user_1", roles=("owner",))
    try:
        store = PostgresGovernanceStore(connection=conn)
        engine = DiscoveryEngine(load_bundled_packs())
        session = _concluded_session(store, tenant_id, engine)

        failing_provider = FakeGenerationProvider(fail=True)
        draft_tool = PlanDraftTool(store, failing_provider, now=lambda: 2000.0)
        result = draft_tool.invoke({PAYLOAD_INSTRUCTION: session.id}, tenant)
        assert result["ok"] is True  # fail-safe: a broken LLM doesn't fail the whole draft
        draft = json.loads(result["output"])
        assert draft["items"]
        assert all(item["rationale"] for item in draft["items"])  # fallback text, never empty
        assert result["warnings"]  # but the fallback is flagged, not silent
    finally:
        _cleanup(conn, tenant_id)
