"""Rasheed V2 LLM Tools — a real, read-only GRC tool (`generate_text`) that turns a prompt into
generated text by **wrapping the frozen generation stack** (an injected `GenerationProvider` — the
`generation-engine` Claude/Gemini/Ollama/OpenAI adapters, or the `GenerationEngine` around one). Raw
generation for drafting/summarizing/rewriting; no SDK, no re-implementation, no Core change.
"""

from llm_tools.tool import GENERATE_TEXT_TOOL, LLMTool

__all__ = ["LLMTool", "GENERATE_TEXT_TOOL"]
