"""Aggregate root for the Policies bounded context.

The lifecycle encodes a human-in-the-loop review/approval flow: a policy cannot be
published without first being approved by a qualified person.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..frameworks.value_objects import FrameworkControlRef
from ..shared.entity import AggregateRoot
from ..shared.identifiers import ControlId, OrganizationId, PolicyId, UserId
from ..shared.value_objects import Citation
from .enums import PolicyStatus
from .events import (
    PolicyApproved,
    PolicyDrafted,
    PolicyPublished,
    PolicyRetired,
    PolicySubmittedForReview,
)
from .exceptions import IllegalPolicyTransition
from .value_objects import PolicyBody, PolicyVersion


@dataclass(kw_only=True, eq=False)
class Policy(AggregateRoot):
    id: PolicyId
    organization_id: OrganizationId
    title: str
    body: PolicyBody
    owner_id: UserId
    status: PolicyStatus = PolicyStatus.DRAFT
    version: PolicyVersion = field(default_factory=lambda: PolicyVersion(1))
    approved_by: UserId | None = None
    linked_control_ids: set[ControlId] = field(default_factory=set)
    framework_controls: set[FrameworkControlRef] = field(default_factory=set)
    citations: tuple[Citation, ...] = field(default_factory=tuple)

    @classmethod
    def draft(
        cls,
        *,
        id: PolicyId,
        organization_id: OrganizationId,
        title: str,
        body: PolicyBody,
        owner_id: UserId,
        citations: tuple[Citation, ...] = (),
    ) -> Policy:
        if not title.strip():
            raise ValueError("Policy title must not be empty")
        policy = cls(
            id=id,
            organization_id=organization_id,
            title=title,
            body=body,
            owner_id=owner_id,
            citations=citations,
        )
        policy._record_event(PolicyDrafted(policy_id=id, organization_id=organization_id))
        return policy

    def submit_for_review(self) -> None:
        if self.status is not PolicyStatus.DRAFT:
            raise IllegalPolicyTransition("Only a draft policy can be submitted for review")
        self.status = PolicyStatus.IN_REVIEW
        self._record_event(PolicySubmittedForReview(policy_id=self.id))

    def approve(self, *, approver_id: UserId) -> None:
        if self.status is not PolicyStatus.IN_REVIEW:
            raise IllegalPolicyTransition("Only a policy in review can be approved")
        self.status = PolicyStatus.APPROVED
        self.approved_by = approver_id
        self._record_event(PolicyApproved(policy_id=self.id, approved_by=approver_id))

    def publish(self) -> None:
        if self.status is not PolicyStatus.APPROVED:
            raise IllegalPolicyTransition("Only an approved policy can be published")
        self.status = PolicyStatus.PUBLISHED
        self._record_event(PolicyPublished(policy_id=self.id))

    def retire(self) -> None:
        if self.status is not PolicyStatus.PUBLISHED:
            raise IllegalPolicyTransition("Only a published policy can be retired")
        self.status = PolicyStatus.RETIRED
        self._record_event(PolicyRetired(policy_id=self.id))

    def revise(self, *, new_body: PolicyBody) -> None:
        """Start a new draft revision from a published/approved policy."""
        self.body = new_body
        self.version = self.version.next()
        self.status = PolicyStatus.DRAFT
        self.approved_by = None
        self._record_event(
            PolicyDrafted(policy_id=self.id, organization_id=self.organization_id)
        )
