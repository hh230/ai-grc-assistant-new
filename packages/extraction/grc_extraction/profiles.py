"""Extraction profiles and their registry.

A profile is configuration/data selected by document type: which grammar to segment with,
which extractors to run (by reference), confidence thresholds, and language defaults. Adding
a new document type or regulator is a new profile — no engine change. Profiles and the
registry are pure (no I/O).
"""
from __future__ import annotations

from dataclasses import dataclass

from grc_domain.knowledge import DocumentType

from .exceptions import DuplicateProfileError, UnknownProfileError


@dataclass(frozen=True)
class ExtractorRef:
    """A reference to an extractor by name (and optional pinned version; None = latest)."""

    name: str
    version: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("ExtractorRef name must not be empty")
        if self.version is not None and not self.version.strip():
            raise ValueError("ExtractorRef version, if provided, must not be empty")


@dataclass(frozen=True)
class ConfidenceThresholds:
    """Per-profile policy for routing candidates by confidence.

    ``auto_accept_at`` and above may be auto-published (per object type/scope policy); below
    ``review_below`` goes to human review; at or below ``discard_below`` is dropped.
    """

    auto_accept_at: float = 0.75
    review_below: float = 0.75
    discard_below: float = 0.0

    def __post_init__(self) -> None:
        for name, value in (
            ("auto_accept_at", self.auto_accept_at),
            ("review_below", self.review_below),
            ("discard_below", self.discard_below),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"ConfidenceThresholds {name} must be within [0, 1]")
        if self.discard_below > self.review_below:
            raise ValueError("discard_below must not exceed review_below")


@dataclass(frozen=True)
class ExtractionProfile:
    """Document-type extraction configuration (data, not code)."""

    document_type: DocumentType
    version: str
    grammar_ref: str
    extractor_refs: tuple[ExtractorRef, ...]
    thresholds: ConfidenceThresholds = ConfidenceThresholds()
    default_language: str | None = None
    relationship_extractor_refs: tuple[ExtractorRef, ...] = ()

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("ExtractionProfile version must not be empty")
        if not self.grammar_ref.strip():
            raise ValueError("ExtractionProfile grammar_ref must not be empty")
        if not self.extractor_refs:
            raise ValueError("ExtractionProfile must reference at least one extractor")

    @property
    def key(self) -> tuple[DocumentType, str]:
        return (self.document_type, self.version)


class ProfileRegistry:
    """In-memory registry of extraction profiles, keyed by (document_type, version)."""

    def __init__(self) -> None:
        self._profiles: dict[tuple[DocumentType, str], ExtractionProfile] = {}
        self._latest: dict[DocumentType, ExtractionProfile] = {}

    def register(self, profile: ExtractionProfile) -> None:
        if profile.key in self._profiles:
            raise DuplicateProfileError(
                f"Profile already registered: {profile.document_type.value} v{profile.version}"
            )
        self._profiles[profile.key] = profile
        # Last registration for a document type is treated as its latest.
        self._latest[profile.document_type] = profile

    def get(self, document_type: DocumentType, version: str | None = None) -> ExtractionProfile:
        if version is not None:
            profile = self._profiles.get((document_type, version))
            if profile is None:
                raise UnknownProfileError(f"No profile for {document_type.value} v{version}")
            return profile
        latest = self._latest.get(document_type)
        if latest is None:
            raise UnknownProfileError(f"No profile registered for {document_type.value}")
        return latest

    def list(self) -> tuple[ExtractionProfile, ...]:
        return tuple(self._profiles.values())
