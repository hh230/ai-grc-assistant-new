"""Deployment reader — parse the LaunchAgent plist the Settings page mirrors, and confirm the live
worker probe fails soft (never raises) for a label that isn't loaded."""

from __future__ import annotations

from pathlib import Path

from devteam_dashboard import deployment

_PLIST = Path(__file__).parent / "fixtures" / "com.rasheed.devteam-monitor.plist"


def test_read_launch_agent_parses_program_arguments() -> None:
    info = deployment.read_launch_agent(_PLIST, label="fallback")
    assert info is not None
    assert info.label == "com.rasheed.devteam-monitor"
    assert info.repos == ["hh230/ai-grc-assistant-new"]
    assert info.repo_root == "/Users/x/AI GRC Assistant"
    assert info.poll_seconds == 60.0
    assert info.max_attempts == 3
    assert info.log_path == "/Users/x/Library/Logs/devteam-monitor/monitor.err.log"
    assert info.program[:3] == ["/opt/venv/bin/python", "-m", "devteam_runtime.monitor"]


def test_read_launch_agent_missing_plist_is_none(tmp_path: Path) -> None:
    assert deployment.read_launch_agent(tmp_path / "absent.plist", label="x") is None


def test_worker_status_unknown_label_fails_soft() -> None:
    status = deployment.worker_status("com.rasheed.nonexistent-probe-xyz")
    assert status.running is False
    assert status.present is False  # not loaded (or launchctl unavailable) — never raises
