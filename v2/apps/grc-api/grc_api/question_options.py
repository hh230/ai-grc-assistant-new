"""One normalized view of a question's options, so nothing downstream has to ask which shape it got.

A pack question writes its options in one of two forms:

    "لا توجد سياسات"                                  a bare string — every shipped question
    {"option_id": "none", "text_ar": "لا توجد سياسات"} an object — only where a signal is declared

The second exists because a declaration is keyed by a STABLE id (ADR 0068 §D1b): revising Arabic
wording or adding a translation must not be able to move a compliance decision. The first stays
because 141 of 142 shipped questions declare nothing, and rewriting them to gain ids they will
never use would be churn with a review cost and no benefit.

Rather than let every reader branch on the shape — which is how the two forms drift apart — both
normalize to the same pair here. **A bare string's id is the string itself**, which makes the
legacy path behave exactly as it did before this module existed: the answer a customer submits is
the option text, and the text is the id, so a lookup by id finds it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Option:
    option_id: str
    text_ar: str

    @property
    def has_stable_id(self) -> bool:
        """False when the id is only the text standing in for one. A question may not declare a
        signal in that state — see `signal_declarations`."""
        return self.option_id != self.text_ar


def normalized_options(question: dict[str, Any]) -> tuple[Option, ...]:
    """Every option as `(option_id, text_ar)`, whichever form the pack used."""
    options: list[Option] = []
    for raw in question.get("options") or ():
        if isinstance(raw, dict):
            option_id = str(raw.get("option_id") or "").strip()
            text = str(raw.get("text_ar") or "").strip()
            options.append(Option(option_id=option_id or text, text_ar=text))
        else:
            text = str(raw)
            options.append(Option(option_id=text, text_ar=text))
    return tuple(options)


def option_texts(question: dict[str, Any]) -> list[str]:
    """Just the text, for the readers that only ever cared about wording — the pack linter's
    near-duplicate and multi-select heuristics, which read Arabic and nothing else."""
    return [option.text_ar for option in normalized_options(question)]
