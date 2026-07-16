"""In-memory vector provider: reads the generated embedding artifacts
(`v2/knowledge/embeddings/*.json`) into a numpy matrix and does filtered cosine search.

Temporary by design — the next phase replaces it with a `PgVectorProvider` that implements
the same `VectorSearchProvider.search` contract, and nothing above this file changes. The engine
never learns that vectors were ever an in-memory numpy array.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import numpy as np

from retrieval_engine.providers.corpus import InMemoryCorpus, passes_filter
from retrieval_engine.providers.interfaces import Filter, ScoredHit
from retrieval_engine.providers.vector import DEFAULT_DIMENSION, hash_embed_query

_RESERVED = {"embedding_manifest.json", "embedding_index.json", "_checkpoint.json"}


class InMemoryVectorProvider:
    def __init__(
        self,
        corpus: InMemoryCorpus,
        matrix: np.ndarray,
        chunk_ids: list[str],
        embed_query: Callable[[str, int], list[float]] | None = None,
    ) -> None:
        self._corpus = corpus
        self._chunk_ids = chunk_ids
        self._dimension = matrix.shape[1] if matrix.size else DEFAULT_DIMENSION
        # L2-normalize rows once so cosine similarity is a single matmul at query time.
        if matrix.size:
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            self._matrix = (matrix / norms).astype(np.float32)
        else:
            self._matrix = matrix.astype(np.float32)
        self._embed = embed_query or hash_embed_query

    @classmethod
    def load(cls, corpus: InMemoryCorpus, embeddings_dir: Path, **kwargs) -> InMemoryVectorProvider:
        """Stream the embedding files, keep vectors for chunks present in the corpus, and
        stack them into one matrix (memory-bounded: one file's JSON at a time)."""
        blocks: list[np.ndarray] = []
        chunk_ids: list[str] = []
        for path in sorted(embeddings_dir.glob("*.json")):
            if path.name in _RESERVED:
                continue
            records = json.loads(path.read_text(encoding="utf-8"))
            vecs = []
            for r in records:
                cid = str(r["chunk_id"])
                if cid in corpus.by_id:
                    chunk_ids.append(cid)
                    vecs.append(r["vector"])
            if vecs:
                blocks.append(np.asarray(vecs, dtype=np.float32))
        matrix = np.vstack(blocks) if blocks else np.zeros((0, DEFAULT_DIMENSION), dtype=np.float32)
        return cls(corpus=corpus, matrix=matrix, chunk_ids=chunk_ids, **kwargs)

    def search(self, query: str, filter: Filter, top_k: int) -> list[ScoredHit]:
        if self._matrix.shape[0] == 0 or top_k <= 0:
            return []
        q = np.asarray(self._embed(query, self._dimension), dtype=np.float32)
        qn = np.linalg.norm(q) or 1.0
        q = q / qn
        scores = self._matrix @ q  # cosine, since rows and q are unit vectors

        # Apply the metadata filter as a mask (pre-scoring predicate over corpus metadata).
        if not filter.is_empty():
            mask = np.fromiter(
                (passes_filter(self._corpus.by_id[cid], filter) for cid in self._chunk_ids),
                dtype=bool,
                count=len(self._chunk_ids),
            )
            scores = np.where(mask, scores, -np.inf)
            eligible = int(mask.sum())
        else:
            eligible = len(self._chunk_ids)
        if eligible == 0:
            return []

        k = min(top_k, eligible)
        top_idx = np.argpartition(-scores, k - 1)[:k]
        top_idx = top_idx[np.argsort(-scores[top_idx])]

        hits: list[ScoredHit] = []
        for i in top_idx:
            score = float(scores[i])
            if score == -np.inf:
                continue
            chunk = self._corpus.by_id[self._chunk_ids[int(i)]]
            hits.append(ScoredHit(chunk=chunk, score=score, source="vector"))
        return hits
