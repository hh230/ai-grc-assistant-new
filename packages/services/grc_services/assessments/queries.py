"""Queries for the Assessment capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.shared.identifiers import AssessmentId

from ..shared.messages import Query


@dataclass(frozen=True, kw_only=True)
class GetAssessment(Query):
    assessment_id: AssessmentId


@dataclass(frozen=True, kw_only=True)
class ListAssessments(Query):
    pass
