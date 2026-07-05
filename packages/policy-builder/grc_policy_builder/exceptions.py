"""Exceptions raised by Policy Builder."""

from __future__ import annotations


class PolicyBuilderError(Exception):
    """Base class for every error this package raises."""


class ObligationNotFoundError(PolicyBuilderError):
    """The ``obligation_id`` given to ``draft_policy_from_obligation`` does not resolve to a
    confirmed obligation — either it does not exist, or it exists but is not yet ``confirmed``
    (``pending_review``/``rejected`` obligations are treated identically to absent ones: Policy
    Builder only ever drafts from the same confirmed evidence Policy Hunter and Policy Analyst
    already rely on)."""
