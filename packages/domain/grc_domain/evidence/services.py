"""Domain services for the Evidence bounded context.

`EvidenceValidityService` is pure: it answers whether evidence is valid at a moment, based
on its validity window. No I/O.
"""
from __future__ import annotations

from datetime import datetime

from .entities import Evidence


class EvidenceValidityService:
    @staticmethod
    def is_valid_at(evidence: Evidence, moment: datetime) -> bool:
        if evidence.validity is None:
            return True
        return evidence.validity.contains(moment)
