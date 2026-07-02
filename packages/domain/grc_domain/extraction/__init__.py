"""Knowledge Extraction bounded context — the engine's pure domain model.

The engine turns raw documents into canonical Knowledge Objects. This package holds only the
domain core: the ``ExtractionRun`` aggregate and its lifecycle, the ``StageExecution``
checkpoint, the output value objects (``ExtractionCandidate`` / ``CandidateRelationship``)
that map 1:1 onto the Knowledge Domain, and the repository interface.

Pure domain: no document adapters, OCR, normalization libraries, LLMs, or persistence — those
are ports/adapters in outer layers. This context depends on ``knowledge`` (it produces that
context's objects) and never the reverse.
"""
from __future__ import annotations

from .entities import ExtractionRun, StageExecution
from .enums import ExtractionRunStatus, ExtractionStage, StageStatus
from .exceptions import (
    IllegalExtractionRunTransition,
    IllegalStageTransition,
    StageExecutionNotFound,
)
from .repositories import ExtractionRunRepository
from .value_objects import (
    CandidateRelationship,
    ExtractionCandidate,
    ExtractionError,
    RawDocumentDescriptor,
)

__all__ = [
    # aggregate / entity
    "ExtractionRun",
    "StageExecution",
    # value objects
    "RawDocumentDescriptor",
    "ExtractionError",
    "ExtractionCandidate",
    "CandidateRelationship",
    # enums
    "ExtractionRunStatus",
    "ExtractionStage",
    "StageStatus",
    # exceptions
    "IllegalExtractionRunTransition",
    "IllegalStageTransition",
    "StageExecutionNotFound",
    # repository interface
    "ExtractionRunRepository",
]
