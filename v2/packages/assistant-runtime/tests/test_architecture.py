"""Test #5 — dependency direction. The Assistant consumes the Core; the Core never depends back on
the Assistant, and the Assistant depends only on `mission-engine` + `pipeline-contracts` (the
`MissionRuntime` is injected behind the `MissionDriver` port). Verified structurally by parsing each
source file's imports (AST — ignores docstrings/comments)."""

from __future__ import annotations

import ast
from pathlib import Path
from types import ModuleType


def _sources(module: ModuleType) -> list[Path]:
    assert module.__file__ is not None
    return list(Path(module.__file__).parent.rglob("*.py"))


def _imported_top_level(py: Path) -> set[str]:
    tree = ast.parse(py.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module.split(".")[0])
    return modules


def test_core_packages_do_not_import_the_assistant() -> None:
    """No reverse dependency: mission-engine / mission-store / mission-integration must not import
    `assistant_runtime` (the arrow points one way, Assistant → Core)."""
    import mission_engine
    import mission_integration
    import mission_store

    for package in (mission_engine, mission_store, mission_integration):
        for py in _sources(package):
            assert "assistant_runtime" not in _imported_top_level(py), (
                f"reverse dependency: {py} imports assistant_runtime"
            )


def test_assistant_source_depends_only_on_engine_and_contracts() -> None:
    """The Assistant runtime must not reach into the outer Core (mission-store, mission-integration,
    event-bus) or the driver (psycopg): it depends only on `mission_engine` and `pipeline_contracts`
    — the `MissionRuntime` is injected behind `MissionDriver`."""
    import assistant_runtime

    forbidden = {"mission_store", "mission_integration", "event_bus", "psycopg"}
    for py in _sources(assistant_runtime):
        leaked = _imported_top_level(py) & forbidden
        assert not leaked, (
            f"{py} imports {leaked} — the Assistant must depend only on mission_engine + "
            "pipeline_contracts (MissionRuntime is injected via the MissionDriver port)"
        )
