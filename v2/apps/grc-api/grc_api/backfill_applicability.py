"""Backfill v1 applicability versions from what is already stored (ADR 0068 §D9).

    python -m grc_api.backfill_applicability --dry-run
    python -m grc_api.backfill_applicability

The rule this obeys, and the reason it is a separate command rather than a line in a migration:
**it never runs the engine.** Every decision it records already exists — `discovery_sessions`
holds the `applicability` computed when each session concluded — so the job is to COPY it, not to
recompute it. Recomputing would quietly re-decide old plans with today's rules, which is precisely
the failure the versioned table exists to prevent.

Provenance is reconstructed from stored rows, not guessed: `discovery_answers` is append-only, so
a signal with an answer row was ANSWERED, and a signal in the session's blob with no answer row was
DERIVED. Nothing is inferred from the shape of the value.

What it will not do:

* invent a version for a session that never stored an applicability — those are counted and
  reported, and their plans keep `source_applicability_id = NULL`. "Not recorded" is a fact about
  the past; filling it in with a fresh computation would be a lie with a timestamp.
* run twice. `ON CONFLICT DO NOTHING` plus the table's unique index make a second run a no-op.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from typing import Any

CORE_CONCLUSION = "core_conclusion"


@dataclass(frozen=True)
class BackfillReport:
    sessions_eligible: int
    versions_written: int
    versions_already_present: int
    sessions_without_applicability: int
    plans_linked: int
    plans_left_unlinked: int

    def render(self) -> str:
        return "\n".join(
            (
                f"  concluded sessions with a stored applicability : {self.sessions_eligible}",
                f"  v1 versions written                            : {self.versions_written}",
                "  v1 versions already present (re-run)           : "
                f"{self.versions_already_present}",
                f"  concluded sessions with NO stored applicability : "
                f"{self.sessions_without_applicability}  (no version — left as-is)",
                f"  plans linked to their v1                       : {self.plans_linked}",
                f"  plans left unlinked                            : {self.plans_left_unlinked}",
            )
        )


def _version_id(tenant_id: str, session_id: str) -> str:
    """Deterministic, so a re-run computes the same id and collides with itself rather than
    inserting a duplicate under a fresh uuid."""
    digest = hashlib.sha256(f"{tenant_id}|{session_id}|1".encode()).hexdigest()[:32]
    return f"av_{digest}"


def _resolved_signals(signals: dict[str, Any], answered: set[str]) -> list[dict[str, Any]]:
    """One record per signal the session carried, marked by what the stored rows can prove."""
    return [
        {
            "signal_key": key,
            "resolved_value": value,
            "origin": "core_answer" if key in answered else "derivation",
            "outcome": "absent_filled",
            "core_claim": {"value": value} if key in answered else None,
            "sector_claims": [],
        }
        for key, value in sorted(signals.items())
    ]


def backfill(connection: Any, *, dry_run: bool = False) -> BackfillReport:
    from psycopg.rows import dict_row

    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, tenant_id, signals, applicability, pack_versions, concluded_at "
            "FROM discovery_sessions WHERE status = 'concluded'"
        )
        sessions = list(cur.fetchall())

    with_applicability = [s for s in sessions if s["applicability"] is not None]
    without = len(sessions) - len(with_applicability)

    written = already = 0
    for session in with_applicability:
        version_id = _version_id(session["tenant_id"], session["id"])
        answered = _answered_signal_keys(connection, session["id"])
        signals = session["signals"] or {}
        if dry_run:
            written += 1
            continue
        from psycopg.types.json import Jsonb

        cur = connection.execute(
            "INSERT INTO session_applicability_versions "
            "(id, tenant_id, session_id, version, source, applicability, resolved_signals, "
            " conflicts, answer_set_hash, engine_pack_versions, computed_at) "
            "VALUES (%(id)s, %(tenant)s, %(session)s, 1, %(source)s, %(applicability)s, "
            "%(resolved)s, '[]'::jsonb, %(hash)s, %(packs)s, "
            "COALESCE(to_timestamp(%(at)s), now())) "
            # Every constraint, not just the primary key. Since ADR 0068's fix, the discovery
            # conclusion writes v1 itself under its own id — so a session can already HAVE a v1
            # that this row would duplicate on (tenant_id, session_id, version) while colliding
            # with nothing on `id`. Naming one conflict target would turn "already done" into a
            # crash halfway through a production backfill.
            "ON CONFLICT DO NOTHING",
            {
                "id": version_id,
                "tenant": session["tenant_id"],
                "session": session["id"],
                "source": CORE_CONCLUSION,
                # The stored jsonb, moved across untouched. No engine call anywhere in this file.
                "applicability": Jsonb(session["applicability"]),
                "resolved": Jsonb(_resolved_signals(signals, answered)),
                "hash": _hash(signals),
                "packs": Jsonb(session["pack_versions"] or {}),
                "at": session["concluded_at"],
            },
        )
        if cur.rowcount == 1:
            written += 1
        else:
            already += 1

    linked, unlinked = _link_plans(connection, dry_run=dry_run)
    return BackfillReport(
        sessions_eligible=len(with_applicability),
        versions_written=written,
        versions_already_present=already,
        sessions_without_applicability=without,
        plans_linked=linked,
        plans_left_unlinked=unlinked,
    )


def _answered_signal_keys(connection: Any, session_id: str) -> set[str]:
    """Which of a session's signals came from an actual answer. `raw_answer IS NULL` means the
    question was SKIPPED, so it proves nothing and is excluded."""
    rows = connection.execute(
        "SELECT DISTINCT resolved_signal_key FROM discovery_answers "
        "WHERE session_id = %s AND raw_answer IS NOT NULL",
        (session_id,),
    ).fetchall()
    return {r[0] for r in rows if r[0]}


def _hash(signals: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(signals, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def _link_plans(connection: Any, *, dry_run: bool) -> tuple[int, int]:
    if dry_run:
        # Counted against the SESSIONS a v1 would be written for, not against the versions table —
        # in a dry run nothing has been written, and joining on an empty table would report zero
        # and read as "this backfill links nothing".
        row = connection.execute(
            "SELECT count(*) FROM governance_plans p JOIN discovery_sessions s "
            "  ON s.id = p.source_session_id AND s.tenant_id = p.tenant_id "
            "WHERE s.status = 'concluded' AND s.applicability IS NOT NULL "
            "  AND p.source_applicability_id IS NULL"
        ).fetchone()
        linked = int(row[0]) if row else 0
    else:
        cur = connection.execute(
            "UPDATE governance_plans p SET source_applicability_id = v.id "
            "FROM session_applicability_versions v "
            "WHERE v.session_id = p.source_session_id AND v.tenant_id = p.tenant_id "
            "  AND v.version = 1 AND p.source_applicability_id IS NULL"
        )
        linked = cur.rowcount
    remaining = connection.execute(
        "SELECT count(*) FROM governance_plans WHERE source_applicability_id IS NULL"
    ).fetchone()
    return linked, int(remaining[0]) if remaining else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill v1 applicability versions (ADR 0068).")
    parser.add_argument("--dry-run", action="store_true", help="count only, write nothing")
    args = parser.parse_args(argv)

    import psycopg

    from grc_api.migrate import MigrationError, core_dsn

    try:
        dsn = core_dsn()
    except MigrationError as exc:
        print(f"backfill: {exc}", file=sys.stderr)
        return 2

    with psycopg.connect(dsn) as conn:
        report = backfill(conn, dry_run=args.dry_run)
        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()
    print(("would backfill" if args.dry_run else "backfilled") + ":")
    print(report.render())
    return 0


if __name__ == "__main__":
    sys.exit(main())
