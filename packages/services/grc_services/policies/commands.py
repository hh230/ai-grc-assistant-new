"""Commands for the Policy capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.shared.identifiers import PolicyId

from ..shared.messages import Command


@dataclass(frozen=True, kw_only=True)
class DraftPolicy(Command):
    title: str
    body_text: str


@dataclass(frozen=True, kw_only=True)
class SubmitPolicyForReview(Command):
    policy_id: PolicyId


@dataclass(frozen=True, kw_only=True)
class ApprovePolicy(Command):
    policy_id: PolicyId


@dataclass(frozen=True, kw_only=True)
class PublishPolicy(Command):
    policy_id: PolicyId


@dataclass(frozen=True, kw_only=True)
class RetirePolicy(Command):
    policy_id: PolicyId
