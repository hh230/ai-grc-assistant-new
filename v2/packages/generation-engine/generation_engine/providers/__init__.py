"""Provider adapters for the `GenerationProvider` port. Each adapter is the only module
allowed to know its SDK exists, and translates SDK errors into the shared domain errors.

The Generation Engine does not choose, route, or compare these — it executes whichever one is
wired in. Each SDK is an optional extra; importing this package pulls in no SDK."""

from generation_engine.providers.claude_provider import ClaudeGenerationProvider
from generation_engine.providers.gemini_provider import GeminiGenerationProvider
from generation_engine.providers.ollama_provider import OllamaGenerationProvider
from generation_engine.providers.openai_provider import OpenAIGenerationProvider

__all__ = [
    "OpenAIGenerationProvider",
    "ClaudeGenerationProvider",
    "GeminiGenerationProvider",
    "OllamaGenerationProvider",
]
