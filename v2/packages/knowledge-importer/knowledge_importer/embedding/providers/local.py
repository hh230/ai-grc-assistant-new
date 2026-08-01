"""A local, deterministic embedding provider — no network, no API key, no dependencies.

It derives a stable pseudo-random unit vector from a text's SHA-256 (same text always
produces the same vector). The vectors are **structurally** valid — correct dimension,
L2-normalized, deterministic — which is exactly what's needed to exercise and validate
the whole Embedding Engine (batching, checkpointing, the skip/regenerate decision,
metadata preservation, the manifest) end-to-end without spending money or egressing the
customer's entire knowledge base to a third party.

They are **not** semantically meaningful — they carry no learned meaning, so they are not
useful for retrieval. That's fine: retrieval is a later phase, and switching to a real
model (OpenAI, Voyage, a local BGE/Nomic) is a configuration change, not a code change.
This provider fills the same "local model" slot the roadmap reserves for BGE/Nomic/Ollama.
"""

from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Sequence
from dataclasses import dataclass

DEFAULT_LOCAL_DIMENSION = 1536


@dataclass
class LocalDeterministicProvider:
    name: str = "local"
    model: str = "local-deterministic-hash-v1"
    dimension: int = DEFAULT_LOCAL_DIMENSION

    def _vector_for(self, text: str) -> list[float]:
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
        rng = random.Random(seed)
        values = [rng.gauss(0.0, 1.0) for _ in range(self.dimension)]
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [round(v / norm, 6) for v in values]

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector_for(text) for text in texts]
