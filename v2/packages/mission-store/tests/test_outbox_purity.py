"""Slice 4's purity promise, mirroring Slice 1: the outbox's pure modules (codec, schema, errors,
publisher) carry no runtime database-driver import; only `outbox.py` touches psycopg, and lazily.
The package-wide "importing loads no driver" guarantee is already enforced by the frozen
`test_purity.py`; this focuses on the new pure modules and the outbox schema/migration parity.
"""

from __future__ import annotations

import ast
from pathlib import Path

from mission_store import outbox_schema

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "mission_store"
MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"

# Modules that must not import the driver at *runtime*. `outbox.py` is excluded on purpose: it
# imports psycopg lazily inside its methods (as store.py does), guarded by the frozen purity suite.
PURE_OUTBOX_MODULES = (
    "outbox_codec.py",
    "outbox_schema.py",
    "outbox_errors.py",
    "outbox_publisher.py",
)


def _runtime_imported_top_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in tree.body:  # module-level statements only (skips function-body & TYPE_CHECKING)
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def test_pure_outbox_modules_carry_no_runtime_driver_import() -> None:
    for name in PURE_OUTBOX_MODULES:
        imported = _runtime_imported_top_modules(PACKAGE_DIR / name)
        assert "psycopg" not in imported, f"{name} must not import a database driver at runtime"


def test_outbox_schema_matches_the_canonical_migration() -> None:
    """`outbox_schema.py` and `migrations/0002_outbox.sql` stay in lock-step (as Slice 1's parity
    test): the table DDL and every index the schema declares appear verbatim in the migration."""
    migration = (MIGRATIONS_DIR / "0002_outbox.sql").read_text(encoding="utf-8")
    assert outbox_schema.create_table_sql() in migration
    for ddl in outbox_schema.index_sql():
        assert ddl in migration
