"""Queries for the Framework capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.shared.identifiers import FrameworkId

from ..shared.messages import Query


@dataclass(frozen=True, kw_only=True)
class GetFramework(Query):
    framework_id: FrameworkId
    version: str


@dataclass(frozen=True, kw_only=True)
class ListPublishedFrameworks(Query):
    pass
