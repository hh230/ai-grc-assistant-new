"""Shared test fixtures — the QA member's suite runner as a fast, real-shaped double."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from devteam_agents import SuiteRunner
from devteam_ci import PackageResult
from devteam_organization import OrganizationRuntime


def _green() -> Sequence[PackageResult]:
    return (PackageResult("pkg-a", 0, "ok"), PackageResult("pkg-b", 0, "ok"))


def _red() -> Sequence[PackageResult]:
    return (PackageResult("pkg-a", 1, "1 failed"), PackageResult("pkg-b", 0, "ok"))


@pytest.fixture
def green_runner() -> SuiteRunner:
    """A QA runner reporting every suite green (fast; the real ``uv`` runner is wired in prod)."""
    return _green


@pytest.fixture
def red_runner() -> SuiteRunner:
    """A QA runner with one failing suite — exercises the shortfall propagation downstream."""
    return _red


@pytest.fixture
def runtime(green_runner: SuiteRunner) -> OrganizationRuntime:
    return OrganizationRuntime(green_runner)
