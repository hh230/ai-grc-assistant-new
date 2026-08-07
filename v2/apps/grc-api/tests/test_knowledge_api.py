"""`/v1/knowledge/*` over a real database (ADR 0067).

What these prove is what only the transport layer can get wrong: that the two audiences get two
different shapes, that authorization is refused at the edge and not merely inside, that a tenant
cannot reach another tenant's assessment, and that an unconfigured deployment says so instead of
inventing knowledge.
"""

from __future__ import annotations

import os
import pathlib

import pytest
from fastapi.testclient import TestClient

psycopg = pytest.importorskip("psycopg")

from grc_api.app import create_app  # noqa: E402
from grc_api.composition import Storage  # noqa: E402

MIGRATIONS = (
    pathlib.Path(__file__).resolve().parents[3] / "packages" / "governance-store" / "migrations"
)
KNOWLEDGE_MIGRATIONS = sorted(
    p for p in MIGRATIONS.glob("*.sql") if int(p.name.split("_", 1)[0]) >= 4
)
DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5432/rasheed_kapi_tests"

APPROVER = {"Authorization": "Bearer dev-knowledge-approver"}
TENANT_A = {"Authorization": "Bearer dev-tenant-a"}
TENANT_B = {"Authorization": "Bearer dev-tenant-b"}


class _Generator:
    """Stands in for Claude. The real one is exercised in `test_knowledge_generation.py`; here the
    point is the route, so this returns the minimum a release needs."""

    def generate(self, *, industry_slug: str) -> list[dict]:
        return [
            {
                "question_id": f"q{i}",
                "canonical_text_ar": "هل لديكم رخصة فال؟",
                "type": "boolean",
                "options": [],
                "required": True,
                "category": "licensing",
                "importance": "critical",
                "references": [{"framework": "REGA", "clause": "FAL"}],
                "why_we_ask": "REVIEWER ONLY — determines whether the organization may broker.",
                "evidence_required": ["License number"],
            }
            for i in range(3)
        ]


@pytest.fixture(scope="module")
def dsn():
    target = os.environ.get("KNOWLEDGE_API_TEST_DSN", DEFAULT_DSN)
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
def client(dsn):
    from governance_store import PostgresKnowledgeStore

    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            "TRUNCATE sector_answers, template_selections, assessments, active_template_history, "
            "question_translations, release_questions RESTART IDENTITY"
        )
        conn.execute("ALTER TABLE template_releases DISABLE TRIGGER template_releases_freeze_trg")
        conn.execute("DELETE FROM active_templates")
        conn.execute("DELETE FROM template_releases")
        conn.execute("ALTER TABLE template_releases ENABLE TRIGGER template_releases_freeze_trg")
        conn.execute("DELETE FROM knowledge_templates")
        conn.execute("DELETE FROM industries")

    app = create_app(
        storage=Storage.MEMORY,
        knowledge_store_factory=lambda: PostgresKnowledgeStore(dsn=dsn),
        knowledge_question_generator=_Generator(),
    )
    with TestClient(app) as c:
        yield c


def _release(client) -> str:
    client.post(
        "/v1/knowledge/industries",
        json={"slug": "real_estate", "canonical_name_ar": "عقارات"},
        headers=APPROVER,
    )
    response = client.post(
        "/v1/knowledge/releases", json={"industry_slug": "real_estate"}, headers=APPROVER
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["release_id"]


def _activate(client, release_id: str) -> None:
    for action in ("submit", "approve", "publish"):
        assert (
            client.post(f"/v1/knowledge/releases/{release_id}/{action}", headers=APPROVER).status_code
            == 200
        )
    assert (
        client.put(
            "/v1/knowledge/industries/real_estate/active-release",
            json={"release_id": release_id, "reason": "first"},
            headers=APPROVER,
        ).status_code
        == 200
    )


# --- the lifecycle over HTTP -------------------------------------------------------------------


def test_the_whole_lifecycle_runs_over_http(client):
    release_id = _release(client)
    _activate(client, release_id)
    release = client.get(f"/v1/knowledge/releases/{release_id}", headers=APPROVER).json()
    assert release["status"] == "released"
    assert release["version"] == 1
    # Provenance travels with the release, because "how was this written?" is an audit question.
    assert release["prompt_version"] == "sector_questions.v1.ar"
    assert release["created_by"] == "knowledge@rasheed.sa"
    assert release["approved_by"] == "knowledge@rasheed.sa"


def test_a_repeated_submit_is_a_success_that_changed_nothing(client):
    """`changed=false` is not an error. The client is told which of the two happened rather than
    having to infer it from a status code."""
    release_id = _release(client)
    first = client.post(f"/v1/knowledge/releases/{release_id}/submit", headers=APPROVER).json()
    second = client.post(f"/v1/knowledge/releases/{release_id}/submit", headers=APPROVER).json()
    assert (first["changed"], first["event"]) == (True, "KnowledgeTemplateSubmitted")
    assert (second["changed"], second["event"]) == (False, None)


def test_rollback_is_one_call_and_the_history_answers_what_was_live(client):
    v1 = _release(client)
    _activate(client, v1)
    v2 = client.post(
        "/v1/knowledge/releases", json={"industry_slug": "real_estate"}, headers=APPROVER
    ).json()["data"]["release_id"]
    for action in ("submit", "approve", "publish"):
        client.post(f"/v1/knowledge/releases/{v2}/{action}", headers=APPROVER)

    client.put(
        "/v1/knowledge/industries/real_estate/active-release",
        json={"release_id": v2, "reason": "upgrade"},
        headers=APPROVER,
    )
    rolled_back = client.put(
        "/v1/knowledge/industries/real_estate/active-release",
        json={"release_id": v1, "reason": "bad question in v2"},
        headers=APPROVER,
    ).json()
    assert rolled_back["data"]["previous_release_id"] == v2

    history = client.get(
        "/v1/knowledge/industries/real_estate/activations", headers=APPROVER
    ).json()["activations"]
    assert [h["reason"] for h in history] == ["bad question in v2", "upgrade", "first"]
    # Rollback moved a pointer. No release was demoted to achieve it.
    releases = client.get("/v1/knowledge/releases", headers=APPROVER).json()["releases"]
    assert {r["status"] for r in releases} == {"released"}


def test_activating_a_draft_is_refused_by_the_database_not_by_a_python_guard(client):
    release_id = _release(client)
    response = client.put(
        "/v1/knowledge/industries/real_estate/active-release",
        json={"release_id": release_id},
        headers=APPROVER,
    )
    assert response.status_code == 409, "a rule the schema states is a conflict, not our bug"
    assert response.json()["error"]["message"] == (
        "the change violates active_templates_release_fk"
    )


# --- the two audiences -------------------------------------------------------------------------


def test_the_interview_never_receives_why_we_ask(client):
    """The reviewer-only text is absent from the customer's payload as a matter of TYPE, not of a
    flag someone remembered to set. Telling a customer "we ask this to see if you may broker at
    all" changes the answer they give."""
    release_id = _release(client)
    _activate(client, release_id)

    interview = client.get(
        "/v1/knowledge/industries/real_estate/active-release", headers=TENANT_A
    ).json()
    assert interview["questions"], "the interview must actually receive questions"
    assert all("why_we_ask" not in q for q in interview["questions"])
    assert "REVIEWER ONLY" not in client.get(
        "/v1/knowledge/industries/real_estate/active-release", headers=TENANT_A
    ).text

    review = client.get(f"/v1/knowledge/releases/{release_id}", headers=APPROVER).json()
    assert all(q["why_we_ask"] for q in review["questions"])


def test_an_industry_with_nothing_activated_serves_no_interview(client):
    """`404`, not an empty question list: an interview must never be handed knowledge nobody
    activated, and a near-miss is worse than nothing."""
    _release(client)  # generated, never published
    assert (
        client.get(
            "/v1/knowledge/industries/real_estate/active-release", headers=TENANT_A
        ).status_code
        == 404
    )


# --- authorization ------------------------------------------------------------------------------


def test_a_tenant_role_cannot_govern_knowledge(client):
    """One release serves every customer in a sector. A per-tenant role — even `approver`, which
    decides that tenant's own mission gates — cannot carry that blast radius."""
    release_id = _release(client)
    forbidden = [
        client.post("/v1/knowledge/releases", json={"industry_slug": "x"}, headers=TENANT_A),
        client.post(f"/v1/knowledge/releases/{release_id}/submit", headers=TENANT_A),
        client.post(f"/v1/knowledge/releases/{release_id}/approve", headers=TENANT_A),
        client.post(f"/v1/knowledge/releases/{release_id}/publish", headers=TENANT_A),
        client.post(f"/v1/knowledge/releases/{release_id}/reject", headers=TENANT_A),
        client.post("/v1/knowledge/industries/real_estate/retire", headers=TENANT_A),
        client.put(
            "/v1/knowledge/industries/real_estate/active-release",
            json={"release_id": release_id},
            headers=TENANT_A,
        ),
        client.get("/v1/knowledge/releases", headers=TENANT_A),
        client.get(f"/v1/knowledge/releases/{release_id}", headers=TENANT_A),
        client.get("/v1/knowledge/industries/real_estate/activations", headers=TENANT_A),
    ]
    assert [r.status_code for r in forbidden] == [403] * 10
    assert all(r.json()["error"]["code"] == "forbidden" for r in forbidden)


def test_an_unauthenticated_caller_reaches_nothing(client):
    assert client.get("/v1/knowledge/releases").status_code == 401
    assert client.get("/v1/knowledge/industries/real_estate/active-release").status_code == 401


def test_a_draft_is_unreviewed_knowledge_and_reading_one_needs_the_role(client):
    """The guard is on the read, not only on the write: an unreviewed question that reaches a
    customer's screen has already done its damage."""
    release_id = _release(client)
    assert client.get(f"/v1/knowledge/releases/{release_id}", headers=TENANT_B).status_code == 403


# --- assessments are tenant-scoped ---------------------------------------------------------------


def _assessment(client, release_id: str, headers: dict) -> str:
    response = client.post(
        "/v1/knowledge/assessments",
        json={"organization_id": "org1", "selected_release_ids": [release_id]},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["assessment_id"]


def test_an_assessment_runs_answers_then_freezes(client):
    release_id = _release(client)
    _activate(client, release_id)
    assessment_id = _assessment(client, release_id, TENANT_A)

    answers = {"answers": [{"release_id": release_id, "question_id": "q0", "answer": False}]}
    assert (
        client.post(
            f"/v1/knowledge/assessments/{assessment_id}/answers", json=answers, headers=TENANT_A
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/v1/knowledge/assessments/{assessment_id}/plan-context", headers=TENANT_A
        ).status_code
        == 409
    ), "an open assessment has no plan context — its answers can still change"

    assert (
        client.post(
            f"/v1/knowledge/assessments/{assessment_id}/complete", headers=TENANT_A
        ).status_code
        == 200
    )
    context = client.get(
        f"/v1/knowledge/assessments/{assessment_id}/plan-context", headers=TENANT_A
    ).json()
    assert context["selection"]["selected_release_ids"] == [release_id]
    assert context["sector_answers"][0]["canonical_text_ar"] == "هل لديكم رخصة فال؟"

    # Frozen: the answers a plan was built from cannot move afterwards.
    frozen = client.post(
        f"/v1/knowledge/assessments/{assessment_id}/answers", json=answers, headers=TENANT_A
    )
    assert frozen.status_code == 409
    assert "accepts no further writes" in frozen.json()["error"]["message"]
    assert "PL/pgSQL" not in frozen.text, "the trigger's message, not its stack frame"


def test_another_tenant_cannot_read_or_conclude_an_assessment(client):
    """`404`, not `403`: replying "that exists, but not for you" confirms the id, and an assessment
    id is a fact about another customer."""
    release_id = _release(client)
    _activate(client, release_id)
    assessment_id = _assessment(client, release_id, TENANT_A)

    assert (
        client.post(
            f"/v1/knowledge/assessments/{assessment_id}/complete", headers=TENANT_B
        ).json()["changed"]
        is False
    )
    assert (
        client.post(
            f"/v1/knowledge/assessments/{assessment_id}/complete", headers=TENANT_A
        ).json()["changed"]
        is True
    ), "tenant B's attempt must not have concluded it"
    assert (
        client.get(
            f"/v1/knowledge/assessments/{assessment_id}/plan-context", headers=TENANT_B
        ).status_code
        == 404
    )


def test_an_assessment_citing_no_release_is_refused_before_the_database(client):
    response = client.post(
        "/v1/knowledge/assessments",
        json={"organization_id": "org1", "selected_release_ids": []},
        headers=TENANT_A,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


# --- an unconfigured deployment -----------------------------------------------------------------


def test_a_deployment_with_no_governance_model_says_so_instead_of_inventing_questions(dsn):
    """The failure this refuses to repeat: the product once answered `"echo: <input>"` in place of
    a governance plan, and nothing said anything was wrong."""
    from governance_store import PostgresKnowledgeStore

    app = create_app(
        storage=Storage.MEMORY,
        knowledge_store_factory=lambda: PostgresKnowledgeStore(dsn=dsn),
        knowledge_question_generator=None,
    )
    with TestClient(app) as unconfigured:
        response = unconfigured.post(
            "/v1/knowledge/releases", json={"industry_slug": "real_estate"}, headers=APPROVER
        )
    assert response.status_code == 503
    assert "not configured" in response.json()["error"]["message"]
