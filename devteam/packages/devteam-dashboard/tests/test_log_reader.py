"""The log reader is the dashboard's window onto what the daemon did — it parses the monitor's
real message shapes into the runbook's metrics, the per-PR daemon annotation, and the last poll."""

from __future__ import annotations

from pathlib import Path

from devteam_dashboard import log_reader

_FIXTURE = Path(__file__).parent / "fixtures" / "monitor.err.log"


def _entries() -> list[log_reader.LogEntry]:
    return log_reader.read_log(_FIXTURE)


def test_parse_line_structures_a_monitor_line() -> None:
    entry = log_reader.parse_line(
        "2026-07-29 00:49:45,715 INFO devteam.monitor: monitoring 2 open PR(s)"
    )
    assert entry.timestamp == "2026-07-29 00:49:45,715"
    assert entry.level == "INFO"
    assert entry.logger == "devteam.monitor"
    assert entry.message == "monitoring 2 open PR(s)"


def test_parse_line_keeps_a_nonconforming_line_as_raw() -> None:
    entry = log_reader.parse_line("<frozen runpy>:128: RuntimeWarning: ...")
    assert entry.timestamp is None
    assert entry.message is None
    assert "RuntimeWarning" in entry.raw


def test_compute_metrics_counts_the_runbook_signals() -> None:
    metrics = log_reader.compute_metrics(_entries())
    assert metrics.detected == 3  # three 'opened mission' lines
    assert metrics.opened_missions == 2  # two reached awaiting_approval
    assert metrics.declined == 1  # one ended '— cancelled'
    assert metrics.green_ci == 1
    assert metrics.exhausted == 1
    assert metrics.average_attempts == 1.33  # mean of [1, 1, 2]
    assert metrics.approved == 0 and metrics.rejected == 0  # not in the daemon log


def test_compute_metrics_windowed_by_since() -> None:
    assert log_reader.compute_metrics(_entries(), since="2026-07-30").detected == 0
    assert log_reader.compute_metrics(_entries(), since="2026-07-29").detected == 3


def test_daemon_prs_takes_the_latest_opening_per_pr() -> None:
    daemon = log_reader.daemon_prs(_entries())
    assert set(daemon) == {12, 13}
    assert daemon[12].attempt == 2  # PR 12's latest opening wins
    assert daemon[12].mission_id == "m-ccc"
    assert daemon[12].status == "awaiting_approval"
    assert daemon[13].attempt == 1 and daemon[13].status == "cancelled"


def test_last_poll_reads_the_most_recent_monitoring_line() -> None:
    timestamp, count = log_reader.last_poll(_entries())
    assert timestamp == "2026-07-29 00:51:45,720"
    assert count == 1


def test_read_log_filters_and_tails() -> None:
    assert len(log_reader.read_log(_FIXTURE, query="green")) == 1
    warnings = log_reader.read_log(_FIXTURE, level="WARNING")
    assert len(warnings) == 1 and "EXHAUSTED" in warnings[0].raw
    tail = log_reader.read_log(_FIXTURE, limit=1)
    assert len(tail) == 1 and "RuntimeWarning" in tail[0].raw


def test_read_log_missing_file_is_empty_not_an_error(tmp_path: Path) -> None:
    assert log_reader.read_log(tmp_path / "nope.log") == []
