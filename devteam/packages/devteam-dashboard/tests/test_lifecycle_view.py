"""The /api/lifecycle route + lifecycle_view: the Lifecycle panel, presentation-only."""

from __future__ import annotations

import json
from pathlib import Path

from devteam_dashboard import lifecycle_view
from devteam_dashboard.app import create_app
from devteam_dashboard.config import load_config
from devteam_dashboard.runtime_gateway import RuntimeGateway
from fastapi.testclient import TestClient

_FIXTURES = Path(__file__).parent / "fixtures"


def _no_gateway() -> RuntimeGateway:
    raise AssertionError("the /api/lifecycle route must not touch the runtime gateway")


def _write(tmp_path: Path) -> Path:
    path = tmp_path / "lifecycle.json"
    path.write_text(
        json.dumps(
            {
                "problems": [
                    {
                        "correlation_ref": "operations:h:endpoint_down",
                        "mission_type": "operations",
                        "asset": "https://a",
                        "evidence_signature": "endpoint_down",
                        "severity": "high",
                        "state": "in_progress",
                    }
                ],
                "metrics": {
                    "active_problems": 1,
                    "mean_time_to_verify": None,
                    "mean_time_to_close": 158.9,
                    "retry_count": 0,
                    "escalation_count": 0,
                    "verification_failures": 0,
                },
            }
        )
    )
    return path


def test_read_lifecycle_shapes_problems_and_metrics(tmp_path: Path) -> None:
    payload = lifecycle_view.read_lifecycle(_write(tmp_path))
    assert payload["count"] == 1 and payload["snapshot_present"] is True
    problems = payload["problems"]
    assert isinstance(problems, list) and problems[0]["state"] == "in_progress"
    metrics = payload["metrics"]
    assert isinstance(metrics, dict)
    assert metrics["active_problems"] == 1 and metrics["mean_time_to_close"] == 158.9


def test_read_lifecycle_absent_is_empty(tmp_path: Path) -> None:
    payload = lifecycle_view.read_lifecycle(tmp_path / "none.json")
    assert payload["snapshot_present"] is False and payload["problems"] == []


def test_api_lifecycle_route(tmp_path: Path) -> None:
    lifecycle = _write(tmp_path)
    config = load_config(
        plist_path=_FIXTURES / "com.rasheed.devteam-monitor.plist",
        repo="o/r",
        repo_root=tmp_path,
        log_path=_FIXTURES / "monitor.err.log",
        actions_log_path=tmp_path / "actions.jsonl",
        journal_path=tmp_path / "runtime.jsonl",
        lifecycle_path=lifecycle,
    )
    body = TestClient(create_app(config, gateway_factory=_no_gateway)).get("/api/lifecycle").json()
    assert body["count"] == 1 and body["problems"][0]["mission_type"] == "operations"
