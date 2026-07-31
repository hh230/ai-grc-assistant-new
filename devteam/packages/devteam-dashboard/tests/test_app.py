"""End-to-end through the FastAPI routes with an injected fake-backed gateway (no network): the read
endpoints shape the runtime/log/plist correctly, and an approve POST drives the real gateway to
COMPLETED. Proves the presentation layer only shapes responses — the decision stays in the runtime.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _fakes import FakeGit, FakeGitHub, seed_source
from devteam_dashboard.actions_log import ActionsLog
from devteam_dashboard.app import create_app
from devteam_dashboard.config import load_config
from devteam_dashboard.runtime_gateway import RuntimeGateway
from fastapi.testclient import TestClient
from mission_engine.adapters import InMemoryMissionStore

_FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    seed_source(tmp_path)
    config = load_config(
        plist_path=_FIXTURES / "com.rasheed.devteam-monitor.plist",
        repo="o/r",
        repo_root=tmp_path,
        log_path=_FIXTURES / "monitor.err.log",
        actions_log_path=tmp_path / "actions.jsonl",
    )
    gateway = RuntimeGateway(
        github=FakeGitHub(),  # type: ignore[arg-type]
        store=InMemoryMissionStore(),
        git_runner=FakeGit(),
        repo_root=tmp_path,
        repo="o/r",
        actions_log=ActionsLog(config.actions_log_path),
    )
    return TestClient(create_app(config, gateway_factory=lambda: gateway))


def test_index_serves_the_page(client: TestClient) -> None:
    res = client.get("/")
    assert res.status_code == 200
    assert "Operations Dashboard" in res.text


def test_missions_endpoint_lists_the_actionable_pr(client: TestClient) -> None:
    body = client.get("/api/missions").json()
    assert body["count"] == 1
    row = body["missions"][0]
    assert row["pr_number"] == 1
    assert row["ci_status"] == "failing"
    assert row["actionable"] is True


def test_mission_details_endpoint_rederives_the_diff(client: TestClient) -> None:
    body = client.get("/api/missions/1").json()
    assert body["state"] == "awaiting_approval"
    assert body["mission_id"]
    assert "@@" in body["diff"]


def test_approve_endpoint_lands_through_the_gateway(client: TestClient) -> None:
    mission_id = client.get("/api/missions/1").json()["mission_id"]
    res = client.post(f"/api/missions/{mission_id}/approve", params={"pr_number": 1})
    assert res.status_code == 200
    assert res.json()["status"] == "completed"


def test_approve_unknown_mission_is_409(client: TestClient) -> None:
    res = client.post("/api/missions/nope/approve")
    assert res.status_code == 409


def test_metrics_endpoint_reads_the_fixture_log(client: TestClient) -> None:
    body = client.get("/api/metrics", params={"window": "all"}).json()
    assert body["detected"] == 3
    assert body["opened_missions"] == 2
    assert body["declined"] == 1
    assert body["green_ci"] == 1


def test_settings_endpoint_mirrors_the_plist(client: TestClient) -> None:
    body = client.get("/api/settings").json()
    assert body["poll_seconds"] == 60.0
    assert body["max_attempts"] == 3
    assert body["github"]["ok"] is True


def test_logs_endpoint_returns_parsed_lines(client: TestClient) -> None:
    body = client.get("/api/logs", params={"tail": 50}).json()
    assert len(body["lines"]) > 0
    assert any("monitoring" in (line["message"] or "") for line in body["lines"])


def test_overview_endpoint_reports_open_pr_count(client: TestClient) -> None:
    body = client.get("/api/overview").json()
    assert body["open_pr_count"] == 1
    assert body["health"] in {"healthy", "degraded", "down"}
