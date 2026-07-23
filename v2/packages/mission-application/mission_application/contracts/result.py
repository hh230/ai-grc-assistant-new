"""`CommandResult` — the stable, framework-free outcome every command returns (ADR 0054).

A command's `execute(...)` returns this on success; REST, CLI, workers, and tests all consume the
same shape without ever touching the Core. It says only what a caller needs to react: which mission,
its status *after* the command, and whether a human gate is now active. Failure is never encoded
here — it is a typed Application error the command raises (see `errors.py`).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandResult:
    mission_id: str
    status: str  # the mission's status AFTER the command (a MissionStatus value)
    approval_pending: bool = False
