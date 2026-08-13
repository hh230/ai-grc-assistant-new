"""The English import path, end to end against a real Postgres (ADR 0067 §3).

Each test here pins one way the import could put the right words on the wrong question — or put
them somewhere a reviewer never agreed to. The Arabic is the source of truth throughout: nothing
in this module writes to `release_questions`, and one test proves it.
"""

from __future__ import annotations

import os
import pathlib
import uuid

import pytest

psycopg = pytest.importorskip("psycopg")

MIGRATIONS = (
    pathlib.Path(__file__).resolve().parents[3] / "packages" / "governance-store" / "migrations"
)
DSN_ENV_VAR = "GOVERNANCE_SCHEMA_TEST_DSN"
DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5432/rasheed_translation_import_tests"


@pytest.fixture(scope="module")
def conn():
    dsn = os.environ.get(DSN_ENV_VAR, DEFAULT_DSN)
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
def store(conn):
    from governance_store.knowledge_store import PostgresKnowledgeStore

    conn.execute("SET session_replication_role = replica")
    for table in (
        "question_translations", "active_template_history", "active_templates",
        "release_questions", "template_releases", "knowledge_templates", "industries",
    ):
        conn.execute(f"DELETE FROM {table}")
    conn.execute("SET session_replication_role = DEFAULT")
    return PostgresKnowledgeStore(connection=conn)


def _question(qid="q_one", ar="سؤال عربي", en="An English question", **overrides):
    q = {
        "question_id": qid,
        "canonical_text_ar": ar,
        "canonical_text_en": en,
        "type": "enum",
        "options": ["نعم", "لا"],
        "options_en": {"نعم": "Yes", "لا": "No"},
        "required": True,
        "category": "governance",
        "importance": "high",
        "references": [{"framework": "ISO 27001", "clause": "5.2"}],
        "why_we_ask": "لأن المراجع يحتاج سببًا",
        "evidence_required": ["وثيقة"],
        "evidence_required_en": ["A document"],
    }
    q.update(overrides)
    return q


def _activate(store, conn, slug="technology", questions=None):
    """A sector with one released, activated release — the state an import targets."""
    questions = questions or [_question()]
    conn.execute(
        "INSERT INTO industries (slug, canonical_name_ar) VALUES (%s, 'تقنية') "
        "ON CONFLICT DO NOTHING", (slug,))
    template_id = f"tpl_{uuid.uuid4().hex[:8]}"
    conn.execute(
        "INSERT INTO knowledge_templates (id, industry_slug) VALUES (%s, %s)",
        (template_id, slug))
    release_id = f"rel_{uuid.uuid4().hex[:8]}"
    store.create_release(
        release_id=release_id, template_id=template_id, questions=questions,
        generated_by_model="authored", prompt_version=f"authored:{slug}",
        generator_commit="test", created_by="tester", expected_outputs=[])
    # `approved_by`/`approved_at` are set with the status because the schema refuses an approval
    # with no recorded identity — the fixture obeys the same rule the product does.
    conn.execute(
        "UPDATE template_releases SET status = 'released', approved_by = 'tester', "
        " approved_at = now() WHERE id = %s",
        (release_id,))
    conn.execute(
        "INSERT INTO active_templates (industry_slug, release_id, release_status, activated_by) "
        "VALUES (%s, %s, 'released', 'tester')", (slug, release_id))
    return release_id


# --- the happy path ------------------------------------------------------------------------


def test_the_dry_run_plans_every_question_and_writes_nothing(store, conn):
    from grc_api.translation_import import plan_import

    _activate(store, conn, questions=[_question("q_one"), _question("q_two", ar="سؤال ثانٍ")])
    report = plan_import(store, {"technology": {"questions": [
        _question("q_one"), _question("q_two", ar="سؤال ثانٍ")]}})

    assert report.ok
    assert report.questions_seen == 2, "two questions"
    assert report.inserts == 8, "two questions x (1 text + 2 options + 1 evidence)"
    assert conn.execute("SELECT count(*) FROM question_translations").fetchone()[0] == 0


def test_the_import_writes_what_the_plan_said_and_stops_at_generated(store, conn):
    from grc_api.translation_import import apply_import, plan_import

    release_id = _activate(store, conn)
    pack = {"technology": {"questions": [_question()]}}
    assert apply_import(store, plan_import(store, pack)) == 4, "one question, four parts"

    row = store.get_translation(release_id=release_id, question_id="q_one", language="en")
    assert row["text"] == "An English question"
    assert row["status"] == "generated", "an import is not a review"


# --- idempotency ---------------------------------------------------------------------------


def test_a_second_run_over_unchanged_content_writes_nothing(store, conn):
    """Not "writes the same thing twice" — writes NOTHING. `save_translation` resets status on
    conflict, so a re-run that wrote would demote a reviewed string back to generated."""
    from grc_api.translation_import import apply_import, plan_import

    release_id = _activate(store, conn)
    pack = {"technology": {"questions": [_question()]}}
    apply_import(store, plan_import(store, pack))
    assert store.review_translation(release_id=release_id, question_id="q_one", language="en")

    second = plan_import(store, pack)
    assert {p.action for p in second.planned} == {"unchanged"}
    assert apply_import(store, second) == 0

    row = store.get_translation(release_id=release_id, question_id="q_one", language="en")
    assert row["status"] == "reviewed", "a re-run must not demote a reviewed translation"
    assert conn.execute("SELECT count(*) FROM question_translations").fetchone()[0] == 4


def test_changed_english_is_an_update_not_a_duplicate(store, conn):
    from grc_api.translation_import import apply_import, plan_import

    release_id = _activate(store, conn)
    apply_import(store, plan_import(store, {"technology": {"questions": [_question()]}}))
    revised = {"technology": {"questions": [_question(en="A corrected English question")]}}
    plan = plan_import(store, revised)
    assert sorted({p.action for p in plan.planned}) == ["unchanged", "update"]
    apply_import(store, plan)

    assert conn.execute("SELECT count(*) FROM question_translations").fetchone()[0] == 4
    row = store.get_translation(release_id=release_id, question_id="q_one", language="en")
    assert row["text"] == "A corrected English question"


# --- what the import must refuse -------------------------------------------------------------


def test_an_incomplete_translation_is_refused_before_any_write(store, conn):
    from grc_api.translation_import import apply_import, plan_import

    _activate(store, conn, questions=[_question("q_one"), _question("q_two", ar="سؤال ثانٍ")])
    pack = {"technology": {"questions": [
        _question("q_one"), _question("q_two", ar="سؤال ثانٍ", canonical_text_en="  ")]}}

    report = plan_import(store, pack)
    assert not report.ok and "no English" in report.errors[0]
    with pytest.raises(ValueError, match="refusing to import"):
        apply_import(store, report)
    assert conn.execute("SELECT count(*) FROM question_translations").fetchone()[0] == 0


def test_a_translation_for_an_unknown_question_is_refused(store, conn):
    from grc_api.translation_import import plan_import

    _activate(store, conn)
    report = plan_import(store, {"technology": {"questions": [_question("q_invented")]}})
    assert not report.ok
    assert "not a question of the active release" in report.errors[0]


def test_a_pack_whose_arabic_drifted_is_refused_rather_than_reconciled(store, conn):
    """The id still matches, so a careless importer would file the English against a question
    whose text has changed underneath it. The release is the authority, not the file."""
    from grc_api.translation_import import plan_import

    _activate(store, conn, questions=[_question(ar="النص العربي المعتمد")])
    report = plan_import(store, {"technology": {"questions": [_question(ar="نص عربي آخر")]}})
    assert not report.ok
    assert "drifted" in report.errors[0]


def test_a_sector_with_nothing_activated_is_refused(store, conn):
    from grc_api.translation_import import plan_import

    report = plan_import(store, {"technology": {"questions": [_question()]}})
    assert not report.ok and "no active release" in report.errors[0]


def test_the_import_never_writes_arabic(store, conn):
    """The whole point of the path: `release_questions` is read, never written."""
    from grc_api.translation_import import apply_import, plan_import

    release_id = _activate(store, conn)
    before = conn.execute(
        "SELECT canonical_text_ar, options, evidence_required FROM release_questions "
        "WHERE release_id = %s", (release_id,)).fetchall()
    apply_import(store, plan_import(store, {"technology": {"questions": [_question()]}}))
    after = conn.execute(
        "SELECT canonical_text_ar, options, evidence_required FROM release_questions "
        "WHERE release_id = %s", (release_id,)).fetchall()
    assert before == after


def test_arabic_can_never_be_stored_as_a_translation(store, conn):
    """Belt and braces: the schema refuses it, and this is where that is stated in a test the
    importer's authors will read."""
    release_id = _activate(store, conn)
    with pytest.raises(Exception):
        store.save_translation(
            release_id=release_id, question_id="q_one", language="ar", text="عربي")


# --- the lifecycle -------------------------------------------------------------------------


def test_generated_reviewed_published_is_traversable_and_ordered(store, conn):
    """Before `review_translation` existed, `publish_translation` accepted only `reviewed` and
    nothing set it — the gate was shut, not strict."""
    from grc_api.translation_import import apply_import, plan_import

    release_id = _activate(store, conn)
    apply_import(store, plan_import(store, {"technology": {"questions": [_question()]}}))
    key = dict(release_id=release_id, question_id="q_one", language="en")

    assert store.publish_question_translation(**key) == 0, "generated may not be published"
    assert store.review_translation(**key) is True
    assert store.review_translation(**key) is False, "reviewing twice changes nothing"
    for part in (("option", 0), ("option", 1), ("evidence", 0)):
        assert store.review_translation(**key, part=part) is True
    assert store.publish_question_translation(**key) == 4, "all four parts, together"
    assert store.get_translation(**key)["status"] == "published"

# =================================================================================================
# ADR 0069 — composite parts, atomicity, partial publication, fallback
# =================================================================================================


def _import(store, question=None):
    """Import one question's parts and return (release_id, question_id)."""
    from grc_api.translation_import import apply_import, plan_import

    question = question or _question()
    release_id = _activate(store, store._conn, questions=[question])  # noqa: SLF001
    report = plan_import(store, {"technology": {"questions": [question]}})
    assert report.ok, report.errors
    apply_import(store, report)
    return release_id, question["question_id"]


def _review_all(store, release_id, qid, skip=None):
    """Review every part except `skip`, so a test can leave exactly one part behind."""
    parts = [("question", 0), ("option", 0), ("option", 1), ("evidence", 0)]
    for part in parts:
        if part != skip:
            store.review_translation(
                release_id=release_id, question_id=qid, language="en", part=part)
    return parts


def _statuses(conn, release_id, qid):
    return {
        (r[0], r[1]): r[2]
        for r in conn.execute(
            "SELECT part_kind, part_index, status FROM question_translations "
            "WHERE release_id = %s AND question_id = %s AND language = 'en'",
            (release_id, qid)).fetchall()
    }


# --- 1-4: atomicity, partial publication, rollback, coverage -------------------------------


def test_publish_refuses_when_any_part_is_unreviewed(store, conn):
    """One unreviewed part must stop the whole question — and leave every other part alone."""
    release_id, qid = _import(store)
    _review_all(store, release_id, qid, skip=("evidence", 0))

    assert store.publish_question_translation(
        release_id=release_id, question_id=qid, language="en") == 0
    after = _statuses(conn, release_id, qid)
    assert "published" not in after.values(), "a refused publish must publish nothing"
    assert after[("evidence", 0)] == "generated"


def test_publish_refuses_a_question_missing_a_part(store, conn):
    """Every part present is reviewed, but one was never imported: publishing would put an English
    question on screen whose evidence line falls back to Arabic."""
    release_id, qid = _import(store)
    conn.execute(
        "DELETE FROM question_translations WHERE release_id = %s AND question_id = %s "
        "AND part_kind = 'evidence'", (release_id, qid))
    _review_all(store, release_id, qid, skip=("evidence", 0))

    assert store.publish_question_translation(
        release_id=release_id, question_id=qid, language="en") == 0
    assert "published" not in _statuses(conn, release_id, qid).values()


def test_a_failed_publish_leaves_no_part_published(store, conn):
    """The rollback case: most parts reviewed, one not, and the write must be all or nothing."""
    release_id, qid = _import(store)
    _review_all(store, release_id, qid, skip=("option", 1))
    before = _statuses(conn, release_id, qid)

    assert store.publish_question_translation(
        release_id=release_id, question_id=qid, language="en") == 0
    assert _statuses(conn, release_id, qid) == before, "a refusal must change nothing at all"


def test_translation_coverage_counts_questions_not_rows(store, conn):
    from governance_discovery.knowledge_template import (
        KnowledgeTemplate, QuestionTranslation, Reference, TemplateQuestion,
        TranslationStatus, translation_coverage,
    )

    release_id, qid = _import(store)
    _review_all(store, release_id, qid)
    published = store.publish_question_translation(
        release_id=release_id, question_id=qid, language="en")
    assert published == 4, "one question, four parts"

    template = KnowledgeTemplate(
        industry_slug="technology", version=1, prompt_version="authored:technology",
        generated_by="authored",
        questions=(TemplateQuestion(
            id=qid, canonical_text="سؤال عربي", type="enum", required=True,
            category="governance", importance="high", why_we_ask="x",
            references=(Reference(framework="ISO 27001"),)),))
    # Four rows, because a question is four parts since ADR 0069. The projection must still say
    # ONE question is covered.
    translations = tuple(
        QuestionTranslation(question_id=qid, language="en", text="x",
                            status=TranslationStatus.PUBLISHED)
        for _ in range(4)
    )
    assert translation_coverage(template, translations, "en") == (1, 1), \
        "four published parts are ONE covered question"


# --- 5-11: the semantic guards ---------------------------------------------------------------


def test_option_index_out_of_range_is_refused(store, conn):
    release_id, qid = _import(store)
    with pytest.raises(IndexError, match="outside"):
        store.save_translation(release_id=release_id, question_id=qid, language="en",
                               text="Beyond the end", part=("option", 99))


def test_option_source_text_mismatch_is_refused(store, conn):
    release_id, qid = _import(store)
    with pytest.raises(ValueError, match="does not match the release"):
        store.save_translation(release_id=release_id, question_id=qid, language="en",
                               text="Yes", part=("option", 0), source_text_ar="نص ليس في الإصدار")


def test_evidence_index_out_of_range_is_refused(store, conn):
    release_id, qid = _import(store)
    with pytest.raises(IndexError, match="outside"):
        store.save_translation(release_id=release_id, question_id=qid, language="en",
                               text="A document", part=("evidence", 7))


def test_question_source_text_mismatch_is_refused(store, conn):
    release_id, qid = _import(store)
    with pytest.raises(ValueError, match="does not match the release"):
        store.save_translation(release_id=release_id, question_id=qid, language="en",
                               text="An English question", source_text_ar="سؤال مختلف")


def test_unknown_question_id_is_refused_by_the_store(store, conn):
    release_id, _ = _import(store)
    with pytest.raises(LookupError, match="no question"):
        store.save_translation(release_id=release_id, question_id="q_invented", language="en",
                               text="Anything")


# --- 12-20: fallback, contract, idempotency --------------------------------------------------


def test_language_ar_returns_exactly_the_untranslated_release(store, conn):
    release_id, qid = _import(store)
    _review_all(store, release_id, qid)
    store.publish_question_translation(release_id=release_id, question_id=qid, language="en")

    plain = store.list_releases(release_id=release_id, with_questions=True)[0]
    arabic = store.list_releases(release_id=release_id, with_questions=True, language="ar")[0]
    assert plain == arabic, "asking for ar must be identical to asking for nothing"
    assert "canonical_text_en" not in arabic["questions"][0]


def test_an_unpublished_question_falls_back_to_arabic_entirely(store, conn):
    release_id, qid = _import(store)  # imported, never reviewed or published
    english = store.list_releases(release_id=release_id, with_questions=True, language="en")[0]
    question = english["questions"][0]
    assert "canonical_text_en" not in question
    assert question["canonical_text_ar"] == "سؤال عربي"


def test_english_fields_are_all_present_or_all_absent(store, conn):
    release_id, qid = _import(store)
    _review_all(store, release_id, qid)
    store.publish_question_translation(release_id=release_id, question_id=qid, language="en")

    question = store.list_releases(
        release_id=release_id, with_questions=True, language="en")[0]["questions"][0]
    present = [k for k in ("canonical_text_en", "options_en", "evidence_required_en")
               if k in question]
    assert len(present) == 3
    assert len(question["options_en"]) == len(question["options"])
    assert len(question["evidence_required_en"]) == len(question["evidence_required"])


def test_reimporting_published_text_is_unchanged_and_keeps_it_published(store, conn):
    """Lifecycle rule: an identical re-import must not demote a published question."""
    from grc_api.translation_import import apply_import, plan_import

    question = _question()
    release_id, qid = _import(store, question)
    _review_all(store, release_id, qid)
    store.publish_question_translation(release_id=release_id, question_id=qid, language="en")

    again = plan_import(store, {"technology": {"questions": [question]}})
    assert {p.action for p in again.planned} == {"unchanged"}
    assert apply_import(store, again) == 0
    assert set(_statuses(conn, release_id, qid).values()) == {"published"}


def test_changing_one_english_string_returns_only_that_part_to_generated(store, conn):
    from grc_api.translation_import import apply_import, plan_import

    question = _question()
    release_id, qid = _import(store, question)
    _review_all(store, release_id, qid)
    store.publish_question_translation(release_id=release_id, question_id=qid, language="en")

    revised = _question(options_en={"نعم": "Yes indeed", "لا": "No"})
    apply_import(store, plan_import(store, {"technology": {"questions": [revised]}}))

    after = _statuses(conn, release_id, qid)
    assert after[("option", 0)] == "generated", "the changed part returns to generated"
    assert after[("question", 0)] == "published", "untouched parts keep their status"
    assert store.publish_question_translation(
        release_id=release_id, question_id=qid, language="en") == 0, \
        "and the question can no longer be published until it is reviewed again"


def test_the_import_writes_every_kind_of_part(store, conn):
    from grc_api.translation_import import plan_import

    _import(store)
    report = plan_import(store, {"technology": {"questions": [_question()]}})
    assert (report.questions_seen, report.options_seen, report.evidence_seen) == (1, 2, 1)
    assert report.strings_seen == 4


def test_a_published_question_that_loses_one_part_falls_back_entirely(store, conn):
    """Found by the isolated rehearsal, not by reasoning: correcting one English string returns
    that part to `generated` while its siblings stay `published`. The read path must treat the
    question as not-available-in-this-language rather than render three quarters of it."""
    release_id, qid = _import(store)
    _review_all(store, release_id, qid)
    assert store.publish_question_translation(
        release_id=release_id, question_id=qid, language="en") == 4

    conn.execute(
        "UPDATE question_translations SET status = 'generated' "
        "WHERE release_id = %s AND question_id = %s AND part_kind = 'evidence'",
        (release_id, qid))

    question = store.list_releases(
        release_id=release_id, with_questions=True, language="en")[0]["questions"][0]
    assert "canonical_text_en" not in question, "a question missing one part shows no English"
    assert "options_en" not in question and "evidence_required_en" not in question
    assert question["canonical_text_ar"] == "سؤال عربي"


# --- ordering, and the tables this feature must never touch ------------------------------------


def _publish_all(store, conn, release_id, questions):
    from grc_api.translation_import import apply_import, plan_import

    apply_import(store, plan_import(store, {"technology": {"questions": questions}}))
    conn.execute("UPDATE question_translations SET status = 'reviewed'")
    for question in questions:
        store.publish_question_translation(
            release_id=release_id, question_id=question["question_id"], language="en")


def test_options_en_is_positionally_aligned_to_the_arabic_options(store, conn):
    """The contract is `list[str]`, not a map — so ORDER is the only thing tying an English option
    to the Arabic one it translates. Options that sort differently in Arabic than in English would
    silently re-label every answer on the screen."""
    question = _question(
        options=["ألف", "باء", "جيم", "دال"],
        options_en={"ألف": "Alpha", "باء": "Bravo", "جيم": "Charlie", "دال": "Delta"})
    release_id = _activate(store, conn, questions=[question])
    _publish_all(store, conn, release_id, [question])

    stored = store.get_active_release("technology", language="en")["questions"][0]
    assert stored["options_en"] == ["Alpha", "Bravo", "Charlie", "Delta"]
    assert len(stored["options_en"]) == len(stored["options"])
    # Position by position, not merely the same set.
    for index, arabic in enumerate(["ألف", "باء", "جيم", "دال"]):
        assert stored["options"][index] == arabic
        assert stored["options_en"][index] == {"ألف": "Alpha", "باء": "Bravo",
                                               "جيم": "Charlie", "دال": "Delta"}[arabic]


def test_evidence_en_is_positionally_aligned_to_the_arabic_evidence(store, conn):
    """`evidence_required` has no identity but its position (ADR 0069), so alignment IS the link."""
    question = _question(
        evidence_required=["أولاً", "ثانياً", "ثالثاً"],
        evidence_required_en=["First", "Second", "Third"])
    release_id = _activate(store, conn, questions=[question])
    _publish_all(store, conn, release_id, [question])

    stored = store.get_active_release("technology", language="en")["questions"][0]
    assert stored["evidence_required_en"] == ["First", "Second", "Third"]
    assert len(stored["evidence_required_en"]) == len(stored["evidence_required"])


def test_publishing_english_changes_neither_release_questions_nor_sector_answers(store, conn):
    """The whole feature adds a second language; it must not touch the Arabic a customer was
    actually asked, nor the answers they gave. Compared as content hashes, not row counts — a
    same-size edit is exactly what a count would miss."""
    question = _question()
    release_id = _activate(store, conn, questions=[question])
    conn.execute(
        "INSERT INTO assessments (id, tenant_id, organization_id) "
        "VALUES ('asm_x', 'tenant_x', 'org_x') ON CONFLICT DO NOTHING")
    conn.execute(
        "INSERT INTO sector_answers (assessment_id, release_id, question_id, tenant_id, answer) "
        "VALUES ('asm_x', %s, %s, 'tenant_x', %s) ON CONFLICT DO NOTHING",
        (release_id, question["question_id"], '"نعم"'))

    def fingerprints():
        return (
            conn.execute("SELECT md5(coalesce(string_agg(release_id || question_id || "
                         "canonical_text_ar || options::text || evidence_required::text, '~' "
                         "ORDER BY release_id, question_id), '')) FROM release_questions"
                         ).fetchone()[0],
            conn.execute("SELECT md5(coalesce(string_agg(assessment_id || question_id || "
                         "answer::text, '~' ORDER BY assessment_id, question_id), '')) "
                         "FROM sector_answers").fetchone()[0],
        )

    before = fingerprints()
    _publish_all(store, conn, release_id, [question])
    assert store.get_active_release("technology", language="en")["questions"][0]["canonical_text_en"]
    assert fingerprints() == before
