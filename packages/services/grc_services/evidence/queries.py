"""Queries for the Evidence capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.shared.identifiers import ControlId, EvidenceId

from ..shared.messages import Query


@dataclass(frozen=True, kw_only=True)
class GetEvidence(Query):
    evidence_id: EvidenceId


@dataclass(frozen=True, kw_only=True)
class ListEvidenceForControl(Query):
    control_id: ControlId
