"""Enums for Autonomous Knowledge Research (KI-P2)."""

from __future__ import annotations

from enum import Enum


class AttemptOutcome(str, Enum):
    """What happened when the coordinator tried one candidate document against one question."""

    GROUNDED = "grounded"
    NOT_GROUNDED = "not_grounded"
    FETCH_FAILED = "fetch_failed"
    DISCOVERY_FAILED = "discovery_failed"


class ResearchStatus(str, Enum):
    """The overall verdict for one research run: did any candidate source ground an answer?"""

    FOUND = "found"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
