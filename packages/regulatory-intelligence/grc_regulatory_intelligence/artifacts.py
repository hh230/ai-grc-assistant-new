"""Immutable value objects passed between the engine and its ports.

Pure stdlib dataclasses — this package depends on nothing else, not even ``grc_domain``, so
the engine can be exercised in complete isolation and any adapter (rule-based or AI-assisted)
can plug in behind the ports in ``ports.py`` without coupling back to this module.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime

from .enums import ClassificationStatus, ControlDomain, ObligationType, Severity


@dataclass(frozen=True)
class RawRegulatoryDocument:
    """One fetched regulatory document, as handed off by a connector.

    ``content_hash`` is the connector's fingerprint of ``raw_text`` (e.g. a sha256 hex
    digest) — it is what makes re-fetching the same document idempotent downstream, and it
    seeds every obligation's ``version_hash`` so re-running the pipeline never double-writes.
    """

    source_id: str
    url: str
    fetched_at: datetime
    content_hash: str
    raw_text: str

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("RawRegulatoryDocument.source_id must not be empty")
        if not self.url.strip():
            raise ValueError("RawRegulatoryDocument.url must not be empty")
        if not self.content_hash.strip():
            raise ValueError("RawRegulatoryDocument.content_hash must not be empty")
        if not self.raw_text.strip():
            raise ValueError("RawRegulatoryDocument.raw_text must not be empty")
        if self.fetched_at.tzinfo is None:
            raise ValueError("RawRegulatoryDocument.fetched_at must be timezone-aware")


@dataclass(frozen=True)
class ObligationCandidate:
    """One atomic obligation split out of a document, before classification.

    ``source_char_start``/``source_char_end`` are the half-open character offsets into the
    originating ``RawRegulatoryDocument.raw_text`` — the provenance span every downstream
    claim about this obligation cites back to (CLAUDE.md §19).
    """

    obligation_text: str
    source_char_start: int
    source_char_end: int

    def __post_init__(self) -> None:
        if not self.obligation_text.strip():
            raise ValueError("ObligationCandidate.obligation_text must not be empty")
        if self.source_char_start < 0:
            raise ValueError("ObligationCandidate.source_char_start must be >= 0")
        if self.source_char_end <= self.source_char_start:
            raise ValueError("ObligationCandidate.source_char_end must be > source_char_start")


@dataclass(frozen=True)
class ObligationClassification:
    """The classifier's judgment for one candidate, plus the provenance of that judgment."""

    obligation_type: ObligationType
    control_domain: ControlDomain
    suggested_policy_title: str
    severity: Severity
    confidence: float
    classifier_model: str | None = None
    prompt_version: str | None = None

    def __post_init__(self) -> None:
        if not self.suggested_policy_title.strip():
            raise ValueError("ObligationClassification.suggested_policy_title must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("ObligationClassification.confidence must be within [0, 1]")

    @classmethod
    def unclassified(cls, *, classifier_model: str | None = None) -> ObligationClassification:
        """The fail-safe placeholder used when a classifier could not produce a valid result
        (CLAUDE.md §16: fail safe, not open) — zero confidence, generic bucket, flagged for a
        human rather than guessed at."""
        return cls(
            obligation_type=ObligationType.OTHER,
            control_domain=ControlDomain.OTHER,
            suggested_policy_title="Unclassified obligation — needs human review",
            severity=Severity.MEDIUM,
            confidence=0.0,
            classifier_model=classifier_model,
            prompt_version=None,
        )


@dataclass(frozen=True)
class ClassifiedObligation:
    """One obligation candidate joined with its classification, ready for storage."""

    candidate: ObligationCandidate
    classification: ObligationClassification
    version_hash: str
    classification_status: ClassificationStatus = ClassificationStatus.PENDING_REVIEW


@dataclass(frozen=True)
class RegulatoryIntelligenceResult:
    """The complete output of one engine run over one document."""

    document: RawRegulatoryDocument
    obligations: tuple[ClassifiedObligation, ...] = field(default_factory=tuple)
    failed_classifications: int = 0


def compute_version_hash(document: RawRegulatoryDocument, candidate: ObligationCandidate) -> str:
    """A deterministic fingerprint of one obligation, stable across pipeline re-runs.

    Derived only from the document's content hash and the candidate's span/text — never from
    a timestamp or run id — so re-processing an unchanged document always yields the same
    hashes and a storage layer can upsert on this key instead of duplicating rows.
    """
    payload = "|".join(
        (
            document.content_hash,
            str(candidate.source_char_start),
            str(candidate.source_char_end),
            candidate.obligation_text,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
