"""Deterministic text rules: Arabic/English normalization, framework detection, and the
small structural cues (conjunction, attachment reference, GRC vocabulary) the classifier
uses. Pure functions, no state, no I/O — everything here is explainable and testable in
isolation.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# ── Arabic normalization ──────────────────────────────────────────────────────
_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
_TATWEEL = "ـ"
_ARABIC_INDIC = "٠١٢٣٤٥٦٧٨٩"
_WESTERN = "0123456789"
_DIGITS = str.maketrans(_ARABIC_INDIC, _WESTERN)
_ARABIC_BLOCK = re.compile(r"[؀-ۿ]")


def normalize(text: str) -> str:
    """Normalize for matching only (never for display): NFKC, strip Arabic diacritics and
    tatweel, unify alef/yaa/taa-marbuta, Arabic-Indic → Western digits, lowercase Latin.
    Patterns in `intents.py` are written in this same normalized form so they line up."""
    text = unicodedata.normalize("NFKC", text.strip())
    text = _DIACRITICS.sub("", text).replace(_TATWEEL, "")
    text = re.sub("[أإآ]", "ا", text).replace("ى", "ي").replace("ة", "ه")
    text = text.translate(_DIGITS)
    return text.lower()


def detect_language(raw_text: str) -> str:
    """Coarse language of the original text: 'ar' if it contains Arabic-block characters,
    else 'en'. A display hint, not linguistic analysis."""
    return "ar" if _ARABIC_BLOCK.search(raw_text) else "en"


# ── Framework / knowledge-source detection ────────────────────────────────────
@dataclass(frozen=True)
class FrameworkHit:
    label: str
    profile: str
    named: bool  # True for a real framework/regulation; False for a generic profile hint


# Ordered specific → generic. Each entry: (pattern, label, target_profile, is_named).
# The target profiles are the Retrieval Engine's routing profiles: e.g. NCA ECC is a
# controls framework for routing purposes, so it maps to `control_framework` (matching the
# approved example output), even though its ingestion Document Profile is `regulation`.
_FRAMEWORK_ALIASES: list[tuple[str, str, str, bool]] = [
    (r"iso\s?/?iec\s?27001", "ISO 27001", "iso_standard", True),
    (r"iso\s?27001", "ISO 27001", "iso_standard", True),
    (r"iso\s?27002", "ISO 27002", "iso_standard", True),
    (r"iso\s?27005", "ISO 27005", "iso_standard", True),
    (r"iso\s?27017", "ISO 27017", "iso_standard", True),
    (r"iso\s?31000", "ISO 31000", "iso_standard", True),
    (r"iso\s?22301", "ISO 22301", "iso_standard", True),
    (r"iso\s?37301", "ISO 37301", "iso_standard", True),
    (r"iso\s?37001", "ISO 37001", "iso_standard", True),
    (r"iso\s?9001", "ISO 9001", "iso_standard", True),
    (r"nist\s?(?:sp\s?)?800-53", "NIST SP 800-53", "control_framework", True),
    (r"nist\s?(?:sp\s?)?800-171", "NIST SP 800-171", "control_framework", True),
    (r"nist\s?(?:sp\s?)?800-61", "NIST SP 800-61", "control_framework", True),
    (r"nist\s?(?:sp\s?)?800-37", "NIST SP 800-37", "control_framework", True),
    (r"ai\s?rmf", "NIST AI RMF", "control_framework", True),
    (r"nist\s?csf|cybersecurity framework", "NIST CSF", "control_framework", True),
    (r"nca\s?ecc|\becc\b|الضوابط الاساسيه", "NCA ECC", "control_framework", True),
    (r"\botcc\b", "NCA OTCC", "control_framework", True),
    (r"\bcscc\b", "NCA CSCC", "control_framework", True),
    (r"\bcobit\b", "COBIT", "control_framework", True),
    (r"\bcoso\b", "COSO", "control_framework", True),
    (r"\bpdpl\b|حمايه البيانات الشخصيه|نظام حمايه البيانات", "PDPL", "law", True),
    (r"\bsama\b|ساما", "SAMA", "regulation", True),
    (r"\bcma\b|هيئه السوق الماليه", "CMA", "regulation", True),
    (r"\bsdaia\b|سدايا", "SDAIA", "regulation", True),
    (r"\bnist\b", "NIST", "control_framework", True),
    (r"\biso\b|iso/?iec", "ISO", "iso_standard", True),
    # generic profile hints (not named frameworks)
    (r"\bpolic(?:y|ies)\b|السياسه|سياسه", "policy", "corporate_policy", False),
    (r"\bcontract\b|العقد|عقد", "contract", "contract", False),
    (r"\bprocedure\b|الاجراء|اجراء", "procedure", "procedure", False),
]
_COMPILED_FRAMEWORKS = [(re.compile(p), label, prof, named) for p, label, prof, named in _FRAMEWORK_ALIASES]


def detect_frameworks(normalized_text: str) -> list[FrameworkHit]:
    """Detect frameworks / profile hints, most-specific first. A matched span is blanked
    before trying more-generic aliases, so `iso 27001` never also counts as a bare `iso`.
    Returns hits in first-occurrence order, de-duplicated by label."""
    work = normalized_text
    hits: list[tuple[int, FrameworkHit]] = []
    seen: set[str] = set()
    for rx, label, profile, named in _COMPILED_FRAMEWORKS:
        for m in rx.finditer(work):
            if label not in seen:
                seen.add(label)
                hits.append((m.start(), FrameworkHit(label=label, profile=profile, named=named)))
        work = rx.sub(lambda mm: " " * (mm.end() - mm.start()), work)
    hits.sort(key=lambda h: h[0])
    return [h for _, h in hits]


def profiles_from_hits(hits: list[FrameworkHit]) -> list[str]:
    """Ordered, de-duplicated target profiles from framework hits."""
    profiles: list[str] = []
    for hit in hits:
        if hit.profile not in profiles:
            profiles.append(hit.profile)
    return profiles


# ── Small structural cues ─────────────────────────────────────────────────────
_CONJUNCTION = re.compile(r"\b(and|then|also|plus)\b|\bو\b|\bثم\b| و |,")
_DOCUMENT_REF = re.compile(
    r"\b(this|the attached|the uploaded|attached|uploaded)\s+(document|file|policy|doc)\b"
    r"|هذا (?:المستند|الملف|العقد)|هذه (?:الوثيقه|السياسه)|المرفق"
)
_GRC_VOCAB = re.compile(
    r"\b(iso|nist|cobit|coso|ecc|otcc|nca|sama|cma|sdaia|pdpl|gdpr|policy|policies|control|controls|"
    r"risk|compliance|complian\w*|obligation|obligations|audit|regulation|regulatory|law|framework|"
    r"governance|gap|mapping|privacy|security|clause|article|standard|segregation|duties|"
    r"access|vendor|third[- ]party|encryption|incident|evidence|attestation|remediation|"
    r"confidential|breach|contract|procedure|requirement|requirements)\b"
    r"|سياسه|ضابط|ضوابط|مخاطر|امتثال|التزام|تدقيق|مراجعه|حوكمه|نظام|لائحه|اطار|معيار|خصوصيه|امن|ماده|بند|لائح"
    r"|فصل المهام|الوصول|تشفير|حادث|دليل|طرف ثالث|مورد|عقد|اجراء|متطلب"
)


def has_conjunction(normalized_text: str) -> bool:
    return bool(_CONJUNCTION.search(normalized_text))


def mentions_document(normalized_text: str) -> bool:
    return bool(_DOCUMENT_REF.search(normalized_text))


def has_grc_vocabulary(normalized_text: str) -> bool:
    return bool(_GRC_VOCAB.search(normalized_text))


# A clause/control code or article reference (ISO A.5.15, NIST AC-2, NCA 1-1-1, Article 12,
# المادة ١٢) — grounds a GRC request even when no framework name is spelled out.
_LOCATOR = re.compile(
    r"\b[a-z]{1,3}[.\-]\d+(?:[.\-(]\d+\)?)*\b"  # A.5.15, AC-2, 5.1.2, AC-2(1)
    r"|\b\d+-\d+(?:-[a-z]+)?-\d+\b"  # NCA ECC 1-1-1, 2-2-p-1
    r"|\barticle\s+\d+|\bclause\s+[\w.]+|ماده\s|المواد|بند\s"
)


def has_locator(normalized_text: str) -> bool:
    return bool(_LOCATOR.search(normalized_text))
