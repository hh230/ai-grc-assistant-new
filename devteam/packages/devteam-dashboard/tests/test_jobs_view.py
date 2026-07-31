"""The /api/jobs route + jobs_view: the Jobs panel reads the snapshot, presentation-only."""

from __future__ import annotations

import json
from pathlib import Path

from devteam_dashboard import jobs_view
from devteam_dashboard.app import create_app
from devteam_dashboard.config import load_config
from devteam_dashboard.runtime_gateway import RuntimeGateway
from fastapi.testclient import TestClient

_FIXTURES = Path(__file__).parent / "fixtures"


def _no_gateway() -> RuntimeGateway:
    raise AssertionError("the /api/jobs route must not touch the runtime gateway")


def _client(tmp_path: Path, jobs_path: Path) -> TestClient:
    config = load_config(
        plist_path=_FIXTURES / "com.rasheed.devteam-monitor.plist",
        repo="o/r",
        repo_root=tmp_path,
        log_path=_FIXTURES / "monitor.err.log",
        actions_log_path=tmp_path / "actions.jsonl",
        journal_path=tmp_path / "runtime.jsonl",
        jobs_path=jobs_path,
    )
    return TestClient(create_app(config, gateway_factory=_no_gateway))


def test_read_jobs_absent_is_empty_not_error(tmp_path: Path) -> None:
    payload = jobs_view.read_jobs(tmp_path / "jobs.json")
    assert payload["snapshot_present"] is False
    assert payload["jobs"] == [] and payload["count"] == 0


def test_read_jobs_shapes_the_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "jobs.json"
    path.write_text(
        json.dumps(
            {
                "jobs": [
                    {"id": "ciso.tls", "name": "TLS", "owner_agent": "ciso", "health": "healthy",
                     "last_run": None, "created_missions": 0, "every_tick": False},
                ]
            }
        )
    )
    payload = jobs_view.read_jobs(path)
    assert payload["snapshot_present"] is True and payload["count"] == 1
    job = payload["jobs"][0]  # type: ignore[index]
    assert job["id"] == "ciso.tls"
    assert job["status"] == "pending"  # never run yet → pending


def test_api_jobs_route_serves_the_organization_jobs(tmp_path: Path) -> None:
    path = tmp_path / "jobs.json"
    path.write_text(
        json.dumps(
            {
                "jobs": [
                    {"id": "ceo.kpi_review", "name": "KPI Review", "owner_agent": "ceo",
                     "health": "healthy", "last_run": 1.0, "created_missions": 0},
                    {"id": "ciso.runtime_health", "name": "Runtime Health Monitor",
                     "owner_agent": "ciso", "health": "degraded", "last_run": 2.0,
                     "created_missions": 1, "execution_result": "action_taken"},
                ]
            }
        )
    )
    body = _client(tmp_path, path).get("/api/jobs").json()
    assert body["count"] == 2
    by_id = {j["id"]: j for j in body["jobs"]}
    assert by_id["ceo.kpi_review"]["status"] == "idle"  # ran, healthy → idle
    assert by_id["ciso.runtime_health"]["status"] == "acted"  # degraded/acted
