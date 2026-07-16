"""Backward-compatibility shim (Phase 12). The OpenAI adapter moved to
`generation_engine.providers.openai_provider` — all SDK knowledge lives there, behind the
shared `GenerationProvider` port, wrapped by `GenerationEngine` for retry/metrics/error
translation. This module contains no OpenAI knowledge; it only forwards the old import
path. Import from `generation_engine` in new code."""

from __future__ import annotations

from generation_engine import OpenAIGenerationProvider

__all__ = ["OpenAIGenerationProvider"]
