"""Queries for the Policy capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.shared.identifiers import PolicyId

from ..shared.messages import Query


@dataclass(frozen=True, kw_only=True)
class GetPolicy(Query):
    policy_id: PolicyId


@dataclass(frozen=True, kw_only=True)
class ListPolicies(Query):
    pass
