"""The query embedder used by the vector-search adapters.

`hash_embed_query` mirrors Phase 4's `local-deterministic-hash-v1` provider exactly, so a
query is embedded in the same space as the corpus. Note: those Phase-4 vectors are
structurally valid but *not semantically meaningful* (they're hash-derived), so vector
search over them contributes little real relevance today — keyword/BM25 carries relevance
until real embeddings (OpenAI, etc.) replace the hash ones. The engine and the
`VectorSearchProvider` contract (pipeline-contracts) do not change when that happens; only
the adapter and the query embedder do.
"""

from __future__ import annotations

import hashlib
import math
import random

DEFAULT_DIMENSION = 1536


def hash_embed_query(text: str, dimension: int = DEFAULT_DIMENSION) -> list[float]:
    """Deterministic unit vector from a text's SHA-256 — identical algorithm to Phase 4's
    LocalDeterministicProvider, so query and corpus vectors share a space."""
    seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
    rng = random.Random(seed)
    values = [rng.gauss(0.0, 1.0) for _ in range(dimension)]
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]
