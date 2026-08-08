"""The two properties the final audit found missing, against a real Postgres (ADR 0068).

**The stored version decides.** Before this, `resolve_applicability` and the draft tool read
`session.applicability` — the CORE analysis — so a sector conclusion could compute a v2, apply
every constraint to it, record it, and then watch the plan be built from something else. The
channel wrote an audit row and called it a decision.

**The conclusion is atomic.** The store is autocommit, so the three writes that end an interview
were three commits: a failure on the last left a session concluded with no analysis version, the
exact state the ADR calls impossible.

Both are tested by making the difference real — v1 says A, v2 says B, and the assertion is which
one the plan is built from — rather than by asserting a call order.
"""

from __future__ import annotations

import json
import os
import pathlib
import uuid

import pytest

psycopg = pytest.importorskip("psycopg")

MIGRATIONS = (
    pathlib.Path(__file__).resolve().parents[4] / "packages" / "governance-store" / "migrations"
)
DSN_ENV_VAR = "GOVERNANCE_SCHEMA_TEST_DSN"
DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5432/rasheed_adr68_authority_tests"
TENANT = "t_auth"


@pytest.fixture(scope="module")
def dsn():
    return os.environ.get(DSN_ENV_VAR, DEFAULT_DSN)


@pytest.fixture(scope="module")
def conn(dsn):
    base, _, database = dsn.rpartition("/")
    try:
        with psycopg.connect(f"{base}/postgres", autocommit=True, connect_timeout=3) as setup:
            setup.execute(f'DROP DATABASE IF EXISTS "{database}"')
            setup.execute(f'CREATE DATABASE "{database}"')
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no reachable PostgreSQL ({exc})")
    connection = psycopg.connect(dsn, autocommit=True)
    for migration in sorted(MIGRATIONS.glob("*.sql"), key=lambda p: p.name):
        connection.execute(migration.read_text(encoding="utf-8"))
    yield connection
    connection.close()


@pytest.fixture
def clean(conn):
    conn.execute("SET session_replication_role = replica")
    for table in ("governance_plan_items", "governance_plans", "session_applicability_versions",
                  "discovery_answers", "discovery_sessions", "organization_profiles"):
        conn.execute(f"DELETE FROM {table}")
    conn.execute("SET session_replication_role = DEFAULT")
    return conn


# Two analyses that are unmistakably different: A recommends nothing, B recommends ISO 27001 and
# carries a plan item. If the plan is built from A when B exists, every assertion below fails.
ANALYSIS_A = {"frameworks": [], "maturity": {}, "maturity_vision": {}, "capacity": {},
              "gaps": [], "plan_items": [], "coverage": {}}
ANALYSIS_B = {
    "frameworks": [{"framework_id": "framework:iso_27001", "confidence": 0.9,
                    "rationale_key": "r.iso"}],
    "maturity": {"security": {"score": 2, "stars": 2, "label": "developing"}},
    "maturity_vision": {"security": {"score": 4, "stars": 4, "label": "managed"}},
    "capacity": {"tier": "mid", "score": 40.0, "per_period_budget": {}},
    "gaps": [{"gap_id": "gap:iso_missing", "severity": "high", "rationale_key": "r.gap"}],
    "plan_items": [{
        "id": "seed:iso_baseline", "pillar": "security", "title_key": "t.iso",
        "objective_key": "o.iso", "rationale_key": "r.iso", "priority": 1,
        "timeframe_bucket": "month_1", "effort_size": "medium", "confidence": 0.9,
        "urgency": "high", "depends_on_item_ids": [], "resolves_signal": None,
        "title": "ISO baseline", "objective": "Establish it", "risk_if_skipped": "Exposure",
        "expected_outcome": "Baseline in place", "source_signal_keys": [],
    }],
    "coverage": {"answered": 1, "required": 1},
}


def _session(conn, session_id="sess_auth"):
    """A concluded session whose `applicability` column still holds A — the stale value the read
    path used to trust."""
    conn.execute(
        "INSERT INTO discovery_sessions (id, tenant_id, status, signals, applicability, "
        " pack_versions, confidence_score, created_at, updated_at, concluded_at) "
        "VALUES (%s, %s, 'concluded', %s::jsonb, %s::jsonb, %s::jsonb, 1, 0, 0, 0)",
        (session_id, TENANT,
         json.dumps({"primary_activity": {"value_type": "enum", "value": "technology",
                                          "confidence": 1.0}}),
         json.dumps(ANALYSIS_A), json.dumps({"pack:core": "1.0"})),
    )
    return session_id


def _version(conn, session_id, version, source, applicability, assessment_id=None):
    version_id = f"av_{uuid.uuid4().hex[:12]}"
    conn.execute(
        "INSERT INTO session_applicability_versions (id, tenant_id, session_id, version, source, "
        " assessment_id, applicability, answer_set_hash) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, 'h')",
        (version_id, TENANT, session_id, version, source, assessment_id,
         json.dumps(applicability)),
    )
    return version_id


def _tenant_ctx():
    from pipeline_contracts import TenantContext

    return TenantContext(tenant_id=TENANT, principal_id="user_1", roles=("owner",))


# --- the stored version decides -----------------------------------------------------------------


def test_the_plan_is_built_from_v2_even_though_the_session_column_still_says_v1(clean) -> None:
    """The decisive one. v1 = A, v2 = B, `session.applicability` = A. If the plan mentions ISO
    27001 and carries the seeded item, it was built from B."""
    from governance_plan_tools import OrgApplicabilityTool
    from governance_store.store import PostgresGovernanceStore
    from tool_registry import PAYLOAD_INSTRUCTION

    session_id = _session(clean)
    _version(clean, session_id, 1, "core_conclusion", ANALYSIS_A)
    v2_id = _version(clean, session_id, 2, "sector_conclusion", ANALYSIS_B, assessment_id="as_1")

    store = PostgresGovernanceStore(connection=clean)
    result = OrgApplicabilityTool(store).invoke({PAYLOAD_INSTRUCTION: session_id}, _tenant_ctx())

    assert result["ok"] is True, result
    rendered = json.loads(result["output"])
    assert rendered["applicability_version_id"] == v2_id
    assert rendered["applicability_version"] == 2
    assert rendered["applicability"] == ANALYSIS_B
    assert rendered["applicability"] != ANALYSIS_A, "the stale column must not win"

    # And the session's own column is untouched — v2 is never written back into it.
    still = clean.execute(
        "SELECT applicability FROM discovery_sessions WHERE id = %s", (session_id,)
    ).fetchone()[0]
    assert still == ANALYSIS_A


def test_a_discovery_only_session_is_built_from_v1(clean) -> None:
    from governance_plan_tools import OrgApplicabilityTool
    from governance_store.store import PostgresGovernanceStore
    from tool_registry import PAYLOAD_INSTRUCTION

    session_id = _session(clean, "sess_v1_only")
    v1_id = _version(clean, session_id, 1, "core_conclusion", ANALYSIS_B)

    store = PostgresGovernanceStore(connection=clean)
    rendered = json.loads(
        OrgApplicabilityTool(store)
        .invoke({PAYLOAD_INSTRUCTION: session_id}, _tenant_ctx())["output"]
    )
    assert (rendered["applicability_version_id"], rendered["applicability_version"]) == (v1_id, 1)


def test_the_draft_and_the_persisted_plan_both_come_from_v2(clean) -> None:
    """Through the real draft and finalize tools: the plan's items and frameworks are B's, and the
    row records WHICH analysis it was built from."""
    from governance_discovery import DiscoveryEngine
    from governance_discovery.pack import load_bundled_packs
    from governance_plan_tools import PlanDraftTool, PlanFinalizeTool
    from governance_store.store import PostgresGovernanceStore
    from tool_registry import PAYLOAD_INSTRUCTION, PAYLOAD_PRIOR_CONTEXT

    session_id = _session(clean, "sess_full")
    _version(clean, session_id, 1, "core_conclusion", ANALYSIS_A)
    v2_id = _version(clean, session_id, 2, "sector_conclusion", ANALYSIS_B, assessment_id="as_2")

    store = PostgresGovernanceStore(connection=clean)
    draft_result = PlanDraftTool(store, _NoLLM(), now=lambda: 2000.0).invoke(
        {PAYLOAD_INSTRUCTION: session_id}, _tenant_ctx()
    )
    assert draft_result["ok"] is True, draft_result
    draft = json.loads(draft_result["output"])

    assert [f["framework_id"] for f in draft["inferred_frameworks"]] == ["framework:iso_27001"]
    assert [item["id"] for item in draft["items"]] == ["seed:iso_baseline"]
    assert draft["source_applicability_id"] == v2_id

    finalize = PlanFinalizeTool(
        store, DiscoveryEngine(load_bundled_packs()), new_id=lambda: "plan_auth",
        now=lambda: 2001.0,
    ).invoke(
        {PAYLOAD_PRIOR_CONTEXT: f"[Step 3]\n{draft_result['output']}", "mission_id": "m1"},
        _tenant_ctx(),
    )
    assert finalize["ok"] is True, finalize

    stored = clean.execute(
        "SELECT source_applicability_id, inferred_frameworks FROM governance_plans "
        "WHERE id = 'plan_auth'"
    ).fetchone()
    assert stored[0] == v2_id, "the plan must name the analysis it rests on"
    assert [f["framework_id"] for f in stored[1]] == ["framework:iso_27001"]


def test_a_second_read_from_a_fresh_connection_agrees_and_runs_no_engine(clean, dsn) -> None:
    """Reading twice, the second time from a store built fresh over a new connection, with
    `analyze` and `apply_derivations` replaced by functions that raise. If the read path computed
    anything, it would raise instead of agreeing."""
    import governance_discovery.analysis as analysis
    import governance_discovery.derivation as derivation
    from governance_plan_tools import OrgApplicabilityTool
    from governance_store.store import PostgresGovernanceStore
    from tool_registry import PAYLOAD_INSTRUCTION

    session_id = _session(clean, "sess_twice")
    _version(clean, session_id, 1, "core_conclusion", ANALYSIS_A)
    _version(clean, session_id, 2, "sector_conclusion", ANALYSIS_B, assessment_id="as_3")

    first = json.loads(
        OrgApplicabilityTool(PostgresGovernanceStore(connection=clean))
        .invoke({PAYLOAD_INSTRUCTION: session_id}, _tenant_ctx())["output"]
    )

    def refuse(*args, **kwargs):  # pragma: no cover - the point is that it never runs
        raise AssertionError("the read path recomputed the analysis")

    original = (analysis.analyze, derivation.apply_derivations)
    analysis.analyze, derivation.apply_derivations = refuse, refuse
    fresh = psycopg.connect(dsn, autocommit=True)
    try:
        second = json.loads(
            OrgApplicabilityTool(PostgresGovernanceStore(connection=fresh))
            .invoke({PAYLOAD_INSTRUCTION: session_id}, _tenant_ctx())["output"]
        )
    finally:
        analysis.analyze, derivation.apply_derivations = original
        fresh.close()

    assert second == first
    assert second["applicability"] == ANALYSIS_B


def test_a_session_with_no_recorded_version_is_refused_not_silently_fallen_back(clean) -> None:
    """A pre-ADR-0068 session that was never backfilled. Refused loudly: a silent fallback to the
    column is how the two values would drift apart with nobody knowing which a plan used."""
    from governance_plan_tools import OrgApplicabilityTool
    from governance_store.store import PostgresGovernanceStore
    from tool_registry import PAYLOAD_INSTRUCTION

    session_id = _session(clean, "sess_no_version")
    result = OrgApplicabilityTool(PostgresGovernanceStore(connection=clean)).invoke(
        {PAYLOAD_INSTRUCTION: session_id}, _tenant_ctx()
    )
    assert result["ok"] is False
    assert "backfill_applicability" in result["warnings"][0]


class _NoLLM:
    """A provider that is unavailable. The draft tool's contract is to fall back to templated
    prose rather than fail — which is what this test wants, because the assertions are about WHICH
    analysis was used, never about wording. It must raise `ProviderUnavailable` specifically: a
    bare `RuntimeError` is an unexpected fault and the tool is right to let that through.
    """

    name = "none"

    def generate(self, request):  # noqa: ARG002
        from pipeline_contracts import ProviderUnavailable

        raise ProviderUnavailable("no model in this test", provider="none")


# --- the conclusion is one transaction ----------------------------------------------------------


class _StoreThatFailsOnTheVersion:
    """The real Postgres store, with one method sabotaged.

    Everything else — the connection, the transaction, the SQL — is the product's. Only
    `record_applicability_version` raises, which is the last of the three writes a conclusion makes
    and therefore the one that used to leave the other two committed behind it.
    """

    def __init__(self, inner):
        self._inner = inner
        self.attempted = False

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def record_applicability_version(self, **fields):
        self.attempted = True
        raise RuntimeError("disk full while recording the analysis")


def _drive(service, tenant_id, answers):
    session, question = service.start(tenant_id)
    guard = 0
    while question is not None and guard < 60:
        guard += 1
        outcome = service.answer(session.id, tenant_id, question.id, answers[question.id])
        session, question = outcome.session, outcome.next_question
        if outcome.concluded:
            return outcome
    return None


def _answers():
    return {
        "q:primary_activity": "legal_services", "q:organization_language": "ar",
        "q:employee_count": 15, "q:provides_saas": False, "q:has_compliance_officer": True,
        "q:has_board": True, "q:org_structure_state": "approved", "q:policy_state": "approved",
        "q:risk_register_state": "approved", "q:internal_audit_state": "approved",
        "q:has_legal_team": True, "q:has_it_team": True,
        "q:execution_capacity": "dedicated_budget", "q:handles_personal_data": False,
        "q:has_gov_clients": False, "q:last_policy_review_date": "2026-01-15",
        "q:ownership_type": "private", "q:outsources_critical_functions": False,
        "q:data_geography": "ksa_only", "q:held_licenses": ["none"],
        "q:additional_context_note": "no further context", "q:tech_team_maturity": "approved",
        "q:cloud_data_residency_controlled": "yes", "q:operates_critical_infrastructure": False,
    }


def _service(store):
    from governance_discovery import DiscoveryEngine
    from governance_discovery.pack import load_bundled_packs
    from governance_session.service import DiscoverySessionService

    counter = {"n": 0, "clock": 1000.0}

    def new_id():
        counter["n"] += 1
        return f"id_{uuid.uuid4().hex[:8]}_{counter['n']}"

    def now():
        counter["clock"] += 1.0
        return counter["clock"]

    return DiscoverySessionService(
        DiscoveryEngine(load_bundled_packs()), store, new_id=new_id, now=now
    )


def test_a_failure_recording_the_version_rolls_the_whole_conclusion_back(clean) -> None:
    """The property, on a real database rather than in call order: after the failure there is no
    concluded session, no version, and no baseline — nothing partial."""
    from governance_store.store import PostgresGovernanceStore

    tenant = "t_rollback"
    store = _StoreThatFailsOnTheVersion(PostgresGovernanceStore(connection=clean))

    with pytest.raises(RuntimeError, match="disk full"):
        _drive(_service(store), tenant, _answers())

    assert store.attempted, "the sabotaged write must actually have been reached"
    concluded = clean.execute(
        "SELECT count(*) FROM discovery_sessions WHERE tenant_id = %s AND status = 'concluded'",
        (tenant,),
    ).fetchone()[0]
    versions = clean.execute(
        "SELECT count(*) FROM session_applicability_versions WHERE tenant_id = %s", (tenant,)
    ).fetchone()[0]
    baselines = clean.execute(
        "SELECT count(*) FROM organization_profiles WHERE tenant_id = %s", (tenant,)
    ).fetchone()[0]

    assert (concluded, versions, baselines) == (0, 0, 0)


def test_the_successful_conclusion_writes_all_three_together(clean) -> None:
    """The other half: the same path, unsabotaged, leaves a concluded session, its v1 and its
    baseline — and the version's applicability is the one the session concluded with."""
    from governance_store.codec import applicability_to_dict
    from governance_store.store import PostgresGovernanceStore

    tenant = "t_commit"
    store = PostgresGovernanceStore(connection=clean)
    outcome = _drive(_service(store), tenant, _answers())

    assert outcome is not None and outcome.concluded is True
    row = clean.execute(
        "SELECT version, source, applicability, session_id FROM session_applicability_versions "
        "WHERE tenant_id = %s", (tenant,)
    ).fetchone()
    assert (row[0], row[1], row[3]) == (1, "core_conclusion", outcome.session.id)
    assert row[2] == applicability_to_dict(outcome.session.applicability)
    assert clean.execute(
        "SELECT status FROM discovery_sessions WHERE id = %s", (outcome.session.id,)
    ).fetchone()[0] == "concluded"
    assert clean.execute(
        "SELECT count(*) FROM organization_profiles WHERE tenant_id = %s", (tenant,)
    ).fetchone()[0] == 1
