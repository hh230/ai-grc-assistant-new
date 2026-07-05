"""Exceptions raised by Policy Analyst."""

from __future__ import annotations


class PolicyAnalystError(Exception):
    """Base class for every error this package raises."""


class PolicyNotFoundError(PolicyAnalystError):
    """The tenant/policy_id pair given to ``review_policy_quality`` does not exist."""
