"""Pure, driver-free translation between `governance_discovery` domain objects and plain storage
rows (ADR 0066 §2). Imports no database driver and does no I/O — mirrors `mission_store/codec.py`
(ADR 0043 §5–§6): `store.py` is the only module that knows psycopg, delegating all shape
translation here.
"""

from __future__ import annotations

from typing import Any

from governance_discovery.analysis import Applicability
from governance_discovery.plan import GovernancePlan, PlanEvent, PlanItem
from governance_discovery.session import DiscoverySession
from governance_discovery.signal import Signal, SignalSet, ValueType

CURRENT_SESSION_PAYLOAD_VERSION = 1
CURRENT_ANSWER_PAYLOAD_VERSION = 1

SESSION_COLUMNS: tuple[str, ...] = (
    "id",
    "tenant_id",
    "status",
    "active_pack_ids",
    "pack_versions",
    "current_question_id",
    "signals",
    "confidence_score",
    "applicability",
    "created_at",
    "updated_at",
    "concluded_at",
)
SESSION_JSONB_COLUMNS: frozenset[str] = frozenset(
    {"active_pack_ids", "pack_versions", "signals", "applicability"}
)

ANSWER_COLUMNS: tuple[str, ...] = (
    "id",
    "session_id",
    "tenant_id",
    "sequence",
    "question_id",
    "question_version",
    "raw_answer",
    "resolved_signal_key",
    "resolved_signal_value",
    "normalized_by",
    "llm_model_version",
    "llm_confidence",
    "created_at",
)
ANSWER_JSONB_COLUMNS: frozenset[str] = frozenset({"raw_answer"})

PLAN_COLUMNS: tuple[str, ...] = (
    "id",
    "tenant_id",
    "source_session_id",
    "source_mission_id",
    "status",
    "version",
    "previous_plan_id",
    "inferred_frameworks",
    "maturity_baseline",
    "maturity_at_supersession",
    "executive_summary",
    "top_risks",
    "created_at",
    "updated_at",
)
PLAN_JSONB_COLUMNS: frozenset[str] = frozenset(
    {"inferred_frameworks", "maturity_baseline", "maturity_at_supersession", "top_risks"}
)

PLAN_ITEM_COLUMNS: tuple[str, ...] = (
    "id",
    "plan_id",
    "tenant_id",
    "pillar",
    "title",
    "title_key",
    "objective",
    "objective_key",
    "expected_outcome",
    "rationale",
    "timeframe_bucket",
    "priority",
    "effort_size",
    "depends_on_item_ids",
    "status",
    "due_at",
    "completed_at",
    "source_signal_keys",
    "source_framework_refs",
    "resolves_signal",
    "evidence_ids",
    "confidence",
    "risk_if_skipped",
    "revisit_at",
    "created_at",
    "updated_at",
)
PLAN_ITEM_JSONB_COLUMNS: frozenset[str] = frozenset(
    {
        "depends_on_item_ids",
        "source_signal_keys",
        "source_framework_refs",
        "resolves_signal",
        "evidence_ids",
    }
)

PLAN_EVENT_COLUMNS: tuple[str, ...] = (
    "id",
    "plan_item_id",
    "tenant_id",
    "event_type",
    "actor_id",
    "created_at",
)
# `sequence` is database-assigned (`GENERATED ALWAYS AS IDENTITY`) — never written, only read, so
# it is a separate column list rather than added to `PLAN_EVENT_COLUMNS` (which `append_plan_event`
# uses to build its INSERT).
PLAN_EVENT_READ_COLUMNS: tuple[str, ...] = ("sequence", *PLAN_EVENT_COLUMNS)


# --- Signal <-> plain dict (nested inside the session row's `signals` jsonb) -------------------


def _signal_to_dict(signal: Signal) -> dict[str, Any]:
    return {
        "value_type": signal.value_type.value,
        "value": signal.value,
        "confidence": signal.confidence,
        "source_answer_id": signal.source_answer_id,
    }


def _signal_from_dict(key: str, data: dict[str, Any]) -> Signal:
    return Signal(
        key=key,
        value_type=ValueType(data["value_type"]),
        value=data.get("value"),
        confidence=float(data.get("confidence", 1.0)),
        source_answer_id=data.get("source_answer_id"),
    )


def signal_set_to_dict(signals: SignalSet) -> dict[str, Any]:
    # SignalSet has no __iter__ (only .keys()/.get()), so `for key in signals` is not an option.
    return {key: _signal_to_dict(signals.get(key)) for key in signals.keys()}  # noqa: SIM118


def signal_set_from_dict(data: dict[str, Any] | None) -> SignalSet:
    return SignalSet({key: _signal_from_dict(key, value) for key, value in (data or {}).items()})


# --- Applicability <-> plain dict (the session row's `applicability` jsonb) ---------------------


def applicability_to_dict(applicability: Applicability) -> dict[str, Any]:
    return {
        "frameworks": list(applicability.frameworks),
        "maturity": applicability.maturity,
        "maturity_vision": applicability.maturity_vision,
        "capacity": applicability.capacity,
        "gaps": list(applicability.gaps),
        "plan_items": list(applicability.plan_items),
        "confidence_score": applicability.confidence_score,
        "confidence": applicability.confidence,
    }


def applicability_from_dict(data: dict[str, Any] | None) -> Applicability | None:
    if data is None:
        return None
    return Applicability(
        frameworks=tuple(data.get("frameworks", ())),
        maturity=data.get("maturity", {}),
        maturity_vision=data.get("maturity_vision", {}),
        capacity=data.get("capacity", {}),
        gaps=tuple(data.get("gaps", ())),
        plan_items=tuple(data.get("plan_items", ())),
        confidence_score=float(data.get("confidence_score", 0.0)),
        confidence=data.get("confidence", "low"),
    )


# --- write side: DiscoverySession -> row --------------------------------------------------------


def session_to_row(session: DiscoverySession) -> dict[str, Any]:
    return {
        "id": session.id,
        "tenant_id": session.tenant_id,
        "status": session.status,
        "active_pack_ids": list(session.active_pack_ids),
        "pack_versions": dict(session.pack_versions),
        "current_question_id": session.current_question_id,
        "signals": signal_set_to_dict(session.signals),
        "confidence_score": session.confidence_score,
        "applicability": (
            applicability_to_dict(session.applicability)
            if session.applicability is not None
            else None
        ),
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "concluded_at": session.concluded_at,
    }


# --- read side: row -> DiscoverySession -----------------------------------------------------


def session_from_row(
    row: dict[str, Any], answered_question_ids: frozenset[str]
) -> DiscoverySession:
    """`answered_question_ids` is NOT derivable from this row alone — signal keys and question ids
    are different namespaces (many questions can write the same signal key over a session's
    lifetime, e.g. after a 'go back' edit), and the session row does not duplicate the answers
    log. It is the caller's (the store's) job to compute the latest-per-question_id set from
    `discovery_answers` and pass it in here — that append-only log is the single source of truth
    for "what has been answered" (CLAUDE.md §19)."""
    return DiscoverySession(
        id=row["id"],
        tenant_id=row["tenant_id"],
        status=row["status"],
        signals=signal_set_from_dict(row.get("signals")),
        answered_question_ids=answered_question_ids,
        active_pack_ids=tuple(row.get("active_pack_ids") or ()),
        pack_versions=dict(row.get("pack_versions") or {}),
        confidence_score=float(row.get("confidence_score", 0.0)),
        applicability=applicability_from_dict(row.get("applicability")),
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
        concluded_at=float(row["concluded_at"]) if row.get("concluded_at") is not None else None,
        current_question_id=row.get("current_question_id"),
    )


# --- DiscoveryAnswer (append-only audit row) ----------------------------------------------------


def answer_to_row(
    *,
    answer_id: str,
    session_id: str,
    tenant_id: str,
    sequence: int,
    question_id: str,
    question_version: str,
    raw_answer: Any,
    resolved_signal_key: str | None,
    resolved_signal_value: Any,
    normalized_by: str,
    llm_model_version: str | None,
    llm_confidence: float | None,
    created_at: float,
) -> dict[str, Any]:
    return {
        "id": answer_id,
        "session_id": session_id,
        "tenant_id": tenant_id,
        "sequence": sequence,
        "question_id": question_id,
        "question_version": question_version,
        "raw_answer": raw_answer,
        "resolved_signal_key": resolved_signal_key,
        # stored as text (schema column is `text`); the typed value lives in the session's
        # `signals` jsonb — this column is an audit/display convenience, not the source of truth.
        "resolved_signal_value": (
            None if resolved_signal_value is None else str(resolved_signal_value)
        ),
        "normalized_by": normalized_by,
        "llm_model_version": llm_model_version,
        "llm_confidence": llm_confidence,
        "created_at": created_at,
    }


# --- GovernancePlan <-> row (ADR 0066 §3.1: immutable snapshots — insert-only, never updated in
# place except the one `superseded`/`maturity_at_supersession` transition) ----------------------


def plan_to_row(plan: GovernancePlan) -> dict[str, Any]:
    return {
        "id": plan.id,
        "tenant_id": plan.tenant_id,
        "source_session_id": plan.source_session_id,
        "source_mission_id": plan.source_mission_id,
        "status": plan.status,
        "version": plan.version,
        "previous_plan_id": plan.previous_plan_id,
        "inferred_frameworks": list(plan.inferred_frameworks),
        "maturity_baseline": plan.maturity_baseline,
        "maturity_at_supersession": plan.maturity_at_supersession,
        "executive_summary": plan.executive_summary,
        "top_risks": list(plan.top_risks),
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
    }


def plan_from_row(row: dict[str, Any]) -> GovernancePlan:
    return GovernancePlan(
        id=row["id"],
        tenant_id=row["tenant_id"],
        source_session_id=row.get("source_session_id"),
        source_mission_id=row["source_mission_id"],
        status=row["status"],
        version=int(row.get("version", 1)),
        previous_plan_id=row.get("previous_plan_id"),
        inferred_frameworks=tuple(row.get("inferred_frameworks") or ()),
        maturity_baseline=row.get("maturity_baseline") or {},
        maturity_at_supersession=row.get("maturity_at_supersession"),
        executive_summary=row.get("executive_summary"),
        top_risks=tuple(row.get("top_risks") or ()),
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
    )


# --- PlanItem <-> row -----------------------------------------------------------------------


def plan_item_to_row(item: PlanItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "plan_id": item.plan_id,
        "tenant_id": item.tenant_id,
        "pillar": item.pillar,
        "title": item.title,
        "title_key": item.title_key,
        "objective": item.objective,
        "objective_key": item.objective_key,
        "expected_outcome": item.expected_outcome,
        "rationale": item.rationale,
        "timeframe_bucket": item.timeframe_bucket,
        "priority": item.priority,
        "effort_size": item.effort_size,
        "depends_on_item_ids": list(item.depends_on_item_ids),
        "status": item.status,
        "due_at": item.due_at,
        "completed_at": item.completed_at,
        "source_signal_keys": list(item.source_signal_keys),
        "source_framework_refs": list(item.source_framework_refs),
        "resolves_signal": item.resolves_signal,
        "evidence_ids": list(item.evidence_ids),
        "confidence": item.confidence,
        "risk_if_skipped": item.risk_if_skipped,
        "revisit_at": item.revisit_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def plan_item_from_row(row: dict[str, Any]) -> PlanItem:
    return PlanItem(
        id=row["id"],
        plan_id=row["plan_id"],
        tenant_id=row["tenant_id"],
        pillar=row["pillar"],
        title=row["title"],
        # `.get`, not `[...]`: a row read from a database that predates these columns has no such
        # key, and a plan drafted before they existed must keep rendering.
        title_key=row.get("title_key") or "",
        objective=row["objective"],
        objective_key=row.get("objective_key") or "",
        expected_outcome=row["expected_outcome"],
        rationale=row["rationale"],
        timeframe_bucket=row["timeframe_bucket"],
        priority=row["priority"],
        effort_size=row["effort_size"],
        depends_on_item_ids=tuple(row.get("depends_on_item_ids") or ()),
        status=row["status"],
        due_at=row.get("due_at"),
        completed_at=row.get("completed_at"),
        source_signal_keys=tuple(row.get("source_signal_keys") or ()),
        source_framework_refs=tuple(row.get("source_framework_refs") or ()),
        resolves_signal=row.get("resolves_signal"),
        evidence_ids=tuple(row.get("evidence_ids") or ()),
        confidence=row.get("confidence"),
        risk_if_skipped=row.get("risk_if_skipped"),
        revisit_at=row.get("revisit_at"),
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
    )


# --- PlanEvent (append-only audit row, ADR 0066 §5.3) ----------------------------------------


def plan_event_to_row(
    *,
    event_id: str,
    plan_item_id: str,
    tenant_id: str,
    event_type: str,
    actor_id: str,
    created_at: float,
) -> dict[str, Any]:
    return {
        "id": event_id,
        "plan_item_id": plan_item_id,
        "tenant_id": tenant_id,
        "event_type": event_type,
        "actor_id": actor_id,
        "created_at": created_at,
    }


def plan_event_from_row(row: dict[str, Any]) -> PlanEvent:
    return PlanEvent(
        id=row["id"],
        sequence=int(row["sequence"]),
        plan_item_id=row["plan_item_id"],
        tenant_id=row["tenant_id"],
        event_type=row["event_type"],
        actor_id=row["actor_id"],
        created_at=float(row["created_at"]),
    )
