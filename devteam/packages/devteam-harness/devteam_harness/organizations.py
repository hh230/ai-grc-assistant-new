"""Deterministic synthetic organizations.

Everything a scenario needs is derived from one integer seed, so a failing run is fully
reproducible from its seed alone — no fixtures to keep in sync, no recorded transcripts to rot
when the interview changes. `faker` is deliberately not used: the interview never reads a company
name, so realistic-looking prose would add a dependency and buy nothing. What actually varies the
system's behaviour is the *posture* — how the organization answers — so that is what is modelled.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum


class Posture(str, Enum):
    """How an organization tends to answer when a question admits a range.

    This is the axis that genuinely changes engine behaviour: an `ABSENT` org activates
    remediation-heavy paths and low maturity scores, a `MATURE` org activates the opposite, and
    `MIXED` produces the messy middle where most real regressions hide.
    """

    ABSENT = "absent"
    MIXED = "mixed"
    MATURE = "mature"


@dataclass(frozen=True)
class SyntheticOrganization:
    """A generated organization. `tenant_id` is derived from the seed so two scenarios can never
    collide, which is what makes tenant-isolation invariants meaningful."""

    seed: int
    tenant_id: str
    posture: Posture
    # Bias applied to yes/no questions: probability of answering True.
    affirmative_bias: float
    # Drives numeric answers (employee count and similar magnitude questions).
    size: int
    # When True, optional questions get skipped rather than answered — exercises the skip path.
    skips_optional: bool

    @property
    def label(self) -> str:
        return f"org-{self.seed:06d}-{self.posture.value}"


def generate_organization(seed: int) -> SyntheticOrganization:
    """Build one organization from a seed. Pure and deterministic: same seed, same org."""
    rng = random.Random(seed)
    posture = rng.choice(tuple(Posture))
    affirmative_bias = {
        Posture.ABSENT: 0.15,
        Posture.MIXED: 0.5,
        Posture.MATURE: 0.85,
    }[posture]
    return SyntheticOrganization(
        seed=seed,
        tenant_id=f"harness-{seed:08d}",
        posture=posture,
        affirmative_bias=affirmative_bias,
        # Spans the size bands the interview branches on, from sole trader to enterprise.
        size=rng.choice((1, 8, 45, 260, 1200, 7500)),
        skips_optional=rng.random() < 0.3,
    )


def generate_organizations(count: int, *, start_seed: int = 0) -> list[SyntheticOrganization]:
    """A reproducible population. Seeds are contiguous so a run is described by a range."""
    return [generate_organization(start_seed + i) for i in range(count)]
