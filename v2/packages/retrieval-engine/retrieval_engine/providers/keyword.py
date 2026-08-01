"""BM25 keyword-search scoring. BM25 (not plain substring match) because the corpus mixes
1-page checklists with 1,200-page rulebooks, where term-frequency saturation and length
normalization matter. Fielded: a query term matching a chunk's title or code is boosted over
the same term buried in body prose. The provider interface itself is the
`KeywordSearchProvider` protocol in pipeline-contracts.
"""

from __future__ import annotations

import math

BM25_K1 = 1.5
BM25_B = 0.75
# extra weight for a query term that also appears in a chunk's code/title/heading_path
FIELD_BOOST = 2.0


def bm25_idf(num_docs: int, doc_freq: int) -> float:
    # BM25 idf with +1 to stay non-negative for very common terms
    return math.log(1.0 + (num_docs - doc_freq + 0.5) / (doc_freq + 0.5))


def bm25_term_score(tf: int, doc_len: int, avgdl: float, idf: float) -> float:
    denom = tf + BM25_K1 * (1.0 - BM25_B + BM25_B * (doc_len / avgdl if avgdl else 1.0))
    return idf * (tf * (BM25_K1 + 1.0)) / (denom or 1.0)
