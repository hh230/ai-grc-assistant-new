"""Sector Knowledge Packs — the repository (ADR 0067; `docs/adr/0067-repository-contract.md`).

Twenty-one atomic SQL operations, plus one Get/List read primitive. Nothing else lives here.

Four methods an earlier draft added were removed rather than promoted into the contract, because
each was a signal about a *different* layer:

- `get_release` / `list_releases` — one concept, not two. Two methods here meant the repository
  was being shaped by the screens that read it.
- `translation_coverage` — a derived projection. It belongs in a read model or a SQL view; a
  repository that computes gains a second job.
- `retire_industry` — coordination: retire the industry, retire its active release, mark it
  inactive. Needing several repository calls means a Service, not a new repository method.

Only `reject_release` was a genuine gap, because it is a state transition and the machine already
had approve, release and retire.

**Repository methods never call other repository methods.** If a caller needs "create, then
release, then activate", that is an Application Service composing three calls — not a shortcut
inside one. A repository calling a repository erases the transaction boundary, the lock scope and
the read/write ordering all at once, and months later nobody can say which method owns the
concurrency. Where a method needs data, it reads it itself, inside its own transaction.

What this module deliberately does not do:

- **No lifecycle logic.** Guards are `WHERE status = …` clauses; which transition is legal is the
  domain's decision. A guarded write that matches zero rows returns `False` — the caller decides
  whether that is an error.
- **No delete of anything.** Knowledge Freeze and Assessment Freeze are enforced by the schema;
  no method here can even attempt one.
- **No tenant defaulting.** Every customer-side method takes the tenant explicitly.
- **No domain objects.** Methods return plain row mappings. Mapping rows to the domain is the
  Application Service's job, and keeping it out means this layer stays purely SQL — which is also
  why the prototype domain model in `governance_discovery.knowledge_template` does not need to be
  reconciled before this exists.

Isolation is `READ COMMITTED` throughout — PostgreSQL's default. Where a stronger guarantee is
needed it comes from a lock, a guarded write, or immutable data. See the contract for why each
method locks what it locks.
"""

from __future__ import annotations

from typing import Any

from governance_store.config import dsn as default_dsn
from governance_store.store import _load_pg

# Every column an interview or a review console needs from a question. Named once so the two
# readers cannot drift apart.
_QUESTION_COLUMNS = (
    "question_id",
    "canonical_text_ar",
    "type",
    "options",
    "required",
    "category",
    "importance",
    '"references"',
    "why_we_ask",
    "evidence_required",
    "position",
    # ADR 0068: the declared channel. NULL on every shipped question — a pack that declares
    # nothing reads back exactly as it did before this column existed.
    "writes_signal",
    "signal_value_map",
)


#: Arabic is the source, never a translation (ADR 0067 §3).
CANONICAL_LANGUAGE = "ar"


class PostgresKnowledgeStore:
    """One connection, one call per method. Mirrors `PostgresGovernanceStore`'s shape."""

    def __init__(self, *, dsn: str | None = None, connection: Any | None = None) -> None:
        self._owns_conn = connection is None
        if connection is not None:
            self._conn = connection
        else:
            psycopg, _, _ = _load_pg()
            self._conn = psycopg.connect(dsn or default_dsn(), autocommit=True)

    def close(self) -> None:
        if self._owns_conn:
            self._conn.close()

    def _rows(self, sql: str, params: Any = None) -> list[dict[str, Any]]:
        _, _, dict_row = _load_pg()
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def _row(self, sql: str, params: Any = None) -> dict[str, Any] | None:
        rows = self._rows(sql, params)
        return rows[0] if rows else None

    # ── industries ───────────────────────────────────────────────────────────────────────────

    def register_industry(self, slug: str, canonical_name_ar: str) -> None:
        """READ COMMITTED · no lock · no retry · idempotent."""
        self._conn.execute(
            "INSERT INTO industries (slug, canonical_name_ar) VALUES (%s, %s) "
            "ON CONFLICT (slug) DO NOTHING",
            (slug, canonical_name_ar),
        )

    def list_industries(self, *, include_retired: bool = False) -> list[dict[str, Any]]:
        """READ COMMITTED · no lock · read."""
        return self._rows(
            "SELECT slug, canonical_name_ar, status FROM industries "
            "WHERE %s OR status = 'active' ORDER BY slug",
            (include_retired,),
        )

    def set_industry_status(self, slug: str, status: str) -> bool:
        """READ COMMITTED · no lock · idempotent. A single atomic write — data access.

        Deliberately NOT `retire_industry`. Retiring an industry also means retiring its active
        release, and that coordination belongs to the `RetireIndustry` service. The distinction is
        exact: the repository can set a status; only a service can retire an industry.
        """
        if status not in ("active", "retired"):
            raise ValueError(f"{status!r} is not an industry status")
        cur = self._conn.execute(
            "UPDATE industries SET status = %s WHERE slug = %s AND status <> %s",
            (status, slug, status),
        )
        return cur.rowcount == 1

    # ── templates ────────────────────────────────────────────────────────────────────────────

    def ensure_template(self, template_id: str, industry_slug: str) -> dict[str, Any] | None:
        """READ COMMITTED · no lock · idempotent.

        Insert-then-read rather than read-then-insert: the second ordering is a race, and the
        `UNIQUE (industry_slug)` constraint would turn it into an error the caller must handle for
        a call that is supposed to be safe to repeat.
        """
        self._conn.execute(
            "INSERT INTO knowledge_templates (id, industry_slug) VALUES (%s, %s) "
            "ON CONFLICT (industry_slug) DO NOTHING",
            (template_id, industry_slug),
        )
        return self._row(
            "SELECT id, industry_slug FROM knowledge_templates WHERE industry_slug = %s",
            (industry_slug,),
        )

    # ── releases ─────────────────────────────────────────────────────────────────────────────

    def create_release(
        self,
        *,
        release_id: str,
        template_id: str,
        questions: list[dict[str, Any]],
        generated_by_model: str,
        prompt_version: str,
        generator_commit: str,
        created_by: str,
        expected_outputs: list[str] | None = None,
    ) -> int:
        """READ COMMITTED · `FOR UPDATE` on the parent template row · no retry. Returns the
        version allocated.

        The lock serialises version allocation for **this industry only**, so two sectors never
        wait on each other. With it held, `max(version) + 1` is atomic and the unique constraint
        is unreachable — which is why there is no retry: a violation here would mean a caller
        supplied a duplicate explicitly, and that is a bug to surface.

        The questions are written in the same transaction because a release with no questions is
        not a release.
        """
        _, jsonb, _ = _load_pg()
        if not questions:
            raise ValueError("a release with no questions is not a release")

        with self._conn.transaction():
            locked = self._conn.execute(
                "SELECT id FROM knowledge_templates WHERE id = %s FOR UPDATE", (template_id,)
            ).fetchone()
            if locked is None:
                raise LookupError(f"no knowledge template {template_id!r}")

            version = (
                self._conn.execute(
                    "SELECT coalesce(max(version), 0) + 1 FROM template_releases "
                    "WHERE template_id = %s",
                    (template_id,),
                ).fetchone()
            )[0]

            self._conn.execute(
                "INSERT INTO template_releases (id, template_id, version, status, "
                " expected_outputs, generated_by_model, prompt_version, generator_commit, "
                " created_by) "
                "VALUES (%s, %s, %s, 'draft', %s, %s, %s, %s, %s)",
                (
                    release_id,
                    template_id,
                    version,
                    jsonb(expected_outputs or []),
                    generated_by_model,
                    prompt_version,
                    generator_commit,
                    created_by,
                ),
            )
            for position, question in enumerate(questions):
                # `writes_signal` / `signal_value_map` are the declared channel from a sector
                # answer to an engine signal (ADR 0068). Both are OPTIONAL and default to NULL:
                # a pack that declares nothing writes nothing, which is every shipped pack.
                #
                # They are carried here and validated by the caller BEFORE this runs
                # (`grc_api.signal_declarations`), never interpreted in the repository. What
                # protects them from a model is upstream, where it belongs: the generator's
                # `_FORBIDDEN_FIELDS` refuses the fields outright, so a declaration reaches this
                # statement only from an authored file a human wrote and a reviewer approved.
                declaration = question.get("signal_value_map")
                self._conn.execute(
                    "INSERT INTO release_questions (release_id, question_id, canonical_text_ar, "
                    ' type, options, required, category, importance, "references", why_we_ask, '
                    " evidence_required, position, writes_signal, signal_value_map) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        release_id,
                        question["question_id"],
                        question["canonical_text_ar"],
                        question["type"],
                        jsonb(question.get("options") or []),
                        question.get("required", True),
                        question["category"],
                        question["importance"],
                        jsonb(question["references"]),
                        question["why_we_ask"],
                        jsonb(question.get("evidence_required") or []),
                        position,
                        question.get("writes_signal"),
                        jsonb(declaration) if declaration is not None else None,
                    ),
                )
        return version

    def attach_translations(self, release: dict[str, Any], language: str) -> dict[str, Any]:
        """Folds PUBLISHED translations into a release's questions, in place, and returns it.

        Published means the whole question was released together (see
        `publish_question_translation`), so a question either gains all three English fields or
        none — there is no partial state for a caller to handle. Arabic is untouched and stays
        authoritative: a question with no published translation simply has no English fields, and
        the interface falls back to Arabic for that question alone.
        """
        if language == CANONICAL_LANGUAGE:
            return release
        parts_by_question: dict[str, dict[tuple[str, int], str]] = {}
        for row in self.list_translations(
            release_id=release["id"], language=language, status="published"
        ):
            parts_by_question.setdefault(row["question_id"], {})[
                (row["part_kind"], row["part_index"])
            ] = row["text"]
        for question in release.get("questions") or []:
            parts = parts_by_question.get(question["question_id"])
            if not parts:
                continue
            # Completeness is re-checked HERE, not assumed from "some parts are published".
            # Publication is all-or-nothing, but a published question can later lose one part:
            # correcting a single English string returns that part to `generated` while its
            # siblings stay `published`. That state is legitimate — it is the lifecycle working —
            # and it means "not fully available in this language", so the whole question falls
            # back to Arabic rather than rendering three quarters translated.
            option_count = len(list(question.get("options") or []))
            evidence_count = len(list(question.get("evidence_required") or []))
            expected = (
                [("question", 0)]
                + [("option", i) for i in range(option_count)]
                + [("evidence", i) for i in range(evidence_count)]
            )
            if any(part not in parts for part in expected):
                continue
            question["canonical_text_en"] = parts[("question", 0)]
            question["options_en"] = [parts[("option", i)] for i in range(option_count)]
            question["evidence_required_en"] = [
                parts[("evidence", i)] for i in range(evidence_count)
            ]
        return release

    def list_releases(
        self,
        *,
        industry_slug: str | None = None,
        release_id: str | None = None,
        status: str | None = None,
        with_questions: bool = False,
        language: str | None = None,
    ) -> list[dict[str, Any]]:
        """READ COMMITTED · no lock · read. The Get/List primitive — not one method per screen.

        An earlier draft had a separate `get_release` because the review console wanted a single
        draft while the listing wanted many. That was designing the repository from the screen's
        point of view rather than the data's: both are the same query with different filters, and
        one method per view is how a repository grows without limit.

        `with_questions` is a filter on depth, not a different operation — a listing does not need
        fifty rows of question text per release, and a review does.
        """
        clauses, params = [], {}
        if industry_slug is not None:
            clauses.append("t.industry_slug = %(industry)s")
            params["industry"] = industry_slug
        if release_id is not None:
            clauses.append("r.id = %(release_id)s")
            params["release_id"] = release_id
        if status is not None:
            clauses.append("r.status = %(status)s")
            params["status"] = status
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        releases = self._rows(
            "SELECT r.id, r.template_id, t.industry_slug, r.version, r.status, "
            " r.expected_outputs, r.generated_by_model, r.prompt_version, r.generator_commit, "
            " r.created_by, r.approved_by, r.approved_at, r.released_at "
            "FROM template_releases r JOIN knowledge_templates t ON t.id = r.template_id "
            f"{where} ORDER BY t.industry_slug, r.version DESC",
            params or None,
        )
        if with_questions:
            for release in releases:
                release["questions"] = self._rows(
                    f"SELECT {', '.join(_QUESTION_COLUMNS)} FROM release_questions "
                    "WHERE release_id = %s ORDER BY position, question_id",
                    (release["id"],),
                )
                if language is not None:
                    self.attach_translations(release, language)
        return releases

    def submit_for_review(self, release_id: str) -> bool:
        """READ COMMITTED · no lock · idempotent. The `WHERE` clause IS the compare-and-swap."""
        cur = self._conn.execute(
            "UPDATE template_releases SET status = 'in_review' "
            "WHERE id = %s AND status = 'draft'",
            (release_id,),
        )
        return cur.rowcount == 1

    def approve_release(self, release_id: str, *, approver: str, at: Any) -> bool:
        """READ COMMITTED · no lock · idempotent.

        `approved_by` is the record of who accepted content every organization in this sector will
        be asked, so the schema refuses the status without it and this refuses an empty identity.
        """
        if not (approver or "").strip():
            raise ValueError("approving sector knowledge requires the approver's identity")
        cur = self._conn.execute(
            "UPDATE template_releases SET status = 'approved', approved_by = %s, approved_at = %s "
            "WHERE id = %s AND status = 'in_review'",
            (approver, at, release_id),
        )
        return cur.rowcount == 1

    def reject_release(self, release_id: str) -> bool:
        """READ COMMITTED · no lock · idempotent. Back to draft, to be regenerated."""
        cur = self._conn.execute(
            "UPDATE template_releases SET status = 'draft' "
            "WHERE id = %s AND status IN ('in_review', 'approved')",
            (release_id,),
        )
        return cur.rowcount == 1

    def mark_released(self, release_id: str, *, at: Any) -> bool:
        """READ COMMITTED · no lock · idempotent.

        Makes a release *eligible* for activation; it does not activate it. Separating the two is
        what lets several releases be `released` while exactly one is active.
        """
        cur = self._conn.execute(
            "UPDATE template_releases SET status = 'released', released_at = %s "
            "WHERE id = %s AND status = 'approved'",
            (at, release_id),
        )
        return cur.rowcount == 1

    def retire_release(self, release_id: str, *, target_status: str) -> bool:
        """READ COMMITTED · no lock · idempotent. Status only — never content, never a delete."""
        if target_status not in ("superseded", "deprecated", "archived"):
            raise ValueError(f"{target_status!r} is not a retirement status")
        cur = self._conn.execute(
            "UPDATE template_releases SET status = %s "
            "WHERE id = %s AND status IN ('released', 'superseded', 'deprecated')",
            (target_status, release_id),
        )
        return cur.rowcount == 1

    # ── activation ───────────────────────────────────────────────────────────────────────────

    def set_active_release(
        self, *, industry_slug: str, release_id: str | None, actor: str, reason: str = ""
    ) -> str | None:
        """READ COMMITTED · `FOR UPDATE` on the industry · no retry. Returns what was live before.

        ONE primitive, because there is one question: **what is the active release for this
        industry?** Only two answers are permitted — a release, or none. `release_id=None` is not a
        second operation called "deactivate"; it is the other permitted answer to the same
        question. Two methods for one fact is how the two drift apart.

        This is also rollback: pointing back at an older release is the same call. No release row
        is touched, and nothing is invented to undo a mistake.

        The lock is on `industries`, not on `active_templates`. `FOR UPDATE` cannot lock a row that
        does not exist, and the first activation for an industry is exactly that case; the industry
        row is guaranteed to exist by the foreign key, so locking it serialises every change to
        this pointer — including the read of the previous value, which is why the return value is
        exact rather than best-effort. Activation is a reviewer action, so serialising per industry
        costs nothing. `ON CONFLICT DO UPDATE` stays: it is what makes insert-or-replace one
        statement.

        The pointer and its history are one transaction. Split apart, a crash between them leaves
        either a pointer nobody can explain or a history entry for something that never took
        effect.

        Clearing it is NOT deleting knowledge: the release row is untouched and every activation
        stays in `active_template_history`. What disappears is only "which release is live right
        now" — and the answer becomes "none".
        """
        with self._conn.transaction():
            self._conn.execute(
                "SELECT slug FROM industries WHERE slug = %s FOR UPDATE", (industry_slug,)
            )
            previous = self._conn.execute(
                "SELECT release_id FROM active_templates WHERE industry_slug = %s",
                (industry_slug,),
            ).fetchone()
            if release_id is None:
                self._conn.execute(
                    "DELETE FROM active_templates WHERE industry_slug = %s", (industry_slug,)
                )
            else:
                self._conn.execute(
                    "INSERT INTO active_templates (industry_slug, release_id, release_status, "
                    " activated_by) VALUES (%s, %s, 'released', %s) "
                    "ON CONFLICT (industry_slug) DO UPDATE SET "
                    " release_id = EXCLUDED.release_id, "
                    " release_status = EXCLUDED.release_status, "
                    " activated_by = EXCLUDED.activated_by, activated_at = now()",
                    (industry_slug, release_id, actor),
                )
                self._conn.execute(
                    "INSERT INTO active_template_history (industry_slug, release_id, "
                    " activated_by, reason) VALUES (%s, %s, %s, %s)",
                    (industry_slug, release_id, actor, reason),
                )
        return previous[0] if previous else None

    def get_active_release(
        self, industry_slug: str, *, language: str | None = None
    ) -> dict[str, Any] | None:
        """READ COMMITTED · **no lock** · read. What an interview draws from.

        Deliberately takes no lock: this runs on every interview, and `FOR UPDATE` here would
        serialise every customer in a sector behind one row. MVCC already gives a consistent read.
        """
        release = self._row(
            "SELECT r.id, r.version, r.status, r.expected_outputs, r.generated_by_model, "
            " r.prompt_version, r.generator_commit, a.activated_at, a.activated_by "
            "FROM active_templates a JOIN template_releases r ON r.id = a.release_id "
            "WHERE a.industry_slug = %s",
            (industry_slug,),
        )
        if release is None:
            return None
        release["questions"] = self._rows(
            f"SELECT {', '.join(_QUESTION_COLUMNS)} FROM release_questions "
            "WHERE release_id = %s ORDER BY position, question_id",
            (release["id"],),
        )
        if language is not None:
            self.attach_translations(release, language)
        return release

    def list_activation_history(self, industry_slug: str) -> list[dict[str, Any]]:
        """READ COMMITTED · no lock · read. Answers "what was live at 10:30?"."""
        return self._rows(
            "SELECT id, release_id, activated_by, activated_at, reason "
            "FROM active_template_history WHERE industry_slug = %s "
            "ORDER BY activated_at DESC, id DESC",
            (industry_slug,),
        )

    # ── translations (ADR 0069) ──────────────────────────────────────────────────────────────
    #
    # A question is three kinds of customer-facing text: its own, its options', and its evidence
    # lines'. Each is a row, addressed by `(part_kind, part_index)`, because 1083 of 1103 authored
    # options carry no `option_id` — their identity IS their Arabic string, which is also what
    # `sector_answers` stores — and evidence lines carry no identity at all. The index is the only
    # addressing scheme that covers all three, and it is stable forever because a release is an
    # immutable snapshot: what is never updated is never reordered.
    #
    # `source_text_ar` is the defensive copy of what was translated. The link is an integer, and an
    # integer is silent; the copy is what turns "this English landed on the wrong option" from
    # forbidden-by-intention into caught-by-comparison.

    QUESTION_PART = ("question", 0)

    def _question_row(self, release_id: str, question_id: str) -> dict[str, Any]:
        row = self._row(
            "SELECT canonical_text_ar, options, evidence_required FROM release_questions "
            "WHERE release_id = %s AND question_id = %s",
            (release_id, question_id),
        )
        if row is None:
            raise LookupError(f"no question {question_id!r} in release {release_id!r}")
        return row

    @staticmethod
    def _option_text(option: Any) -> str:
        """An option is either a bare Arabic string or `{option_id, text_ar}`. Both shapes ship in
        the authored packs, and this is the one place that needs to know it."""
        return option["text_ar"] if isinstance(option, dict) else str(option)

    def _source_text(self, release_id: str, question_id: str, part: tuple[str, int]) -> str:
        """The Arabic this part translates, read from the release — never from the caller.

        Raises rather than returns None for an index outside the array: a translation addressed at
        a part that does not exist is not a near-miss to be tolerated, it is a wrong address.
        """
        kind, index = part
        row = self._question_row(release_id, question_id)
        if kind == "question":
            return str(row["canonical_text_ar"])
        collection = row["options"] if kind == "option" else row["evidence_required"]
        collection = list(collection or [])
        if not 0 <= index < len(collection):
            raise IndexError(
                f"{kind} index {index} is outside {question_id!r}, which has {len(collection)}"
            )
        return self._option_text(collection[index]) if kind == "option" else str(collection[index])

    def expected_parts(self, *, release_id: str, question_id: str) -> int:
        """How many translatable parts this question has: itself, its options, its evidence."""
        row = self._question_row(release_id, question_id)
        return 1 + len(list(row["options"] or [])) + len(list(row["evidence_required"] or []))

    def save_translation(
        self,
        *,
        release_id: str,
        question_id: str,
        language: str,
        text: str,
        part: tuple[str, int] = QUESTION_PART,
        source_text_ar: str | None = None,
    ) -> None:
        """READ COMMITTED · no lock · idempotent. Arabic is refused by the schema, not here.

        `source_text_ar` is VERIFIED against the release, never trusted: if the caller passes text
        that is not what the release holds at that part, the write is refused. That is the check
        that keeps English from being filed against the wrong option — and it lives here rather
        than in a trigger, so the database never needs to know the shape of an authored pack.
        """
        kind, index = part
        actual = self._source_text(release_id, question_id, part)
        if source_text_ar is not None and source_text_ar != actual:
            raise ValueError(
                f"{question_id}/{kind}[{index}]: the source Arabic does not match the release — "
                f"refusing to attach a translation to a part it does not describe"
            )
        self._conn.execute(
            "INSERT INTO question_translations "
            " (release_id, question_id, language, part_kind, part_index, source_text_ar, text) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (release_id, question_id, language, part_kind, part_index) DO UPDATE SET "
            " text = EXCLUDED.text, source_text_ar = EXCLUDED.source_text_ar, status = 'generated'",
            (release_id, question_id, language, kind, index, actual, text),
        )

    def get_translation(
        self,
        *,
        release_id: str,
        question_id: str,
        language: str,
        part: tuple[str, int] = QUESTION_PART,
    ) -> dict[str, Any] | None:
        """READ COMMITTED · no lock · read. What is stored for this part in this language.

        An importer needs this before it writes: a re-run that saved an identical string would
        still reset `status` to `generated` through the ON CONFLICT above, silently demoting
        something a human had already reviewed. Reading first is what makes a second run a true
        no-op rather than a quiet regression.
        """
        kind, index = part
        return self._row(
            "SELECT release_id, question_id, language, part_kind, part_index, source_text_ar, "
            " text, status, created_at FROM question_translations "
            "WHERE release_id = %s AND question_id = %s AND language = %s "
            " AND part_kind = %s AND part_index = %s",
            (release_id, question_id, language, kind, index),
        )

    def list_translations(
        self, *, release_id: str, language: str, status: str | None = None
    ) -> list[dict[str, Any]]:
        """READ COMMITTED · no lock · read. Every part of every question in one release, in one
        query — the read path the interview uses, rather than one query per question."""
        sql = (
            "SELECT question_id, part_kind, part_index, source_text_ar, text, status "
            "FROM question_translations WHERE release_id = %s AND language = %s"
        )
        params: list[Any] = [release_id, language]
        if status is not None:
            sql += " AND status = %s"
            params.append(status)
        return self._rows(sql + " ORDER BY question_id, part_kind, part_index", tuple(params))

    def review_translation(
        self,
        *,
        release_id: str,
        question_id: str,
        language: str,
        part: tuple[str, int] = QUESTION_PART,
    ) -> bool:
        """READ COMMITTED · no lock · idempotent. `generated` -> `reviewed`: a human read this
        string and stands behind it.

        Per PART, deliberately: a reviewer may accept a question and its options while leaving one
        evidence line hanging. Publication is the step that refuses to be partial.
        """
        kind, index = part
        cur = self._conn.execute(
            "UPDATE question_translations SET status = 'reviewed' "
            "WHERE release_id = %s AND question_id = %s AND language = %s "
            " AND part_kind = %s AND part_index = %s AND status = 'generated'",
            (release_id, question_id, language, kind, index),
        )
        return cur.rowcount == 1

    def publish_question_translation(
        self, *, release_id: str, question_id: str, language: str
    ) -> int:
        """READ COMMITTED · one transaction · returns the number of parts published, 0 if refused.

        THE WHOLE QUESTION OR NOTHING. A customer reads a question, its options and its evidence as
        one screen; publishing them separately is how a screen ends up half English and half
        Arabic, which is worse than all Arabic. So this is the only way to publish, and it refuses
        unless, verified HERE against the release itself rather than taken from the caller:

        * every part of the question is present — count matches what the release actually holds;
        * every part's `source_text_ar` still matches the release's own text at that index;
        * every part is `reviewed` (or already `published`, so re-running is harmless).

        The verification and the write share one transaction, so a refusal leaves nothing changed
        and a success changes everything together. The UPDATE re-asserts the two countable
        conditions in its own WHERE as a last guard against a concurrent writer between the check
        and the write.
        """
        with self._conn.transaction():
            row = self._question_row(release_id, question_id)
            sources = [(self.QUESTION_PART, str(row["canonical_text_ar"]))]
            sources += [
                (("option", i), self._option_text(o))
                for i, o in enumerate(list(row["options"] or []))
            ]
            sources += [
                (("evidence", i), str(e))
                for i, e in enumerate(list(row["evidence_required"] or []))
            ]

            stored = {
                (r["part_kind"], r["part_index"]): r
                for r in self._rows(
                    "SELECT part_kind, part_index, source_text_ar, status "
                    "FROM question_translations "
                    "WHERE release_id = %s AND question_id = %s AND language = %s",
                    (release_id, question_id, language),
                )
            }
            for part, source in sources:
                found = stored.get(part)
                if found is None:
                    return 0  # a missing part means the screen would fall back mid-question
                if found["source_text_ar"] != source:
                    return 0  # the English no longer describes the Arabic it claims to translate
                if found["status"] not in ("reviewed", "published"):
                    return 0  # unreviewed text must never reach a customer
            if len(stored) != len(sources):
                return 0  # a part addressed at something the release does not have

            cur = self._conn.execute(
                "UPDATE question_translations SET status = 'published' "
                "WHERE release_id = %s AND question_id = %s AND language = %s "
                " AND NOT EXISTS (SELECT 1 FROM question_translations x "
                "                  WHERE x.release_id = %s AND x.question_id = %s "
                "                    AND x.language = %s "
                "                    AND x.status NOT IN ('reviewed', 'published')) "
                " AND (SELECT count(*) FROM question_translations c "
                "       WHERE c.release_id = %s AND c.question_id = %s AND c.language = %s) = %s",
                (release_id, question_id, language) * 3 + (len(sources),),
            )
            return cur.rowcount

    def open_assessment(
        self,
        *,
        assessment_id: str,
        tenant_id: str,
        organization_id: str,
        source_session_id: str | None = None,
    ) -> None:
        """READ COMMITTED · no lock · no retry · NOT idempotent — a new assessment is a new fact.

        A duplicate id is a caller bug and is surfaced, not absorbed.
        """
        self._conn.execute(
            "INSERT INTO assessments (id, tenant_id, organization_id, source_session_id) "
            "VALUES (%s, %s, %s, %s)",
            (assessment_id, tenant_id, organization_id, source_session_id),
        )

    def record_selection(
        self,
        *,
        assessment_id: str,
        tenant_id: str,
        suggested_industry_slug: str | None,
        selected_release_ids: list[str],
        selected_by: str,
    ) -> None:
        """READ COMMITTED · no lock · idempotent until the assessment concludes.

        The suggestion is stored beside the decision so the two stay comparable: a suggestion
        someone kept and a suggestion nobody examined are different facts.
        """
        if not selected_release_ids:
            raise ValueError("an assessment must cite at least one template release")
        self._conn.execute(
            "INSERT INTO template_selections (assessment_id, tenant_id, suggested_industry_slug, "
            " selected_release_ids, selected_by) VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (assessment_id) DO UPDATE SET "
            " suggested_industry_slug = EXCLUDED.suggested_industry_slug, "
            " selected_release_ids = EXCLUDED.selected_release_ids, "
            " selected_by = EXCLUDED.selected_by, selected_at = now()",
            (
                assessment_id,
                tenant_id,
                suggested_industry_slug,
                list(selected_release_ids),
                selected_by,
            ),
        )

    def find_assessment_for_session(
        self, source_session_id: str, *, tenant_id: str
    ) -> dict[str, Any] | None:
        """READ COMMITTED · no lock · read. The assessment a discovery session opened, if any.

        The back-reference is informational on `assessments` (nullable, no foreign key), so this is
        a plain filtered read — and tenant-scoped like every other assessment operation, because a
        session id is no more a permission than an assessment id is.
        """
        return self._row(
            "SELECT id, tenant_id, organization_id, source_session_id, started_at, completed_at "
            "FROM assessments WHERE source_session_id = %s AND tenant_id = %s "
            "ORDER BY started_at DESC LIMIT 1",
            (source_session_id, tenant_id),
        )

    def find_open_assessment(self, *, tenant_id: str) -> dict[str, Any] | None:
        """READ COMMITTED · no lock · read. The tenant's unfinished assessment, if one exists.

        By TENANT, not by session — which is the whole point. A customer who closes the tab during
        the sector stage comes back with no session id in hand; without this read their answers are
        unreachable and the only way forward is to start the interview again.

        Newest first, and one: `started_at DESC LIMIT 1`. Two open assessments would mean two
        unfinished interviews, and resuming the older one would silently discard the newer.
        """
        return self._row(
            "SELECT id, tenant_id, organization_id, source_session_id, started_at, completed_at "
            "FROM assessments WHERE tenant_id = %s AND completed_at IS NULL "
            "ORDER BY started_at DESC LIMIT 1",
            (tenant_id,),
        )

    def list_sector_answers(self, assessment_id: str, *, tenant_id: str) -> list[dict[str, Any]]:
        """READ COMMITTED · no lock · read. What has been answered so far.

        Separate from `load_plan_context`, which refuses an OPEN assessment because a plan must not
        be built from answers that can still change. This read is for the interview itself, which by
        definition runs while they still can — it is how a customer who comes back sees what they
        already said, without the browser having to remember it.
        """
        return self._rows(
            "SELECT release_id, question_id, answer FROM sector_answers "
            "WHERE assessment_id = %s AND tenant_id = %s ORDER BY question_id",
            (assessment_id, tenant_id),
        )

    def get_selection(self, assessment_id: str, *, tenant_id: str) -> dict[str, Any] | None:
        """READ COMMITTED · no lock · read. Which releases this assessment cites.

        Separate from `load_plan_context`, which refuses an OPEN assessment because a plan must not
        be built from answers that can still change. This one is for the interview itself, which by
        definition runs while the assessment is open.
        """
        return self._row(
            "SELECT suggested_industry_slug, selected_release_ids, selected_by, selected_at "
            "FROM template_selections WHERE assessment_id = %s AND tenant_id = %s",
            (assessment_id, tenant_id),
        )

    def save_sector_answers(
        self, *, assessment_id: str, tenant_id: str, answers: list[dict[str, Any]]
    ) -> None:
        """READ COMMITTED · no lock · explicit transaction · idempotent.

        All or nothing: answers arrive as a set, and half of them persisted is an interview that
        cannot be interpreted — the plan context built from it would be silently incomplete rather
        than obviously broken.

        No lock is needed because one assessment is answered by one interview; there is no second
        writer to race. Writing to a concluded assessment is refused by the schema.
        """
        _, jsonb, _ = _load_pg()
        with self._conn.transaction():
            for answer in answers:
                self._conn.execute(
                    "INSERT INTO sector_answers (assessment_id, release_id, question_id, "
                    " tenant_id, answer) VALUES (%s, %s, %s, %s, %s) "
                    "ON CONFLICT (assessment_id, release_id, question_id) DO UPDATE SET "
                    " answer = EXCLUDED.answer, answered_at = now()",
                    (
                        assessment_id,
                        answer["release_id"],
                        answer["question_id"],
                        tenant_id,
                        jsonb(answer.get("answer")),
                    ),
                )

    def complete_assessment(self, assessment_id: str, *, tenant_id: str, at: Any) -> bool:
        """READ COMMITTED · no lock · idempotent. One-way: the schema refuses re-opening.

        `tenant_id` is in the `WHERE`, not checked afterwards. Concluding is irreversible — after
        it, the schema refuses every further write — so a caller holding another tenant's id must
        find nothing rather than be told "not yours" once the row has already moved.
        """
        cur = self._conn.execute(
            "UPDATE assessments SET completed_at = %s "
            "WHERE id = %s AND tenant_id = %s AND completed_at IS NULL",
            (at, assessment_id, tenant_id),
        )
        return cur.rowcount == 1

    def load_plan_context(self, assessment_id: str, *, tenant_id: str) -> dict[str, Any] | None:
        """READ COMMITTED · no lock · read. **Concluded assessments only.**

        Every one of the reads carries `tenant_id` rather than trusting the first: the column is
        denormalised onto each table, and nothing in the schema yet binds a child row's tenant to
        its parent's, so "the assessment is mine" does not by itself prove "these answers are".

        Four reads with no snapshot, because a concluded assessment accepts no further writes:
        there is nothing left to tear. Refusing an open assessment is what makes that true — take
        it away and this needs snapshot isolation, which would hide a late write rather than
        prevent it.
        """
        assessment = self._row(
            "SELECT id, tenant_id, organization_id, source_session_id, started_at, completed_at "
            "FROM assessments WHERE id = %s AND tenant_id = %s",
            (assessment_id, tenant_id),
        )
        if assessment is None:
            # Indistinguishable from "no such assessment", deliberately: another tenant's id must
            # not be confirmable as existing.
            return None
        if assessment["completed_at"] is None:
            raise ValueError(
                f"assessment {assessment_id!r} is still open; a plan context may only be built "
                f"from a concluded assessment, whose answers can no longer change"
            )

        selection = self._row(
            "SELECT suggested_industry_slug, selected_release_ids, selected_by, selected_at "
            "FROM template_selections WHERE assessment_id = %s AND tenant_id = %s",
            (assessment_id, tenant_id),
        )
        answers = self._rows(
            "SELECT a.release_id, a.question_id, a.answer, q.canonical_text_ar, q.category, "
            ' q."references" '
            "FROM sector_answers a "
            "JOIN release_questions q ON q.release_id = a.release_id "
            " AND q.question_id = a.question_id "
            "WHERE a.assessment_id = %s AND a.tenant_id = %s "
            "ORDER BY a.release_id, q.position, a.question_id",
            (assessment_id, tenant_id),
        )
        return {"assessment": assessment, "selection": selection, "sector_answers": answers}
