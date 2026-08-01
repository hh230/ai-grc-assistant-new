"""Phase-12 extraction guarantees: the old public import paths keep working, the AI
Orchestrator contains no generation logic (no SDK knowledge, no retry), and the
GenerationEngine drops into the orchestrator's port unchanged.

The adapter's behavioural tests moved with the adapter to
`generation-engine/tests/test_openai_adapter.py`; the engine's retry/metrics/error tests
live in `generation-engine/tests/test_engine.py`."""

from __future__ import annotations

import ast
from pathlib import Path

from pipeline_contracts import GenerationProvider as ContractPort

from tests.conftest import FakeGenerationProvider

_PKG = Path(__file__).resolve().parents[1] / "ai_orchestrator"


# ── backward compatibility: the historic import paths still work ──────────────
def test_old_import_paths_still_resolve():
    from ai_orchestrator import GenerationProvider, OpenAIGenerationProvider
    from ai_orchestrator.openai_provider import OpenAIGenerationProvider as ViaModule
    from ai_orchestrator.provider import GenerationProvider as PortViaModule

    assert GenerationProvider is ContractPort          # the shared contract, not a copy
    assert PortViaModule is ContractPort
    assert OpenAIGenerationProvider is ViaModule

    from generation_engine import OpenAIGenerationProvider as Owner

    assert OpenAIGenerationProvider is Owner           # one adapter, re-exported — no duplicate


def test_fake_provider_still_satisfies_the_shared_port():
    assert isinstance(FakeGenerationProvider(), ContractPort)


def test_generation_engine_satisfies_the_port_the_orchestrator_expects():
    from generation_engine import GenerationEngine

    engine = GenerationEngine(FakeGenerationProvider())
    assert isinstance(engine, ContractPort)


# ── proof: no generation logic remains inside the AI Orchestrator ─────────────
def _imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def test_no_sdk_imports_anywhere_in_ai_orchestrator():
    forbidden = {"openai", "anthropic", "google", "ollama", "boto3", "botocore", "httpx", "requests"}
    for source in _PKG.rglob("*.py"):
        assert not (_imports_of(source) & forbidden), f"{source.name} imports an SDK"


def test_orchestrator_module_contains_no_retry_or_provider_logic():
    """Inspect actual code (identifiers), not docstrings: exactly one `generate` call site,
    and no retry/backoff/sleep/openai identifiers anywhere in the module's code."""
    import io
    import tokenize

    source = (_PKG / "orchestrator.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    generate_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute) and node.func.attr == "generate"
    ]
    assert len(generate_calls) == 1  # called once — no retry loop around it

    identifiers = {
        tok.string.lower()
        for tok in tokenize.generate_tokens(io.StringIO(source).readline)
        if tok.type == tokenize.NAME
    }
    assert not identifiers & {"openai", "retry", "retries", "backoff", "sleep"}


def test_shim_modules_carry_no_sdk_knowledge():
    for shim in ("provider.py", "openai_provider.py"):
        imported = _imports_of(_PKG / shim)
        assert imported <= {"pipeline_contracts", "generation_engine", "__future__"}, shim
