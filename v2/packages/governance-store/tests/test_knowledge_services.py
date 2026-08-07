"""Application Services — orchestration only, against a real database.

The store suite proves each SQL operation is right. This proves the *sequences* are: that the
knowledge lifecycle runs end to end, that rollback is one call, that a retired industry stops
serving interviews, and — the point of the layer — that no service decides anything.
"""

from __future__ import annotations

import datetime as dt
import os
import pathlib
import uuid

import pytest

psycopg = pytest.importorskip("psycopg")

from governance_store.knowledge_services import (  # noqa: E402
    ActivateKnowledgeRelease,
    Actor,
    ApproveKnowledgeTemplate,
    CompleteAssessment,
    GenerateKnowledgeTemplate,
    PublishKnowledgeTemplate,
    RecordSectorAnswers,
    RejectKnowledgeTemplate,
    RetireIndustry,
    NotAuthorized,
    OpenSectorInterview,
    StartAssessment,
    SubmitKnowledgeTemplate,
)
from governance_store.knowledge_store import PostgresKnowledgeStore  # noqa: E402

MIGRATIONS = pathlib.Path(__file__).resolve().parents[1] / "migrations"
KNOWLEDGE_MIGRATIONS = sorted(
    p for p in MIGRATIONS.glob("*.sql") if int(p.name.split("_", 1)[0]) >= 4
)
DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5432/rasheed_ksvc_tests"


def _now():
    return dt.datetime.now(dt.timezone.utc)


APPROVER = Actor("reviewer@rasheed.sa", ("knowledge_approver",))
NOT_APPROVER = Actor("analyst@a", ("practitioner", "approver"))


class _Generator:
    """Stands in for Claude. Returns valid questions and decides nothing else."""

    def __init__(self, count: int = 2) -> None:
        self.calls: list[str] = []
        self._count = count

    def generate(self, *, industry_slug: str) -> list[dict]:
        self.calls.append(industry_slug)
        return [
            {
                "question_id": f"q{i}",
                "canonical_text_ar": "هل لديكم رخصة فال؟",
                "type": "boolean",
                "category": "licensing",
                "importance": "critical",
                "references": [{"framework": "REGA", "clause": "FAL"}],
                "why_we_ask": "Determines whether the organization may broker at all.",
                "evidence_required": ["License number"],
            }
            for i in range(self._count)
        ]


@pytest.fixture(scope="module")
def dsn():
    target = os.environ.get("GOVERNANCE_STORE_TEST_DSN", DEFAULT_DSN)
    base, _, database = target.rpartition("/")
    try:
        with psycopg.connect(f"{base}/postgres", autocommit=True, connect_timeout=3) as setup:
            setup.execute(f'DROP DATABASE IF EXISTS "{database}"')
            setup.execute(f'CREATE DATABASE "{database}"')
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no reachable PostgreSQL ({exc})")
    with psycopg.connect(target, autocommit=True) as conn:
        for migration in KNOWLEDGE_MIGRATIONS:
            conn.execute(migration.read_text(encoding="utf-8"))
    return target


@pytest.fixture
def store(dsn):
    s = PostgresKnowledgeStore(dsn=dsn)
    s._conn.execute(
        "TRUNCATE sector_answers, template_selections, assessments, active_template_history, "
        "question_translations, release_questions RESTART IDENTITY"
    )
    s._conn.execute("ALTER TABLE template_releases DISABLE TRIGGER template_releases_freeze_trg")
    s._conn.execute("DELETE FROM active_templates")
    s._conn.execute("DELETE FROM template_releases")
    s._conn.execute("ALTER TABLE template_releases ENABLE TRIGGER template_releases_freeze_trg")
    s._conn.execute("DELETE FROM knowledge_templates")
    s._conn.execute("DELETE FROM industries")
    yield s
    s.close()


def _generate(store, generator, industry="real_estate"):
    store.register_industry(industry, "عقارات")
    service = GenerateKnowledgeTemplate(
        store,
        generator,
        new_id=lambda: uuid.uuid4().hex[:12],
        model="claude-sonnet-5",
        prompt_version="knowledge_prompt_v3",
        generator_commit="9af4c1e",
    )
    return service(industry_slug=industry, actor=APPROVER)


def _to_released(store, release_id):
    SubmitKnowledgeTemplate(store)(release_id=release_id, actor=APPROVER)
    ApproveKnowledgeTemplate(store, now=_now)(release_id=release_id, actor=APPROVER)
    PublishKnowledgeTemplate(store, now=_now)(release_id=release_id, actor=APPROVER)


# --- generation ------------------------------------------------------------------------------


def test_generation_creates_a_draft_and_names_its_provenance(store):
    outcome = _generate(store, _Generator())
    assert outcome.changed is True
    assert outcome.event.name == "KnowledgeTemplateGenerated"
    assert outcome.event.payload["version"] == 1
    assert outcome.event.payload["question_count"] == 2
    # A subscriber asking "where did this come from?" must not have to read the row back.
    assert outcome.event.payload["generated_by_model"] == "claude-sonnet-5"
    assert outcome.event.payload["prompt_version"] == "knowledge_prompt_v3"
    assert outcome.event.payload["generator_commit"] == "9af4c1e"


def test_generated_knowledge_is_a_DRAFT_and_reaches_no_customer(store):
    """The whole reason the review workflow exists."""
    outcome = _generate(store, _Generator())
    assert store.list_releases(release_id=outcome.data["release_id"])[0]["status"] == "draft"
    assert store.get_active_release("real_estate") is None


def test_regenerating_reuses_the_container_and_mints_a_new_version(store):
    generator = _Generator()
    first = _generate(store, generator)
    second = _generate(store, generator)
    assert (first.event.payload["version"], second.event.payload["version"]) == (1, 2)
    assert len(store.list_releases(industry_slug="real_estate")) == 2
    assert generator.calls == ["real_estate", "real_estate"]


# --- the lifecycle ---------------------------------------------------------------------------


def test_the_full_lifecycle_runs_generate_to_active(store):
    release_id = _generate(store, _Generator()).data["release_id"]

    assert SubmitKnowledgeTemplate(store)(release_id=release_id, actor=APPROVER).event.name == (
        "KnowledgeTemplateSubmitted"
    )
    assert ApproveKnowledgeTemplate(store, now=_now)(
        release_id=release_id, actor=APPROVER
    ).event.name == "KnowledgeTemplateApproved"
    assert PublishKnowledgeTemplate(store, now=_now)(
        release_id=release_id, actor=APPROVER
    ).event.name == "KnowledgeTemplatePublished"

    activated = ActivateKnowledgeRelease(store)(
        industry_slug="real_estate", release_id=release_id, actor=APPROVER, reason="first"
    )
    assert activated.event.name == "ActiveReleaseChanged"
    assert store.get_active_release("real_estate")["id"] == release_id


def test_a_no_op_is_reported_as_unchanged_with_NO_event(store):
    """`changed=False` is not an error — and an event that did not happen must not be emitted."""
    release_id = _generate(store, _Generator()).data["release_id"]
    SubmitKnowledgeTemplate(store)(release_id=release_id, actor=APPROVER)

    repeated = SubmitKnowledgeTemplate(store)(release_id=release_id, actor=APPROVER)
    assert repeated.changed is False
    assert repeated.event is None


def test_rejection_returns_a_release_to_draft(store):
    release_id = _generate(store, _Generator()).data["release_id"]
    SubmitKnowledgeTemplate(store)(release_id=release_id, actor=APPROVER)
    outcome = RejectKnowledgeTemplate(store)(release_id=release_id, actor=APPROVER)
    assert outcome.event.name == "KnowledgeTemplateRejected"
    assert store.list_releases(release_id=release_id)[0]["status"] == "draft"


def test_activation_does_not_re_check_what_the_database_already_refuses(store):
    """The service passes the request through; the composite FK is the rule. A Python guard would
    be a second, weaker copy of something the database states exactly."""
    release_id = _generate(store, _Generator()).data["release_id"]
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        ActivateKnowledgeRelease(store)(
            industry_slug="real_estate", release_id=release_id, actor=APPROVER
        )


def test_rollback_is_the_same_service_call(store):
    generator = _Generator()
    v1 = _generate(store, generator).data["release_id"]
    v2 = _generate(store, generator).data["release_id"]
    _to_released(store, v1)
    _to_released(store, v2)
    activate = ActivateKnowledgeRelease(store)

    activate(industry_slug="real_estate", release_id=v1, actor=APPROVER, reason="first")
    activate(industry_slug="real_estate", release_id=v2, actor=APPROVER, reason="upgrade")
    activate(industry_slug="real_estate", release_id=v1, actor=APPROVER, reason="rollback")

    assert store.get_active_release("real_estate")["id"] == v1
    assert [h["reason"] for h in store.list_activation_history("real_estate")][0] == "rollback"
    assert {r["status"] for r in store.list_releases(industry_slug="real_estate")} == {"released"}


# --- the service that proved this layer exists -------------------------------------------------


def test_retiring_an_industry_also_takes_its_active_release_out_of_service(store):
    """Two repository calls in one transaction: a crash between them would leave an industry that
    is retired but still serving interviews."""
    release_id = _generate(store, _Generator()).data["release_id"]
    _to_released(store, release_id)
    ActivateKnowledgeRelease(store)(
        industry_slug="real_estate", release_id=release_id, actor=APPROVER
    )

    outcome = RetireIndustry(store, connection=store._conn)(
        industry_slug="real_estate", actor=APPROVER
    )

    assert outcome.event.name == "IndustryRetired"
    assert store.get_active_release("real_estate") is None, "it must stop serving interviews"
    assert outcome.event.payload["retired_release_id"] == release_id
    assert store.list_industries() == []
    assert store.list_releases(release_id=release_id)[0]["status"] == "deprecated"


def test_retiring_an_industry_with_no_active_release_is_still_valid(store):
    store.register_industry("unused", "غير مستخدم")
    outcome = RetireIndustry(store, connection=store._conn)(
        industry_slug="unused", actor=APPROVER
    )
    assert outcome.changed is True
    assert outcome.event.payload["retired_release_id"] is None


# --- assessments ------------------------------------------------------------------------------


def _start(store, release_ids, *, suggested="real_estate"):
    return StartAssessment(
        store, connection=store._conn, new_id=lambda: f"as_{uuid.uuid4().hex[:8]}"
    )(
        tenant_id="t1",
        organization_id="org1",
        suggested_industry_slug=suggested,
        selected_release_ids=release_ids,
        selected_by="reviewer",
    )


def test_starting_an_assessment_records_the_selection_in_the_same_transaction(store):
    release_id = _generate(store, _Generator()).data["release_id"]
    _to_released(store, release_id)
    outcome = _start(store, [release_id])

    assert outcome.event.name == "AssessmentStarted"
    assessment_id = outcome.data["assessment_id"]
    CompleteAssessment(store, now=_now)(assessment_id=assessment_id, tenant_id="t1")
    context = store.load_plan_context(assessment_id, tenant_id="t1")
    assert context["selection"]["selected_release_ids"] == [release_id]


def test_the_event_carries_what_was_SUGGESTED_as_well_as_what_was_chosen(store):
    """A suggestion someone accepted and one nobody examined look identical without it."""
    release_id = _generate(store, _Generator()).data["release_id"]
    _to_released(store, release_id)
    outcome = _start(store, [release_id], suggested="healthcare")
    assert outcome.event.payload["suggested_industry_slug"] == "healthcare"
    assert outcome.event.payload["selected_release_ids"] == [release_id]


def test_a_failed_selection_leaves_no_orphan_assessment(store):
    """One transaction: an assessment that exists without a selection is a row nobody can
    explain."""
    with pytest.raises(ValueError, match="at least one template release"):
        _start(store, [])
    assert store._conn.execute("SELECT count(*) FROM assessments").fetchone()[0] == 0


def test_recording_answers_then_completing_freezes_the_assessment(store):
    release_id = _generate(store, _Generator()).data["release_id"]
    _to_released(store, release_id)
    assessment_id = _start(store, [release_id]).data["assessment_id"]

    recorded = RecordSectorAnswers(store)(
        assessment_id=assessment_id,
        tenant_id="t1",
        answers=[{"release_id": release_id, "question_id": "q0", "answer": False}],
    )
    assert recorded.event.name == "SectorAnswersRecorded"
    assert recorded.event.payload["answer_count"] == 1

    completed = CompleteAssessment(store, now=_now)(assessment_id=assessment_id, tenant_id="t1")
    assert completed.event.name == "AssessmentCompleted"

    with pytest.raises(psycopg.errors.RaiseException, match="accepts no further writes"):
        RecordSectorAnswers(store)(
            assessment_id=assessment_id,
            tenant_id="t1",
            answers=[{"release_id": release_id, "question_id": "q1", "answer": True}],
        )


def test_completing_twice_reports_unchanged_and_emits_nothing(store):
    release_id = _generate(store, _Generator()).data["release_id"]
    _to_released(store, release_id)
    assessment_id = _start(store, [release_id]).data["assessment_id"]
    complete = CompleteAssessment(store, now=_now)

    assert complete(assessment_id=assessment_id, tenant_id="t1").changed is True
    repeated = complete(assessment_id=assessment_id, tenant_id="t1")
    assert (repeated.changed, repeated.event) == (False, None)


def test_the_retirement_ORDER_is_the_only_one_the_database_permits(store):
    """The schema refuses to demote a release while it is active — so retiring must deactivate
    first. Doing it the other way round is not a style choice; it fails."""
    release_id = _generate(store, _Generator()).data["release_id"]
    _to_released(store, release_id)
    ActivateKnowledgeRelease(store)(
        industry_slug="real_estate", release_id=release_id, actor=APPROVER
    )
    with pytest.raises(psycopg.errors.CheckViolation, match="must_be_released"):
        store.retire_release(release_id, target_status="deprecated")


def test_activation_reports_what_it_replaced(store):
    """A first activation and a rollback are the same call, and read identically without this."""
    generator = _Generator()
    v1 = _generate(store, generator).data["release_id"]
    v2 = _generate(store, generator).data["release_id"]
    _to_released(store, v1)
    _to_released(store, v2)
    activate = ActivateKnowledgeRelease(store)

    first = activate(industry_slug="real_estate", release_id=v1, actor=APPROVER, reason="first")
    upgrade = activate(industry_slug="real_estate", release_id=v2, actor=APPROVER, reason="upgrade")
    assert first.event.payload["previous_release_id"] is None
    assert upgrade.event.payload["previous_release_id"] == v1


# --- authorization ----------------------------------------------------------------------------


def test_governing_knowledge_requires_the_KNOWLEDGE_APPROVER_role(store):
    """A tenant-side approver is deliberately not enough. One release serves every customer in a
    sector, so the blast radius of a bad one is all of them — a per-tenant role cannot carry that."""
    store.register_industry("real_estate", "عقارات")
    with pytest.raises(NotAuthorized, match="knowledge_approver"):
        GenerateKnowledgeTemplate(
            store,
            _Generator(),
            new_id=lambda: uuid.uuid4().hex[:12],
            model="claude-sonnet-5",
            prompt_version="knowledge_prompt_v3",
            generator_commit="9af4c1e",
        )(industry_slug="real_estate", actor=NOT_APPROVER)


def test_an_unauthorized_generation_never_reaches_the_model(store):
    """The guard runs before the LLM: refusing after the call would still have spent the money and
    still have sent the request."""
    store.register_industry("real_estate", "عقارات")
    generator = _Generator()
    with pytest.raises(NotAuthorized):
        GenerateKnowledgeTemplate(
            store, generator, new_id=lambda: uuid.uuid4().hex[:12],
            model="m", prompt_version="p", generator_commit="c",
        )(industry_slug="real_estate", actor=NOT_APPROVER)
    assert generator.calls == []
    assert store.list_releases() == []


def test_every_consequential_knowledge_operation_is_guarded(store):
    """Enumerated rather than sampled: a new service added without a guard fails here."""
    release_id = _generate(store, _Generator()).data["release_id"]
    guarded = [
        lambda: SubmitKnowledgeTemplate(store)(release_id=release_id, actor=NOT_APPROVER),
        lambda: ApproveKnowledgeTemplate(store, now=_now)(
            release_id=release_id, actor=NOT_APPROVER
        ),
        lambda: RejectKnowledgeTemplate(store)(release_id=release_id, actor=NOT_APPROVER),
        lambda: PublishKnowledgeTemplate(store, now=_now)(
            release_id=release_id, actor=NOT_APPROVER
        ),
        lambda: ActivateKnowledgeRelease(store)(
            industry_slug="real_estate", release_id=release_id, actor=NOT_APPROVER
        ),
        lambda: RetireIndustry(store, connection=store._conn)(
            industry_slug="real_estate", actor=NOT_APPROVER
        ),
    ]
    for call in guarded:
        with pytest.raises(NotAuthorized):
            call()


def test_the_actor_recorded_is_the_authenticated_principal(store):
    """`approved_by` is what an auditor reads a year from now. It comes from authentication, not
    from a name in the request body."""
    release_id = _generate(store, _Generator()).data["release_id"]
    SubmitKnowledgeTemplate(store)(release_id=release_id, actor=APPROVER)
    ApproveKnowledgeTemplate(store, now=_now)(release_id=release_id, actor=APPROVER)
    release = store.list_releases(release_id=release_id)[0]
    assert release["created_by"] == APPROVER.principal_id
    assert release["approved_by"] == APPROVER.principal_id


# --- the loop: a concluded discovery session opens a sector interview ---------------------------


class _Session:
    def __init__(self, status="concluded", activity="real_estate"):
        self.status = status
        self.signals = _Signals(activity)


class _Signals:
    def __init__(self, activity):
        self._activity = activity

    def value(self, key, default=None):
        return self._activity if key == "primary_activity" else default


class _Sessions:
    def __init__(self, session=None):
        self._session = session

    def get_session(self, session_id, tenant_id):
        return self._session


def _open(store, session, session_id="sess_1"):
    return OpenSectorInterview(
        store, _Sessions(session), connection=store._conn, new_id=lambda: f"as_{uuid.uuid4().hex[:8]}"
    )(session_id=session_id, tenant_id="t1", organization_id="org1")


def _live_release(store):
    release_id = _generate(store, _Generator()).data["release_id"]
    _to_released(store, release_id)
    ActivateKnowledgeRelease(store)(
        industry_slug="real_estate", release_id=release_id, actor=APPROVER
    )
    return release_id


def test_a_concluded_session_opens_an_assessment_citing_what_is_LIVE(store):
    """The loop, closed: what the reviewer activated is exactly what the customer is asked."""
    release_id = _live_release(store)
    outcome = _open(store, _Session())

    assert outcome.changed is True
    assert outcome.data["status"] == "opened"
    assert outcome.data["release_id"] == release_id
    assert outcome.event.name == "AssessmentStarted"


def test_the_suggestion_and_the_selection_are_both_recorded(store):
    """`primary_activity` SUGGESTS; the activation pointer decides. Storing only the outcome would
    make an accepted suggestion and an unexamined one look identical."""
    release_id = _live_release(store)
    assessment_id = _open(store, _Session()).data["assessment_id"]
    CompleteAssessment(store, now=_now)(assessment_id=assessment_id, tenant_id="t1")
    selection = store.load_plan_context(assessment_id, tenant_id="t1")["selection"]
    assert selection["suggested_industry_slug"] == "real_estate"
    assert selection["selected_release_ids"] == [release_id]


def test_opening_twice_returns_the_SAME_assessment(store):
    """A customer who reloads mid-interview must not start a second assessment — the first one
    holds their answers, and two would make "which one is the assessment?" unanswerable."""
    _live_release(store)
    first = _open(store, _Session())
    second = _open(store, _Session())
    assert second.changed is False
    assert second.data["status"] == "already_open"
    assert second.data["assessment_id"] == first.data["assessment_id"]


def test_a_sector_with_NOTHING_ACTIVATED_is_a_normal_state_not_a_failure(store):
    """Most sectors will have no published pack for a long time. A customer must still be able to
    finish — the alternative is a product that refuses to work until every sector is authored."""
    store.register_industry("real_estate", "عقارات")
    outcome = _open(store, _Session())
    assert outcome.changed is False
    assert outcome.data["status"] == "no_sector_pack"
    assert outcome.event is None


def test_a_DRAFT_release_is_not_reachable_by_a_customer(store):
    """The whole reason the review workflow exists: generated-but-unapproved knowledge must not be
    what an organization is asked."""
    _generate(store, _Generator())  # generated, never published, never activated
    assert _open(store, _Session()).data["status"] == "no_sector_pack"


def test_an_UNCONCLUDED_session_cannot_open_a_sector_interview(store):
    _live_release(store)
    with pytest.raises(ValueError, match="has not concluded"):
        _open(store, _Session(status="in_progress"))


def test_a_customer_who_named_no_sector_gets_no_sector_interview(store):
    _live_release(store)
    assert _open(store, _Session(activity=None)).data["status"] == "no_sector_pack"
