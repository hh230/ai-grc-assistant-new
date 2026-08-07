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
    ApproveKnowledgeTemplate,
    CompleteAssessment,
    GenerateKnowledgeTemplate,
    PublishKnowledgeTemplate,
    RecordSectorAnswers,
    RejectKnowledgeTemplate,
    RetireIndustry,
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
    return service(industry_slug=industry, requested_by="approver@example.com")


def _to_released(store, release_id):
    SubmitKnowledgeTemplate(store)(release_id=release_id)
    ApproveKnowledgeTemplate(store, now=_now)(release_id=release_id, approver="r@example.com")
    PublishKnowledgeTemplate(store, now=_now)(release_id=release_id)


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

    assert SubmitKnowledgeTemplate(store)(release_id=release_id).event.name == (
        "KnowledgeTemplateSubmitted"
    )
    assert ApproveKnowledgeTemplate(store, now=_now)(
        release_id=release_id, approver="r@example.com"
    ).event.name == "KnowledgeTemplateApproved"
    assert PublishKnowledgeTemplate(store, now=_now)(
        release_id=release_id
    ).event.name == "KnowledgeTemplatePublished"

    activated = ActivateKnowledgeRelease(store)(
        industry_slug="real_estate", release_id=release_id, actor="approver", reason="first"
    )
    assert activated.event.name == "ActiveReleaseChanged"
    assert store.get_active_release("real_estate")["id"] == release_id


def test_a_no_op_is_reported_as_unchanged_with_NO_event(store):
    """`changed=False` is not an error — and an event that did not happen must not be emitted."""
    release_id = _generate(store, _Generator()).data["release_id"]
    SubmitKnowledgeTemplate(store)(release_id=release_id)

    repeated = SubmitKnowledgeTemplate(store)(release_id=release_id)
    assert repeated.changed is False
    assert repeated.event is None


def test_rejection_returns_a_release_to_draft(store):
    release_id = _generate(store, _Generator()).data["release_id"]
    SubmitKnowledgeTemplate(store)(release_id=release_id)
    outcome = RejectKnowledgeTemplate(store)(release_id=release_id, rejected_by="r@example.com")
    assert outcome.event.name == "KnowledgeTemplateRejected"
    assert store.list_releases(release_id=release_id)[0]["status"] == "draft"


def test_activation_does_not_re_check_what_the_database_already_refuses(store):
    """The service passes the request through; the composite FK is the rule. A Python guard would
    be a second, weaker copy of something the database states exactly."""
    release_id = _generate(store, _Generator()).data["release_id"]
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        ActivateKnowledgeRelease(store)(
            industry_slug="real_estate", release_id=release_id, actor="approver"
        )


def test_rollback_is_the_same_service_call(store):
    generator = _Generator()
    v1 = _generate(store, generator).data["release_id"]
    v2 = _generate(store, generator).data["release_id"]
    _to_released(store, v1)
    _to_released(store, v2)
    activate = ActivateKnowledgeRelease(store)

    activate(industry_slug="real_estate", release_id=v1, actor="a", reason="first")
    activate(industry_slug="real_estate", release_id=v2, actor="a", reason="upgrade")
    activate(industry_slug="real_estate", release_id=v1, actor="a", reason="rollback")

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
        industry_slug="real_estate", release_id=release_id, actor="approver"
    )

    outcome = RetireIndustry(store, connection=store._conn)(industry_slug="real_estate")

    assert outcome.event.name == "IndustryRetired"
    assert store.get_active_release("real_estate") is None, "it must stop serving interviews"
    assert outcome.event.payload["retired_release_id"] == release_id
    assert store.list_industries() == []
    assert store.list_releases(release_id=release_id)[0]["status"] == "deprecated"


def test_retiring_an_industry_with_no_active_release_is_still_valid(store):
    store.register_industry("unused", "غير مستخدم")
    outcome = RetireIndustry(store, connection=store._conn)(industry_slug="unused")
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
    CompleteAssessment(store, now=_now)(assessment_id=assessment_id)
    context = store.load_plan_context(assessment_id)
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

    completed = CompleteAssessment(store, now=_now)(assessment_id=assessment_id)
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

    assert complete(assessment_id=assessment_id).changed is True
    repeated = complete(assessment_id=assessment_id)
    assert (repeated.changed, repeated.event) == (False, None)


def test_the_retirement_ORDER_is_the_only_one_the_database_permits(store):
    """The schema refuses to demote a release while it is active — so retiring must deactivate
    first. Doing it the other way round is not a style choice; it fails."""
    release_id = _generate(store, _Generator()).data["release_id"]
    _to_released(store, release_id)
    ActivateKnowledgeRelease(store)(
        industry_slug="real_estate", release_id=release_id, actor="approver"
    )
    with pytest.raises(psycopg.errors.CheckViolation, match="must_be_released"):
        store.retire_release(release_id, target_status="deprecated")


def test_deactivating_removes_the_pointer_but_keeps_the_history(store):
    """Not a deletion of knowledge: the release row is untouched and every activation remains
    recorded. What disappears is only "which release is live right now"."""
    release_id = _generate(store, _Generator()).data["release_id"]
    _to_released(store, release_id)
    ActivateKnowledgeRelease(store)(
        industry_slug="real_estate", release_id=release_id, actor="approver", reason="first"
    )
    assert store.deactivate_industry("real_estate") == release_id
    assert store.get_active_release("real_estate") is None
    assert store.deactivate_industry("real_estate") is None, "idempotent"
    assert len(store.list_activation_history("real_estate")) == 1
    assert store.list_releases(release_id=release_id)[0]["status"] == "released"
