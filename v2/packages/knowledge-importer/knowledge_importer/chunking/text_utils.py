"""Small, honest text helpers shared by every recognizer. Nothing here rewrites,
summarizes, translates, or otherwise alters wording — nothing beyond what "whitespace
normalization" means is permitted to touch a chunk's stored text."""

from __future__ import annotations

import re

_ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_WESTERN_DIGITS = "0123456789"
_DIGIT_TRANSLATION = str.maketrans(_ARABIC_DIGITS, _WESTERN_DIGITS)

_ARABIC_BLOCK = re.compile(r"[؀-ۿ]")
_LATIN_LETTER = re.compile(r"[A-Za-z]")

_MULTI_BLANK_LINES = re.compile(r"\n{3,}")
_TRAILING_LINE_SPACE = re.compile(r"[ \t]+\n")


def normalize_digits(text: str) -> str:
    """Arabic-Indic digits -> Western digits, for internal pattern matching and
    confidence scoring only. Never applied to a chunk's stored `text` — Saudi legal
    source documents mix both digit systems, and this is what lets a recognizer treat
    them as the same number without altering a single character of the source."""
    return text.translate(_DIGIT_TRANSLATION)


def normalize_whitespace(text: str) -> str:
    """The one transformation this engine is allowed to apply to extracted content:
    normalize line endings, drop the page-break form-feed characters Phase 2 itself
    introduced (never part of the original document), strip trailing whitespace from
    each line, collapse runs of 3+ blank lines to one, and trim the chunk's outer edges.
    Wording, numbers, and punctuation are never touched."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n")
    text = _TRAILING_LINE_SPACE.sub("\n", text)
    text = _MULTI_BLANK_LINES.sub("\n\n", text)
    return text.strip()


def detect_language(text: str) -> str:
    """A minimal, honest heuristic — not linguistic analysis. Counts Arabic-block vs.
    Latin-letter characters and returns whichever is the majority; defaults to "en" for
    text with no letters of either kind (e.g. a pure numbers/table chunk)."""
    arabic_count = len(_ARABIC_BLOCK.findall(text))
    latin_count = len(_LATIN_LETTER.findall(text))
    return "ar" if arabic_count > latin_count else "en"


def slugify(value: str) -> str:
    """Lowercase, ASCII-safe identifier fragment for building deterministic chunk_ids.
    Non-alphanumeric runs collapse to a single hyphen; Arabic and other non-ASCII text
    (which cannot round-trip through this scheme) collapses to `x` markers rather than
    being dropped silently, so two different Arabic-only codes don't collide into an
    identical empty slug."""
    normalized = normalize_digits(value)
    ascii_only = re.sub(r"[^A-Za-z0-9]+", "-", normalized)
    ascii_only = re.sub(r"-{2,}", "-", ascii_only).strip("-").lower()
    return ascii_only or "x"


_SENTENCE_BOUNDARY = re.compile(r"[.!?؟۔]\s")
_PARAGRAPH_BOUNDARY = re.compile(r"\n\s*\n")


def find_break_point(text: str, target: int, lookback: int = 200) -> int:
    """Finds the best place at or before `target` to cut `text` without splitting a
    sentence or paragraph in half. Prefers a paragraph break, then a sentence end,
    within `lookback` characters before `target`; falls back to `target` itself (a hard
    cut) only when neither exists nearby — an accepted, documented edge case for the
    windowed fallback, never used for structure-aware chunks."""
    window_start = max(0, target - lookback)
    search_region = text[window_start:target]

    last_para = None
    for match in _PARAGRAPH_BOUNDARY.finditer(search_region):
        last_para = match
    if last_para is not None:
        return window_start + last_para.end()

    last_sentence = None
    for match in _SENTENCE_BOUNDARY.finditer(search_region):
        last_sentence = match
    if last_sentence is not None:
        return window_start + last_sentence.end()

    return target
