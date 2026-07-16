"""The contract every embedding backend implements. A provider does exactly one thing:
turn a batch of texts into a batch of vectors, in order. Everything provider-agnostic —
batching, retry, checkpointing, the skip/regenerate decision, manifest accounting — lives
in `embedding/engine.py`, never inside a provider.

Adding Voyage AI, Gemini, a local BGE/Nomic model, or Ollama means implementing this one
method in a new module under `providers/` and registering it in `registry.py`. Nothing
else in the engine, the stage, or the pipeline changes, and no business logic ever imports
a vendor SDK directly (CLAUDE.md §4/§5)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class EmbeddingProvider(Protocol):
    name: str  # stable provider id, e.g. "openai", "local"
    model: str  # model identity used in the skip decision + recorded on every embedding
    dimension: int  # length of every vector this provider returns

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order. Length of the result
        must equal `len(texts)`, and every vector must have length `self.dimension`.
        May raise on transient failure — the engine wraps this call in retry."""
        ...
