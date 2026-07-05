"""Unit tests for RegulatoryIntelligenceEngine: extraction, classification, per-candidate
fail-safe handling, and deterministic (idempotent) version hashing."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from grc_regulatory_intelligence import (
    ClassificationStatus,
    ControlDomain,
    ObligationCandidate,
    ObligationClassification,
    ObligationClassificationError,
    ObligationClassifierPort,
    ObligationExtractorPort,
    ObligationType,
    RawRegulatoryDocument,
    RegulatoryIntelligenceEngine,
    Severity,
    compute_version_hash,
)

_DEFAULT_RAW_TEXT = "1. Entities shall encrypt data. 2. Entities shall log access."


def _document(raw_text: str = _DEFAULT_RAW_TEXT) -> RawRegulatoryDocument:
    return RawRegulatoryDocument(
        source_id="src-nca-ecc",
        url="https://example.gov/nca-ecc",
        fetched_at=datetime(2026, 7, 5, tzinfo=timezone.utc),
        content_hash="hash-of-fixture",
        raw_text=raw_text,
    )


class StubExtractor(ObligationExtractorPort):
    def __init__(self, candidates: tuple[ObligationCandidate, ...]) -> None:
        self._candidates = candidates

    async def extract(self, document: RawRegulatoryDocument) -> tuple[ObligationCandidate, ...]:
        return self._candidates


class StubClassifier(ObligationClassifierPort):
    """Classifies deterministically by obligation text, and can be told to fail for one."""

    def __init__(self, *, fail_for_text: str | None = None) -> None:
        self._fail_for_text = fail_for_text
        self.calls: list[ObligationCandidate] = []

    async def classify(
        self, candidate: ObligationCandidate, *, document: RawRegulatoryDocument
    ) -> ObligationClassification:
        self.calls.append(candidate)
        if candidate.obligation_text == self._fail_for_text:
            raise ObligationClassificationError("malformed classifier output")
        return ObligationClassification(
            obligation_type=ObligationType.REQUIREMENT,
            control_domain=ControlDomain.DATA_PROTECTION,
            suggested_policy_title="Data Encryption Policy",
            severity=Severity.HIGH,
            confidence=0.9,
            classifier_model="stub-model",
            prompt_version="classify_regulatory_obligation.v1",
        )


def _candidates() -> tuple[ObligationCandidate, ...]:
    return (
        ObligationCandidate(
            obligation_text="Entities shall encrypt data.", source_char_start=3, source_char_end=31
        ),
        ObligationCandidate(
            obligation_text="Entities shall log access.", source_char_start=35, source_char_end=61
        ),
    )


async def test_run_splits_and_classifies_every_candidate() -> None:
    document = _document()
    classifier = StubClassifier()
    engine = RegulatoryIntelligenceEngine(
        extractor=StubExtractor(_candidates()), classifier=classifier
    )

    result = await engine.run(document)

    assert len(result.obligations) == 2
    assert len(classifier.calls) == 2
    assert result.failed_classifications == 0
    for obligation in result.obligations:
        assert obligation.classification.obligation_type == ObligationType.REQUIREMENT
        assert obligation.classification.confidence == 0.9
        # Never auto-confirmed — always starts pending a human review (CLAUDE.md §1).
        assert obligation.classification_status == ClassificationStatus.PENDING_REVIEW


async def test_run_is_deterministic_and_idempotent_via_version_hash() -> None:
    document = _document()
    engine = RegulatoryIntelligenceEngine(
        extractor=StubExtractor(_candidates()), classifier=StubClassifier()
    )

    first = await engine.run(document)
    second = await engine.run(document)

    first_hashes = [o.version_hash for o in first.obligations]
    second_hashes = [o.version_hash for o in second.obligations]
    assert first_hashes == second_hashes
    assert len(set(first_hashes)) == 2  # distinct candidates hash distinctly

    # The hash is computed the same way independently, by construction (used for upserts).
    for candidate, expected_hash in zip(_candidates(), first_hashes, strict=True):
        assert compute_version_hash(document, candidate) == expected_hash


async def test_classifier_failure_for_one_candidate_does_not_abort_the_run() -> None:
    document = _document()
    candidates = _candidates()
    classifier = StubClassifier(fail_for_text=candidates[1].obligation_text)
    engine = RegulatoryIntelligenceEngine(
        extractor=StubExtractor(candidates), classifier=classifier
    )

    result = await engine.run(document)

    assert len(result.obligations) == 2
    assert result.failed_classifications == 1
    failed_obligation = result.obligations[1]
    assert failed_obligation.classification.obligation_type == ObligationType.OTHER
    assert failed_obligation.classification.confidence == 0.0
    assert failed_obligation.classification_status == ClassificationStatus.PENDING_REVIEW
    # The successful sibling is unaffected.
    assert result.obligations[0].classification.confidence == 0.9


async def test_run_with_no_candidates_returns_an_empty_result() -> None:
    document = _document()
    engine = RegulatoryIntelligenceEngine(extractor=StubExtractor(()), classifier=StubClassifier())

    result = await engine.run(document)

    assert result.obligations == ()
    assert result.failed_classifications == 0


def test_raw_regulatory_document_requires_timezone_aware_fetched_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        RawRegulatoryDocument(
            source_id="s",
            url="https://example.gov",
            fetched_at=datetime(2026, 7, 5),  # naive
            content_hash="h",
            raw_text="text",
        )


def test_obligation_candidate_rejects_invalid_span() -> None:
    with pytest.raises(ValueError, match="source_char_end"):
        ObligationCandidate(obligation_text="x", source_char_start=5, source_char_end=5)


def test_obligation_classification_rejects_out_of_range_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        ObligationClassification(
            obligation_type=ObligationType.REQUIREMENT,
            control_domain=ControlDomain.OTHER,
            suggested_policy_title="x",
            severity=Severity.LOW,
            confidence=1.5,
        )
