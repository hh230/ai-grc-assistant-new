"""Which LLM does what — selected by configuration, per ROLE, never hardcoded.

Two roles, deliberately separated because they are different jobs with different risk profiles:

    GOVERNANCE  — sector knowledge generation and governance plan drafting. **Claude only.**
    TECHNICAL   — documents, OCR, classification, embeddings, retrieval. OpenAI by default.

The split is not a preference to be respected; it is **enforced**. `GOVERNANCE` refuses to resolve
to a technical-tier provider even when the environment asks it to, because a deployment that
quietly swaps the model behind every customer's compliance advice is exactly the failure this
separation exists to prevent — and a convention nothing checks is a convention that erodes.

Resolution for a role, first match wins:

    1. GRC_<ROLE>_LLM_PROVIDER / GRC_<ROLE>_LLM_MODEL   — explicit, per role
    2. GRC_LLM_PROVIDER / GRC_LLM_MODEL                 — the general default (TECHNICAL only)
    3. the role's own default provider, and that vendor's model variable
       (ANTHROPIC_MODEL / OPENAI_MODEL), which is how the model is already configured today

Credentials are never read here. Every adapter resolves its own key through its SDK
(`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`), so no key passes through this codebase.

**Unconfigured is not the same as broken.** A role with no provider returns `None`, and the caller
degrades with a warning naming exactly what is missing — what a local `pytest`, a CI job and
`next build` all need. What must never happen is a *silent* fallback: the product once answered
`"echo: <input>"` in place of a governance plan and nothing said so.
"""

from __future__ import annotations

import enum
import logging
import os
from typing import Any

LOGGER = logging.getLogger(__name__)


class LLMRole(str, enum.Enum):
    """What the model is being asked to do. Roles, not vendors."""

    GOVERNANCE = "governance"
    TECHNICAL = "technical"


# Legacy/general variables. They configure TECHNICAL only — GOVERNANCE deliberately does not read
# them, so flipping the general provider can never silently move compliance advice to another
# vendor.
PROVIDER_ENV_VAR = "GRC_LLM_PROVIDER"
MODEL_ENV_VAR = "GRC_LLM_MODEL"

_ROLE_DEFAULT_PROVIDER: dict[LLMRole, str] = {
    LLMRole.GOVERNANCE: "claude",
    LLMRole.TECHNICAL: "openai",
}

# Providers each role is ALLOWED to use. Governance is restricted to Claude by decision, not by
# accident; if that ever changes it changes here, in review, with this comment as the argument.
_ROLE_ALLOWED_PROVIDERS: dict[LLMRole, frozenset[str]] = {
    LLMRole.GOVERNANCE: frozenset({"claude"}),
    LLMRole.TECHNICAL: frozenset({"openai", "claude", "gemini", "ollama"}),
}

# The credential each adapter's SDK expects, and the variable that already carries its model in
# this project's `.env`. Named here only so an unconfigured deployment can be told precisely what
# to set — the credential value is never read.
_CREDENTIAL_BY_PROVIDER = {
    "openai": "OPENAI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "ollama": "",  # runs locally; no credential
}
_VENDOR_MODEL_ENV_VAR = {
    "openai": "OPENAI_MODEL",
    "claude": "ANTHROPIC_MODEL",
    "gemini": "GEMINI_MODEL",
    "ollama": "OLLAMA_MODEL",
}


class UnknownProviderError(ValueError):
    """A configured provider name no adapter implements."""


class ProviderNotAllowedForRoleError(ValueError):
    """A provider was configured for a role that is not permitted to use it."""


def _role_env(role: LLMRole, suffix: str) -> str:
    return f"GRC_{role.value.upper()}_LLM_{suffix}"


def _construct(provider: str, model: str | None) -> Any:
    # The adapters' own defaults are not this project's defaults (the Claude adapter defaults to an
    # Opus model), so the model is always passed explicitly when configured.
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
        f"{provider!r} names no adapter; expected one of {sorted(_CREDENTIAL_BY_PROVIDER)}"
    )


def resolve(role: LLMRole, env: dict[str, str] | None = None) -> tuple[str, str | None]:
    """The `(provider, model)` a role resolves to. Raises on misconfiguration, never guesses."""
    source = os.environ if env is None else env

    provider = (source.get(_role_env(role, "PROVIDER")) or "").strip().lower()
    if not provider and role is not LLMRole.GOVERNANCE:
        provider = (source.get(PROVIDER_ENV_VAR) or "").strip().lower()
    if not provider:
        provider = _ROLE_DEFAULT_PROVIDER[role]

    if provider not in _CREDENTIAL_BY_PROVIDER:
        raise UnknownProviderError(
            f"{_role_env(role, 'PROVIDER')}={provider!r} names no adapter; expected one of "
            f"{sorted(_CREDENTIAL_BY_PROVIDER)}"
        )
    if provider not in _ROLE_ALLOWED_PROVIDERS[role]:
        raise ProviderNotAllowedForRoleError(
            f"the {role.value} role may not use {provider!r} — allowed: "
            f"{sorted(_ROLE_ALLOWED_PROVIDERS[role])}. Governance advice is restricted to a single "
            f"vendor on purpose; change the allow-list in review, not by configuration."
        )

    model = (source.get(_role_env(role, "MODEL")) or "").strip()
    if not model and role is not LLMRole.GOVERNANCE:
        model = (source.get(MODEL_ENV_VAR) or "").strip()
    if not model:
        model = (source.get(_VENDOR_MODEL_ENV_VAR[provider]) or "").strip()
    return provider, (model or None)


def build_generation_provider(
    role: LLMRole = LLMRole.TECHNICAL, env: dict[str, str] | None = None
) -> Any | None:
    """The provider for a role, or `None` when this deployment has not configured one.

    Raises only for a *misconfiguration* — an unknown provider, or one this role may not use. A
    name nobody can satisfy should stop the boot, not degrade quietly.
    """
    source = os.environ if env is None else env
    provider, model = resolve(role, source)

    credential = _CREDENTIAL_BY_PROVIDER[provider]
    if credential and not (source.get(credential) or "").strip():
        LOGGER.warning(
            "llm_provider_unconfigured: role=%s provider=%s needs %s, which is not set — this "
            "capability will not run",
            role.value,
            provider,
            credential,
        )
        return None

    try:
        built = _construct(provider, model)
    except (UnknownProviderError, ProviderNotAllowedForRoleError):
        raise
    except Exception as exc:  # noqa: BLE001 — see below
        # A missing SDK extra, or an SDK that rejects its own credential resolution, is a
        # DEPLOYMENT problem. Degrading loudly beats crashing the boot: the rest of the API still
        # serves, and the capability that needs this model says exactly why it cannot run. Narrow
        # catches are the rule elsewhere; here the point is that no vendor SDK's private exception
        # type may take the host down.
        LOGGER.warning(
            "llm_provider_unavailable: role=%s provider=%s could not be constructed (%s: %s)",
            role.value,
            provider,
            type(exc).__name__,
            exc,
        )
        return None

    LOGGER.info(
        "llm_provider_selected: role=%s provider=%s model=%s",
        role.value,
        provider,
        model or "adapter default",
    )
    return built
