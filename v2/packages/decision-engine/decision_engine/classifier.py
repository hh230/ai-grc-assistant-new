"""Deterministic classifier: score every intent's patterns against the normalized request,
pick the winner, and decide between a single intent, a multi-step composite, ambiguity, a
conversation, or an unsupported request. Fully explainable — the winning cues and scores
are carried on the `Classification` for the plan's `reason`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from decision_engine.intents import INTENT_PATTERNS, MAPPING_CUE
from decision_engine.models import Intent, UserRequest
from decision_engine.rules import (
    FrameworkHit,
    detect_frameworks,
    detect_language,
    has_conjunction,
    has_grc_vocabulary,
    has_locator,
    mentions_document,
    normalize,
)

# A secondary intent must reach this fraction of the top score (and the absolute floor) to
# count as part of a composite; a near-tie without a conjunction is treated as ambiguous.
_SECONDARY_RATIO = 0.6
_STRONG_FLOOR = 2.0
_AMBIGUOUS_MARGIN = 0.75


@dataclass(frozen=True, kw_only=True)
class Classification:
    """Keyword-only: nine positional fields made every construction unreadable, so each
    call site now names exactly what it sets; anything unstated takes the empty default."""

    primary: Intent
    confidence: float
    reason: str
    secondaries: list[Intent] = field(default_factory=list)
    frameworks: list[FrameworkHit] = field(default_factory=list)
    matched_cues: list[str] = field(default_factory=list)
    scores: dict[Intent, float] = field(default_factory=dict)
    language: str = "en"
    mentions_document: bool = False


def _score(normalized: str) -> tuple[dict[Intent, float], dict[Intent, list[str]]]:
    scores: dict[Intent, float] = {}
    cues: dict[Intent, list[str]] = {}
    for intent, patterns in INTENT_PATTERNS.items():
        total = 0.0
        hit_cues: list[str] = []
        for rx, weight in patterns:
            match = rx.search(normalized)
            if match:
                total += weight
                hit_cues.append(match.group(0).strip())
        if total > 0:
            scores[intent] = total
            cues[intent] = hit_cues
    return scores, cues


def _confidence(primary: Intent, scores: dict[Intent, float]) -> float:
    if primary is Intent.AMBIGUOUS:
        return 0.35
    if primary is Intent.UNSUPPORTED:
        return 0.6
    ordered = sorted(scores.values(), reverse=True)
    top = ordered[0] if ordered else 0.0
    second = ordered[1] if len(ordered) > 1 else 0.0
    if primary is Intent.CONVERSATION:
        return 0.85
    if top >= 3.0:
        base = 0.85
    elif top >= 2.0:
        base = 0.78
    elif top >= 1.0:
        base = 0.68
    else:
        base = 0.55
    if second == 0.0:
        base += 0.10
    elif (top - second) >= 1.5:
        base += 0.05
    elif (top - second) < _AMBIGUOUS_MARGIN:
        base -= 0.10
    return round(min(0.98, max(0.3, base)), 2)


def classify(request: UserRequest) -> Classification:
    normalized = normalize(request.query)
    language = detect_language(request.query)
    frameworks = detect_frameworks(normalized)
    doc_ref = mentions_document(normalized) or request.has_document

    if not normalized:
        if request.has_document:
            return Classification(
                primary=Intent.DOCUMENT_ANALYSIS, confidence=0.7,
                reason="Empty query with an attachment — defaulting to document analysis.",
                frameworks=frameworks, language=language, mentions_document=True,
            )
        return Classification(
            primary=Intent.UNSUPPORTED, confidence=0.6,
            reason="Empty request — nothing to classify.",
            frameworks=frameworks, language=language, mentions_document=doc_ref,
        )

    scores, cues = _score(normalized)

    # Cross-framework promotion: an explicit mapping cue + two or more named frameworks is a
    # cross-framework mapping regardless of whether "control mapping" was said.
    named = [f for f in frameworks if f.named]
    if MAPPING_CUE.search(normalized) and len(named) >= 2:
        scores[Intent.CROSS_FRAMEWORK_MAPPING] = scores.get(Intent.CROSS_FRAMEWORK_MAPPING, 0.0) + 3.0
        cues.setdefault(Intent.CROSS_FRAMEWORK_MAPPING, []).append("mapping cue + 2 frameworks")
        # cross-framework mapping subsumes control mapping when two frameworks are mapped,
        # so the two don't compete into a false "ambiguous".
        scores.pop(Intent.CONTROL_MAPPING, None)

    grc_scores = {i: s for i, s in scores.items() if i is not Intent.CONVERSATION}

    # ── Conversation ─────────────────────────────────────────────────────────
    # A greeting/meta cue wins when it scores at least as high as any GRC verb, so a
    # "hello, how can you help" isn't dragged into a weak GRC intent (e.g. "how" →
    # explanation). A genuine GRC verb ("hi, compare X with Y") still outranks the greeting.
    conversation_score = scores.get(Intent.CONVERSATION, 0.0)
    top_grc = max(grc_scores.values()) if grc_scores else 0.0
    if conversation_score > 0.0 and conversation_score >= top_grc:
        return Classification(
            primary=Intent.CONVERSATION, confidence=_confidence(Intent.CONVERSATION, scores),
            reason="Greeting / meta cue detected and no stronger GRC task verb — conversation (no retrieval).",
            frameworks=frameworks, matched_cues=cues.get(Intent.CONVERSATION, []),
            scores=scores, language=language, mentions_document=doc_ref,
        )

    # ── No GRC intent matched ────────────────────────────────────────────────
    if not grc_scores:
        if request.has_document:
            return Classification(
                primary=Intent.DOCUMENT_ANALYSIS, confidence=0.7,
                reason="An attachment is present with no explicit task — defaulting to document analysis.",
                frameworks=frameworks, scores=scores, language=language, mentions_document=True,
            )
        if has_grc_vocabulary(normalized) or frameworks:
            fw = ", ".join(f.label for f in frameworks) or "GRC terms"
            return Classification(
                primary=Intent.AMBIGUOUS, confidence=0.35,
                reason=f"GRC topic detected ({fw}) but no clear task verb — ambiguous, ask a follow-up.",
                frameworks=frameworks, scores=scores, language=language, mentions_document=doc_ref,
            )
        return Classification(
            primary=Intent.UNSUPPORTED, confidence=0.6,
            reason="No GRC intent, vocabulary, or greeting detected — out of scope.",
            frameworks=frameworks, scores=scores, language=language, mentions_document=doc_ref,
        )

    # ── A GRC intent matched ─────────────────────────────────────────────────
    primary = max(grc_scores, key=lambda i: grc_scores[i])
    top = grc_scores[primary]

    # Grounding guard: the generic question intents (`lookup` = "what is …", `explanation` =
    # "explain …") fire on non-GRC topics too ("what is the weather", "explain quantum
    # physics"). Require GRC grounding — a framework, GRC vocabulary, a clause code, or an
    # attachment — for those two; without it, the request is out of scope. Strong-verb
    # intents (summarize, compare, risk analysis, …) are not guarded: their verb is the
    # signal, and they may legitimately operate on provided content.
    grounded = has_grc_vocabulary(normalized) or bool(frameworks) or doc_ref or has_locator(normalized)
    if not grounded and primary in {Intent.LOOKUP, Intent.EXPLANATION}:
        return Classification(
            primary=Intent.UNSUPPORTED, confidence=0.55,
            reason=f"Matched a generic '{primary.value}' cue but the request has no GRC grounding "
                   f"(no framework, vocabulary, clause code, or attachment) — out of scope.",
            frameworks=frameworks, matched_cues=cues.get(primary, []),
            scores=scores, language=language, mentions_document=doc_ref,
        )
    secondaries = [
        i
        for i, s in grc_scores.items()
        if i is not primary and s >= _SECONDARY_RATIO * top and s >= _STRONG_FLOOR
    ]
    secondaries.sort(key=lambda i: grc_scores[i], reverse=True)

    conjunction = has_conjunction(normalized)
    primary_cues = cues.get(primary, [])

    if secondaries and conjunction:
        # legitimate composite ("compare … and which controls our policy misses"): a
        # conjunction joining two strong task verbs → a multi-step plan.
        cue_txt = "; ".join(f"{i.value}: {', '.join(cues.get(i, []))}" for i in [primary, *secondaries])
        reason = f"Composite request → primary '{primary.value}', also [{', '.join(s.value for s in secondaries)}] joined by a conjunction. Cues — {cue_txt}."
        return Classification(
            primary=primary, secondaries=secondaries, confidence=_confidence(primary, grc_scores),
            reason=reason, frameworks=frameworks, matched_cues=primary_cues,
            scores=scores, language=language, mentions_document=doc_ref,
        )

    # Otherwise a single request: the highest-scoring intent wins deterministically; weaker
    # matches are dropped. (Genuine ambiguity is only raised above, when *no* task verb
    # matched at all — a bare entity like "NCA ECC controls".)
    fw = ", ".join(f"{f.label}→{f.profile}" for f in frameworks)
    reason = f"Classified as '{primary.value}' from cue(s): {', '.join(primary_cues)}."
    if fw:
        reason += f" Detected: {fw}."
    return Classification(
        primary=primary, confidence=_confidence(primary, grc_scores), reason=reason,
        frameworks=frameworks, matched_cues=primary_cues,
        scores=scores, language=language, mentions_document=doc_ref,
    )
