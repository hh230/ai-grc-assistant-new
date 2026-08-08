"""Concluding a sector assessment, and the one recomputation it triggers (ADR 0068 §D5).

This is the only place in the product where a sector answer can change a decision, and it happens
exactly once per assessment, inside one transaction.

The ordering is deliberate and load-bearing:

    lock the assessment row      — two concurrent conclusions cannot both proceed
    refuse if already concluded  — conclusion is one-way; this is not a retry point
    read answers + declarations  — reads, so the freeze has not engaged yet
    resolve → derive → analyze   — pure computation, no I/O
    INSERT the applicability version
    UPDATE assessments SET completed_at  ← LAST: the freeze engages here
    COMMIT

`completed_at` goes last because ADR 0067's guard refuses every write to an assessment's rows once
it is set. Writing it first would make the reads above illegal in the same breath. And because all
of it is one transaction, a failure anywhere leaves neither a version nor a concluded assessment —
never a plan built on an analysis that half-exists.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from governance_discovery.analysis import analyze
from governance_discovery.resolution import Resolution, SectorClaim, resolve
from governance_discovery.signal import ValueType

SECTOR_CONCLUSION = "sector_conclusion"


class AlreadyConcluded(RuntimeError):
    """A concluded assessment is not re-concluded. Any future recomputation is a NEW, explicit,
    versioned operation with its own gate — never a second conclusion (ADR 0068 §D8)."""


@dataclass(frozen=True)
class ConclusionResult:
    assessment_id: str
    session_id: str | None
    version_id: str | None
    version: int | None
    conflicts: tuple[dict[str, Any], ...]
    claims_considered: int

    @property
    def recomputed(self) -> bool:
        return self.version_id is not None


def _claims(rows: list[dict[str, Any]], value_types: dict[str, ValueType]) -> list[SectorClaim]:
    """Answers that DECLARED a signal, turned into claims.

    The declared map is consulted by `option_id` and the answer's text is never read — that is what
    makes rewording or translating an option incapable of moving a decision. An answer whose option
    is not in the map, or maps to null, produces no claim at all: it is not a `False`.
    """
    claims: list[SectorClaim] = []
    for row in rows:
        signal_key = row.get("writes_signal")
        value_map = row.get("signal_value_map") or {}
        if not signal_key or signal_key not in value_types:
            continue
        option_id = _option_id(row.get("answer"))
        if option_id is None or option_id not in value_map:
            continue
        value = value_map[option_id]
        if value is None:
            continue
        claims.append(
            SectorClaim(
                signal_key=signal_key,
                value=value,
                release_id=str(row.get("release_id") or ""),
                question_id=str(row.get("question_id") or ""),
                option_id=option_id,
                value_type=value_types[signal_key],
            )
        )
    return claims


def _option_id(answer: Any) -> str | None:
    """The stored answer, as the id the declaration is keyed by.

    Booleans answer with the reserved ids 'true'/'false' so that every question type declares the
    same way. A list (a multi-select answer) returns None: multi-select is outside this channel
    until an ADR decides where its "if any of these" condition may live.
    """
    if isinstance(answer, bool):
        return "true" if answer else "false"
    if isinstance(answer, str):
        return answer
    return None


def _answer_set_hash(rows: list[dict[str, Any]]) -> str:
    """A fingerprint of the inputs, so a reader can tell 'the same answers' from 'the same
    result'. Sorted, because a hash that depends on row order describes the query, not the data."""
    material = sorted(
        (
            str(r.get("release_id")),
            str(r.get("question_id")),
            json.dumps(r.get("answer"), sort_keys=True, ensure_ascii=False),
        )
        for r in rows
    )
    return hashlib.sha256(json.dumps(material, ensure_ascii=False).encode()).hexdigest()


def conclude_sector_assessment(
    *,
    connection: Any,
    knowledge_store: Any,
    governance_store: Any,
    engine: Any,
    assessment_id: str,
    tenant_id: str,
    now: Any,
) -> ConclusionResult:
    """Conclude, and record the analysis that conclusion produced.

    Returns without a version — and without failing — when there is nothing to recompute: no
    session behind the assessment, or no answer that declared a signal. A sector interview that
    only gathered prose leaves the decision exactly where the core interview left it, which is the
    behaviour every shipped pack has today.
    """
    locked = connection.execute(
        "SELECT id, source_session_id, completed_at FROM assessments "
        "WHERE id = %s AND tenant_id = %s FOR UPDATE",
        (assessment_id, tenant_id),
    ).fetchone()
    if locked is None:
        raise LookupError(assessment_id)
    if locked[2] is not None:
        raise AlreadyConcluded(assessment_id)
    session_id = locked[1]

    rows = _answers_with_declarations(connection, assessment_id, tenant_id)
    value_types = _writable(engine)
    claims = _claims(rows, value_types)

    version_id: str | None = None
    version: int | None = None
    resolution: Resolution | None = None

    session = governance_store.get_session(session_id, tenant_id) if session_id else None
    if session is not None and claims:
        # v1 is NOT created here. It is written by the discovery conclusion that computed it
        # (`DiscoverySessionService._advance`), and its absence means this session concluded before
        # ADR 0068 — in which case `record_applicability_version` will refuse the row, because the
        # schema says version 1 IS the core conclusion. Backfilling it from here would be a second
        # write path for one fact, and would let a stale analysis be minted at an arbitrary later
        # moment. Historical sessions get their v1 from `grc_api.backfill_applicability`.
        resolution = resolve(session.signals, claims)
        applicability = analyze(resolution.signals, engine)
        version = governance_store.next_applicability_version(session_id, tenant_id)
        version_id = f"av_{uuid4().hex}"
        governance_store.record_applicability_version(
            version_id=version_id,
            tenant_id=tenant_id,
            session_id=session_id,
            version=version,
            source=SECTOR_CONCLUSION,
            assessment_id=assessment_id,
            applicability=_as_json(applicability),
            resolved_signals=resolution.as_audit(),
            conflicts=[c.as_dict() for c in resolution.conflicts],
            answer_set_hash=_answer_set_hash(rows),
            engine_pack_versions=dict(session.pack_versions or {}),
        )

    connection.execute(
        "UPDATE assessments SET completed_at = %s WHERE id = %s AND tenant_id = %s "
        "AND completed_at IS NULL",
        (now, assessment_id, tenant_id),
    )
    return ConclusionResult(
        assessment_id=assessment_id,
        session_id=session_id,
        version_id=version_id,
        version=version,
        conflicts=tuple(c.as_dict() for c in (resolution.conflicts if resolution else ())),
        claims_considered=len(claims),
    )


def _answers_with_declarations(
    connection: Any, assessment_id: str, tenant_id: str
) -> list[dict[str, Any]]:
    """Each answer beside the declaration of the question it answered.

    `tenant_id` is on the answer row and carried explicitly rather than inferred from the
    assessment — the same discipline `load_plan_context` follows, for the same reason.
    """
    from psycopg.rows import dict_row

    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT a.release_id, a.question_id, a.answer, q.writes_signal, q.signal_value_map "
            "FROM sector_answers a "
            "LEFT JOIN release_questions q "
            "  ON q.release_id = a.release_id AND q.question_id = a.question_id "
            "WHERE a.assessment_id = %s AND a.tenant_id = %s",
            (assessment_id, tenant_id),
        )
        return list(cur.fetchall())


def _writable(engine: Any) -> dict[str, ValueType]:
    from governance_discovery.writable_signals import writable_signals

    return writable_signals(engine.packs if hasattr(engine, "packs") else {})


def _as_json(applicability: Any) -> dict[str, Any]:
    from governance_store.codec import applicability_to_dict

    return applicability_to_dict(applicability)
