"""The Answer Validation Engine — deterministic, structural validation of a generated answer.

It answers one question: *is this generated answer well-formed and honestly grounded in the
context it was given?* It checks the answer text against the `ContextPackage` (the citable
evidence), the citations embedded in the text ([S1], [S2], … — the marker style the Prompt
Orchestrator renders), and the `ResponseContract` (what this workflow required).

Hard boundaries (Phase 13):
  • it never generates, retrieves, or extracts citations from the model;
  • it never mutates the `Answer` — the confidence change it reports is a *suggestion*;
  • it makes no semantic judgement (no LLM-as-judge, no reviewer) — only deterministic,
    reproducible structural checks. Semantic prohibitions in `forbidden_outputs` are
    guidance to the model, not something a string match can adjudicate, so they are not
    flagged here (that belongs to a future reviewer phase).
"""

from __future__ import annotations

import re

from pipeline_contracts import Answer, ContextPackage, ResponseContract

from answer_validation.models import (
    ConfidencePenalty,
    ValidatedAnswer,
    ValidationCode,
    ValidationIssue,
    ValidationSeverity,
    ValidationStatus,
    default_severity,
)

# Any bracketed token that starts with S and looks like a source marker. Well-formed markers
# match _WELL_FORMED; anything else caught here is malformed.
_SOURCE_MARKER = re.compile(r"\[\s*S[^\]]*\]", re.IGNORECASE)
_WELL_FORMED = re.compile(r"^\[S(\d+)\]$")
_ALLOWED_CONFIDENCE = {"high", "medium", "low"}
# A labelled confidence statement: "Confidence: high", "confidence level — medium", etc.
_CONFIDENCE_VALUE = re.compile(
    r"confidence(?:\s*level)?\s*(?:is|:|-|—|=)\s*\*{0,2}([A-Za-z0-9.]+)", re.IGNORECASE
)
_CONFIDENCE_WORD = re.compile(r"\b(high|medium|low)\b", re.IGNORECASE)


class AnswerValidator:
    """Validates one `Answer` against its `ContextPackage` and `ResponseContract`. Stateless
    and deterministic — the same inputs always yield the same `ValidatedAnswer`. The penalty
    policy is injectable so the confidence-adjustment weights stay explicit."""

    def __init__(self, *, penalty: ConfidencePenalty | None = None) -> None:
        self._penalty = penalty or ConfidencePenalty()

    def validate(
        self,
        answer: Answer,
        *,
        context: ContextPackage | None = None,
        contract: ResponseContract | None = None,
    ) -> ValidatedAnswer:
        issues: list[ValidationIssue] = []
        text = answer.text or ""

        # 1. empty answer — nothing else is meaningful once this fires.
        if not text.strip():
            issues.append(self._issue(ValidationCode.EMPTY_ANSWER, "the answer is empty"))
            return self._assemble(answer, issues)

        block_count = len(context.all_blocks()) if context is not None else 0
        cited, malformed = self._scan_citations(text)

        # 2. malformed citation markers.
        for marker in malformed:
            issues.append(self._issue(
                ValidationCode.MALFORMED_CITATION,
                f"citation marker {marker} is not the required [S<n>] form",
                detail=marker,
            ))

        # 3. citations that point outside the ContextPackage (fabricated / hallucinated).
        for n in sorted(cited):
            if n < 1 or n > block_count:
                issues.append(self._issue(
                    ValidationCode.UNKNOWN_CITATION,
                    f"citation [S{n}] is not present in the context "
                    f"({block_count} source block(s) available)",
                    detail=f"S{n}",
                ))

        # 4. required citations that are simply absent (only when evidence existed to cite).
        if contract is not None and contract.required_citations and block_count > 0 and not cited:
            issues.append(self._issue(
                ValidationCode.MISSING_CITATIONS,
                "citations are required for this workflow but the answer cites no source",
            ))

        # 5. confidence signal.
        if contract is not None and contract.required_confidence:
            issues.extend(self._check_confidence(text))

        # 6. required sections present as headings/labels.
        if contract is not None:
            for section in contract.required_sections:
                if not self._section_present(text, section):
                    issues.append(self._issue(
                        ValidationCode.MISSING_SECTION,
                        f"required section '{section}' is missing from the answer",
                        detail=section,
                    ))

        return self._assemble(answer, issues)

    # ── checks ────────────────────────────────────────────────────────────────
    @staticmethod
    def _scan_citations(text: str) -> tuple[set[int], list[str]]:
        """Return (well-formed source indices, malformed marker strings)."""
        cited: set[int] = set()
        malformed: list[str] = []
        for token in _SOURCE_MARKER.findall(text):
            normalized = re.sub(r"\s+", "", token)
            match = _WELL_FORMED.match(normalized)
            if match:
                cited.add(int(match.group(1)))
            else:
                malformed.append(token)
        return cited, malformed

    def _check_confidence(self, text: str) -> list[ValidationIssue]:
        stated_value: str | None = None
        for line in text.splitlines():
            if "confidence" not in line.lower():
                continue
            value_match = _CONFIDENCE_VALUE.search(line)
            if value_match:
                stated_value = value_match.group(1).lower()
                break
            word_match = _CONFIDENCE_WORD.search(line)
            if word_match:
                stated_value = word_match.group(1).lower()
                break
            stated_value = ""  # a confidence line with no recognizable value
        if stated_value is None:
            return [self._issue(
                ValidationCode.MISSING_CONFIDENCE,
                "a confidence level (high/medium/low) is required but none was stated",
            )]
        if stated_value not in _ALLOWED_CONFIDENCE:
            shown = stated_value or "(none)"
            return [self._issue(
                ValidationCode.UNSUPPORTED_CONFIDENCE,
                f"stated confidence '{shown}' is not one of high/medium/low",
                detail=shown,
            )]
        return []

    @staticmethod
    def _section_present(text: str, section: str) -> bool:
        return section.strip().lower() in text.lower()

    # ── assembly ────────────────────────────────────────────────────────────────
    @staticmethod
    def _issue(code: ValidationCode, message: str, *, detail: str = "") -> ValidationIssue:
        return ValidationIssue(
            code=code, severity=default_severity(code), message=message, detail=detail
        )

    def _assemble(self, answer: Answer, issues: list[ValidationIssue]) -> ValidatedAnswer:
        errors = [i for i in issues if i.severity is ValidationSeverity.ERROR]
        warnings = [i for i in issues if i.severity is ValidationSeverity.WARNING]
        if errors:
            status = ValidationStatus.FAILED
        elif warnings:
            status = ValidationStatus.WARNINGS
        else:
            status = ValidationStatus.PASSED
        return ValidatedAnswer(
            answer=answer,
            status=status,
            issues=tuple(issues),
            confidence_adjustment=self._confidence_adjustment(issues),
        )

    def _confidence_adjustment(self, issues: list[ValidationIssue]) -> float:
        penalty = 0.0
        for issue in issues:
            if issue.code is ValidationCode.MISSING_CITATIONS:
                penalty -= self._penalty.missing_citations
            elif issue.code is ValidationCode.UNKNOWN_CITATION:
                penalty -= self._penalty.per_unknown_citation
            elif issue.severity is ValidationSeverity.WARNING:
                penalty -= self._penalty.per_warning
        return max(self._penalty.floor, penalty)
