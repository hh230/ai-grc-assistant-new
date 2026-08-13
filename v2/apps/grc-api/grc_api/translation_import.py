"""Importing authored English into the knowledge store (ADR 0069).

A question is three kinds of customer-facing text and all three are imported: the question itself,
each option, each `evidence_required` line. `why_we_ask` is NOT imported and never will be — it is
the reviewer's case for a question, and `InterviewQuestionView` deliberately has no field for it.
That boundary already existed; this module respects it rather than redrawing it.

IDEMPOTENCY. `save_translation` upserts and resets `status` to `generated`. A naive re-run would
therefore demote every string a human had reviewed or published. So the importer READS first and
writes only what actually differs: a second run over unchanged content performs zero writes.

THE ARABIC IS NEVER TOUCHED. Nothing here writes to `release_questions`. The Arabic, the ids, the
`writes_signal` and the `signal_value_map` are read-only inputs used to VERIFY that each English
string is attached to the part it claims — an import whose pack has drifted from the release it
targets is refused rather than reconciled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

LANGUAGE = "en"


def option_key(option: Any) -> str:
    """An option's identity: its `option_id` when it has one, else the Arabic string — which is
    what `sector_answers` stores for the 1083 options authored before ADR 0068."""
    return option["option_id"] if isinstance(option, dict) else str(option)


def option_text(option: Any) -> str:
    return option["text_ar"] if isinstance(option, dict) else str(option)


@dataclass(frozen=True)
class PlannedWrite:
    """One intended row. `action` is what a run would actually do to the database."""

    industry_slug: str
    release_id: str
    question_id: str
    part_kind: str
    part_index: int
    source_text_ar: str
    text: str
    action: str  # "insert" | "update" | "unchanged"


@dataclass
class ImportReport:
    language: str = LANGUAGE
    planned: list[PlannedWrite] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    sectors: list[str] = field(default_factory=list)

    def _of(self, kind: str) -> int:
        return sum(1 for p in self.planned if p.part_kind == kind)

    @property
    def questions_seen(self) -> int:
        return self._of("question")

    @property
    def options_seen(self) -> int:
        return self._of("option")

    @property
    def evidence_seen(self) -> int:
        return self._of("evidence")

    @property
    def inserts(self) -> int:
        return sum(1 for p in self.planned if p.action == "insert")

    @property
    def updates(self) -> int:
        return sum(1 for p in self.planned if p.action == "update")

    @property
    def unchanged(self) -> int:
        return sum(1 for p in self.planned if p.action == "unchanged")

    @property
    def writes(self) -> int:
        return self.inserts + self.updates

    @property
    def strings_seen(self) -> int:
        return len(self.planned)

    @property
    def ok(self) -> bool:
        return not self.errors


def _parts(question: dict[str, Any]) -> list[tuple[str, int, str, str]]:
    """(part_kind, part_index, source_ar, english) for every translatable part of a question."""
    parts: list[tuple[str, int, str, str]] = [
        ("question", 0, question["canonical_text_ar"], question.get("canonical_text_en") or "")
    ]
    english_options = question.get("options_en") or {}
    for index, option in enumerate(question.get("options") or []):
        parts.append(
            ("option", index, option_text(option), english_options.get(option_key(option), ""))
        )
    english_evidence = list(question.get("evidence_required_en") or [])
    for index, evidence in enumerate(question.get("evidence_required") or []):
        english = english_evidence[index] if index < len(english_evidence) else ""
        parts.append(("evidence", index, str(evidence), english))
    return parts


def plan_import(store: Any, packs: dict[str, dict[str, Any]]) -> ImportReport:
    """Reads every pack against the release each sector currently serves, and returns what a write
    would do. No writes. `packs` is `{industry_slug: pack}`.

    Refuses, rather than reconciles, five kinds of mismatch — each of which means the English would
    land somewhere nobody agreed to:

    * the sector has no active release (nothing to attach a translation to);
    * a question in the pack is not in that release;
    * the pack's Arabic for any PART differs from the release's (the pack has moved on);
    * a part exists in the pack that the release does not have, or vice versa;
    * the English for any part is missing or blank.
    """
    report = ImportReport()
    for slug in sorted(packs):
        pack = packs[slug]
        report.sectors.append(slug)
        release = store.get_active_release(slug)
        if release is None:
            report.errors.append(f"{slug}: no active release — nothing to attach a translation to")
            continue
        live = {q["question_id"]: q for q in release.get("questions") or []}

        for question in pack["questions"]:
            qid = question["question_id"]
            stored = live.get(qid)
            if stored is None:
                report.errors.append(f"{slug}/{qid}: not a question of the active release")
                continue

            pack_parts = _parts(question)
            release_parts = _parts(dict(stored, canonical_text_en="", options_en={},
                                        evidence_required_en=[]))
            if len(pack_parts) != len(release_parts):
                report.errors.append(
                    f"{slug}/{qid}: the pack has {len(pack_parts)} parts and the release has "
                    f"{len(release_parts)} — the pack has drifted; publish a new release rather "
                    f"than translating across versions"
                )
                continue

            for (kind, index, source_ar, english), (_, _, live_ar, _) in zip(
                pack_parts, release_parts
            ):
                where = f"{slug}/{qid}/{kind}[{index}]"
                if source_ar != live_ar:
                    report.errors.append(
                        f"{where}: the pack's Arabic differs from the release's — the pack has "
                        f"drifted; publish a new release rather than translating across versions"
                    )
                    continue
                if not english.strip():
                    report.errors.append(f"{where}: no English")
                    continue

                existing = store.get_translation(
                    release_id=release["id"], question_id=qid, language=LANGUAGE,
                    part=(kind, index),
                )
                action = (
                    "insert" if existing is None
                    else "unchanged" if existing["text"] == english
                    else "update"
                )
                report.planned.append(
                    PlannedWrite(slug, release["id"], qid, kind, index, source_ar, english, action)
                )
    return report


def apply_import(store: Any, report: ImportReport) -> int:
    """Writes exactly what `plan_import` planned, and nothing else. Returns rows written.

    Refuses to write at all when the plan carries an error: a partial import of a question's parts
    is worse than none, because the half that landed looks ready to publish.
    """
    if not report.ok:
        raise ValueError(
            f"refusing to import: {len(report.errors)} error(s), first is {report.errors[0]}"
        )
    written = 0
    for plan in report.planned:
        if plan.action == "unchanged":
            continue
        store.save_translation(
            release_id=plan.release_id,
            question_id=plan.question_id,
            language=LANGUAGE,
            text=plan.text,
            part=(plan.part_kind, plan.part_index),
            source_text_ar=plan.source_text_ar,
        )
        written += 1
    return written


def format_report(report: ImportReport) -> str:
    """The dry-run, in the shape a reviewer can check against the authored files."""
    lines = [
        f"language              : {report.language}",
        f"sectors               : {len(report.sectors)}",
        "",
        f"question texts        : {report.questions_seen:>5}",
        f"options               : {report.options_seen:>5}",
        f"evidence items        : {report.evidence_seen:>5}",
        f"                        {'-' * 5}",
        f"strings planned       : {report.strings_seen:>5}",
        "",
        f"  insert              : {report.inserts:>5}",
        f"  update              : {report.updates:>5}",
        f"  unchanged (no write): {report.unchanged:>5}",
        "",
        f"errors                : {len(report.errors)}",
    ]
    lines += [f"  - {e}" for e in report.errors[:20]]
    if len(report.errors) > 20:
        lines.append(f"  ... and {len(report.errors) - 20} more")
    return "\n".join(lines)
