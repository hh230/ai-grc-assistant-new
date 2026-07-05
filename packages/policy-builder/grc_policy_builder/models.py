"""Value objects for the Policy Builder drafting engine.

Deliberately independent of ``grc_persistence_web`` types — the Tool in ``tools.py``
translates a concrete record into ``ObligationForDrafting`` at the boundary (CLAUDE.md §15),
which is what keeps ``drafting.py`` a pure function of plain data, exactly the same pattern
``grc_policy_hunter``/``grc_policy_analyst`` already established.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ObligationForDrafting:
    """One confirmed regulatory obligation, with enough of its source's provenance to cite —
    the only input the drafting engine ever sees. Policy Builder never reads a tenant's
    existing policies: whether this obligation is already covered is Policy Hunter's
    question, not this package's (CLAUDE.md §15 boundary, ADR-0024)."""

    obligation_id: str
    obligation_text: str
    control_domain: str
    suggested_policy_title: str
    source_id: str
    source_url: str

    def __post_init__(self) -> None:
        if not self.obligation_id.strip():
            raise ValueError("ObligationForDrafting.obligation_id must not be empty")
        if not self.obligation_text.strip():
            raise ValueError("ObligationForDrafting.obligation_text must not be empty")
        if not self.suggested_policy_title.strip():
            raise ValueError("ObligationForDrafting.suggested_policy_title must not be empty")


@dataclass(frozen=True)
class PolicyDraft:
    """A proposed starter policy — never persisted by this package. Every substantive claim
    traces to ``citation``; every section the engine cannot responsibly fill in on its own
    is listed in ``sections_requiring_human_input`` and rendered as an explicit placeholder
    in ``body``, never invented text (CLAUDE.md §1, §19)."""

    obligation_id: str
    title: str
    body: str
    citation: str
    sections_requiring_human_input: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("PolicyDraft.title must not be empty")
        if not self.body.strip():
            raise ValueError("PolicyDraft.body must not be empty")
