"""The store's promise: the psycopg driver is loaded *lazily*, so the package — and its pure codec
— import with no database driver present, and the codec/config/errors/schema modules carry no
runtime driver import at all. This keeps aggregate↔row translation unit-testable without a DB and
mirrors the Retrieval Engine's pgvector adapter (driver imported inside the methods)."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "mission_store"

# Modules that must not import the driver at *runtime*. `store.py` is intentionally excluded: it
# imports psycopg, but only lazily inside its methods (proved by the subprocess test below). A
# `TYPE_CHECKING`-guarded import (schema.py annotates a `psycopg.Connection`) is type-only and never
# executes, so the check below inspects module-level statements only — which excludes both
# function-body and `if TYPE_CHECKING:` imports.
PURE_MODULES = ("codec.py", "config.py", "errors.py", "schema.py")


def _runtime_imported_top_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in tree.body:  # module-level statements only
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def test_pure_modules_carry_no_runtime_driver_import() -> None:
    for name in PURE_MODULES:
        imported = _runtime_imported_top_modules(PACKAGE_DIR / name)
        assert "psycopg" not in imported, f"{name} must not import a database driver at runtime"


def test_importing_the_package_loads_no_driver() -> None:
    """In a clean interpreter, importing `mission_store` must not pull in psycopg — even though it
    is installed for the dev suite. Run in a subprocess so other tests that import the driver
    cannot pollute this process's `sys.modules`."""
    code = "import sys, mission_store; assert 'psycopg' not in sys.modules, sorted(sys.modules)"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
