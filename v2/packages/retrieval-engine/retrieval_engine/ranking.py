"""Deterministic business-rule ranking, applied *after* fusion (and, in a later phase,
after a cross-encoder rerank). Learned/statistical relevance decides the base order; these
transparent GRC boosts adjust it. Every boost is small and logged in the returned score so
a reviewer can see why a result placed where it did.

MVP boosts:
 - exact-code match: a chunk whose `code` equals a code the query asked for is pinned up.
 - language match: a small nudge for same-language results (cross-lingual still allowed).
 - structural de-emphasis: bare heading-only chunks are nudged down vs. substantive text.
"""

from __future__ import annotations

from dataclasses import dataclass

from retrieval_engine.providers.interfaces import FusedHit

EXACT_CODE_BOOST = 1.0
LANGUAGE_BOOST = 0.03
HEADING_ONLY_PENALTY = 0.05


@dataclass(frozen=True)
class RankedHit:
    hit: FusedHit
    final_score: float
    boosts: dict[str, float]


def rank(
    fused: list[FusedHit],
    query_codes: tuple[str, ...] = (),
    query_language: str | None = None,
) -> list[RankedHit]:
    ranked: list[RankedHit] = []
    for f in fused:
        boosts: dict[str, float] = {}
        score = f.fused_score
        chunk = f.chunk

        if query_codes and chunk.code and any(chunk.code == c or chunk.code.startswith(c) for c in query_codes):
            boosts["exact_code"] = EXACT_CODE_BOOST
            score += EXACT_CODE_BOOST
        if query_language and chunk.language == query_language:
            boosts["language_match"] = LANGUAGE_BOOST
            score += LANGUAGE_BOOST
        if chunk.content_type == "heading_only":
            boosts["heading_only"] = -HEADING_ONLY_PENALTY
            score -= HEADING_ONLY_PENALTY

        ranked.append(RankedHit(hit=f, final_score=score, boosts=boosts))

    ranked.sort(key=lambda r: r.final_score, reverse=True)
    return ranked
