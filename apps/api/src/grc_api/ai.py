"""AI wiring — building the Orchestrator and its agent roster for the API runtime.

The Orchestrator is the brain (CLAUDE.md §7): it owns routing, the decision trail, and the human
gate. Agents reason through the provider-agnostic ``ChatModel``; which provider backs it is a
composition-root decision (ADL-0009: OpenAI is approved). The default is a deterministic **fake**
provider so the API runs with no egress and no key (CLAUDE.md §22).

Scope note: this binding wires the five LLM reasoning agents (Compliance, Risk, Report, Policy,
Workflow). The **Knowledge** (RAG-grounding) agent is intentionally not wired here because it
depends on the knowledge store, which is deferred pending ADL-0008. The orchestrator's
governance — deterministic routing, decision trail, and human gates on consequential output — is
fully exercised regardless.
"""

from __future__ import annotations

from grc_agents import (
    ComplianceAgent,
    Orchestrator,
    PolicyAgent,
    ReportAgent,
    RiskAgent,
    WorkflowAgent,
)
from grc_llm import ChatModel, EmbeddingModel, FakeChatModel, FakeEmbeddingModel
from grc_llm.settings import OpenAISettings

from .observability import get_logger
from .settings import Settings

_logger = get_logger("grc_api.ai")

# A deterministic, clearly-labelled fake response (valid agent JSON: output + confidence).
_FAKE_RESPONSE = (
    '{"output": "[fake-llm] deterministic placeholder reasoning. '
    'Set LLM_PROVIDER=openai with OPENAI_API_KEY for real agent reasoning.", '
    '"confidence": 0.5}'
)


def build_chat_model(settings: Settings) -> ChatModel:
    """Select the chat model from configuration. Fails fast if OpenAI is selected without a key."""
    if settings.llm_provider == "openai":
        openai_settings = OpenAISettings.from_env()  # raises if OPENAI_API_KEY is absent
        from grc_llm import OpenAIChatModel

        _logger.info("llm_provider_selected", extra={"provider": "openai"})
        return OpenAIChatModel(openai_settings)
    _logger.info("llm_provider_selected", extra={"provider": "fake"})
    return FakeChatModel(default_response=_FAKE_RESPONSE)


def build_embedding_model(settings: Settings) -> EmbeddingModel:
    """Select the embedding model from the same ``llm_provider`` switch ``build_chat_model``
    uses (Knowledge Intelligence KI-P7, ADR-0031: regulation-section embeddings generated only
    after admin approval). Fails fast if OpenAI is selected without a key.

    The fake model's dimension is pinned to 3072 to match `regulation_sections.embedding`'s
    fixed `vector(3072)` column width (OpenAI text-embedding-3-large) — the same dimension the
    real provider produces, so tests exercise the real write path end to end.
    """
    if settings.llm_provider == "openai":
        openai_settings = OpenAISettings.from_env()  # raises if OPENAI_API_KEY is absent
        from grc_llm import OpenAIEmbeddingModel

        _logger.info("embedding_provider_selected", extra={"provider": "openai"})
        return OpenAIEmbeddingModel(openai_settings)
    _logger.info("embedding_provider_selected", extra={"provider": "fake"})
    return FakeEmbeddingModel(dimension=3072)


def build_orchestrator(settings: Settings) -> Orchestrator:
    """Construct the Orchestrator with the governed LLM reasoning roster."""
    chat = build_chat_model(settings)
    return Orchestrator(
        [
            ComplianceAgent(chat),
            RiskAgent(chat),
            ReportAgent(chat),
            PolicyAgent(chat),
            WorkflowAgent(chat),
        ]
    )
