"""The bus is a *local* abstraction: no messaging infrastructure, no broker, no network."""

import ast
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "event_bus"

FORBIDDEN_MODULES = (
    "kafka", "confluent_kafka", "pika", "redis", "nats", "aio_pika",
    "psycopg", "sqlalchemy", "requests", "httpx", "socket", "threading",
    "asyncio", "multiprocessing", "openai", "anthropic",
)

ALLOWED = {"dataclasses", "enum", "typing", "collections", "time", "event_bus", "__future__"}


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def test_source_has_zero_messaging_infrastructure():
    for source in PACKAGE_DIR.rglob("*.py"):
        imported = _imported_modules(source)
        forbidden = imported & set(FORBIDDEN_MODULES)
        assert not forbidden, f"{source.name} imports infrastructure: {sorted(forbidden)}"
        assert imported <= ALLOWED, f"{source.name} imports unexpected modules: {sorted(imported)}"


def test_import_loads_no_messaging_infrastructure():
    import event_bus  # noqa: F401

    loaded = {name.split(".")[0] for name in sys.modules}
    assert not (loaded & {"kafka", "redis", "pika", "nats"})


def test_public_surface_is_complete():
    import event_bus as eb

    for name in eb.__all__:
        assert getattr(eb, name, None) is not None, f"missing export: {name}"
