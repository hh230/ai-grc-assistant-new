"""Rasheed V2 Generation Engine (Phase 12).

Executes a provider-agnostic `LLMRequest` through the shared `GenerationProvider` port
(`pipeline_contracts.generation`), adding retry, execution timing, metrics, and a
provider-independent error boundary. Owns the provider adapters. Never chooses providers or
models, never routes, never modifies prompts, never validates answers.
"""

from generation_engine.engine import GenerationEngine
from generation_engine.models import GenerationMetrics, RetryPolicy
from generation_engine.providers.claude_provider import ClaudeGenerationProvider
from generation_engine.providers.gemini_provider import GeminiGenerationProvider
from generation_engine.providers.ollama_provider import OllamaGenerationProvider
from generation_engine.providers.openai_provider import OpenAIGenerationProvider

__all__ = [
    "GenerationEngine",
    "GenerationMetrics",
    "RetryPolicy",
    "OpenAIGenerationProvider",
    "ClaudeGenerationProvider",
    "GeminiGenerationProvider",
    "OllamaGenerationProvider",
]
