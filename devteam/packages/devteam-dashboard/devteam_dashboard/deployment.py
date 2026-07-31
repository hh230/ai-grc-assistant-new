"""Read-only view of how the ContinuousMonitor is DEPLOYED on this machine: the LaunchAgent plist
(what it watches, how often) and its live ``launchctl`` state (is the worker running).

The plist is not in the repo — it was created out of band (see the monitor runbook), so the
dashboard reads the *live* file at runtime rather than importing any config. Everything here is pure
OS/plist inspection: no runtime imports, no writes, and every call fails soft (a missing plist or an
unavailable ``launchctl`` returns 'unknown', never an exception) so the dashboard degrades cleanly.
"""

from __future__ import annotations

import os
import plistlib
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_STATE_RE = re.compile(r"state\s*=\s*(\w+)")
_PID_RE = re.compile(r"pid\s*=\s*(\d+)")


@dataclass(frozen=True)
class LaunchAgentInfo:
    """What the monitor's LaunchAgent plist declares — the Settings page's read-only source."""

    label: str
    repos: list[str] = field(default_factory=list)
    repo_root: str | None = None
    poll_seconds: float | None = None
    max_attempts: int | None = None
    log_path: str | None = None  # StandardErrorPath — the monitor logs to stderr
    out_path: str | None = None
    program: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WorkerStatus:
    """The monitor's live state from ``launchctl``. ``present`` is whether the service is loaded at
    all; ``running`` is whether it is up now. ``state`` is 'unknown' when launchctl can't tell."""

    label: str
    present: bool
    running: bool
    state: str
    pid: int | None = None


def read_launch_agent(plist_path: Path | str, *, label: str) -> LaunchAgentInfo | None:
    """Parse the LaunchAgent plist into the config the dashboard displays. Returns ``None`` if the
    plist is absent or unreadable (the monitor may be run some other way)."""
    try:
        with Path(plist_path).open("rb") as handle:
            data = plistlib.load(handle)
    except (FileNotFoundError, OSError, plistlib.InvalidFileException):
        return None
    if not isinstance(data, dict):
        return None
    program = [str(arg) for arg in data.get("ProgramArguments", []) if isinstance(arg, str)]
    return LaunchAgentInfo(
        label=str(data.get("Label", label)),
        repos=_flag_values(program, "--repo"),
        repo_root=_flag_value(program, "--repo-root"),
        poll_seconds=_as_float(_flag_value(program, "--poll-seconds")),
        max_attempts=_as_int(_flag_value(program, "--max-attempts")),
        log_path=_as_str(data.get("StandardErrorPath")),
        out_path=_as_str(data.get("StandardOutPath")),
        program=program,
    )


def worker_status(label: str, *, uid: int | None = None) -> WorkerStatus:
    """The monitor's live state via ``launchctl print gui/<uid>/<label>`` (read-only). A non-zero
    exit means the service isn't loaded; any failure to run launchctl reads as 'unknown'."""
    target = f"gui/{uid if uid is not None else os.getuid()}/{label}"
    try:
        completed = subprocess.run(
            ["launchctl", "print", target],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return WorkerStatus(label=label, present=False, running=False, state="unknown")
    if completed.returncode != 0:
        # launchctl returns non-zero when the label isn't bootstrapped in this domain.
        return WorkerStatus(label=label, present=False, running=False, state="not loaded")
    state_match = _STATE_RE.search(completed.stdout)
    pid_match = _PID_RE.search(completed.stdout)
    state = state_match.group(1) if state_match is not None else "unknown"
    return WorkerStatus(
        label=label,
        present=True,
        running=(state == "running"),
        state=state,
        pid=int(pid_match.group(1)) if pid_match is not None else None,
    )


def _flag_values(args: list[str], name: str) -> list[str]:
    return [args[i + 1] for i, tok in enumerate(args) if tok == name and i + 1 < len(args)]


def _flag_value(args: list[str], name: str) -> str | None:
    values = _flag_values(args, name)
    return values[0] if values else None


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _as_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _as_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
