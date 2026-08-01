"""Deduplication — no duplicated context ever reaches the package.

Three signals, cheapest first:

1. **chunk_id** — the same retrieved chunk appearing twice.
2. **checksum** — a content hash of the normalized text: byte-different chunks that say the
   same thing (very common when the same clause is embedded in two documents).
3. **similarity** — near-duplicates via Jaccard over normalized token shingles, plus
   containment (a short chunk wholly inside a longer one). Above a threshold they are the
   same context; we keep the higher-scoring representative.

Also home to the shared text-normalization helpers (Arabic tatweel/diacritics stripped,
punctuation folded, whitespace collapsed) used across the builder.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

from context_builder.models import ContextBlock

# Arabic diacritics (harakat) and tatweel — noise for identity/similarity.
_ARABIC_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۜ۟-۪ۨ-ۭـ]")
_NON_WORD = re.compile(r"[^\w؀-ۿ]+", re.UNICODE)

DEFAULT_SIMILARITY_THRESHOLD = 0.9
DEFAULT_CONTAINMENT_THRESHOLD = 0.95


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = _ARABIC_DIACRITICS.sub("", text)
    text = _NON_WORD.sub(" ", text.lower())
    return text.strip()


def content_hash(text: str) -> str:
    return hashlib.sha1(normalize_text(text).encode("utf-8")).hexdigest()


def token_set(text: str) -> frozenset[str]:
    return frozenset(normalize_text(text).split())


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / len(a | b)


def containment(a: frozenset[str], b: frozenset[str]) -> float:
    """Fraction of the smaller set contained in the larger — catches a child chunk sitting
    verbatim inside its parent."""
    if not a or not b:
        return 0.0
    small, large = (a, b) if len(a) <= len(b) else (b, a)
    return len(small & large) / len(small)


def _are_duplicates(
    a: ContextBlock, ta: frozenset[str], b: ContextBlock, tb: frozenset[str],
    sim_threshold: float, contain_threshold: float,
) -> bool:
    if a.content_hash and a.content_hash == b.content_hash:
        return True
    if jaccard(ta, tb) >= sim_threshold:
        return True
    # containment only collapses within the same document (same clause restated); across
    # documents a shared passage is legitimately two citations and must be kept.
    if a.document_id == b.document_id and containment(ta, tb) >= contain_threshold:
        return True
    return False


def dedup_by_content_hash(blocks: list[ContextBlock]) -> tuple[list[ContextBlock], int]:
    """Exact-text ("checksum") dedup only — collapses byte-identical normalized text,
    keeping the higher-scoring block and folding provenance. Unlike `deduplicate` it uses no
    similarity/containment, so it can never drop a *distinct* child; safe to run as a final
    guard after merge/expansion (which can introduce identical parents or restated clauses).
    """
    seen: dict[str, ContextBlock] = {}
    out: list[ContextBlock] = []
    removed = 0
    for block in sorted(blocks, key=lambda b: b.score, reverse=True):
        h = block.content_hash
        if h and h in seen:
            winner = seen[h]
            winner.source_chunk_ids = tuple(dict.fromkeys((*winner.source_chunk_ids, *block.source_chunk_ids)))
            removed += 1
            continue
        if h:
            seen[h] = block
        out.append(block)
    return out, removed


def deduplicate(
    blocks: list[ContextBlock],
    *,
    sim_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    contain_threshold: float = DEFAULT_CONTAINMENT_THRESHOLD,
) -> tuple[list[ContextBlock], int]:
    """Return (unique blocks, removed count). Higher-scoring block wins each collision; the
    survivor absorbs the loser's source_chunk_ids so provenance is not lost."""
    kept: list[ContextBlock] = []
    kept_tokens: list[frozenset[str]] = []
    seen_ids: set[str] = set()
    removed = 0

    # Highest score first so the representative we keep is the strongest hit.
    for block in sorted(blocks, key=lambda b: b.score, reverse=True):
        if block.block_id in seen_ids:
            removed += 1
            continue
        tokens = token_set(block.text)
        dup_index = next(
            (i for i, (k, kt) in enumerate(zip(kept, kept_tokens))
             if _are_duplicates(k, kt, block, tokens, sim_threshold, contain_threshold)),
            None,
        )
        if dup_index is not None:
            winner = kept[dup_index]
            winner.source_chunk_ids = tuple(dict.fromkeys((*winner.source_chunk_ids, *block.source_chunk_ids)))
            removed += 1
            continue
        seen_ids.add(block.block_id)
        kept.append(block)
        kept_tokens.append(tokens)
    return kept, removed
