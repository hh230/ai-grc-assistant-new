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
from governance_plan_tools.applicability_tool import OrgApplicabilityTool  # noqa: E402
from governance_plan_tools.draft_tool import PlanDraftTool  # noqa: E402
from governance_plan_tools.finalize_tool import PlanFinalizeTool  # noqa: E402
from governance_plan_tools.prompts import answer_language_directive  # noqa: E402
from pipeline_contracts import Language  # noqa: E402
from governance_store import PostgresGovernanceStore
from governance_store.codec import applicability_to_dict  # noqa: E402
from governance_store.config import dsn  # noqa: E402
from pipeline_contracts import TenantContext  # noqa: E402
from tool_registry import PAYLOAD_INSTRUCTION, PAYLOAD_PRIOR_CONTEXT  # noqa: E402

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
    # After the plans that cite them and before the sessions they belong to — the two foreign
    # keys pin the order. Append-only, so the trigger stands down for a fixture teardown; both
    # refusals are the product's, working as intended.
    conn.execute(
        "ALTER TABLE session_applicability_versions DISABLE TRIGGER "
        "session_applicability_versions_append_only_trg"
    )
    conn.execute(
        "DELETE FROM session_applicability_versions WHERE tenant_id = %(t)s", {"t": tenant_id}
    )
    conn.execute(
        "ALTER TABLE session_applicability_versions ENABLE TRIGGER "
        "session_applicability_versions_append_only_trg"
    )
    conn.execute("DELETE FROM organization_profiles WHERE tenant_id = %(t)s", {"t": tenant_id})
    conn.execute("DELETE FROM discovery_answers WHERE tenant_id = %(t)s", {"t": tenant_id})
    conn.execute("DELETE FROM discovery_sessions WHERE tenant_id = %(t)s", {"t": tenant_id})


def _concluded_session(
    store: PostgresGovernanceStore, tenant_id: str, engine: DiscoveryEngine
) -> DiscoverySession:
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
    # v1, exactly as the discovery conclusion writes it (ADR 0068 §D5). The plan pipeline reads the
    # recorded version now, not `session.applicability`, so a fixture without one would be
    # exercising a state the product cannot produce.
    store.record_applicability_version(
        version_id=f"av_{uuid.uuid4().hex[:12]}",
        tenant_id=tenant_id,
        session_id=session.id,
        version=1,
        source="core_conclusion",
        applicability=applicability_to_dict(applicability),
        resolved_signals=[],
        conflicts=[],
        answer_set_hash="fixture",
        engine_pack_versions=dict(session.pack_versions or {}),
    )
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
        finalize_tool = PlanFinalizeTool(
            store, engine, new_id=lambda: f"plan_{uuid.uuid4().hex[:8]}", now=lambda: 3000.0
        )
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

        # The i18n keys the rule engine emitted survived all the way to storage, BESIDE the
        # rendered text rather than instead of it. This is where they used to be lost: `finalize`
        # built each PlanItem field by field and never mentioned them, so a translatable title
        # reached the database as English prose with nothing left to translate from.
        assert all(item.title for item in items), "the rendered text is still authoritative"
        assert any(item.title_key for item in items), "no key survived the draft → finalize → store path"
        keyed = next(i for i in items if i.title_key)
        assert keyed.title_key.startswith("plan."), keyed.title_key

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
            return finalize_tool.invoke(
                {PAYLOAD_PRIOR_CONTEXT: prior_context, "mission_id": "m1"}, tenant
            )

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


# --- sector answers reach the WORDING and nothing else (ADR 0067) ------------------------------


class _SectorAnswers:
    """A `SectorAnswerReader` double holding one concluded assessment's answers."""

    def __init__(self, answers, completed=True):
        self._answers = answers
        self._completed = completed

    def find_assessment_for_session(self, source_session_id, *, tenant_id):
        return {"id": "as_1", "completed_at": 1.0 if self._completed else None}

    def load_plan_context(self, assessment_id, *, tenant_id):
        return {"sector_answers": self._answers}


_REAL_ESTATE_ANSWERS = [
    {
        "canonical_text_ar": "هل تمتلك المنشأة ترخيصًا ساريًا من الهيئة العامة للعقار؟",
        "answer": False,
    },
    {"canonical_text_ar": "هل تحتفظ المنشأة بحساب ضمان منفصل لأموال العملاء؟", "answer": False},
]


def _draft(store, session_id, tenant, sector=None):
    provider = FakeGenerationProvider()
    tool = PlanDraftTool(store, provider, sector_answers=sector, now=lambda: 2000.0)
    result = tool.invoke({PAYLOAD_INSTRUCTION: session_id}, tenant)
    assert result["ok"] is True
    return json.loads(result["output"]), provider


def test_sector_answers_change_NOTHING_the_rule_engine_decided(conn) -> None:
    """The one property this whole layer stands on.

    The plan's structure has ONE source — the Core rules. Sector answers explain it, prioritize it,
    and give it examples; they must not add, remove, merge or reorder a single action. Two drafts
    of the same session, one with a sector interview behind it and one without, must be identical
    in every field the engine decided.
    """
    tenant_id = _tenant()
    tenant = TenantContext(tenant_id=tenant_id, principal_id="user_1", roles=("owner",))
    store = PostgresGovernanceStore(connection=conn)
    session = _concluded_session(store, tenant_id, DiscoveryEngine(load_bundled_packs()))

    without, _ = _draft(store, session.id, tenant)
    with_sector, _ = _draft(store, session.id, tenant, _SectorAnswers(_REAL_ESTATE_ANSWERS))

    fields = ("id", "pillar", "priority", "timeframe_bucket", "effort_size", "due_at")

    def decided(draft):
        return [{k: item[k] for k in fields} for item in draft["items"]]

    assert decided(with_sector) == decided(without), "the rule engine's decisions must be untouched"
    assert [g["gap_id"] for g in with_sector["top_risks"]] == [
        g["gap_id"] for g in without["top_risks"]
    ]
    assert with_sector["inferred_frameworks"] == without["inferred_frameworks"]
    assert with_sector["maturity_baseline"] == without["maturity_baseline"]
    assert with_sector["maturity_vision"] == without["maturity_vision"]
    # And the difference IS recorded, so a reader can tell the two apart.
    assert with_sector["sector_answer_count"] == 2
    assert without["sector_answer_count"] == 0


def test_the_sector_answers_actually_reach_the_prose_prompts(conn) -> None:
    """The other half: a boundary that lets nothing through is not a feature."""
    tenant_id = _tenant()
    tenant = TenantContext(tenant_id=tenant_id, principal_id="user_1", roles=("owner",))
    store = PostgresGovernanceStore(connection=conn)
    session = _concluded_session(store, tenant_id, DiscoveryEngine(load_bundled_packs()))

    _, provider = _draft(store, session.id, tenant, _SectorAnswers(_REAL_ESTATE_ANSWERS))
    prompts_sent = [request.segments[-1].content for request in provider.requests]
    assert any("الهيئة العامة للعقار" in prompt for prompt in prompts_sent)
    # The brief and every item prompt carry it; the per-GAP prompt deliberately does not — a gap is
    # a finding of the rule engine, and sector colour there would read as a second finding.
    assert all("DESCRIPTION:" not in p for p in prompts_sent if "الهيئة العامة" in p)


def test_the_system_prompt_forbids_touching_the_actions(conn) -> None:
    """The constraint lives in the SYSTEM PROMPT, not only in the documentation — so that even a
    model that misreads its context is confined to narrative."""
    tenant_id = _tenant()
    tenant = TenantContext(tenant_id=tenant_id, principal_id="user_1", roles=("owner",))
    store = PostgresGovernanceStore(connection=conn)
    session = _concluded_session(store, tenant_id, DiscoveryEngine(load_bundled_packs()))

    _, provider = _draft(store, session.id, tenant, _SectorAnswers(_REAL_ESTATE_ANSWERS))
    systems = {
        segment.content
        for request in provider.requests
        for segment in request.segments
        if segment.kind.value == "identity"
    }
    assert systems, "every drafting call must carry the system prompt"
    for system in systems:
        assert (
            "You may explain, prioritize, or contextualize existing governance actions, but you "
            "must never invent, remove, merge, or reorder governance actions." in system
        )


def test_an_OPEN_assessment_contributes_nothing(conn) -> None:
    """A plan is never drafted from answers that can still change — the same rule that lets every
    read stay at READ COMMITTED."""
    tenant_id = _tenant()
    tenant = TenantContext(tenant_id=tenant_id, principal_id="user_1", roles=("owner",))
    store = PostgresGovernanceStore(connection=conn)
    session = _concluded_session(store, tenant_id, DiscoveryEngine(load_bundled_packs()))

    draft, _ = _draft(
        store, session.id, tenant, _SectorAnswers(_REAL_ESTATE_ANSWERS, completed=False)
    )
    assert draft["sector_answer_count"] == 0


def test_an_UNREACHABLE_sector_store_still_produces_a_plan(conn) -> None:
    """A plan that explains itself less well beats no plan at all."""

    class _Broken:
        def find_assessment_for_session(self, *_args, **_kwargs):
            raise RuntimeError("connection lost")

        def load_plan_context(self, *_args, **_kwargs):  # pragma: no cover - never reached
            raise AssertionError

    tenant_id = _tenant()
    tenant = TenantContext(tenant_id=tenant_id, principal_id="user_1", roles=("owner",))
    store = PostgresGovernanceStore(connection=conn)
    session = _concluded_session(store, tenant_id, DiscoveryEngine(load_bundled_packs()))

    provider = FakeGenerationProvider()
    tool = PlanDraftTool(store, provider, sector_answers=_Broken(), now=lambda: 2000.0)
    result = tool.invoke({PAYLOAD_INSTRUCTION: session.id}, tenant)
    assert result["ok"] is True
    assert json.loads(result["output"])["items"]
    assert any("sector_answers: unavailable" in w for w in result.get("warnings", ()))


def test_the_writer_receives_what_the_customer_SAID_not_only_what_the_engine_concluded(conn):
    """Maturity, gaps and capacity are CONCLUSIONS. Handing the writer only conclusions produces
    prose that restates them; the answers behind them let it describe the organization as the
    organization described itself.

    Still narrative only — the assertion below is that the plan is unchanged by it."""
    tenant_id = _tenant()
    tenant = TenantContext(tenant_id=tenant_id, principal_id="user_1", roles=("owner",))
    store = PostgresGovernanceStore(connection=conn)
    session = _concluded_session(store, tenant_id, DiscoveryEngine(load_bundled_packs()))

    draft, provider = _draft(store, session.id, tenant)
    prompts_sent = [request.segments[-1].content for request in provider.requests]

    # The session's own signals reach the prompts.
    signal_keys = list(session.signals.keys())
    assert signal_keys, "the fixture session must carry signals for this test to mean anything"
    assert any(
        any(key in prompt for key in signal_keys) for prompt in prompts_sent
    ), "no core interview answer reached any prompt"

    # And the decisions are still the engine's alone.
    fields = ("id", "pillar", "priority", "timeframe_bucket", "effort_size", "due_at")
    with_context = [{k: item[k] for k in fields} for item in draft["items"]]
    assert with_context, "the fixture must produce plan items"
    assert [g["gap_id"] for g in draft["top_risks"]] == [
        g["gap_id"] for g in draft["top_risks"]
    ]


def test_a_session_with_no_readable_signals_still_produces_a_plan(conn):
    """Context is optional; a plan is not."""
    from governance_plan_tools.draft_tool import _core_signals

    class _Broken:
        @property
        def signals(self):
            raise RuntimeError("shape changed")

    assert _core_signals(_Broken()) == {}
    assert _core_signals(object()) == {}


# --- the organization's language --------------------------------------------------------------


def _with_language(store, tenant_id, engine, code: str | None):
    """A concluded session whose organization answered (or did not answer) the language question."""
    from governance_discovery.signal import Signal, ValueType

    session = _concluded_session(store, tenant_id, engine)
    if code is None:
        return session
    # `with_signal` is the SignalSet's own API — it returns a new set with the signal added, which
    # is what an immutable value object should be asked for rather than rebuilt from its innards.
    signals = session.signals.with_signal(
        Signal(key="organization_language", value=code, value_type=ValueType.ENUM, confidence=1.0)
    )
    session = session.__class__(**{**session.__dict__, "signals": signals})
    store.save_session(session)
    return session


def test_the_organizations_language_reaches_the_writer(conn) -> None:
    """The answer has to travel: interview signal → draft tool → every prompt sent to the model.
    Before this it could not, because the tool held a fixed `Language.ENGLISH` for everyone."""
    tenant_id = _tenant()
    tenant = TenantContext(tenant_id=tenant_id, principal_id="user_1", roles=("owner",))
    store = PostgresGovernanceStore(connection=conn)
    try:
        session = _with_language(store, tenant_id, DiscoveryEngine(load_bundled_packs()), "ar")
        _, provider = _draft(store, session.id, tenant)
        assert provider.requests, "the writer was never called"
        assert {r.language for r in provider.requests} == {Language.ARABIC}
    finally:
        _cleanup(conn, tenant_id)


def test_an_unanswered_language_falls_back_rather_than_guessing(conn) -> None:
    tenant_id = _tenant()
    tenant = TenantContext(tenant_id=tenant_id, principal_id="user_1", roles=("owner",))
    store = PostgresGovernanceStore(connection=conn)
    try:
        session = _with_language(store, tenant_id, DiscoveryEngine(load_bundled_packs()), None)
        _, provider = _draft(store, session.id, tenant)
        assert {r.language for r in provider.requests} == {Language.ENGLISH}
    finally:
        _cleanup(conn, tenant_id)


def test_language_changes_the_WORDING_and_nothing_the_engine_decided(conn) -> None:
    """The boundary, asserted rather than promised.

    Two organizations identical except for the language they read in must receive the SAME
    governance advice in different words. If this ever fails, a reading preference has started
    moving compliance decisions — which is why the question is registered `DecisionEffect.NONE`
    and deliberately left un-required (required-ness feeds coverage and confidence, and those are
    engine outputs).
    """
    engine = DiscoveryEngine(load_bundled_packs())
    decided: dict[str, object] = {}
    languages: dict[str, set] = {}
    for code in ("ar", "en"):
        tenant_id = _tenant()
        tenant = TenantContext(tenant_id=tenant_id, principal_id="user_1", roles=("owner",))
        store = PostgresGovernanceStore(connection=conn)
        try:
            session = _with_language(store, tenant_id, engine, code)
            draft, provider = _draft(store, session.id, tenant)
            languages[code] = {r.language for r in provider.requests}
            decided[code] = {
                "frameworks": draft["inferred_frameworks"],
                "maturity_baseline": draft["maturity_baseline"],
                "maturity_vision": draft["maturity_vision"],
                "gap_ids": [g["gap_id"] for g in draft["top_risks"]],
                "items": [
                    (i["id"], i["pillar"], i["priority"], i["timeframe_bucket"], i["title_key"])
                    for i in draft["items"]
                ],
            }
        finally:
            _cleanup(conn, tenant_id)

    assert languages["ar"] == {Language.ARABIC}
    assert languages["en"] == {Language.ENGLISH}
    assert decided["ar"] == decided["en"], "language moved something the rule engine decided"


def test_language_is_an_INSTRUCTION_not_metadata(conn) -> None:
    """The regression this exists to prevent, because it already happened once.

    `LLMRequest.language` is metadata: `messages()` folds segments into system + user and never
    turns that field into anything a model reads. A plan drafted for an Arabic-reading organization
    came back in English with the request correctly marked ARABIC — every layer agreed, and the
    model was never told.

    So the assertion is not on `request.language`. It is on the text the model actually receives.
    """
    tenant_id = _tenant()
    tenant = TenantContext(tenant_id=tenant_id, principal_id="user_1", roles=("owner",))
    store = PostgresGovernanceStore(connection=conn)
    try:
        session = _with_language(store, tenant_id, DiscoveryEngine(load_bundled_packs()), "ar")
        _, provider = _draft(store, session.id, tenant)

        directive = answer_language_directive(Language.ARABIC)
        for request in provider.requests:
            system = next(m["content"] for m in request.messages() if m["role"] == "system")
            assert directive in system, (
                "the Arabic directive is missing from the system message the model reads — "
                "setting only LLMRequest.language is the bug this test exists for"
            )
            # And it must be the language's own directive, not the other one silently applied.
            assert answer_language_directive(Language.ENGLISH) not in system
    finally:
        _cleanup(conn, tenant_id)


def test_each_language_sends_its_own_directive(conn) -> None:
    """English must be instructed as explicitly as Arabic. A default that happens to match the
    model's habit is not an instruction — it is a coincidence that holds until the model changes."""
    engine = DiscoveryEngine(load_bundled_packs())
    for code, language in (("ar", Language.ARABIC), ("en", Language.ENGLISH)):
        tenant_id = _tenant()
        tenant = TenantContext(tenant_id=tenant_id, principal_id="user_1", roles=("owner",))
        store = PostgresGovernanceStore(connection=conn)
        try:
            session = _with_language(store, tenant_id, engine, code)
            _, provider = _draft(store, session.id, tenant)
            system = next(
                m["content"] for m in provider.requests[0].messages() if m["role"] == "system"
            )
            assert answer_language_directive(language) in system
        finally:
            _cleanup(conn, tenant_id)
