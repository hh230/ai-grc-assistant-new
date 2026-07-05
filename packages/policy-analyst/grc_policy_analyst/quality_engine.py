"""The Policy Analyst quality engine — pure, deterministic, no LLM (the same design choice
ADR-0020 made for Policy Hunter: a comparison/detection problem does not need a model's
free-form guess when a reproducible algorithm is available and sufficient — CLAUDE.md §1).

Four analysis dimensions, each a pure function of ``PolicyDocument`` (+ confirmed obligations
+ a reference clock, injected so tests are deterministic):

- **Completeness** (``_check_completeness``): does the policy body mention each of the
  required sections at all (purpose, scope, ownership, responsibilities, controls, review
  cycle, exceptions)? A lexical, deterministic keyword-absence check.
- **Regulatory alignment** (``_check_regulatory_alignment``): for every confirmed obligation
  whose *title* is relevant to this policy (``_is_relevant``), how well does the policy
  *body* actually cover that obligation's text? Scored the same word-overlap way as Policy
  Hunter (ADR-0020), but against the full body rather than just a title/summary, since this
  is a deep read of one policy rather than a fast scan across many.
- **Internal consistency** (``_check_internal_consistency``): unclear ownership (the
  structured ``owner_name`` field is blank or a placeholder), ambiguous language (known
  weasel phrases), and conflicting requirements (the same anchor keyword — e.g. "review" —
  associated with two different frequency words — e.g. "annually" and "quarterly" — anywhere
  in the body).
- **Freshness** (``_check_freshness``): the policy itself is stale (untouched for over a
  year), or a *substantively covered* obligation's source regulation was fetched more
  recently than the policy was last updated (a *weakly* covered obligation that's also newer
  is reported as ``OUTDATED_REFERENCE`` under regulatory alignment instead — see
  ``_classify_alignment``).

No finding is ever produced without underlying evidence: every ``QualityFinding.evidence`` is
built from the actual text/date that triggered it, never invented.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from .enums import FindingType, Severity
from .models import PolicyDocument, PolicyQualityReport, QualityFinding, RelatedObligation

_STALE_POLICY_MAX_AGE_DAYS = 365

# Relevance filter (is this obligation even about this policy's area) vs. depth-of-coverage
# score (does the body actually address the specific requirement) — see module docstring.
# Coverage is a *recall* score (fraction of the obligation's own significant words found
# anywhere in the body), not a symmetric Jaccard overlap — a long, multi-section policy body
# would otherwise dilute a genuine match just by containing many other, unrelated words.
_WEAK_COVERAGE_THRESHOLD = 0.25
_STRONG_COVERAGE_THRESHOLD = 0.60

_REQUIRED_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("purpose", ("purpose",)),
    ("scope", ("scope",)),
    ("ownership", ("owner", "ownership")),
    ("responsibilities", ("responsibilit",)),
    ("controls", ("control",)),
    ("review cycle", ("review cycle", "reviewed annually", "periodic review", "review period")),
    ("exceptions", ("exception", "exemption")),
)

_OWNERSHIP_PLACEHOLDERS = frozenset({"", "tbd", "unassigned", "n/a", "na", "unknown", "todo"})

_AMBIGUOUS_PHRASES = (
    "as appropriate",
    "as needed",
    "where feasible",
    "where practicable",
    "may consider",
    "if possible",
    "from time to time",
    "best effort",
)

_FREQUENCY_WORDS = (
    "annually",
    "semi-annually",
    "quarterly",
    "monthly",
    "weekly",
    "daily",
    "biennially",
)
# Deliberately specific (not the bare word "review"): a policy body legitimately mixes
# "policy review" cadence with unrelated cadences (e.g. "access reviews are conducted
# quarterly") that must not collide with each other as a false conflict.
_CADENCE_ANCHOR_WORDS = ("reviewed", "audited", "assessed", "trained")

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
        # Generic document-naming words: nearly every policy title ends in one of these, so
        # treating them as content would make unrelated titles falsely appear "relevant".
        "policy",
        "policies",
    }
)
_WORD_RE = re.compile(r"[a-zA-Z]+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _tokenize(text: str) -> frozenset[str]:
    words = _WORD_RE.findall(text.lower())
    return frozenset(word for word in words if word not in _STOPWORDS and len(word) > 2)


def _similarity(a: str, b: str) -> float:
    """Symmetric Jaccard overlap — used only for the coarse title-vs-title relevance filter,
    where both texts are short and a symmetric measure is appropriate."""
    tokens_a, tokens_b = _tokenize(a), _tokenize(b)
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def _coverage_ratio(obligation_text: str, body_text: str) -> float:
    """What fraction of the obligation's own significant words appear anywhere in the policy
    body — a *recall* score, not Jaccard. A long, multi-section body must not be penalized
    just for containing many other words unrelated to this one obligation."""
    obligation_tokens = _tokenize(obligation_text)
    body_tokens = _tokenize(body_text)
    if not obligation_tokens or not body_tokens:
        return 0.0
    return len(obligation_tokens & body_tokens) / len(obligation_tokens)


def _policy_citation(policy: PolicyDocument) -> str:
    return f"policy:{policy.policy_id}"


def _obligation_citation(obligation: RelatedObligation) -> str:
    return f"{obligation.source_id}#{obligation.obligation_id}"


def review_policy(
    policy: PolicyDocument,
    obligations: Sequence[RelatedObligation],
    *,
    now: datetime,
) -> PolicyQualityReport:
    """Run every check and return the combined report. ``now`` is injected (not
    ``datetime.now()``) so freshness checks are deterministic and testable."""
    if now.tzinfo is None:
        raise ValueError("review_policy(now=...) must be timezone-aware")

    evaluations = [
        _evaluate(policy, obligation)
        for obligation in obligations
        if _is_relevant(policy, obligation)
    ]

    findings: list[QualityFinding] = []
    findings.extend(_check_completeness(policy))
    findings.extend(_check_internal_consistency(policy))
    findings.extend(_check_regulatory_alignment(policy, evaluations))
    findings.extend(_check_freshness(policy, evaluations, now=now))

    return PolicyQualityReport(
        policy_id=policy.policy_id,
        findings=tuple(findings),
        obligations_considered=len(obligations),
    )


# --- A) completeness ------------------------------------------------------------------------
def _check_completeness(policy: PolicyDocument) -> tuple[QualityFinding, ...]:
    body_lower = (policy.body or "").lower()
    findings: list[QualityFinding] = []
    for section_name, keywords in _REQUIRED_SECTIONS:
        if any(keyword in body_lower for keyword in keywords):
            continue
        findings.append(
            QualityFinding(
                finding_type=FindingType.MISSING_REQUIRED_SECTION,
                severity=Severity.HIGH,
                evidence=f"No {section_name!r} section was found in the policy body.",
                citation=_policy_citation(policy),
                recommendation=f"Add a clear {section_name.title()!r} section to the policy.",
                confidence=0.9,
            )
        )
    return tuple(findings)


# --- C) internal consistency ----------------------------------------------------------------
def _check_internal_consistency(policy: PolicyDocument) -> tuple[QualityFinding, ...]:
    findings: list[QualityFinding] = []

    if policy.owner_name.strip().lower() in _OWNERSHIP_PLACEHOLDERS:
        findings.append(
            QualityFinding(
                finding_type=FindingType.UNCLEAR_OWNERSHIP,
                severity=Severity.HIGH,
                evidence=f"Policy owner is {policy.owner_name!r} — not a specific role or name.",
                citation=_policy_citation(policy),
                recommendation="Assign a named owner or accountable role for this policy.",
                confidence=0.9,
            )
        )

    body = policy.body or ""
    body_lower = body.lower()
    found_phrases = [phrase for phrase in _AMBIGUOUS_PHRASES if phrase in body_lower]
    if found_phrases:
        findings.append(
            QualityFinding(
                finding_type=FindingType.AMBIGUOUS_LANGUAGE,
                severity=Severity.MEDIUM,
                evidence=f"Ambiguous phrasing found: {', '.join(found_phrases)!s}.",
                citation=_policy_citation(policy),
                recommendation="Replace vague qualifiers with specific, testable requirements.",
                confidence=min(1.0, 0.5 + 0.1 * len(found_phrases)),
            )
        )

    findings.extend(_find_conflicting_requirements(policy, body))
    return tuple(findings)


def _find_conflicting_requirements(policy: PolicyDocument, body: str) -> tuple[QualityFinding, ...]:
    anchor_frequencies: dict[str, set[str]] = {}
    for sentence in _SENTENCE_SPLIT_RE.split(body):
        lowered = sentence.lower()
        frequencies_here = {word for word in _FREQUENCY_WORDS if word in lowered}
        if not frequencies_here:
            continue
        for anchor in _CADENCE_ANCHOR_WORDS:
            if anchor in lowered:
                anchor_frequencies.setdefault(anchor, set()).update(frequencies_here)

    findings: list[QualityFinding] = []
    for anchor, frequencies in anchor_frequencies.items():
        if len(frequencies) <= 1:
            continue
        listed = " and ".join(sorted(frequencies))
        findings.append(
            QualityFinding(
                finding_type=FindingType.CONFLICTING_REQUIREMENTS,
                severity=Severity.HIGH,
                evidence=f"{listed} both appear as the stated cadence for {anchor!r}.",
                citation=_policy_citation(policy),
                recommendation=f"Reconcile the {anchor} cadence to a single, unambiguous value.",
                confidence=0.8,
            )
        )
    return tuple(findings)


# --- B) regulatory alignment + D) freshness (obligation-linked half) ------------------------
def _is_relevant(policy: PolicyDocument, obligation: RelatedObligation) -> bool:
    """A coarse relevance filter: does this obligation even belong to this policy's area?
    (title vs. title/suggested-title — the same shallow comparison Policy Hunter uses to scan
    many obligations at once, ADR-0020). Obligations that fail this never produce a finding
    here — an uncovered obligation with no relevant policy at all is Policy Hunter's job."""
    return _similarity(policy.title, obligation.suggested_policy_title) > 0.0


@dataclass(frozen=True)
class _ObligationEvaluation:
    """The one comparison every relevant obligation needs, computed once and shared between
    the regulatory-alignment and freshness checks (they classify from the same two numbers)."""

    obligation: RelatedObligation
    coverage_score: float
    obligation_is_newer: bool
    finding_type: FindingType | None


def _evaluate(policy: PolicyDocument, obligation: RelatedObligation) -> _ObligationEvaluation:
    body_text = f"{policy.title} {policy.body or ''}"
    coverage_score = _coverage_ratio(obligation.obligation_text, body_text)
    obligation_is_newer = obligation.source_document_fetched_at > policy.updated_at
    return _ObligationEvaluation(
        obligation=obligation,
        coverage_score=coverage_score,
        obligation_is_newer=obligation_is_newer,
        finding_type=_classify_alignment(coverage_score, obligation_is_newer),
    )


def _classify_alignment(coverage_score: float, obligation_is_newer: bool) -> FindingType | None:
    if coverage_score < _WEAK_COVERAGE_THRESHOLD:
        return FindingType.MISSING_CLAUSE
    if coverage_score < _STRONG_COVERAGE_THRESHOLD:
        if obligation_is_newer:
            return FindingType.OUTDATED_REFERENCE
        return FindingType.WEAK_REGULATORY_COVERAGE
    return FindingType.POLICY_OLDER_THAN_REGULATION if obligation_is_newer else None


def _check_regulatory_alignment(
    policy: PolicyDocument, evaluations: Sequence[_ObligationEvaluation]
) -> tuple[QualityFinding, ...]:
    """MISSING_CLAUSE / WEAK_REGULATORY_COVERAGE / OUTDATED_REFERENCE only —
    POLICY_OLDER_THAN_REGULATION is reported once, under freshness, not here."""
    findings: list[QualityFinding] = []
    for evaluation in evaluations:
        if (
            evaluation.finding_type is None
            or evaluation.finding_type is FindingType.POLICY_OLDER_THAN_REGULATION
        ):
            continue
        findings.append(_alignment_finding(policy, evaluation))
    return tuple(findings)


def _alignment_finding(policy: PolicyDocument, evaluation: _ObligationEvaluation) -> QualityFinding:
    obligation = evaluation.obligation
    finding_type = evaluation.finding_type
    # Callers only reach here for MISSING_CLAUSE / WEAK_REGULATORY_COVERAGE / OUTDATED_REFERENCE
    # (see _check_regulatory_alignment) — never None or POLICY_OLDER_THAN_REGULATION.
    assert finding_type is not None
    confidence = round(evaluation.coverage_score, 2)
    if finding_type is FindingType.MISSING_CLAUSE:
        evidence = f"{policy.title!r} does not address: {obligation.obligation_text!r}"
        recommendation = "Add a clause addressing this specific obligation."
        confidence = round(1.0 - evaluation.coverage_score, 2)
    elif finding_type is FindingType.WEAK_REGULATORY_COVERAGE:
        evidence = f"{policy.title!r} only partially overlaps: {obligation.obligation_text!r}"
        recommendation = "Strengthen the policy's language to fully cover this obligation."
    else:  # OUTDATED_REFERENCE
        evidence = (
            f"{policy.title!r} partially overlaps {obligation.obligation_text!r}, and the "
            f"source regulation was fetched after this policy was last updated."
        )
        recommendation = "Review this obligation's current text and update the policy's coverage."
    return QualityFinding(
        finding_type=finding_type,
        severity=Severity.HIGH if finding_type is FindingType.MISSING_CLAUSE else Severity.MEDIUM,
        evidence=evidence,
        citation=_obligation_citation(obligation),
        recommendation=recommendation,
        confidence=confidence,
        related_obligation_id=obligation.obligation_id,
    )


# --- D) freshness ----------------------------------------------------------------------------
def _check_freshness(
    policy: PolicyDocument, evaluations: Sequence[_ObligationEvaluation], *, now: datetime
) -> tuple[QualityFinding, ...]:
    findings: list[QualityFinding] = []

    age = now - policy.updated_at
    if age > timedelta(days=_STALE_POLICY_MAX_AGE_DAYS):
        findings.append(
            QualityFinding(
                finding_type=FindingType.STALE_POLICY,
                severity=Severity.MEDIUM,
                evidence=(
                    f"Policy last updated {age.days} days ago "
                    f"(max {_STALE_POLICY_MAX_AGE_DAYS})."
                ),
                citation=_policy_citation(policy),
                recommendation="Review and re-approve this policy on its scheduled cadence.",
                confidence=0.95,
            )
        )

    for evaluation in evaluations:
        if evaluation.finding_type is not FindingType.POLICY_OLDER_THAN_REGULATION:
            continue
        obligation = evaluation.obligation
        findings.append(
            QualityFinding(
                finding_type=FindingType.POLICY_OLDER_THAN_REGULATION,
                severity=Severity.MEDIUM,
                evidence=(
                    f"{policy.title!r} substantively covers {obligation.obligation_text!r}, "
                    f"but its source regulation was fetched after this policy was last updated."
                ),
                citation=_obligation_citation(obligation),
                recommendation="Re-review this policy against the current regulation text.",
                confidence=round(evaluation.coverage_score, 2),
                related_obligation_id=obligation.obligation_id,
            )
        )
    return tuple(findings)
