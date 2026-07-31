"""Discover & run the standalone v2/v3 package test suites (ADR 0061, Phase 0.2 — close CI gap #1).

The v2/ and v3/ packages are standalone uv projects invisible to root CI: each has its own uv.lock
and .venv, so ``uv sync --all-packages`` at the root never touches them and their ~1,000 tests never
run (confirmed in v2/docs/ROADMAP.md). This module discovers every package with a ``pyproject.toml``
and a ``tests/`` directory under the configured roots and runs its suite with
``uv run --directory <pkg> pytest``. DB-gated tests skip cleanly without Postgres (ADR 0043).

Pure stdlib — it depends on nothing in the Core, so it runs in CI or locally wherever ``uv`` is on
PATH. Fail-open (ADR 0058): one package that errors or times out becomes a failed row, never an
aborted sweep, so the other suites still report.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

# The standalone package trees invisible to root CI (v2/apps composes v2/packages; v3 is separate;
# devteam is this system, kept self-covered).
DEFAULT_ROOTS: tuple[str, ...] = ("v2/packages", "v2/apps", "v3/packages", "devteam/packages")

# pytest exit codes we treat as "not a failure": 0 = all passed, 5 = no tests were collected.
_OK_RETURNCODES = frozenset({0, 5})


@dataclass(frozen=True)
class PackageResult:
    """The outcome of one package's suite. ``ok`` folds pass + no-tests-collected; ``returncode``
    and ``summary`` (pytest's last stdout line) preserve the detail for the CI log."""

    name: str
    returncode: int
    summary: str

    @property
    def ok(self) -> bool:
        return self.returncode in _OK_RETURNCODES


def discover_packages(repo_root: Path, roots: Iterable[str]) -> list[Path]:
    """Every standalone package under ``roots`` with both a ``pyproject.toml`` and a ``tests/`` dir,
    sorted by path. A missing root is skipped — not every tree exists in every checkout."""
    found: list[Path] = []
    for root in roots:
        base = repo_root / root
        if not base.is_dir():
            continue
        for entry in sorted(base.iterdir()):
            if (entry / "pyproject.toml").is_file() and (entry / "tests").is_dir():
                found.append(entry)
    return found


def classify(returncode: int, stdout: str) -> str:
    """The one-line summary for a finished run: pytest's last non-empty stdout line, or a fallback
    keyed on the exit code so an empty/aborted run is still legible in the CI log."""
    for line in reversed(stdout.splitlines()):
        if line.strip():
            return line.strip()
    if returncode == 5:
        return "no tests collected"
    return f"exit {returncode} (no output)"


def run_package(pkg: Path, *, timeout: float) -> PackageResult:
    """Run one package's suite via ``uv run --directory <pkg> pytest -q``. A timeout or a missing
    ``uv`` becomes a failed ``PackageResult``, never an exception — one bad package must not
    abort the whole sweep (fail-open, ADR 0058)."""
    try:
        proc = subprocess.run(
            ["uv", "run", "--directory", str(pkg), "pytest", "-q"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return PackageResult(pkg.name, returncode=124, summary=f"TIMEOUT after {timeout:.0f}s")
    except FileNotFoundError:
        return PackageResult(pkg.name, returncode=127, summary="`uv` not found on PATH")
    return PackageResult(pkg.name, proc.returncode, classify(proc.returncode, proc.stdout))


def run_all(packages: Sequence[Path], *, timeout: float) -> list[PackageResult]:
    """Run each package in turn. Sequential and simple — a parallel/matrix runner is a later
    optimization; correctness and legible output come first."""
    return [run_package(pkg, timeout=timeout) for pkg in packages]


def format_report(results: Sequence[PackageResult]) -> str:
    """A compact PASS/FAIL table for the CI log, plus a totals line and the failed names."""
    width = max((len(r.name) for r in results), default=4)
    lines = [f"  [{'PASS' if r.ok else 'FAIL'}] {r.name:<{width}}  {r.summary}" for r in results]
    failed = [r for r in results if not r.ok]
    total, n_failed = len(results), len(failed)
    lines.append("")
    lines.append(f"  {total} package(s): {total - n_failed} ok, {n_failed} failed")
    if failed:
        lines.append("  failed: " + ", ".join(r.name for r in failed))
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the standalone v2/v3 package test suites.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--root",
        action="append",
        dest="roots",
        default=None,
        help="package tree to scan (repeatable); defaults to the v2/v3/devteam trees",
    )
    parser.add_argument(
        "--select",
        action="append",
        dest="select",
        default=None,
        help="only run packages whose name contains this substring (repeatable)",
    )
    parser.add_argument("--timeout", type=float, default=900.0)
    args = parser.parse_args(argv)

    roots: tuple[str, ...] = tuple(args.roots) if args.roots else DEFAULT_ROOTS
    packages = discover_packages(args.repo_root, roots)
    if args.select:
        selects: list[str] = list(args.select)
        packages = [p for p in packages if any(s in p.name for s in selects)]

    if not packages:
        print("no standalone packages discovered", file=sys.stderr)
        return 0

    print(f"running {len(packages)} standalone package suite(s)...")
    results = run_all(packages, timeout=float(args.timeout))
    print(format_report(results))
    return 1 if any(not r.ok for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
