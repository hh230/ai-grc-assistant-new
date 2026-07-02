"""Enumerations for the Evidence bounded context."""
from __future__ import annotations

from enum import Enum


class EvidenceType(str, Enum):
    DOCUMENT = "document"
    SCREENSHOT = "screenshot"
    LOG = "log"
    CONFIGURATION = "configuration"
    ATTESTATION = "attestation"
    TICKET = "ticket"
    SCAN_RESULT = "scan_result"


class EvidenceStatus(str, Enum):
    COLLECTED = "collected"
    VALIDATED = "validated"
    EXPIRED = "expired"
    REJECTED = "rejected"
