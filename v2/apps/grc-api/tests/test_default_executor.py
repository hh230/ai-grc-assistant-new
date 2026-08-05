"""The production default executor — the seam that decided whether the product was real.

For as long as `create_app` defaulted to `EchoExecutor`, every mission step returned
`"echo: <input>"`, and the Governance Plan draft step produced a string the frontend rejected with
"The governance plan draft was not valid JSON." Nothing in the system said so: the fallback was
silent, and only an end-to-end attempt against a running app revealed it.

So these tests assert the two things that actually matter about the default:
  1. with a provider configured, the default is the REAL executor — not echo;
  2. without one, it degrades to echo *and says so*, because a silent degrade is what hid this.
"""

from __future__ import annotations

import logging

import sys

from grc_api.app import _default_executor

# `grc_api/__init__.py` does `from grc_api.app import app`, which rebinds the package attribute
# `grc_api.app` from the MODULE to the FastAPI instance. So neither `import grc_api.app as m` nor
# a "grc_api.app.x" monkeypatch target reaches the module. `sys.modules` always does.
app_module = sys.modules["grc_api.app"]
from grc_api.execution import GovernancePlanExecutor
from grc_api.llm_provider import (
    PROVIDER_ENV_VAR,
    UnknownProviderError,
    build_generation_provider,
)
from mission_engine import EchoExecutor

import pytest


class _Provider:
    """Stands in for a configured LLM; the executor only holds it."""


def _engine():
    from governance_discovery.engine import DiscoveryEngine
    from governance_discovery.pack import load_bundled_packs

    return DiscoveryEngine(load_bundled_packs())


# --- the selector -----------------------------------------------------------------------


def test_no_credential_yields_no_provider_and_names_the_missing_variable(caplog):
    with caplog.at_level(logging.WARNING):
        assert build_generation_provider({PROVIDER_ENV_VAR: "openai"}) is None
    assert "OPENAI_API_KEY" in caplog.text, "the operator must be told WHICH variable is missing"


def test_an_unknown_provider_is_a_misconfiguration_not_a_quiet_fallback():
    """A name nobody can satisfy should stop the boot, not degrade to echo — otherwise a typo in
    deployment config silently costs every customer their governance plan."""
    with pytest.raises(UnknownProviderError, match="names no adapter"):
        build_generation_provider({PROVIDER_ENV_VAR: "gpt5-turbo-max"})


def test_ollama_needs_no_credential(monkeypatch):
    """It runs locally, so absence of a key must not be read as 'unconfigured'."""
    import grc_api.llm_provider as module

    monkeypatch.setattr(module, "_construct", lambda provider, model: _Provider())
    assert build_generation_provider({PROVIDER_ENV_VAR: "ollama"}) is not None


# --- the default executor ---------------------------------------------------------------


def test_with_a_provider_the_default_is_the_real_executor(monkeypatch):
    """The whole point of the Wave 1 wiring: production runs tools, not echo."""
    monkeypatch.setattr(app_module, "build_generation_provider", lambda: _Provider())
    executor = _default_executor(_engine(), lambda: None)

    assert isinstance(executor, GovernancePlanExecutor)
    assert not isinstance(executor, EchoExecutor)


def test_without_a_provider_it_degrades_to_echo_and_says_so(monkeypatch, caplog):
    monkeypatch.setattr(app_module, "build_generation_provider", lambda: None)
    with caplog.at_level(logging.WARNING):
        executor = _default_executor(_engine(), lambda: None)

    assert isinstance(executor, EchoExecutor)
    assert "execution_degraded" in caplog.text
    assert "ECHO" in caplog.text


# --- store lifetime ---------------------------------------------------------------------


def test_the_executor_opens_and_closes_a_store_per_step():
    """ADR 0055: no durable store lives at app scope. `PostgresGovernanceStore` holds one
    connection for its lifetime, so a registry built once at startup would share a single
    connection across every concurrent request — and leak one per step if never closed."""
    opened, closed = [], []

    class _Store:
        def close(self):
            closed.append(self)

    def factory():
        store = _Store()
        opened.append(store)
        return store

    executor = GovernancePlanExecutor(
        store_factory=factory, discovery_engine=_engine(), generation_provider=_Provider()
    )

    class _Boom(Exception):
        pass

    class _Registry:
        def get(self, name):
            raise _Boom

    # Even when the step fails, the connection must come back.
    import grc_api.execution as execution

    original = execution.RegistryExecutor
    execution.RegistryExecutor = lambda registry: _Registry()  # type: ignore[assignment]
    try:
        with pytest.raises(Exception):
            executor.execute(object())  # type: ignore[arg-type]
    finally:
        execution.RegistryExecutor = original  # type: ignore[assignment]

    assert len(opened) == 1
    assert closed == opened, "a store opened for a failing step must still be closed"
