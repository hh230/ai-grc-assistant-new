"""In-memory keyword provider: builds a BM25 inverted index over the corpus chunk text
(plus boosted code/title/heading fields) and scores filtered candidates. Temporary — a
`PgSearchProvider` (Postgres FTS / BM25) replaces it next phase behind the same contract.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from retrieval_engine.providers.corpus import InMemoryCorpus, passes_filter
from retrieval_engine.providers.interfaces import Filter, ScoredHit
from retrieval_engine.providers.keyword import FIELD_BOOST, bm25_idf, bm25_term_score
from retrieval_engine.text import tokenize


class InMemoryKeywordProvider:
    def __init__(self, corpus: InMemoryCorpus) -> None:
        self._corpus = corpus
        self._doc_tokens: dict[str, Counter[str]] = {}
        self._field_tokens: dict[str, set[str]] = {}
        self._doc_len: dict[str, int] = {}
        self._postings: dict[str, set[str]] = defaultdict(set)
        self._build()

    def _build(self) -> None:
        total_len = 0
        for chunk in self._corpus.chunks:
            tokens = tokenize(chunk.text)
            counts = Counter(tokens)
            self._doc_tokens[chunk.chunk_id] = counts
            self._doc_len[chunk.chunk_id] = len(tokens)
            total_len += len(tokens)
            for term in counts:
                self._postings[term].add(chunk.chunk_id)
            # boosted fields: code, title, heading_path
            field_text = " ".join(
                filter(None, [chunk.code or "", chunk.title or "", " ".join(chunk.heading_path)])
            )
            self._field_tokens[chunk.chunk_id] = set(tokenize(field_text))
        self._num_docs = len(self._corpus.chunks)
        self._avgdl = (total_len / self._num_docs) if self._num_docs else 0.0

    def search(self, query: str, filter: Filter, top_k: int) -> list[ScoredHit]:
        terms = tokenize(query)
        if not terms or top_k <= 0:
            return []

        idf = {t: bm25_idf(self._num_docs, len(self._postings.get(t, ()))) for t in set(terms)}

        # candidate docs = union of postings for the query terms, then metadata-filtered
        candidates: set[str] = set()
        for t in set(terms):
            candidates |= self._postings.get(t, set())

        scored: list[tuple[float, str]] = []
        for cid in candidates:
            chunk = self._corpus.by_id[cid]
            if not filter.is_empty() and not passes_filter(chunk, filter):
                continue
            counts = self._doc_tokens[cid]
            doc_len = self._doc_len[cid]
            fields = self._field_tokens[cid]
            score = 0.0
            for t in terms:
                tf = counts.get(t, 0)
                if tf:
                    score += bm25_term_score(tf, doc_len, self._avgdl, idf[t])
                if t in fields:
                    score += FIELD_BOOST * idf[t]
            if score > 0:
                scored.append((score, cid))

        scored.sort(key=lambda s: s[0], reverse=True)
        return [
            ScoredHit(chunk=self._corpus.by_id[cid], score=score, source="keyword")
            for score, cid in scored[:top_k]
        ]
