"""Architectural guards — the properties that keep this package honest about its own size.

An audit asked whether this is the simplest design that delivers the capabilities. It was not: six
modules (~1,700 lines, 29% of the package) were reachable only from their own tests, which reads
as "dead code" to anyone auditing it and as "tested system behaviour" to anyone reading the suite.
Neither was true — they are investigation instruments, not gate code.

These tests make the distinction enforceable instead of remembered.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys


def _modules_under(root: pathlib.Path) -> set[str]:
    names = {
        str(path.relative_to(root)).replace("/", ".")[:-3].replace(".__init__", "")
        for path in root.rglob("*.py")
    }
    return {name for name in names if name and name != "__init__"}


_PROBE = """
import io, contextlib, json, sys
from devteam_harness.__main__ import main
with contextlib.redirect_stdout(io.StringIO()):
    main(["--team", "--count", "5", "--baseline", "/tmp/_arch_probe.json", "--update-baseline"])
print(json.dumps(sorted(
    m[len("devteam_harness."):] for m in sys.modules if m.startswith("devteam_harness.")
)), file=sys.stderr)
"""


def _run_the_gate() -> set[str]:
    """Execute the gate in a CLEAN process and report what Python actually loaded.

    A subprocess, not an in-process call: `sys.modules` is global, so any module imported by an
    earlier test in the same session would look like the gate had loaded it. That false reading is
    exactly what this test exists to catch, so the measurement must not be able to produce it.
    """
    result = subprocess.run(
        [sys.executable, "-c", _PROBE], capture_output=True, text=True, check=True
    )
    return set(json.loads(result.stderr.strip().splitlines()[-1]))


def test_every_non_investigation_module_is_actually_used_by_the_gate() -> None:
    """No dead weight in the gate. If a module is not `investigation/`, the gate must load it —
    otherwise it is code that ships, is tested, and does nothing.

    Measured by RUNNING the gate rather than by parsing imports: an AST walk got this wrong twice
    during the audit (it mishandled package re-exports), and a wrong measurement is worse than none.
    """
    root = pathlib.Path(__file__).resolve().parent.parent / "devteam_harness"
    loaded = _run_the_gate()
    unused = sorted(
        m for m in _modules_under(root) if not m.startswith("investigation") and m not in loaded
    )
    assert not unused, f"gate modules that the gate never loads: {unused}"


def test_the_gate_never_loads_an_investigation_instrument() -> None:
    """The boundary runs both ways. An instrument may be slow, may need an LLM or a live app, and
    must never be able to make the gate flake or block a release."""
    loaded = _run_the_gate()
    leaked = sorted(m for m in loaded if m.startswith("investigation"))
    assert not leaked, f"the gate pulled in investigation instruments: {leaked}"


def test_no_module_is_reachable_only_from_its_own_test() -> None:
    """The specific shape of the defect this audit found.

    A module whose only caller is its own test is either dead code or an instrument. Both are
    fine to have — what is not fine is being unable to tell which, which is exactly what a flat
    namespace produced.
    """
    root = pathlib.Path(__file__).resolve().parent.parent / "devteam_harness"
    loaded = _run_the_gate()
    for module in sorted(_modules_under(root)):
        if module.startswith("investigation"):
            continue  # declared an instrument — its status is explicit
        assert module in loaded, (
            f"{module} is neither loaded by the gate nor declared an instrument; "
            f"move it under investigation/ or delete it"
        )
