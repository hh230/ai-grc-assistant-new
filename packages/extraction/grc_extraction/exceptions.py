"""Errors for the extraction engine's application layer (registries, profiles, pipeline)."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grc_domain.extraction import ExtractionError
    from grc_domain.shared.identifiers import ExtractionRunId


class ExtractionEngineError(Exception):
    """Base class for extraction-engine application errors."""


class PipelineError(ExtractionEngineError):
    """Raised when a pipeline run fails. The ``ExtractionRun`` is left FAILED (fail-safe) and
    carries the structured stage error, so the caller can persist and later resume it."""

    def __init__(self, run_id: ExtractionRunId, error: ExtractionError) -> None:
        super().__init__(
            f"Extraction run {run_id} failed at stage {error.stage.value}: {error.message}"
        )
        self.run_id = run_id
        self.error = error


class RegistryError(ExtractionEngineError):
    """Base class for extractor/profile registry errors."""


class DuplicateExtractorError(RegistryError):
    """Raised when registering an extractor whose (name, version) is already registered."""


class UnknownExtractorError(RegistryError):
    """Raised when resolving an extractor that is not registered."""


class DuplicateProfileError(RegistryError):
    """Raised when registering a profile whose (document_type, version) already exists."""


class UnknownProfileError(RegistryError):
    """Raised when requesting a profile that is not registered."""
