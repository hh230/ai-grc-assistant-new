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

import difflib
import json
import pathlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from grc_api.question_options import option_texts

PACKS_DIR = pathlib.Path(__file__).with_name("knowledge_packs")

# The schema's vocabulary (`release_questions_type_renderable`). Named here so a malformed pack
# fails on its own question id rather than on a constraint name from three layers down.
_QUESTION_TYPES = frozenset({"boolean", "enum", "multi_select", "numeric", "date", "text"})
_CHOICE_TYPES = frozenset({"enum", "multi_select"})
_IMPORTANCE = frozenset({"critical", "high", "medium", "low"})

AUTHORED_BY_MODEL = "authored"

# `re_activities_practiced`, `lg_dnfbp_activities`, `mk_regulated_sectors` — a short sector prefix
# and a readable name. Enforced because these ids are cited by every stored answer forever: a typo
# is not a typo once a customer has answered it.
_QUESTION_ID = re.compile(r"^[a-z][a-z0-9]{1,4}_[a-z][a-z0-9_]*[a-z0-9]$")

# Options that mean "several of the above apply". In a `multi_select` the customer just ticks
# several boxes, so the phrase is unnecessary; in an `enum` it is worse than unnecessary — a
# single-choice question cannot express multiplicity, so the option records THAT several apply
# while losing WHICH, and every downstream reader is left with an answer nothing can act on.
#
# This rule was learned three times before it was written down: the authored real-estate, legal and
# marketing packs each shipped one, and each was rewritten by hand. A rule discovered three times is
# a rule the machine should be checking.
_MEANS_SEVERAL = (
    "أكثر من",
    "الفئتين",
    "كلاهما",
    "كليهما",
    "جميع ما سبق",
    "كل ما سبق",
    "مزيج",
    "more than one",
    "all of the above",
    "both",
)

# "أكثر من 70%" is a QUANTITY; "أكثر من جهة" is a multiplicity. The first version of this check did
# not know the difference and reported three findings against the real-estate pack, two of them
# wrong — which is why the rule reports a warning a person reads rather than an error the machine
# enforces. A check that is wrong two times in three does not get obeyed; it gets worked around.
_FOLLOWED_BY_A_NUMBER = re.compile(r"(أكثر من|more than)\s*[\d٠-٩]")


# The SECOND shape of the same defect, and the one the first rule could not see. The IT pack was
# authored without any "أكثر من" escape at all — the author simply listed facts that co-occur
# (cloud provider, data centre, MSP, security services) under a single-choice type. Nothing tripped
# the rule, because there was no offending option to trip it; the offence was the TYPE.
#
# Two signals, both cheap and both readable in the authored text:
#   - the question asks for "أياً من" / "جميع" — grammar that anticipates several answers;
#   - several options open with the same affirmative ("نعم - …"), which is what listing separate
#     yeses looks like when they should have been separate boxes.
# "أي من" was missing until the e-commerce pack used it twice and sailed through clean. Arabic
# writes the same phrase three ways depending on case ending and whether the tanween is typed, and
# a list that carries only one spelling silently covers only one third of the authors.
_ASKS_FOR_SEVERAL = (
    "أي من",
    "أياً من",
    "أيا من",
    "جميع الخدمات",
    "جميع الفئات",
    "any of the following",
)
_AFFIRMATIVE = re.compile(r"^\s*(نعم|yes)\b")


def _reads_as_multi_select(question: dict[str, Any], options: list[str]) -> str | None:
    """Why this single-choice question looks like it should accept several answers, or None."""
    text = str(question.get("canonical_text_ar", ""))
    if any(phrase in text for phrase in _ASKS_FOR_SEVERAL):
        return "its wording asks which of several apply"
    affirmatives = [o for o in options if _AFFIRMATIVE.match(o)]
    # THREE, not two. At two the rule fired on six questions across four packs and was right about
    # roughly one: a pair of yeses is almost always a maturity distinction — "yes, with controls" /
    # "yes, without" — which is genuinely one answer or the other. Three or more is a LIST of
    # mechanisms, and a customer using two of them cannot record both.
    if len(affirmatives) >= 3:
        return f"{len(affirmatives)} of its options are separate 'نعم' answers"
    return None


def _means_several(option: str) -> bool:
    if _FOLLOWED_BY_A_NUMBER.search(option):
        return False
    return any(phrase in option for phrase in _MEANS_SEVERAL)

# Above this, two questions are reported as possibly the same question asked twice. Deliberately a
# WARNING and not an error: the measure is similarity of wording, and two genuinely different
# questions about the same subject can score high. A person decides.
_NEAR_DUPLICATE = 0.82


@dataclass(frozen=True)
class Finding:
    """One thing wrong with a pack. `error` blocks the import; `warning` is reported and imports.

    The split matters: a structural fault is a fact and the machine may refuse it, but "these two
    questions look alike" is a judgement, and a validator that blocks on judgement teaches people
    to work around the validator.
    """

    severity: str
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.where}: {self.message}"


def _normalise(text: str) -> str:
    """Arabic text reduced to what two questions would share if they asked the same thing:
    diacritics, tatweel, punctuation and alef/ya/ta-marbuta spelling variants removed."""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\u064B-\u0652\u0640]", "", text)   # harakat + tatweel
    text = re.sub(r"[إأآا]", "ا", text)
    text = re.sub(r"[ىي]", "ي", text)
    text = text.replace("ة", "ه")
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


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
    _validate_declarations(questions, matches[0].name)
    return pack


def _validate_declarations(questions: list[Any], filename: str) -> None:
    """A pack may declare which engine signal an answer writes (ADR 0068). Checked HERE, at the
    file boundary, so an invalid declaration never reaches the repository — the repository carries
    the two columns and interprets neither.

    Import-time and not write-time on purpose: the caller has the option list in hand here, which
    is what makes "every option has a declared value" checkable at all.
    """
    from grc_api.signal_declarations import validate_pack_declarations

    errors = validate_pack_declarations({"questions": questions})
    if errors:
        raise AuthoredPackRejected(
            f"{filename}: invalid signal declaration — " + "; ".join(str(e) for e in errors[:3])
        )


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


def reachable_slugs() -> frozenset[str]:
    """The sector slugs a customer can actually choose, read from the discovery interview itself.

    Read rather than restated: a second copy of this list would be right on the day it was written
    and wrong on the day somebody added a sector to the interview.
    """
    try:
        from governance_discovery.pack import load_bundled_packs

        for pack in load_bundled_packs().values():
            for question in pack.questions:
                if question.writes_signal == "primary_activity" and question.options:
                    return frozenset(question.options)
    except Exception:  # noqa: BLE001 — the reachability check is a courtesy, not a gate
        return frozenset()
    return frozenset()


def lint_pack(industry_slug: str) -> list[Finding]:
    """Every problem in a pack, rather than the first one.

    `load_pack` raises on the first error because a caller about to import needs a decision, not a
    report. An author needs the opposite: the whole list, so one pass of edits fixes everything.
    """
    matches = sorted(PACKS_DIR.glob(f"{industry_slug}.*.json"))
    if not matches:
        return [Finding("error", industry_slug, f"no authored pack in {PACKS_DIR.name}/")]

    name = matches[0].name
    try:
        pack = json.loads(matches[0].read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [Finding("error", name, f"is not valid JSON — {exc}")]

    findings: list[Finding] = []
    if pack.get("industry_slug") != industry_slug:
        findings.append(
            Finding("error", name, f"declares industry {pack.get('industry_slug')!r}, not {industry_slug!r}")
        )

    reachable = reachable_slugs()
    if reachable and industry_slug not in reachable:
        # The failure this catches is entirely silent: the pack imports, is approved, published and
        # activated without complaint, and then reaches nobody, because no customer can select a
        # sector the interview never offers. Nothing downstream would ever report it.
        findings.append(
            Finding(
                "error",
                name,
                f"{industry_slug!r} is not an option in the interview's primary_activity question, "
                f"so no customer can ever be routed to this pack. Choose one of: "
                f"{', '.join(sorted(reachable))}",
            )
        )

    questions = pack.get("questions")
    if not isinstance(questions, list) or not questions:
        findings.append(Finding("error", name, "has no questions"))
        return findings

    seen: set[str] = set()
    for index, question in enumerate(questions):
        findings.extend(_lint_question(question, index, seen, name))
    findings.extend(_lint_across_questions(questions, name))
    return findings


def _lint_question(question: Any, index: int, seen: set[str], filename: str) -> list[Finding]:
    where = f"{filename} question[{index}]"
    if not isinstance(question, dict):
        return [Finding("error", where, "is not an object")]

    out: list[Finding] = []
    qid = str(question.get("question_id", "")).strip()
    label = f"{where} ({qid})" if qid else where

    try:
        _validate(question, index, seen, filename)
    except AuthoredPackRejected as exc:
        out.append(Finding("error", where, str(exc).split(": ", 1)[-1]))

    if qid and not _QUESTION_ID.match(qid):
        out.append(Finding("error", label, "question_id must look like `re_fal_license` — a short sector prefix, an underscore, then lowercase words"))

    kind = str(question.get("type", ""))
    # Through the shared model, so the linter reads WORDING whatever shape the pack used.
    options = option_texts(question)
    if kind == "enum":
        # Reported once per question. A question carrying both an "أكثر من" option AND a list of
        # yeses has one problem, not two, and saying so twice makes a reviewer trust the list less.
        already = any(_means_several(o) for o in options)
        reason = None if already else _reads_as_multi_select(question, options)
        if reason:
            out.append(
                Finding(
                    "warning",
                    label,
                    f"is single-choice, but {reason} — a customer who is two of these can only "
                    f"record one. Consider multi_select",
                )
            )
        for option in options:
            if _means_several(option):
                out.append(
                    Finding(
                        "warning",
                        label,
                        f"is a single-choice question offering {option!r}, which records THAT "
                        f"several apply while losing WHICH. Make it a multi_select and drop that option",
                    )
                )

    refs = question.get("references") or []
    keys = [(str(r.get("framework", "")), str(r.get("clause", ""))) for r in refs if isinstance(r, dict)]
    for key in {k for k in keys if keys.count(k) > 1}:
        out.append(Finding("error", label, f"cites {key[0]!r} / {key[1]!r} twice"))

    duplicate_options = {o for o in options if options.count(o) > 1}
    for option in duplicate_options:
        out.append(Finding("error", label, f"offers the option {option!r} twice"))
    return out


def _lint_across_questions(questions: list[Any], filename: str) -> list[Finding]:
    """Whole-pack checks — the ones no single question can fail on its own."""
    out: list[Finding] = []
    texts = [
        (str(q.get("question_id", i)), _normalise(str(q.get("canonical_text_ar", ""))))
        for i, q in enumerate(questions)
        if isinstance(q, dict)
    ]
    for i, (qid_a, text_a) in enumerate(texts):
        for qid_b, text_b in texts[i + 1 :]:
            if not text_a or not text_b:
                continue
            ratio = difflib.SequenceMatcher(None, text_a, text_b).ratio()
            if ratio >= _NEAR_DUPLICATE:
                out.append(
                    Finding(
                        "warning",
                        filename,
                        f"{qid_a} and {qid_b} are {ratio:.0%} alike — check they are not the same "
                        f"question asked twice",
                    )
                )
    return out


def describe_packs() -> list[dict[str, Any]]:
    """Every authored pack on disk, described well enough for a reviewer to choose one.

    Validates each as it goes: a pack that would fail on import is better surfaced in the list,
    where it can be fixed, than at the moment somebody tries to deploy a sector.
    """
    described: list[dict[str, Any]] = []
    for slug in available_packs():
        findings = lint_pack(slug)
        errors = [f for f in findings if f.severity == "error"]
        warnings = [str(f) for f in findings if f.severity == "warning"]
        if errors:
            described.append(
                {
                    "industry_slug": slug,
                    "canonical_name_ar": slug,
                    "question_count": 0,
                    "authored_by": "",
                    "problem": "; ".join(str(e) for e in errors),
                    "warnings": warnings,
                }
            )
            continue
        pack = load_pack(slug)
        described.append(
            {
                "industry_slug": slug,
                "canonical_name_ar": pack.get("canonical_name_ar", slug),
                "question_count": len(pack["questions"]),
                "authored_by": pack.get("authored_by", "human"),
                "problem": None,
                # Reported beside an importable pack, never instead of it. A warning is a question
                # for the reviewer, and the reviewer is the one the import gate exists for.
                "warnings": warnings,
            }
        )
    return described


class AuthoredPackGenerator:
    """A `QuestionGenerator` that reads the authored pack instead of calling a model.

    Same port, so `GenerateKnowledgeTemplate` needs no branch: the service still ensures the
    container, obtains questions, and mints a version. Where the questions came from is the
    generator's business, and the provenance columns record which it was.
    """

    def generate(self, *, industry_slug: str) -> list[dict[str, Any]]:
        return list(load_pack(industry_slug)["questions"])
