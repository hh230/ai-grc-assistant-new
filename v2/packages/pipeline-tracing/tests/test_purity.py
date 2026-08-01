"""The package's one hard promise: tracing is a pure abstraction. No infrastructure, no
logging framework, no exporter — importing the whole package must pull in nothing beyond a
tiny stdlib surface."""

import ast
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "pipeline_tracing"

FORBIDDEN_MODULES = (
    "psycopg", "pgvector", "numpy", "openai", "anthropic", "sqlalchemy",
    "requests", "httpx", "logging", "opentelemetry", "prometheus_client",
    "os", "pathlib", "socket",
)

ALLOWED = {"dataclasses", "enum", "typing", "time", "uuid", "types",
           "pipeline_tracing", "__future__"}


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
        assert imported <= ALLOWED, f"{source.name} imports unexpected modules: {sorted(imported)}"


def test_import_loads_no_infrastructure():
    import pipeline_tracing  # noqa: F401

    loaded = {name.split(".")[0] for name in sys.modules}
    assert not (loaded & {"psycopg", "pgvector", "numpy", "openai", "opentelemetry"})


def test_public_surface_is_complete():
    import pipeline_tracing as pt

    for name in pt.__all__:
        assert getattr(pt, name, None) is not None, f"missing export: {name}"
