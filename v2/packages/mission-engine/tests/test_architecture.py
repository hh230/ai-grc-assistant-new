"""Architectural guardrails — the dependency directions this package must never lose
(ADR 0042 §3, §5, §12.3). These lock the structure by scanning imports, so a future change
that couples the domain to infrastructure or to a concrete adapter fails here, loudly."""

import ast
from pathlib import Path

from mission_engine import EchoExecutor, InMemoryMissionStore
from mission_engine.ports import ExecutionPort, MissionStorePort

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "mission_engine"


def _imports(module: str) -> set[str]:
    tree = ast.parse((PACKAGE_DIR / module).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
    return names


def test_engine_does_not_depend_on_reference_adapters():
    # [1] The engine is wired to the ports only — never to a concrete adapter. Swapping in the
    # real Pipeline-Tool executor / Postgres store must not touch the engine.
    assert "mission_engine.adapters" not in _imports("engine.py")


def test_aggregate_has_no_infrastructure_or_adapter_knowledge():
    # [2] The aggregate knows nothing of the bus, the store, the executor, the engine, or any
    # adapter — it is pure domain. It may depend only on pure siblings (contracts) and its own
    # domain modules.
    imported = _imports("mission.py")
    forbidden = {
        "mission_engine.adapters",
        "mission_engine.engine",
        "event_bus",
        "event_bus.bus",
        "event_bus.events",
    }
    leaked = imported & forbidden
    assert not leaked, f"aggregate leaked an infrastructure/adapter dependency: {sorted(leaked)}"


def test_ports_do_not_depend_on_adapters():
    # [3] Ports are the abstraction; adapters implement them, never the reverse.
    assert "mission_engine.adapters" not in _imports("ports.py")


def test_reference_adapters_satisfy_their_ports():
    # [3] The reference adapters structurally conform to the port Protocols — proof the seam is
    # real and the same seam the production adapters will implement.
    assert isinstance(EchoExecutor(), ExecutionPort)
    assert isinstance(InMemoryMissionStore(), MissionStorePort)
