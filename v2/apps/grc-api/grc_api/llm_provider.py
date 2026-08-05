"""Which LLM writes the governance plan draft — selected by configuration, never hardcoded.

The `GenerationProvider` port already has four adapters (OpenAI, Claude, Gemini, Ollama) and the
business code never imports an SDK (CLAUDE.md §4). This module is only the *selector*: it turns
two environment variables into one provider, so swapping vendors is a deployment decision rather
than a code change.

    GRC_LLM_PROVIDER   openai (default) | claude | gemini | ollama
    GRC_LLM_MODEL      optional; each adapter has its own sensible default

Credentials are never read here. Every adapter resolves its own key from the environment through
its SDK (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, …), so no key passes through this codebase.

**Unconfigured is not the same as broken.** A deployment with no provider gets `None`, and the
caller falls back to the echo executor with a warning naming exactly what is missing — which is
what a local `pytest` run, a CI job, and `next build` all need. What must never happen is a
*silent* fallback: for a year the product answered `"echo: <input>"` in place of a governance
plan, and nothing said so.
"""

from __future__ import annotations

import logging
import os
from typing import Any

LOGGER = logging.getLogger(__name__)

PROVIDER_ENV_VAR = "GRC_LLM_PROVIDER"
MODEL_ENV_VAR = "GRC_LLM_MODEL"
DEFAULT_PROVIDER = "openai"

# The credential each adapter's SDK expects. Named here only so an unconfigured deployment can be
# told precisely which variable to set — the value is never read.
_CREDENTIAL_BY_PROVIDER = {
    "openai": "OPENAI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "ollama": "",  # runs locally; no credential
}


class UnknownProviderError(ValueError):
    """A configured provider name no provider adapter implements."""


def _construct(provider: str, model: str | None) -> Any:
    kwargs = {"model": model} if model else {}
    if provider == "openai":
        from generation_engine.providers.openai_provider import OpenAIGenerationProvider

        return OpenAIGenerationProvider(**kwargs)
    if provider == "claude":
        from generation_engine.providers.claude_provider import ClaudeGenerationProvider

        return ClaudeGenerationProvider(**kwargs)
    if provider == "gemini":
        from generation_engine.providers.gemini_provider import GeminiGenerationProvider

        return GeminiGenerationProvider(**kwargs)
    if provider == "ollama":
        from generation_engine.providers.ollama_provider import OllamaGenerationProvider

        return OllamaGenerationProvider(**kwargs)
    raise UnknownProviderError(
        f"{PROVIDER_ENV_VAR}={provider!r} names no adapter; expected one of "
        f"{sorted(_CREDENTIAL_BY_PROVIDER)}"
    )


def build_generation_provider(env: dict[str, str] | None = None) -> Any | None:
    """The configured provider, or `None` when this deployment has none.

    Raises only for a *misconfiguration* (an unknown provider name) — a name nobody can satisfy is
    a deployment mistake that should stop the boot, not degrade quietly.
    """
    source = os.environ if env is None else env
    provider = (source.get(PROVIDER_ENV_VAR) or DEFAULT_PROVIDER).strip().lower()
    model = (source.get(MODEL_ENV_VAR) or "").strip() or None

    if provider not in _CREDENTIAL_BY_PROVIDER:
        raise UnknownProviderError(
            f"{PROVIDER_ENV_VAR}={provider!r} names no adapter; expected one of "
            f"{sorted(_CREDENTIAL_BY_PROVIDER)}"
        )

    credential = _CREDENTIAL_BY_PROVIDER[provider]
    if credential and not (source.get(credential) or "").strip():
        LOGGER.warning(
            "llm_provider_unconfigured: %s=%s needs %s, which is not set — governance plan "
            "drafting will fall back to the echo executor and produce no real plan",
            PROVIDER_ENV_VAR,
            provider,
            credential,
        )
        return None

    try:
        built = _construct(provider, model)
    except UnknownProviderError:
        raise
    except Exception as exc:  # noqa: BLE001 — see below
        # A missing SDK extra, or an SDK that rejects its own credential resolution, is a
        # DEPLOYMENT problem. Degrading loudly beats crashing the boot: the rest of the API (the
        # whole Discovery interview, every read model) still serves, and the one capability that
        # needs an LLM says exactly why it cannot run. Narrow catches are the rule elsewhere; here
        # the whole point is that no vendor SDK's private exception type may take the host down.
        LOGGER.warning(
            "llm_provider_unavailable: %s=%s could not be constructed (%s: %s) — governance plan "
            "drafting will fall back to the echo executor",
            PROVIDER_ENV_VAR,
            provider,
            type(exc).__name__,
            exc,
        )
        return None

    LOGGER.info("llm_provider_selected: provider=%s model=%s", provider, model or "adapter default")
    return built
