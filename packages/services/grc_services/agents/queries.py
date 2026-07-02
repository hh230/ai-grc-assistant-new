"""Queries for the Agent Management capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.shared.identifiers import AgentId

from ..shared.messages import Query


@dataclass(frozen=True, kw_only=True)
class GetAgent(Query):
    agent_id: AgentId


@dataclass(frozen=True, kw_only=True)
class ListActiveAgents(Query):
    pass
