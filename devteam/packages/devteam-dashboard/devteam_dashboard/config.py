"""Resolve the dashboard's settings — WHAT to observe and WHERE the daemon's artifacts are — from
the live LaunchAgent plist first, then explicit overrides, then sensible fallbacks.

Owner principle (see the monitor runbook): never hardcode the project path. ``repo_root`` comes from
the plist, else ``git rev-parse --show-toplevel``, else the cwd. Likewise the repo and log path come
from the plist so the dashboard reflects the *actual* deployment rather than a typed literal.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from devteam_observability import JOURNAL_FILENAME

from devteam_dashboard.deployment import LaunchAgentInfo, read_launch_agent

DEFAULT_LABEL = "com.rasheed.devteam-monitor"
DEFAULT_PLIST = Path.home() / "Library" / "LaunchAgents" / f"{DEFAULT_LABEL}.plist"
DEFAULT_LOG = Path.home() / "Library" / "Logs" / "devteam-monitor" / "monitor.err.log"
_ACTIONS_FILE = "dashboard-actions.jsonl"
# The runtime journal the monitor writes and this dashboard reads — the same file, in the monitor's
# log directory. The filename is imported (not re-typed) so the two never drift apart.
_JOURNAL_FILE = JOURNAL_FILENAME
# The AI Organization Jobs + Connectors snapshots the organization service writes, same log dir.
_JOBS_FILE = "jobs.json"
_CONNECTORS_FILE = "connectors.json"
_LIFECYCLE_FILE = "lifecycle.json"
_OPERATIONS_FILE = "operations.json"


@dataclass(frozen=True)
class DashboardConfig:
    """Everything the dashboard needs to run, fully resolved. ``poll_seconds``/``max_attempts``/
    ``repos`` are read-only mirrors of the deployment for the Settings page; ``worker_status`` is a
    live call the app makes separately."""

    label: str
    plist_path: Path
    repo: str  # the primary repo the dashboard observes (first monitored repo); "" if unconfigured
    repos: list[str]  # every repo the LaunchAgent watches (Settings display)
    repo_root: Path
    log_path: Path
    actions_log_path: Path
    journal_path: Path  # the runtime observability journal the monitor writes, this dashboard reads
    jobs_path: Path  # the AI Organization Jobs snapshot the organization service writes
    connectors_path: Path  # the AI Organization Connectors snapshot the service writes
    lifecycle_path: Path  # the Mission Lifecycle snapshot (ledger + metrics) the service writes
    operations_path: Path  # the single OperationsSnapshot the daemon projects (S6)
    host: str = "127.0.0.1"
    port: int = 8787
    poll_seconds: float | None = None
    max_attempts: int | None = None
    launch_agent: LaunchAgentInfo | None = field(default=None, repr=False)


def load_config(
    *,
    plist_path: Path | str | None = None,
    label: str | None = None,
    repo: str | None = None,
    repo_root: Path | str | None = None,
    log_path: Path | str | None = None,
    actions_log_path: Path | str | None = None,
    journal_path: Path | str | None = None,
    jobs_path: Path | str | None = None,
    connectors_path: Path | str | None = None,
    lifecycle_path: Path | str | None = None,
    operations_path: Path | str | None = None,
    host: str = "127.0.0.1",
    port: int = 8787,
) -> DashboardConfig:
    """Build the config from the live plist + overrides + fallbacks. Any argument left ``None`` is
    filled from the plist, then a safe default — so the deployed machine needs no arguments."""
    resolved_label = label or DEFAULT_LABEL
    resolved_plist = Path(plist_path) if plist_path is not None else DEFAULT_PLIST
    info = read_launch_agent(resolved_plist, label=resolved_label)

    repos = [repo] if repo else (list(info.repos) if info else [])
    primary = repos[0] if repos else ""

    resolved_root = _first_path(
        repo_root,
        info.repo_root if info else None,
        _git_root(),
        Path.cwd(),
    )
    resolved_log = _first_path(
        log_path,
        info.log_path if info else None,
        DEFAULT_LOG,
    )
    resolved_actions = (
        Path(actions_log_path)
        if actions_log_path is not None
        else resolved_log.parent / _ACTIONS_FILE
    )
    resolved_journal = (
        Path(journal_path)
        if journal_path is not None
        else resolved_log.parent / _JOURNAL_FILE
    )
    resolved_jobs = (
        Path(jobs_path) if jobs_path is not None else resolved_log.parent / _JOBS_FILE
    )
    resolved_connectors = (
        Path(connectors_path)
        if connectors_path is not None
        else resolved_log.parent / _CONNECTORS_FILE
    )
    resolved_lifecycle = (
        Path(lifecycle_path)
        if lifecycle_path is not None
        else resolved_log.parent / _LIFECYCLE_FILE
    )
    resolved_operations = (
        Path(operations_path)
        if operations_path is not None
        else resolved_log.parent / _OPERATIONS_FILE
    )
    return DashboardConfig(
        label=resolved_label,
        plist_path=resolved_plist,
        repo=primary,
        repos=repos,
        repo_root=resolved_root,
        log_path=resolved_log,
        actions_log_path=resolved_actions,
        journal_path=resolved_journal,
        jobs_path=resolved_jobs,
        connectors_path=resolved_connectors,
        lifecycle_path=resolved_lifecycle,
        operations_path=resolved_operations,
        host=host,
        port=port,
        poll_seconds=info.poll_seconds if info else None,
        max_attempts=info.max_attempts if info else None,
        launch_agent=info,
    )


def _first_path(*candidates: Path | str | None) -> Path:
    for candidate in candidates:
        if candidate:
            return Path(candidate)
    return Path.cwd()


def _git_root() -> Path | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return None
    root = completed.stdout.strip()
    return Path(root) if completed.returncode == 0 and root else None
