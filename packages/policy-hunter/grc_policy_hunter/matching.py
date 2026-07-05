"""The Policy Hunter matching engine — pure, deterministic, no LLM.

Coverage gaps are not guessed at by a model: they are computed from a plain word-overlap
similarity between one obligation's text and each of the tenant's policies, and the
obligation source's fetch time versus the matched policy's last update. This is CLAUDE.md §1
("we would rather say 'I don't know' than guess") applied literally — every finding's
confidence score is a property of this algorithm, not a fabricated model confidence, and the
same inputs always produce the same output (no false positives from hallucination).

Classification (given ``best_score``, the highest similarity against any tenant policy):

- ``best_score == 0.0``            -> UNMAPPED_REGULATORY_OBLIGATION (shares nothing with any
                                       policy at all — including when the tenant has none).
- ``0.0 < best_score < PARTIAL``   -> MISSING_REQUIRED_POLICY (a faint signal only).
- ``PARTIAL <= best_score < STRONG`` -> INCOMPLETE_COVERAGE (related, but not substantive).
- ``best_score >= STRONG``         -> covered, unless the source regulation was fetched more
                                       recently than the matched policy was updated, in which
                                       case OUTDATED_POLICY.

Thresholds are conservative on purpose: word-overlap (Jaccard) scores between a short
regulatory sentence and a policy title/summary are modest even for a genuinely relevant pair,
so requiring a very high score to call something "covered" would produce false negatives
(missed gaps) — the safer failure mode for a compliance tool is to under-claim coverage, not
over-claim it.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from .enums import GapCategory
from .models import CoverageScanResult, GapFinding, ObligationSummary, PolicySummary

_PARTIAL_MATCH_THRESHOLD = 0.15
_STRONG_MATCH_THRESHOLD = 0.30

_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "in",
        "for",
        "on",
        "with",
        "by",
        "at",
        "is",
        "are",
        "be",
        "as",
        "that",
        "this",
        "shall",
        "must",
        "should",
        "may",
        "not",
        "entities",
        "entity",
        "each",
        "any",
        "all",
        "its",
        "their",
    }
)
_WORD_RE = re.compile(r"[a-zA-Z]+")


def _tokenize(text: str) -> frozenset[str]:
    words = _WORD_RE.findall(text.lower())
    return frozenset(word for word in words if word not in _STOPWORDS and len(word) > 2)


def _similarity(a: str, b: str) -> float:
    """Jaccard similarity over the two texts' significant words. 0.0 if either has none."""
    tokens_a, tokens_b = _tokenize(a), _tokenize(b)
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def _best_match(
    obligation: ObligationSummary, policies: Sequence[PolicySummary]
) -> tuple[PolicySummary | None, float]:
    obligation_text = f"{obligation.suggested_policy_title} {obligation.obligation_text}"
    best_policy: PolicySummary | None = None
    best_score = 0.0
    for policy in policies:
        policy_text = f"{policy.title} {policy.summary or ''}"
        score = _similarity(obligation_text, policy_text)
        if score > best_score:
            best_score = score
            best_policy = policy
    return best_policy, best_score


def _classify(
    score: float, best_policy: PolicySummary | None, obligation: ObligationSummary
) -> GapCategory | None:
    if score == 0.0:
        return GapCategory.UNMAPPED_REGULATORY_OBLIGATION
    if score < _PARTIAL_MATCH_THRESHOLD:
        return GapCategory.MISSING_REQUIRED_POLICY
    if score < _STRONG_MATCH_THRESHOLD:
        return GapCategory.INCOMPLETE_COVERAGE
    assert best_policy is not None  # score > 0 implies a best_policy was found
    if obligation.source_document_fetched_at > best_policy.updated_at:
        return GapCategory.OUTDATED_POLICY
    return None  # substantively matched and the policy postdates the source -> covered


def _rationale(category: GapCategory, best_policy: PolicySummary | None) -> str:
    if category is GapCategory.UNMAPPED_REGULATORY_OBLIGATION:
        return "No existing policy shares any meaningful terms with this obligation."
    if category is GapCategory.MISSING_REQUIRED_POLICY:
        return "No policy substantively addresses this obligation."
    if category is GapCategory.INCOMPLETE_COVERAGE:
        title = best_policy.title if best_policy else "the closest matching policy"
        return f"{title!r} partially overlaps this obligation but does not clearly cover it."
    title = best_policy.title if best_policy else "the matched policy"
    return f"{title!r} matches this obligation but predates a newer source regulation version."


def _confidence_for(category: GapCategory, score: float) -> float:
    if category in (
        GapCategory.UNMAPPED_REGULATORY_OBLIGATION,
        GapCategory.MISSING_REQUIRED_POLICY,
    ):
        # Confidence in the gap: a lower best match means higher confidence nothing covers it.
        return round(1.0 - score, 2)
    # INCOMPLETE_COVERAGE / OUTDATED_POLICY: confidence in the match itself.
    return round(score, 2)


def scan_coverage(
    obligations: Sequence[ObligationSummary], policies: Sequence[PolicySummary]
) -> CoverageScanResult:
    """Compare every obligation against every policy and report only the gaps — a fully
    covered obligation produces no finding at all."""
    findings: list[GapFinding] = []
    for obligation in obligations:
        best_policy, score = _best_match(obligation, policies)
        category = _classify(score, best_policy, obligation)
        if category is None:
            continue
        findings.append(
            GapFinding(
                obligation_id=obligation.obligation_id,
                gap_category=category,
                source_id=obligation.source_id,
                source_url=obligation.source_url,
                citation=f"{obligation.source_id}#{obligation.obligation_id}",
                confidence=_confidence_for(category, score),
                matched_policy_id=best_policy.policy_id if best_policy else None,
                matched_policy_title=best_policy.title if best_policy else None,
                rationale=_rationale(category, best_policy),
            )
        )
    return CoverageScanResult(
        findings=tuple(findings),
        obligations_scanned=len(obligations),
        policies_considered=len(policies),
    )
