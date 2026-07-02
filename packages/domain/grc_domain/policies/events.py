"""Domain events for the Policies bounded context."""
from __future__ import annotations

from dataclasses import dataclass

from ..shared.events import DomainEvent
from ..shared.identifiers import OrganizationId, PolicyId, UserId


@dataclass(frozen=True, kw_only=True)
class PolicyDrafted(DomainEvent):
    policy_id: PolicyId
    organization_id: OrganizationId


@dataclass(frozen=True, kw_only=True)
class PolicySubmittedForReview(DomainEvent):
    policy_id: PolicyId


@dataclass(frozen=True, kw_only=True)
class PolicyApproved(DomainEvent):
    policy_id: PolicyId
    approved_by: UserId


@dataclass(frozen=True, kw_only=True)
class PolicyPublished(DomainEvent):
    policy_id: PolicyId


@dataclass(frozen=True, kw_only=True)
class PolicyRetired(DomainEvent):
    policy_id: PolicyId
