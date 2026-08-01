"""The package's hard promise: the Mission Engine is pure domain. No database, no LLM SDK, no
tool registry, no framework, no messaging infrastructure — importing it pulls in nothing but
the stdlib and the pure V2 contract/event packages (ADR 0042 §3, §12.3)."""

import ast
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "mission_engine"

FORBIDDEN_MODULES = (
    "psycopg", "sqlalchemy", "pgvector", "numpy", "openai", "anthropic",
    "requests", "httpx", "socket", "threading", "asyncio", "multiprocessing",
    "kafka", "redis", "pika", "nats", "fastapi", "pydantic", "os", "sqlite3",
)

# Only the stdlib primitives the domain needs, plus the pure intra-platform packages it is
# allowed to depend on (its contracts and the event bus). Anything else is a design smell.
ALLOWED = {
    "dataclasses", "enum", "typing", "collections", "time", "uuid", "__future__",
    "mission_engine", "pipeline_contracts", "event_bus",
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


def test_source_has_zero_infrastructure_imports():
    for source in PACKAGE_DIR.rglob("*.py"):
        imported = _imported_modules(source)
        forbidden = imported & set(FORBIDDEN_MODULES)
        assert not forbidden, f"{source.name} imports infrastructure: {sorted(forbidden)}"
        assert imported <= ALLOWED, (
            f"{source.name} imports unexpected modules: {sorted(imported - ALLOWED)}"
        )


def test_import_loads_no_infrastructure():
    import mission_engine  # noqa: F401

    loaded = {name.split(".")[0] for name in sys.modules}
    assert not (loaded & {"psycopg", "sqlalchemy", "openai", "anthropic", "pgvector", "numpy"})


def test_public_surface_is_complete():
    import mission_engine as me

    for name in me.__all__:
        assert getattr(me, name, None) is not None, f"missing export: {name}"
