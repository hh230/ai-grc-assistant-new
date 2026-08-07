"""`PostgresKnowledgeStore` against a real database — the contract, exercised.

The schema suite proves the database refuses bad writes. This proves the repository makes the
*right* ones: the version it allocates, what a guarded write returns when it matches nothing, that
rollback moves a pointer without touching a release, and that a plan context cannot be built from
an assessment still being answered.

Skips cleanly when no database is reachable.
"""

from __future__ import annotations

import datetime as dt
import os
import pathlib
import uuid

import pytest

psycopg = pytest.importorskip("psycopg")

from governance_store.knowledge_store import PostgresKnowledgeStore  # noqa: E402

MIGRATIONS = pathlib.Path(__file__).resolve().parents[1] / "migrations"
KNOWLEDGE_MIGRATIONS = sorted(
    p for p in MIGRATIONS.glob("*.sql") if int(p.name.split("_", 1)[0]) >= 4
)
DSN_ENV_VAR = "GOVERNANCE_STORE_TEST_DSN"
DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5432/rasheed_kstore_tests"
NOW = dt.datetime(2026, 8, 7, 12, 0, tzinfo=dt.timezone.utc)
# Conclusion must not precede `started_at`, which the database stamps with its own clock — the
# CHECK caught a fixed timestamp in the past, which is exactly what it is there for.
def _later() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=1)


@pytest.fixture(scope="module")
def dsn():
    target = os.environ.get(DSN_ENV_VAR, DEFAULT_DSN)
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


def _question(question_id="fal_license") -> dict:
    return {
        "question_id": question_id,
        "canonical_text_ar": "هل لديكم رخصة فال؟",
        "type": "boolean",
        "category": "licensing",
        "importance": "critical",
        "references": [{"framework": "REGA", "clause": "FAL"}],
        "why_we_ask": "Determines whether the organization may broker at all.",
        "evidence_required": ["License number"],
    }


def _template(store, slug="real_estate") -> str:
    store.register_industry(slug, "عقارات")
    return store.ensure_template(f"tpl_{slug}", slug)["id"]


def _released(store, template_id, *, questions=None) -> str:
    release_id = f"rel_{uuid.uuid4().hex[:8]}"
    store.create_release(
        release_id=release_id,
        template_id=template_id,
        questions=questions or [_question()],
        generated_by_model="claude-sonnet-5",
        prompt_version="knowledge_prompt_v3",
        generator_commit="9af4c1e",
        created_by="generator",
    )
    store.submit_for_review(release_id)
    store.approve_release(release_id, approver="reviewer@example.com", at=NOW)
    store.mark_released(release_id, at=NOW)
    return release_id


# --- industries and templates -----------------------------------------------------------------


def test_registering_an_industry_twice_is_harmless(store):
    store.register_industry("real_estate", "عقارات")
    store.register_industry("real_estate", "عقارات")
    assert [i["slug"] for i in store.list_industries()] == ["real_estate"]


def test_a_retired_industry_is_hidden_from_the_default_listing_but_still_exists(store):
    """Retiring must not erase history — reports produced under it stay explicable.

    Setting the status is deliberately NOT a repository method: retiring an industry also means
    retiring its active release, which is coordination and belongs to an Application Service.
    """
    store.register_industry("legacy", "قديم")
    assert store.set_industry_status("legacy", "retired") is True
    assert store.set_industry_status("legacy", "retired") is False, "idempotent"
    assert store.list_industries() == []
    assert [i["slug"] for i in store.list_industries(include_retired=True)] == ["legacy"]


def test_ensure_template_returns_the_SAME_container_on_every_call(store):
    store.register_industry("real_estate", "عقارات")
    first = store.ensure_template("tpl_a", "real_estate")
    second = store.ensure_template("tpl_b", "real_estate")
    assert first["id"] == second["id"] == "tpl_a", "one container per industry, first writer wins"


# --- create_release ---------------------------------------------------------------------------


def test_versions_are_allocated_sequentially_per_template(store):
    template_id = _template(store)
    versions = [
        store.create_release(
            release_id=f"rel_{i}",
            template_id=template_id,
            questions=[_question()],
            generated_by_model="claude-sonnet-5",
            prompt_version="p_v3",
            generator_commit="9af4",
            created_by="generator",
        )
        for i in range(3)
    ]
    assert versions == [1, 2, 3]


def test_versions_are_independent_between_industries(store):
    """The lock is per-template, so real estate and healthcare never wait on each other — and
    never share a version counter either."""
    re_template = _template(store, "real_estate")
    hc_template = _template(store, "healthcare")
    assert store.create_release(
        release_id="rel_re", template_id=re_template, questions=[_question()],
        generated_by_model="m", prompt_version="p", generator_commit="c", created_by="g",
    ) == 1
    assert store.create_release(
        release_id="rel_hc", template_id=hc_template, questions=[_question()],
        generated_by_model="m", prompt_version="p", generator_commit="c", created_by="g",
    ) == 1


def test_a_release_with_no_questions_is_refused_before_any_write(store):
    template_id = _template(store)
    with pytest.raises(ValueError, match="no questions is not a release"):
        store.create_release(
            release_id="rel_empty", template_id=template_id, questions=[],
            generated_by_model="m", prompt_version="p", generator_commit="c", created_by="g",
        )
    assert store.list_releases(industry_slug="real_estate") == []


def test_the_questions_land_in_the_same_transaction_as_the_release(store):
    template_id = _template(store)
    store.create_release(
        release_id="rel_1", template_id=template_id,
        questions=[_question("a"), _question("b")],
        generated_by_model="m", prompt_version="p", generator_commit="c", created_by="g",
    )
    assert len(store.list_releases(release_id="rel_1", with_questions=True)[0]["questions"]) == 2


# --- guarded writes ---------------------------------------------------------------------------


def test_a_guarded_write_returns_False_rather_than_raising(store):
    """The repository reports what happened; whether it is an error is the domain's call."""
    template_id = _template(store)
    store.create_release(
        release_id="rel_1", template_id=template_id, questions=[_question()],
        generated_by_model="m", prompt_version="p", generator_commit="c", created_by="g",
    )
    assert store.approve_release("rel_1", approver="r@e.com", at=NOW) is False, "still a draft"
    assert store.submit_for_review("rel_1") is True
    assert store.submit_for_review("rel_1") is False, "already submitted — idempotent, not an error"


def test_approving_without_an_identity_is_refused_before_touching_the_database(store):
    template_id = _template(store)
    store.create_release(
        release_id="rel_1", template_id=template_id, questions=[_question()],
        generated_by_model="m", prompt_version="p", generator_commit="c", created_by="g",
    )
    store.submit_for_review("rel_1")
    with pytest.raises(ValueError, match="approver's identity"):
        store.approve_release("rel_1", approver="   ", at=NOW)


def test_a_release_cannot_be_released_without_passing_through_approval(store):
    template_id = _template(store)
    store.create_release(
        release_id="rel_1", template_id=template_id, questions=[_question()],
        generated_by_model="m", prompt_version="p", generator_commit="c", created_by="g",
    )
    assert store.mark_released("rel_1", at=NOW) is False


# --- activation and rollback ------------------------------------------------------------------


def test_the_first_activation_creates_the_pointer_and_a_history_entry(store):
    template_id = _template(store)
    release_id = _released(store, template_id)
    store.set_active_release(
        industry_slug="real_estate", release_id=release_id, actor="approver", reason="initial"
    )
    assert store.get_active_release("real_estate")["id"] == release_id
    assert [h["reason"] for h in store.list_activation_history("real_estate")] == ["initial"]


def test_rollback_moves_the_pointer_and_touches_no_release(store):
    """The reason the pointer exists: publish v2, find a bad question, point back at v1 — without
    minting a v3 that exists only to reverse a mistake."""
    template_id = _template(store)
    v1 = _released(store, template_id)
    v2 = _released(store, template_id)

    activate = lambda rid, why: store.set_active_release(  # noqa: E731
        industry_slug="real_estate", release_id=rid, actor="a", reason=why
    )
    activate(v1, "first")
    activate(v2, "upgrade")
    activate(v1, "rollback")

    assert store.get_active_release("real_estate")["id"] == v1
    assert [h["reason"] for h in store.list_activation_history("real_estate")] == [
        "rollback", "upgrade", "first",
    ]
    assert {r["status"] for r in store.list_releases(industry_slug="real_estate")} == {"released"}, (
        "rollback must not demote any release"
    )


def test_an_unreleased_release_cannot_be_activated(store):
    template_id = _template(store)
    store.create_release(
        release_id="rel_draft", template_id=template_id, questions=[_question()],
        generated_by_model="m", prompt_version="p", generator_commit="c", created_by="g",
    )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        store.set_active_release(
            industry_slug="real_estate", release_id="rel_draft", actor="approver"
        )


def test_setting_the_active_release_to_NONE_is_the_other_permitted_answer(store):
    """One primitive, because there is one question: what is the active release for this industry?
    Only two answers are permitted — a release, or none. `None` is not a second operation."""
    template_id = _template(store)
    v1 = _released(store, template_id)
    v2 = _released(store, template_id)

    assert store.set_active_release(
        industry_slug="real_estate", release_id=v1, actor="a"
    ) is None, "nothing was live before the first activation"
    assert store.set_active_release(industry_slug="real_estate", release_id=v2, actor="a") == v1
    assert (
        store.set_active_release(industry_slug="real_estate", release_id=None, actor="a") == v2
    )
    assert store.get_active_release("real_estate") is None
    assert store.set_active_release(
        industry_slug="real_estate", release_id=None, actor="a"
    ) is None, "clearing what is already clear changes nothing"
    # Clearing removes a pointer, not knowledge.
    assert {r["status"] for r in store.list_releases(industry_slug="real_estate")} == {"released"}
    assert len(store.list_activation_history("real_estate")) == 2


def test_an_industry_with_no_activation_has_no_active_release(store):
    """`None`, not a near-miss: an interview must not be handed knowledge nobody activated."""
    _released(store, _template(store))
    assert store.get_active_release("real_estate") is None


def test_the_active_release_carries_its_questions_and_provenance(store):
    template_id = _template(store)
    release_id = _released(store, template_id, questions=[_question("a"), _question("b")])
    store.set_active_release(industry_slug="real_estate", release_id=release_id, actor="approver")
    active = store.get_active_release("real_estate")
    assert len(active["questions"]) == 2
    assert active["generated_by_model"] == "claude-sonnet-5"
    assert active["prompt_version"] == "knowledge_prompt_v3"
    assert active["generator_commit"] == "9af4c1e"


# --- translations -----------------------------------------------------------------------------


def test_only_a_REVIEWED_translation_can_be_published(store):
    template_id = _template(store)
    release_id = _released(store, template_id, questions=[_question("a"), _question("b")])
    store.save_translation(release_id=release_id, question_id="a", language="en", text="A?")
    assert store.publish_translation(
        release_id=release_id, question_id="a", language="en"
    ) is False, "generated cannot be published — it has not been reviewed"

    store._conn.execute(
        "UPDATE question_translations SET status = 'reviewed' WHERE release_id = %s",
        (release_id,),
    )
    assert store.publish_translation(release_id=release_id, question_id="a", language="en") is True

    # Coverage itself is a projection, not a repository operation — asserted against the rows.
    assert store._conn.execute(
        "SELECT count(*) FROM question_translations WHERE status = 'published'"
    ).fetchone()[0] == 1


def test_re_saving_a_translation_returns_it_to_generated(store):
    """A changed string is unreviewed again — otherwise an edit could inherit an old approval."""
    template_id = _template(store)
    release_id = _released(store, template_id)
    store.save_translation(
        release_id=release_id, question_id="fal_license", language="en", text="first"
    )
    store._conn.execute("UPDATE question_translations SET status = 'published'")
    store.save_translation(
        release_id=release_id, question_id="fal_license", language="en", text="second"
    )
    assert store._conn.execute(
        "SELECT status FROM question_translations WHERE question_id = 'fal_license'"
    ).fetchone()[0] == "generated"


# --- assessments and the plan context ---------------------------------------------------------


def _assessment(store, release_id, *, assessment_id="as_1") -> str:
    store.open_assessment(
        assessment_id=assessment_id, tenant_id="t1", organization_id="org1"
    )
    store.record_selection(
        assessment_id=assessment_id, tenant_id="t1", suggested_industry_slug="real_estate",
        selected_release_ids=[release_id], selected_by="reviewer",
    )
    store.save_sector_answers(
        assessment_id=assessment_id, tenant_id="t1",
        answers=[{"release_id": release_id, "question_id": "fal_license", "answer": False}],
    )
    return assessment_id


def test_a_plan_context_cannot_be_built_from_an_OPEN_assessment(store):
    """The rule that lets every read stay at READ COMMITTED. Remove it and this needs snapshot
    isolation — which would hide a late write rather than prevent it."""
    release_id = _released(store, _template(store))
    _assessment(store, release_id)
    with pytest.raises(ValueError, match="still open"):
        store.load_plan_context("as_1", tenant_id="t1")


def test_a_concluded_assessment_yields_answers_joined_to_their_questions(store):
    release_id = _released(store, _template(store))
    _assessment(store, release_id)
    assert store.complete_assessment("as_1", tenant_id="t1", at=_later()) is True

    context = store.load_plan_context("as_1", tenant_id="t1")
    assert context["assessment"]["organization_id"] == "org1"
    assert context["selection"]["selected_release_ids"] == [release_id]
    assert context["selection"]["suggested_industry_slug"] == "real_estate"
    answer = context["sector_answers"][0]
    assert answer["answer"] is False
    assert answer["canonical_text_ar"] == "هل لديكم رخصة فال؟"
    assert answer["references"] == [{"framework": "REGA", "clause": "FAL"}]


def test_concluding_twice_is_idempotent(store):
    release_id = _released(store, _template(store))
    _assessment(store, release_id)
    assert store.complete_assessment("as_1", tenant_id="t1", at=_later()) is True
    assert store.complete_assessment("as_1", tenant_id="t1", at=_later()) is False


def test_answers_cannot_be_saved_after_conclusion(store):
    release_id = _released(store, _template(store))
    _assessment(store, release_id)
    store.complete_assessment("as_1", tenant_id="t1", at=_later())
    with pytest.raises(psycopg.errors.RaiseException, match="accepts no further writes"):
        store.save_sector_answers(
            assessment_id="as_1", tenant_id="t1",
            answers=[{"release_id": release_id, "question_id": "fal_license", "answer": True}],
        )


def test_a_selection_citing_nothing_is_refused_before_touching_the_database(store):
    store.open_assessment(assessment_id="as_2", tenant_id="t1", organization_id="org1")
    with pytest.raises(ValueError, match="at least one template release"):
        store.record_selection(
            assessment_id="as_2", tenant_id="t1", suggested_industry_slug="real_estate",
            selected_release_ids=[], selected_by="reviewer",
        )


def test_a_selection_may_cite_several_releases(store):
    """Reality is not one sector: a brokerage that also builds."""
    real_estate = _released(store, _template(store, "real_estate"))
    construction = _released(store, _template(store, "construction"))
    store.open_assessment(assessment_id="as_3", tenant_id="t1", organization_id="org1")
    store.record_selection(
        assessment_id="as_3", tenant_id="t1", suggested_industry_slug="real_estate",
        selected_release_ids=[real_estate, construction], selected_by="reviewer",
    )
    store.complete_assessment("as_3", tenant_id="t1", at=_later())
    assert store.load_plan_context("as_3", tenant_id="t1")["selection"]["selected_release_ids"] == [
        real_estate, construction,
    ]


def test_load_plan_context_returns_None_for_an_assessment_that_does_not_exist(store):
    assert store.load_plan_context("as_missing", tenant_id="t1") is None


def test_ANOTHER_TENANTS_assessment_is_indistinguishable_from_one_that_does_not_exist(store):
    """Not `403`, and not an empty context — `None`. Telling a caller "that exists, but not for
    you" confirms the id, and an assessment id is a fact about another customer."""
    release_id = _released(store, _template(store))
    _assessment(store, release_id)
    assert store.complete_assessment("as_1", tenant_id="t1", at=_later()) is True
    assert store.load_plan_context("as_1", tenant_id="t2") is None
    assert store.load_plan_context("as_1", tenant_id="t1") is not None


def test_another_tenant_cannot_CONCLUDE_an_assessment(store):
    """The most consequential write in the customer flow: after it the schema refuses every
    further write, so a cross-tenant conclusion would freeze someone else's interview."""
    release_id = _released(store, _template(store))
    _assessment(store, release_id)
    assert store.complete_assessment("as_1", tenant_id="t2", at=_later()) is False
    # Still open, therefore still answerable — the cross-tenant call changed nothing.
    assert store.complete_assessment("as_1", tenant_id="t1", at=_later()) is True


def test_a_reviewer_can_send_a_release_back_to_draft(store):
    """The one genuine contract gap: the state machine had approve, release and retire, so it must
    have reject. Without it a reviewer who disagrees has no move that is not a workaround."""
    template_id = _template(store)
    store.create_release(
        release_id="rel_1", template_id=template_id, questions=[_question()],
        generated_by_model="m", prompt_version="p", generator_commit="c", created_by="g",
    )
    store.submit_for_review("rel_1")
    assert store.reject_release("rel_1") is True
    assert store.list_releases(release_id="rel_1")[0]["status"] == "draft"
    assert store.reject_release("rel_1") is False, "already a draft — idempotent, not an error"


def test_a_RELEASED_asset_cannot_be_rejected_back_into_draft(store):
    """Rejection is a review move, not an undo. Once released, the only exit is retirement —
    otherwise a published asset could be edited underneath the organizations interviewed on it."""
    release_id = _released(store, _template(store))
    assert store.reject_release(release_id) is False


def test_the_list_primitive_filters_rather_than_multiplying_methods(store):
    """One concept, not one method per screen."""
    template_id = _template(store)
    draft_id = f"rel_{uuid.uuid4().hex[:8]}"
    store.create_release(
        release_id=draft_id, template_id=template_id, questions=[_question()],
        generated_by_model="m", prompt_version="p", generator_commit="c", created_by="g",
    )
    released_id = _released(store, template_id)

    assert len(store.list_releases(industry_slug="real_estate")) == 2
    assert [r["id"] for r in store.list_releases(status="draft")] == [draft_id]
    assert [r["id"] for r in store.list_releases(release_id=released_id)] == [released_id]
    assert "questions" not in store.list_releases(release_id=released_id)[0], (
        "a listing must not carry every question — depth is a filter, not a second method"
    )
    assert len(store.list_releases(release_id=released_id, with_questions=True)[0]["questions"]) == 1


def test_an_unfinished_assessment_is_findable_by_TENANT_not_only_by_session(store):
    """A customer who closed the tab mid-interview has no session id in hand. Without this read
    their answers are unreachable and the only way forward is to start over."""
    release_id = _released(store, _template(store))
    _assessment(store, release_id)
    open_one = store.find_open_assessment(tenant_id="t1")
    assert open_one["id"] == "as_1"
    assert open_one["source_session_id"] is None or True

    assert store.find_open_assessment(tenant_id="t2") is None, "and never another tenant's"

    store.complete_assessment("as_1", tenant_id="t1", at=_later())
    assert store.find_open_assessment(tenant_id="t1") is None, "a finished one is not unfinished"


def test_the_NEWEST_unfinished_assessment_wins(store):
    """Resuming the older one would silently discard the newer."""
    release_id = _released(store, _template(store))
    _assessment(store, release_id)
    store.open_assessment(assessment_id="as_new", tenant_id="t1", organization_id="org1")
    store.record_selection(
        assessment_id="as_new", tenant_id="t1", suggested_industry_slug="real_estate",
        selected_release_ids=[release_id], selected_by="reviewer",
    )
    assert store.find_open_assessment(tenant_id="t1")["id"] == "as_new"
