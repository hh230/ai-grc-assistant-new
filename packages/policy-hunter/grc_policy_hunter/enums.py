"""The gap taxonomy Policy Hunter reports findings in."""

from __future__ import annotations

from enum import Enum


class GapCategory(str, Enum):
    """Why a confirmed regulatory obligation is not (fully) covered by a tenant's policies.

    Ordered from least to most "something exists" — see ``matching.py`` for exactly how a
    finding is classified into one of these (or into no finding at all, meaning covered).
    """

    UNMAPPED_REGULATORY_OBLIGATION = "unmapped_regulatory_obligation"
    """No tenant policy shares any meaningful terms with this obligation at all — it has not
    been triaged into the tenant's policy program in any way."""

    MISSING_REQUIRED_POLICY = "missing_required_policy"
    """Some weak signal exists (the tenant's policies touch on related terms), but no policy
    substantively addresses this obligation."""

    INCOMPLETE_COVERAGE = "incomplete_coverage"
    """A policy addresses the same general area but the match is only partial — it does not
    clearly cover the specific obligation."""

    OUTDATED_POLICY = "outdated_policy"
    """A policy substantively matches this obligation, but the obligation's source regulation
    was updated more recently than the policy was last touched."""
