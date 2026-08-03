"""The answer strategy — the design decision the whole harness rests on.

The interview is **adaptive**: which question comes next depends on every answer so far, and the
question set changes whenever a Knowledge Pack changes. So a harness must never replay a recorded
script — a recorded script would silently stop covering the real tree the day someone adds a
question, which is precisely the regression we are trying to catch.

Instead this answers whatever arrives, driven only by the question's declared `value_type`,
`options`, and `required` flag. Adding a new question to a pack therefore needs **zero** harness
changes and is exercised on the very next run. Answers stay deterministic per (organization,
question), so a failure reproduces exactly from its seed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from governance_discovery.pack import Question
from governance_discovery.signal import ValueType

from devteam_harness.organizations import SyntheticOrganization

# Returned instead of a value to mean "skip this question" — only ever legal for optional ones.
SKIP = object()


@dataclass(frozen=True)
class AnswerStrategy:
    """Answers any question the engine can emit, deterministically for a given organization."""

    organization: SyntheticOrganization

    def _rng(self, question: Question) -> random.Random:
        """Per-question RNG seeded by (org seed, question id) — so the same organization always
        answers the same question identically, regardless of the order questions arrive in or how
        many other questions exist. Order-independence is what keeps a replayed seed stable when
        the pack changes shape."""
        return random.Random(f"{self.organization.seed}:{question.id}")

    def answer(self, question: Question) -> object:
        """Return a value for `question`, or `SKIP` for an optional question this org skips."""
        if not question.required and self.organization.skips_optional:
            return SKIP

        rng = self._rng(question)
        options = question.options or ()

        if question.value_type is ValueType.BOOLEAN:
            return rng.random() < self.organization.affirmative_bias

        if question.value_type is ValueType.ENUM:
            if not options:
                # A malformed enum question (no options) is a real defect worth surfacing loudly
                # rather than silently guessing a value.
                raise ValueError(f"enum question {question.id!r} declares no options")
            chosen = self._choose_enum(question, options, rng)
            return [chosen] if question.allow_multiple else chosen

        if question.value_type in (ValueType.NUMERIC, ValueType.PERCENTAGE):
            if question.value_type is ValueType.PERCENTAGE:
                return rng.randint(0, 100)
            return self.organization.size

        if question.value_type is ValueType.DATE:
            # Deterministic, always in the past, always a valid calendar date.
            return f"{rng.randint(2019, 2025):04d}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"

        # TEXT and EVIDENCE_BACKED both accept free text; it is captured as context and never
        # gates control flow, so any stable string is a faithful answer.
        return f"harness note for {question.id}"

    def _choose_enum(
        self, question: Question, options: tuple[str, ...], rng: random.Random
    ) -> str:
        """Pick an option biased by posture.

        Options are treated as an ordered scale (the packs' maturity scales are declared
        low->high), so an ABSENT org leans to the first options and a MATURE org to the last.
        For unordered option sets this degrades to a stable arbitrary pick, which is still valid.
        """
        bias = self.organization.affirmative_bias
        # Map bias onto the option list, then jitter by one step so a posture explores its
        # neighbourhood instead of pinning to a single option forever.
        target = int(bias * (len(options) - 1))
        jitter = rng.choice((-1, 0, 0, 1))
        return options[max(0, min(len(options) - 1, target + jitter))]
