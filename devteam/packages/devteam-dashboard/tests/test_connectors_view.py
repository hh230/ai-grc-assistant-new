"""The /api/connectors route + connectors_view: the Connectors panel, presentation-only."""

from __future__ import annotations

import json
from pathlib import Path

from devteam_dashboard import connectors_view
from devteam_dashboard.app import create_app
from devteam_dashboard.config import load_config
from devteam_dashboard.runtime_gateway import RuntimeGateway
from fastapi.testclient import TestClient

_FIXTURES = Path(__file__).parent / "fixtures"


def _no_gateway() -> RuntimeGateway:
    raise AssertionError("the /api/connectors route must not touch the runtime gateway")


def _write(tmp_path: Path) -> tuple[Path, Path]:
    connectors = tmp_path / "connectors.json"
    connectors.write_text(
        json.dumps(
            {
                "connectors": [
                    {"id": "website", "name": "Website", "type": "website", "owner": "ciso",
                     "health": "unavailable", "status": "unavailable", "latency_ms": None},
                    {"id": "runtime", "name": "Runtime", "type": "runtime", "owner": "supervisor",
                     "health": "healthy", "status": "ok", "latency_ms": 12.0},
                ]
            }
        )
    )
    jobs = tmp_path / "jobs.json"
    jobs.write_text(
        json.dumps(
            {
                "jobs": [
                    {"id": "ciso.website_health", "name": "Website Health Monitor",
                     "connector_id": "website"},
                    {"id": "ceo.kpi_review", "name": "KPI Review", "connector_id": "runtime"},
                    {"id": "supervisor.supervise", "name": "Supervisor", "connector_id": "runtime"},
                ]
            }
        )
    )
    return connectors, jobs


def _client(tmp_path: Path, connectors: Path, jobs: Path) -> TestClient:
    config = load_config(
        plist_path=_FIXTURES / "com.rasheed.devteam-monitor.plist",
        repo="o/r",
        repo_root=tmp_path,
        log_path=_FIXTURES / "monitor.err.log",
        actions_log_path=tmp_path / "actions.jsonl",
        journal_path=tmp_path / "runtime.jsonl",
        jobs_path=jobs,
        connectors_path=connectors,
    )
    return TestClient(create_app(config, gateway_factory=_no_gateway))


def test_read_connectors_joins_owner_jobs(tmp_path: Path) -> None:
    connectors, jobs = _write(tmp_path)
    payload = connectors_view.read_connectors(connectors, jobs)
    assert payload["count"] == 2
    by_id = {c["id"]: c for c in payload["connectors"]}  # type: ignore[index,union-attr]
    assert by_id["website"]["owner_jobs"] == ["Website Health Monitor"]
    assert sorted(by_id["runtime"]["owner_jobs"]) == ["KPI Review", "Supervisor"]  # two consumers


def test_read_connectors_absent_is_empty(tmp_path: Path) -> None:
    payload = connectors_view.read_connectors(tmp_path / "none.json", tmp_path / "jobs.json")
    assert payload["snapshot_present"] is False and payload["connectors"] == []


def test_api_connectors_route(tmp_path: Path) -> None:
    connectors, jobs = _write(tmp_path)
    body = _client(tmp_path, connectors, jobs).get("/api/connectors").json()
    assert body["count"] == 2
    by_id = {c["id"]: c for c in body["connectors"]}
    assert by_id["runtime"]["health"] == "healthy" and by_id["website"]["status"] == "unavailable"
