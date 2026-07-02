"""Queries for the Knowledge capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.shared.identifiers import KnowledgeSourceId

from ..shared.messages import Query


@dataclass(frozen=True, kw_only=True)
class GetKnowledgeSource(Query):
    source_id: KnowledgeSourceId


@dataclass(frozen=True, kw_only=True)
class ListKnowledgeSources(Query):
    pass
