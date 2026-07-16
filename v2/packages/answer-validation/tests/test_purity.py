"""Validation is pure: it depends only on the shared contracts and the stdlib — no
provider SDKs, no retrieval, no infrastructure. And it must never mutate the answer."""

import ast
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "answer_validation"

FORBIDDEN_MODULES = (
    "openai", "anthropic", "google", "ollama", "psycopg", "pgvector", "numpy",
    "sqlalchemy", "requests", "httpx", "retrieval_engine", "generation_engine",
)

ALLOWED = {"dataclasses", "enum", "typing", "re", "pipeline_contracts",
           "answer_validation", "__future__"}


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def test_source_imports_only_contracts_and_stdlib():
    for source in PACKAGE_DIR.rglob("*.py"):
        imported = _imported_modules(source)
        forbidden = imported & set(FORBIDDEN_MODULES)
        assert not forbidden, f"{source.name} imports infrastructure: {sorted(forbidden)}"
        assert imported <= ALLOWED, f"{source.name} imports unexpected modules: {sorted(imported)}"


def test_import_loads_no_provider_sdk():
    import answer_validation  # noqa: F401

    loaded = {name.split(".")[0] for name in sys.modules}
    assert not (loaded & {"openai", "anthropic", "ollama"})


def test_public_surface_is_complete():
    import answer_validation as av

    for name in av.__all__:
        assert getattr(av, name, None) is not None, f"missing export: {name}"
