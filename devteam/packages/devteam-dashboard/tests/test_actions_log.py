"""The ActionsLog is the dashboard's own record of decisions IT performed (the only source for the
Approved/Rejected metrics). Assert append/read round-trips and the day window."""

from __future__ import annotations

from pathlib import Path

from devteam_dashboard.actions_log import ActionsLog


def test_record_then_count(tmp_path: Path) -> None:
    log = ActionsLog(tmp_path / "actions.jsonl")
    log.record("approved", mission_id="m-1", status="completed", pr_number=12)
    log.record("rejected", mission_id="m-2", status="cancelled", pr_number=13)
    log.record("approved", mission_id="m-3", status="completed")

    counts = log.counts()
    assert counts.approved == 2
    assert counts.rejected == 1


def test_records_round_trip(tmp_path: Path) -> None:
    log = ActionsLog(tmp_path / "actions.jsonl")
    log.record("approved", mission_id="m-1", status="completed", pr_number=12)
    records = log.records()
    assert len(records) == 1
    assert records[0].action == "approved"
    assert records[0].mission_id == "m-1"
    assert records[0].pr_number == 12
    assert records[0].day  # a YYYY-MM-DD stamp was written


def test_counts_windowed_by_since_today(tmp_path: Path) -> None:
    log = ActionsLog(tmp_path / "actions.jsonl")
    log.record("approved", mission_id="m-1", status="completed")
    assert log.counts(since=ActionsLog.today()).approved == 1
    assert log.counts(since="2999-01-01").approved == 0  # nothing that far in the future


def test_missing_and_corrupt_lines_are_not_fatal(tmp_path: Path) -> None:
    path = tmp_path / "actions.jsonl"
    assert ActionsLog(path).counts().approved == 0  # missing file
    path.write_text('not json\n{"action": "approved", "mission_id": "m-9", "day": "2026-07-29"}\n')
    counts = ActionsLog(path).counts()
    assert counts.approved == 1  # corrupt line skipped, valid line kept
