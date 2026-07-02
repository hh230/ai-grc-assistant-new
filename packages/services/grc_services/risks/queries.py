"""Queries for the Risk capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.shared.identifiers import RiskId

from ..shared.messages import Query


@dataclass(frozen=True, kw_only=True)
class GetRisk(Query):
    risk_id: RiskId


@dataclass(frozen=True, kw_only=True)
class ListRisks(Query):
    pass
