"""Unit tests for LearningCycleScheduler: pure interval-based cadence, timezone-aware inputs
required, never runs early, always due on a never-run worker."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from grc_knowledge_worker import LearningCycleScheduler

_NOW = datetime(2026, 1, 2, tzinfo=timezone.utc)


def test_rejects_a_non_positive_interval() -> None:
    with pytest.raises(ValueError, match="positive duration"):
        LearningCycleScheduler(interval=timedelta(0))


def test_is_due_when_never_run_before() -> None:
    scheduler = LearningCycleScheduler(interval=timedelta(days=1))

    assert scheduler.is_due(last_run_at=None, now=_NOW) is True


def test_is_not_due_before_the_interval_elapses() -> None:
    scheduler = LearningCycleScheduler(interval=timedelta(days=1))
    last_run_at = _NOW - timedelta(hours=1)

    assert scheduler.is_due(last_run_at=last_run_at, now=_NOW) is False


def test_is_due_exactly_at_the_interval_boundary() -> None:
    scheduler = LearningCycleScheduler(interval=timedelta(days=1))
    last_run_at = _NOW - timedelta(days=1)

    assert scheduler.is_due(last_run_at=last_run_at, now=_NOW) is True


def test_is_due_after_the_interval_elapses() -> None:
    scheduler = LearningCycleScheduler(interval=timedelta(days=1))
    last_run_at = _NOW - timedelta(days=2)

    assert scheduler.is_due(last_run_at=last_run_at, now=_NOW) is True


def test_is_due_rejects_a_naive_now() -> None:
    scheduler = LearningCycleScheduler(interval=timedelta(days=1))

    with pytest.raises(ValueError, match="timezone-aware"):
        scheduler.is_due(last_run_at=None, now=datetime(2026, 1, 2))


def test_is_due_rejects_a_naive_last_run_at() -> None:
    scheduler = LearningCycleScheduler(interval=timedelta(days=1))

    with pytest.raises(ValueError, match="timezone-aware"):
        scheduler.is_due(last_run_at=datetime(2026, 1, 1), now=_NOW)


def test_next_run_at_is_none_when_never_run_before() -> None:
    scheduler = LearningCycleScheduler(interval=timedelta(days=1))

    assert scheduler.next_run_at(last_run_at=None) is None


def test_next_run_at_adds_the_interval() -> None:
    scheduler = LearningCycleScheduler(interval=timedelta(days=1))
    last_run_at = _NOW

    assert scheduler.next_run_at(last_run_at=last_run_at) == _NOW + timedelta(days=1)
