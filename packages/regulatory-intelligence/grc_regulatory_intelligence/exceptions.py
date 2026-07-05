"""Exceptions raised by the pure Regulatory Intelligence engine."""

from __future__ import annotations


class RegulatoryIntelligenceError(Exception):
    """Base class for every error this package raises."""


class ObligationClassificationError(RegulatoryIntelligenceError):
    """Raised by an ``ObligationClassifierPort`` adapter when it cannot produce a valid,
    schema-conformant classification for a candidate (e.g. malformed or unsupported LLM
    output). The engine catches this per-candidate and fails safe (CLAUDE.md §16) rather than
    aborting the whole document — see ``RegulatoryIntelligenceEngine``.
    """
