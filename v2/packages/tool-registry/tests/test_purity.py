"""The Tool Registry is pure domain and — critically — knows NOTHING about execution: it
neither imports the Mission Engine, the pipeline, an agent runtime, nor any infrastructure
(ADR 0042 §5, §9). Importing it pulls in nothing but the stdlib and the pure contracts."""

import ast
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "tool_registry"

# The decoupling that matters most: the Registry must never reach toward execution. If any of
# these ever appears in an import, the "knows nothing about execution" invariant has broken.
FORBIDDEN_MODULES = (
    "mission_engine", "event_bus",
    "psycopg", "sqlalchemy", "pgvector", "numpy", "openai", "anthropic",
    "requests", "httpx", "socket", "threading", "asyncio", "multiprocessing",
    "kafka", "redis", "fastapi", "pydantic", "os", "sqlite3",
)

ALLOWED = {
    "dataclasses", "enum", "typing", "__future__",
    "tool_registry", "pipeline_contracts",
}


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def test_source_has_zero_forbidden_imports():
    for source in PACKAGE_DIR.rglob("*.py"):
        imported = _imported_modules(source)
        forbidden = imported & set(FORBIDDEN_MODULES)
        assert not forbidden, f"{source.name} imports the forbidden: {sorted(forbidden)}"
        assert imported <= ALLOWED, (
            f"{source.name} imports unexpected modules: {sorted(imported - ALLOWED)}"
        )


def test_import_loads_no_execution_layer_or_infrastructure():
    import tool_registry  # noqa: F401

    loaded = {name.split(".")[0] for name in sys.modules}
    assert not (loaded & {"mission_engine", "event_bus", "psycopg", "openai", "anthropic"})


def test_public_surface_is_complete():
    import tool_registry as tr

    for name in tr.__all__:
        assert getattr(tr, name, None) is not None, f"missing export: {name}"
