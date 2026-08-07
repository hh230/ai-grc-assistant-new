"""ADR 0067 schema — every guarantee proved by trying to violate it against a real Postgres.

A constraint nobody has attempted to break is a comment. Each test here performs the exact write
the schema is supposed to refuse, and asserts the database refuses it — so "the migration proves
one property" means something checkable rather than aspirational.

Skips cleanly when no database is reachable, like the other integration suites.
"""

from __future__ import annotations

import os
import pathlib
import uuid

import pytest

psycopg = pytest.importorskip("psycopg")

MIGRATIONS = pathlib.Path(__file__).resolve().parents[1] / "migrations"
KNOWLEDGE_MIGRATIONS = sorted(
    p for p in MIGRATIONS.glob("*.sql") if int(p.name.split("_", 1)[0]) >= 4
)
DSN_ENV_VAR = "GOVERNANCE_SCHEMA_TEST_DSN"
DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5432/rasheed_adr67_tests"


def _admin_dsn(dsn: str) -> tuple[str, str]:
    base, _, database = dsn.rpartition("/")
    return f"{base}/postgres", database


@pytest.fixture(scope="module")
def conn():
    """A database containing ONLY the ADR 0067 tables, built from the migrations themselves.

    Rebuilt per run: a schema test that trusts a database someone else prepared is testing that
    person's memory, not the migrations.
    """
    dsn = os.environ.get(DSN_ENV_VAR, DEFAULT_DSN)
    admin, database = _admin_dsn(dsn)
    try:
        with psycopg.connect(admin, autocommit=True, connect_timeout=3) as setup:
            setup.execute(f'DROP DATABASE IF EXISTS "{database}"')
            setup.execute(f'CREATE DATABASE "{database}"')
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no reachable PostgreSQL ({exc})")

    connection = psycopg.connect(dsn, autocommit=True)
    for migration in KNOWLEDGE_MIGRATIONS:
        connection.execute(migration.read_text(encoding="utf-8"))
    yield connection
    connection.close()


@pytest.fixture
def clean(conn):
    """Truncate between tests. Order matters: children before parents."""
    # TRUNCATE does not fire row triggers, which is what makes the frozen-assessment rows
    # clearable between tests without disabling the very trigger under test.
    conn.execute(
        "TRUNCATE sector_answers, template_selections, assessments, active_template_history, "
        "question_translations, release_questions RESTART IDENTITY"
    )
    # The freeze trigger forbids DELETE, so these two are cleared with it disabled — the trigger's
    # behaviour is what the tests below exercise deliberately, not something to work around
    # silently elsewhere.
    conn.execute("ALTER TABLE template_releases DISABLE TRIGGER template_releases_freeze_trg")
    conn.execute("DELETE FROM active_templates")
    conn.execute("DELETE FROM template_releases")
    conn.execute("ALTER TABLE template_releases ENABLE TRIGGER template_releases_freeze_trg")
    conn.execute("DELETE FROM knowledge_templates")
    conn.execute("DELETE FROM industries")
    return conn


def _industry(conn, slug="real_estate") -> str:
    conn.execute(
        "INSERT INTO industries (slug, canonical_name_ar) VALUES (%s, %s) "
        "ON CONFLICT DO NOTHING",
        (slug, "عقارات"),
    )
    return slug


def _template(conn, slug="real_estate") -> str:
    template_id = f"tpl_{uuid.uuid4().hex[:8]}"
    conn.execute(
        "INSERT INTO knowledge_templates (id, industry_slug) VALUES (%s, %s)",
        (template_id, _industry(conn, slug)),
    )
    return template_id


def _release(conn, template_id: str, version: int = 1, status: str = "draft") -> str:
    """Any status past `in_review` needs an approver identity — the schema requires it, so the
    helper supplies one rather than working around the constraint under test."""
    release_id = f"rel_{uuid.uuid4().hex[:8]}"
    needs_approver = status not in ("draft", "in_review")
    approved_by = "reviewer@example.com" if needs_approver else None
    approved_at = "now()" if needs_approver else "NULL"
    conn.execute(
        "INSERT INTO template_releases "
        "(id, template_id, version, status, generated_by_model, prompt_version, "
        " generator_commit, created_by, approved_by, approved_at) "
        f"VALUES (%s, %s, %s, %s, 'claude-sonnet-5', 'knowledge_prompt_v3', '9af4c1e', "
        f"        'generator', %s, {approved_at})",
        (release_id, template_id, version, status, approved_by),
    )
    return release_id


def _question(conn, release_id: str, question_id: str = "fal_license") -> str:
    conn.execute(
        'INSERT INTO release_questions (release_id, question_id, canonical_text_ar, type, '
        'category, importance, "references", why_we_ask) '
        "VALUES (%s, %s, %s, 'boolean', 'licensing', 'critical', "
        "        '[{\"framework\":\"REGA\",\"clause\":\"FAL\"}]'::jsonb, %s)",
        (release_id, question_id, "هل لديكم رخصة فال؟", "Determines licensing scope."),
    )
    return question_id


# --- 0004/0005: identity ----------------------------------------------------------------------


def test_an_industry_can_only_have_ONE_knowledge_container(clean):
    """Two containers would make "which template does real estate use?" ambiguous."""
    _template(clean)
    with pytest.raises(psycopg.errors.UniqueViolation):
        clean.execute(
            "INSERT INTO knowledge_templates (id, industry_slug) VALUES ('tpl_dup', 'real_estate')"
        )


def test_a_release_cannot_reuse_a_version_number(clean):
    template_id = _template(clean)
    _release(clean, template_id, version=1)
    with pytest.raises(psycopg.errors.UniqueViolation):
        _release(clean, template_id, version=1)


# --- 0006: Knowledge Freeze -------------------------------------------------------------------


def test_a_released_asset_can_NEVER_be_deleted(clean):
    """§8: a report issued a year ago must remain literally reconstructable."""
    release_id = _release(clean, _template(clean), status="released")
    with pytest.raises(psycopg.errors.RaiseException, match="never deleted"):
        clean.execute("DELETE FROM template_releases WHERE id = %s", (release_id,))


def test_a_DRAFT_release_cannot_be_deleted_either(clean):
    """The rule is "knowledge is never deleted", not "released knowledge is never deleted" — a
    draft is still a record of what a generator produced."""
    release_id = _release(clean, _template(clean))
    with pytest.raises(psycopg.errors.RaiseException, match="never deleted"):
        clean.execute("DELETE FROM template_releases WHERE id = %s", (release_id,))


def test_a_released_asset_cannot_have_its_PROVENANCE_rewritten(clean):
    """§7: freezing the questions alone would leave the prompt version editable, and the
    reproduction metadata would then describe a generator that no longer exists."""
    release_id = _release(clean, _template(clean), status="released")
    for column, value in (
        ("prompt_version", "knowledge_prompt_v9"),
        ("generated_by_model", "some-other-model"),
        ("generator_commit", "deadbeef"),
        ("expected_outputs", '["rewritten"]'),
    ):
        with pytest.raises(psycopg.errors.RaiseException, match="Knowledge Freeze"):
            clean.execute(
                f"UPDATE template_releases SET {column} = %s WHERE id = %s", (value, release_id)
            )


def test_a_released_asset_MAY_still_move_forward_in_its_lifecycle(clean):
    """Freeze protects content and provenance, not the status — superseding and archiving must
    remain possible or the lifecycle is unusable."""
    release_id = _release(clean, _template(clean), status="released")
    clean.execute("UPDATE template_releases SET status = 'superseded' WHERE id = %s", (release_id,))
    assert clean.execute(
        "SELECT status FROM template_releases WHERE id = %s", (release_id,)
    ).fetchone()[0] == "superseded"


def test_an_unapproved_release_cannot_claim_to_be_released(clean):
    """§8: approval without a recorded identity is not an approval."""
    template_id = _template(clean)
    with pytest.raises(psycopg.errors.CheckViolation, match="approved_has_identity"):
        clean.execute(
            "INSERT INTO template_releases (id, template_id, version, status, "
            " generated_by_model, prompt_version, generator_commit, created_by) "
            "VALUES ('rel_x', %s, 9, 'released', 'm', 'p', 'c', 'g')",
            (template_id,),
        )


def test_provenance_is_never_optional(clean):
    """An output that cannot be reproduced cannot be audited (CLAUDE.md §19)."""
    template_id = _template(clean)
    with pytest.raises(psycopg.errors.NotNullViolation):
        clean.execute(
            "INSERT INTO template_releases (id, template_id, version, status, prompt_version, "
            " generator_commit, created_by) VALUES ('rel_y', %s, 8, 'draft', 'p', 'c', 'g')",
            (template_id,),
        )


# --- 0007: questions --------------------------------------------------------------------------


def test_a_question_id_is_unique_within_its_release(clean):
    """Answers are keyed by it; a duplicate silently overwrites an answer."""
    release_id = _release(clean, _template(clean))
    _question(clean, release_id)
    with pytest.raises(psycopg.errors.UniqueViolation):
        _question(clean, release_id)


def test_a_question_must_rest_on_at_least_one_reference(clean):
    release_id = _release(clean, _template(clean))
    with pytest.raises(psycopg.errors.CheckViolation, match="has_a_reference"):
        clean.execute(
            'INSERT INTO release_questions (release_id, question_id, canonical_text_ar, type, '
            'category, importance, "references", why_we_ask) '
            "VALUES (%s, 'q', 'س', 'boolean', 'c', 'critical', '[]'::jsonb, 'w')",
            (release_id,),
        )


def test_an_enum_question_needs_at_least_two_options(clean):
    release_id = _release(clean, _template(clean))
    with pytest.raises(psycopg.errors.CheckViolation, match="enum_has_options"):
        clean.execute(
            'INSERT INTO release_questions (release_id, question_id, canonical_text_ar, type, '
            'options, category, importance, "references", why_we_ask) '
            "VALUES (%s, 'q', 'س', 'enum', '[\"only\"]'::jsonb, 'c', 'high', "
            "        '[{\"framework\":\"X\"}]'::jsonb, 'w')",
            (release_id,),
        )


def test_the_schema_offers_NO_column_that_would_put_an_llm_fact_on_the_decision_path(clean):
    """§2, structurally: Claude authors language, not truth. A column here would be an invitation
    to store an LLM-asserted decision, so none exists."""
    columns = {
        row[0]
        for row in clean.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'release_questions'"
        ).fetchall()
    }
    forbidden = {
        "writes_signal", "signal", "rule", "rules", "predicate", "effect",
        "severity", "maturity_delta", "priority", "plan_seed", "resolves_signal",
    }
    assert not (columns & forbidden), f"decision columns leaked into the schema: {columns & forbidden}"


# --- 0008: Arabic is the single source of truth ------------------------------------------------


def test_arabic_can_NEVER_be_stored_as_a_translation(clean):
    """Storing it twice is the second copy that later drifts."""
    release_id = _release(clean, _template(clean))
    _question(clean, release_id)
    with pytest.raises(psycopg.errors.CheckViolation, match="never_arabic"):
        clean.execute(
            "INSERT INTO question_translations (release_id, question_id, language, text) "
            "VALUES (%s, 'fal_license', 'ar', 'نسخة ثانية')",
            (release_id,),
        )


def test_a_translation_must_belong_to_a_question_that_exists_in_that_release(clean):
    release_id = _release(clean, _template(clean))
    _question(clean, release_id)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        clean.execute(
            "INSERT INTO question_translations (release_id, question_id, language, text) "
            "VALUES (%s, 'no_such_question', 'en', 'x')",
            (release_id,),
        )


# --- 0009: the active pointer -----------------------------------------------------------------


def test_an_industry_can_NEVER_have_two_active_releases(clean):
    """The primary key is the guarantee — unrepresentable, not merely discouraged."""
    template_id = _template(clean)
    first = _release(clean, template_id, version=1, status="released")
    second = _release(clean, template_id, version=2, status="released")
    clean.execute(
        "INSERT INTO active_templates (industry_slug, release_id, release_status, activated_by) "
        "VALUES ('real_estate', %s, 'released', 'approver')",
        (first,),
    )
    with pytest.raises(psycopg.errors.UniqueViolation):
        clean.execute(
            "INSERT INTO active_templates (industry_slug, release_id, release_status, "
            " activated_by) VALUES ('real_estate', %s, 'released', 'approver')",
            (second,),
        )


def test_a_release_that_was_never_RELEASED_cannot_be_activated(clean):
    """Declarative: the composite foreign key to (id, status) plus the CHECK, not a trigger and
    not application code."""
    draft = _release(clean, _template(clean), status="draft")
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        clean.execute(
            "INSERT INTO active_templates (industry_slug, release_id, release_status, "
            " activated_by) VALUES ('real_estate', %s, 'released', 'approver')",
            (draft,),
        )


def test_rollback_is_ONE_update_and_touches_no_release(clean):
    """The reason the pointer exists (§4, alternative D): publish v4, find a bad question, point
    back at v3 — without minting a v5 that exists only to reverse a mistake."""
    template_id = _template(clean)
    v3 = _release(clean, template_id, version=3, status="released")
    v4 = _release(clean, template_id, version=4, status="released")
    clean.execute(
        "INSERT INTO active_templates (industry_slug, release_id, release_status, activated_by) "
        "VALUES ('real_estate', %s, 'released', 'approver')",
        (v4,),
    )
    clean.execute(
        "UPDATE active_templates SET release_id = %s WHERE industry_slug = 'real_estate'", (v3,)
    )

    assert clean.execute(
        "SELECT release_id FROM active_templates WHERE industry_slug = 'real_estate'"
    ).fetchone()[0] == v3
    still_released = clean.execute(
        "SELECT count(*) FROM template_releases WHERE status = 'released'"
    ).fetchone()[0]
    assert still_released == 2, "rollback must not demote or invent any release"


def test_an_active_release_cannot_be_demoted_out_of_released(clean):
    """ON UPDATE CASCADE rewrites the pointer's copy of the status, which then violates its CHECK.
    Deliberate: a release cannot be quietly withdrawn while customers are being interviewed on it."""
    template_id = _template(clean)
    release_id = _release(clean, template_id, version=1, status="released")
    clean.execute(
        "INSERT INTO active_templates (industry_slug, release_id, release_status, activated_by) "
        "VALUES ('real_estate', %s, 'released', 'approver')",
        (release_id,),
    )
    with pytest.raises(psycopg.errors.CheckViolation, match="must_be_released"):
        clean.execute(
            "UPDATE template_releases SET status = 'deprecated' WHERE id = %s", (release_id,)
        )


# --- 0010: the activation history --------------------------------------------------------------


def test_the_activation_history_can_never_be_rewritten(clean):
    """An audit trail that can be rewritten is not an audit trail."""
    release_id = _release(clean, _template(clean), status="released")
    clean.execute(
        "INSERT INTO active_template_history (industry_slug, release_id, activated_by, reason) "
        "VALUES ('real_estate', %s, 'approver', 'initial release')",
        (release_id,),
    )
    with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
        clean.execute("UPDATE active_template_history SET reason = 'rewritten'")
    with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
        clean.execute("DELETE FROM active_template_history")


# --- 0011-0013: the customer side ---------------------------------------------------------------


def test_an_assessment_cannot_end_before_it_starts(clean):
    with pytest.raises(psycopg.errors.CheckViolation, match="ends_after_it_starts"):
        clean.execute(
            "INSERT INTO assessments (id, tenant_id, organization_id, started_at, completed_at) "
            "VALUES ('as_1', 't', 'o', now(), now() - interval '1 day')"
        )


def test_an_assessment_needs_no_session_because_backfill_is_forbidden(clean):
    """ADR 0067's migration plan forbids inventing history, so an assessment must be creatable
    without a session, and old sessions keep working with no assessment at all."""
    clean.execute(
        "INSERT INTO assessments (id, tenant_id, organization_id) VALUES ('as_2', 't', 'o')"
    )
    assert clean.execute(
        "SELECT source_session_id FROM assessments WHERE id = 'as_2'"
    ).fetchone()[0] is None


def test_a_selection_must_cite_at_least_one_release(clean):
    clean.execute(
        "INSERT INTO assessments (id, tenant_id, organization_id) VALUES ('as_3', 't', 'o')"
    )
    with pytest.raises(psycopg.errors.CheckViolation, match="cites_a_release"):
        clean.execute(
            "INSERT INTO template_selections (assessment_id, tenant_id, selected_release_ids, "
            " selected_by) VALUES ('as_3', 't', ARRAY[]::text[], 'reviewer')"
        )


def test_a_selection_may_cite_SEVERAL_releases(clean):
    """Reality is not one sector: a brokerage that also builds."""
    clean.execute(
        "INSERT INTO assessments (id, tenant_id, organization_id) VALUES ('as_4', 't', 'o')"
    )
    clean.execute(
        "INSERT INTO template_selections (assessment_id, tenant_id, suggested_industry_slug, "
        " selected_release_ids, selected_by) "
        "VALUES ('as_4', 't', 'real_estate', ARRAY['rel_a','rel_b'], 'reviewer')"
    )
    assert clean.execute(
        "SELECT array_length(selected_release_ids, 1) FROM template_selections "
        "WHERE assessment_id = 'as_4'"
    ).fetchone()[0] == 2


def test_an_answer_cannot_reference_a_question_outside_its_release(clean):
    """The composite foreign key is the point."""
    release_id = _release(clean, _template(clean))
    _question(clean, release_id)
    clean.execute(
        "INSERT INTO assessments (id, tenant_id, organization_id) VALUES ('as_5', 't', 'o')"
    )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        clean.execute(
            "INSERT INTO sector_answers (assessment_id, release_id, question_id, tenant_id, "
            " answer) VALUES ('as_5', %s, 'not_in_this_release', 't', 'false'::jsonb)",
            (release_id,),
        )


def test_knowledge_tables_carry_no_tenant_id_and_customer_tables_all_do(clean):
    """Sector knowledge is generated once and shared by every organization in that sector — that
    is the whole point of ADR 0067. Tenant scoping starts where customer data does."""
    def columns(table: str) -> set[str]:
        return {
            row[0]
            for row in clean.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
                (table,),
            ).fetchall()
        }

    for shared in (
        "industries", "knowledge_templates", "template_releases", "release_questions",
        "question_translations", "active_templates", "active_template_history",
    ):
        assert "tenant_id" not in columns(shared), f"{shared} must not be tenant-scoped"

    for scoped in ("assessments", "template_selections", "sector_answers"):
        assert "tenant_id" in columns(scoped), f"{scoped} must be tenant-scoped (CLAUDE.md §20)"


# --- 0014: Assessment Freeze -------------------------------------------------------------------
#
# The rule that let `load_plan_context` stay at READ COMMITTED: freeze the source instead of
# snapshotting the read. Stronger, because a snapshot would have made a late write INVISIBLE to
# the read while still letting it land.


def _concluded_assessment(conn, assessment_id: str = "as_frozen") -> str:
    conn.execute(
        "INSERT INTO assessments (id, tenant_id, organization_id) VALUES (%s, 't', 'o')",
        (assessment_id,),
    )
    conn.execute(
        "UPDATE assessments SET completed_at = now() WHERE id = %s", (assessment_id,)
    )
    return assessment_id


def test_a_concluded_assessment_accepts_no_new_sector_answers(clean):
    release_id = _release(clean, _template(clean))
    _question(clean, release_id)
    assessment_id = _concluded_assessment(clean)
    with pytest.raises(psycopg.errors.RaiseException, match="accepts no further writes"):
        clean.execute(
            "INSERT INTO sector_answers (assessment_id, release_id, question_id, tenant_id, "
            " answer) VALUES (%s, %s, 'fal_license', 't', 'true'::jsonb)",
            (assessment_id, release_id),
        )


def test_an_answer_already_recorded_cannot_be_CHANGED_after_conclusion(clean):
    """The dangerous case: the interview is over, and someone edits what was answered."""
    release_id = _release(clean, _template(clean))
    _question(clean, release_id)
    clean.execute(
        "INSERT INTO assessments (id, tenant_id, organization_id) VALUES ('as_edit', 't', 'o')"
    )
    clean.execute(
        "INSERT INTO sector_answers (assessment_id, release_id, question_id, tenant_id, answer) "
        "VALUES ('as_edit', %s, 'fal_license', 't', 'false'::jsonb)",
        (release_id,),
    )
    clean.execute("UPDATE assessments SET completed_at = now() WHERE id = 'as_edit'")

    with pytest.raises(psycopg.errors.RaiseException, match="accepts no further writes"):
        clean.execute(
            "UPDATE sector_answers SET answer = 'true'::jsonb WHERE assessment_id = 'as_edit'"
        )
    with pytest.raises(psycopg.errors.RaiseException, match="accepts no further writes"):
        clean.execute("DELETE FROM sector_answers WHERE assessment_id = 'as_edit'")


def test_the_template_selection_freezes_too(clean):
    """Which knowledge produced the report must not change after the report exists."""
    assessment_id = _concluded_assessment(clean, "as_sel")
    with pytest.raises(psycopg.errors.RaiseException, match="accepts no further writes"):
        clean.execute(
            "INSERT INTO template_selections (assessment_id, tenant_id, selected_release_ids, "
            " selected_by) VALUES (%s, 't', ARRAY['rel_x'], 'reviewer')",
            (assessment_id,),
        )


def test_an_OPEN_assessment_still_accepts_writes(clean):
    """The freeze must not break the interview it exists to protect."""
    release_id = _release(clean, _template(clean))
    _question(clean, release_id)
    clean.execute(
        "INSERT INTO assessments (id, tenant_id, organization_id) VALUES ('as_open', 't', 'o')"
    )
    clean.execute(
        "INSERT INTO sector_answers (assessment_id, release_id, question_id, tenant_id, answer) "
        "VALUES ('as_open', %s, 'fal_license', 't', 'false'::jsonb)",
        (release_id,),
    )
    assert clean.execute(
        "SELECT count(*) FROM sector_answers WHERE assessment_id = 'as_open'"
    ).fetchone()[0] == 1


def test_conclusion_is_one_way(clean):
    """Re-opening would defeat every guarantee above."""
    assessment_id = _concluded_assessment(clean, "as_reopen")
    with pytest.raises(psycopg.errors.RaiseException, match="one-way"):
        clean.execute(
            "UPDATE assessments SET completed_at = NULL WHERE id = %s", (assessment_id,)
        )
    with pytest.raises(psycopg.errors.RaiseException, match="one-way"):
        clean.execute(
            "UPDATE assessments SET completed_at = now() + interval '1 day' WHERE id = %s",
            (assessment_id,),
        )
