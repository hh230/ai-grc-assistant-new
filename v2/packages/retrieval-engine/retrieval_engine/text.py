"""Shared, dependency-free text handling: Arabic/English normalization and tokenization
for keyword matching and query normalization. Normalization is for *matching only* — it
never alters stored text or citations."""

from __future__ import annotations

import re
import unicodedata

# Arabic diacritics / marks ONLY — never letters (Arabic letters are U+0621–U+064A). The
# class is built from explicit codepoint ranges so it can't accidentally span the letter
# block: harakat/marks (U+0610–U+061A, U+064B–U+065F), superscript alef (U+0670), Quranic
# marks (U+06D6–U+06ED).
_MARK_RANGES = [(0x0610, 0x061A), (0x064B, 0x065F), (0x0670, 0x0670), (0x06D6, 0x06ED)]
_DIACRITICS = re.compile("[" + "".join(f"{chr(a)}-{chr(b)}" for a, b in _MARK_RANGES) + "]")
_TATWEEL = chr(0x0640)  # ـ

_ARABIC_INDIC = "".join(chr(0x0660 + i) for i in range(10))
_WESTERN = "0123456789"
_DIGITS = str.maketrans(_ARABIC_INDIC, _WESTERN)

_ALEF = re.compile("[" + chr(0x0623) + chr(0x0625) + chr(0x0622) + "]")  # أ إ آ → ا
_ALEF_BASE = chr(0x0627)
_YAA_MAQSURA, _YAA = chr(0x0649), chr(0x064A)  # ى → ي
_TAA_MARBUTA, _HAA = chr(0x0629), chr(0x0647)  # ة → ه

# a token is a run of latin/digits or a run of Arabic-block characters (U+0600–U+06FF)
_TOKEN = re.compile("[0-9a-z]+|[" + chr(0x0600) + "-" + chr(0x06FF) + "]+")

_STOPWORDS = frozenset(
    {
        "the", "a", "an", "of", "and", "or", "to", "in", "on", "for", "is", "are", "be",
        "with", "by", "as", "at", "our", "this", "that", "what", "which", "how", "does",
        "do", "we", "i", "me", "us",
        "من", "في", "على", "هذا",
        "هذه", "ما", "هل", "و", "او",
        "الى", "مع", "هو", "هي",
    }
)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text.strip())
    text = _DIACRITICS.sub("", text).replace(_TATWEEL, "")
    text = _ALEF.sub(_ALEF_BASE, text)
    text = text.replace(_YAA_MAQSURA, _YAA).replace(_TAA_MARBUTA, _HAA)
    text = text.translate(_DIGITS)
    return text.lower()


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(normalize(text)) if t not in _STOPWORDS and len(t) > 1]
