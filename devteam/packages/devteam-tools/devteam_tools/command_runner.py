"""Running external commands for the consequential Git Tools — an injected seam, not a Port.

The Git Tools change repository state by shelling out to git/gh. To keep them deterministic and
testable, the actual execution is injected: a tool holds a CommandRunner and never calls subprocess
itself. There is one production realization (SubprocessCommandRunner); tests inject a fake. Per the
Port-Worthiness rule a test double is not a second production realization, so this is a plain
injected dependency, not a Port.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class CommandResult:
    """The outcome of one command: its exit code and captured output. ``ok`` is ``code == 0``."""

    code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.code == 0


class CommandRunner(Protocol):
    """Runs one external command in a working directory, optionally feeding stdin, and returns its
    result. It must NOT raise on a non-zero exit — the tool inspects ``CommandResult.ok`` and maps a
    failure to a fail-safe ``ToolStepResult`` (ADR 0042 §7)."""

    def run(self, args: Sequence[str], *, cwd: Path, stdin: str | None = None) -> CommandResult: ...


class SubprocessCommandRunner:
    """The production CommandRunner: runs the command via subprocess, capturing output. It never
    raises on a non-zero exit, and it turns a missing executable into a non-zero result rather than
    crashing the mission — so the Mission Engine can fail the step safely."""

    def run(self, args: Sequence[str], *, cwd: Path, stdin: str | None = None) -> CommandResult:
        try:
            completed = subprocess.run(
                list(args),
                cwd=str(cwd),
                input=stdin,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            return CommandResult(code=127, stdout="", stderr=str(exc))
        return CommandResult(
            code=completed.returncode, stdout=completed.stdout, stderr=completed.stderr
        )
