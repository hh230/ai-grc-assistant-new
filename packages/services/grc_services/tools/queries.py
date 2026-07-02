"""Queries for the Tool Management capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.shared.identifiers import ToolId

from ..shared.messages import Query


@dataclass(frozen=True, kw_only=True)
class GetTool(Query):
    tool_id: ToolId


@dataclass(frozen=True, kw_only=True)
class ListActiveTools(Query):
    pass
