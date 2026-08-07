"""Seeding an AUTHORED knowledge pack (ADR 0067).

The generator is one source of sector questions. It is not the only one, and it is not the best
one: a pack a GRC practitioner wrote and stands behind outranks anything a model proposes. This is
the path for those — a JSON file in `knowledge_packs/`, loaded into a release exactly as written.

Two rules the generated path applies do NOT apply here, and the reasons matter:

- **No question ceiling.** The generator is capped at fifteen because that is how many questions a
  reviewer can be expected to check properly in one sitting when a model wrote them. A human who
  authored twenty-two has already done that reviewing.
- **No Arabic-only heuristic on the model's behalf.** The text is authored, not translated; there
  is no model to catch drifting into English.

What DOES still apply, and is enforced here rather than assumed:

- the schema's closed type vocabulary, checked before the insert so a bad pack names its own
  offending question instead of surfacing a constraint name;
- every question carries at least one reference and a `why_we_ask`, because a reviewer's console
  shows both and a question with neither cannot be judged;
- provenance is recorded honestly — `generated_by_model` says `authored`, not a model name that
  never ran.

The release still lands as a DRAFT. Authored is not approved: the same human gate that governs a
generated pack governs this one, because the point of the gate was never distrust of the model —
it was that somebody must be accountable for what thousands of customers are asked.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

PACKS_DIR = pathlib.Path(__file__).with_name("knowledge_packs")

# The schema's vocabulary (`release_questions_type_renderable`). Named here so a malformed pack
# fails on its own question id rather than on a constraint name from three layers down.
_QUESTION_TYPES = frozenset({"boolean", "enum", "multi_select", "numeric", "date", "text"})
_CHOICE_TYPES = frozenset({"enum", "multi_select"})
_IMPORTANCE = frozenset({"critical", "high", "medium", "low"})

AUTHORED_BY_MODEL = "authored"


class AuthoredPackRejected(ValueError):
    """The pack file is not usable. Named for the file, not for the database."""


def available_packs() -> list[str]:
    """Every industry slug with an authored pack on disk."""
    return sorted(path.name.split(".", 1)[0] for path in PACKS_DIR.glob("*.json"))


def load_pack(industry_slug: str) -> dict[str, Any]:
    """Read and validate an authored pack. Raises rather than returning something half-checked."""
    matches = sorted(PACKS_DIR.glob(f"{industry_slug}.*.json"))
    if not matches:
        raise AuthoredPackRejected(f"no authored pack for {industry_slug!r} in {PACKS_DIR.name}/")

    pack = json.loads(matches[0].read_text(encoding="utf-8"))
    if pack.get("industry_slug") != industry_slug:
        raise AuthoredPackRejected(
            f"{matches[0].name} declares industry {pack.get('industry_slug')!r}, not "
            f"{industry_slug!r} — the filename and the content must agree"
        )

    questions = pack.get("questions")
    if not isinstance(questions, list) or not questions:
        raise AuthoredPackRejected(f"{matches[0].name} has no questions")

    seen: set[str] = set()
    for index, question in enumerate(questions):
        _validate(question, index, seen, matches[0].name)
    return pack


def _validate(question: Any, index: int, seen: set[str], filename: str) -> None:
    where = f"{filename} question[{index}]"
    if not isinstance(question, dict):
        raise AuthoredPackRejected(f"{where} is not an object")

    question_id = str(question.get("question_id", "")).strip()
    if not question_id:
        raise AuthoredPackRejected(f"{where} has no question_id")
    if question_id in seen:
        raise AuthoredPackRejected(f"{where} repeats question_id {question_id!r}")
    seen.add(question_id)

    kind = str(question.get("type", ""))
    if kind not in _QUESTION_TYPES:
        raise AuthoredPackRejected(
            f"{where} ({question_id}) has type {kind!r}; the schema permits "
            f"{sorted(_QUESTION_TYPES)}"
        )
    if kind in _CHOICE_TYPES and len(question.get("options") or []) < 2:
        raise AuthoredPackRejected(f"{where} ({question_id}) is a {kind} with fewer than 2 options")
    if str(question.get("importance", "")) not in _IMPORTANCE:
        raise AuthoredPackRejected(f"{where} ({question_id}) has an unknown importance")
    if not str(question.get("canonical_text_ar", "")).strip():
        raise AuthoredPackRejected(f"{where} ({question_id}) has no canonical_text_ar")
    if not str(question.get("category", "")).strip():
        raise AuthoredPackRejected(f"{where} ({question_id}) has no category")
    if not str(question.get("why_we_ask", "")).strip():
        # The review console shows this beside the question; without it a reviewer is asked to
        # approve text with no stated reason to exist.
        raise AuthoredPackRejected(f"{where} ({question_id}) has no why_we_ask")
    if not (question.get("references") or []):
        raise AuthoredPackRejected(
            f"{where} ({question_id}) cites no framework: a question nothing requires is a "
            f"question nobody has to answer"
        )


class AuthoredPackGenerator:
    """A `QuestionGenerator` that reads the authored pack instead of calling a model.

    Same port, so `GenerateKnowledgeTemplate` needs no branch: the service still ensures the
    container, obtains questions, and mints a version. Where the questions came from is the
    generator's business, and the provenance columns record which it was.
    """

    def generate(self, *, industry_slug: str) -> list[dict[str, Any]]:
        return list(load_pack(industry_slug)["questions"])
