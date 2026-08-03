"""`PostgresGovernanceStore` — durable persistence for `DiscoverySession` + its answer log (ADR
0066 §2, §3 "Persistence"). Mirrors `mission_store.store.PostgresMissionStore` (ADR 0043) closely:
tenant isolation enforced in SQL, the psycopg driver imported lazily so the package (and the pure
codec) import with no driver present, autocommit connections (each call is one durable write/read,
except `record_item_transition`, which explicitly spans two statements in one transaction — see
its docstring, Phase 3 hardening).

`discovery_answers` is append-only (ADR 0066 §2): `append_answer` always INSERTs at the next
sequence for the session, never UPDATEs — re-answering a question writes a new row, and
`answered_question_ids`/history reads take the *latest* row per `question_id`.

Governance Plans/Items are immutable snapshots once created (ADR 0066 §3.1): `create_plan`/
`create_plan_item` are INSERT-only, and the only legitimate mutations afterward are
`supersede_plan` (a plan's one status transition) and `record_item_transition` (an item's
status/evidence, optimistically locked on `updated_at`) — there is no general-purpose "overwrite
this plan/item" method to reach for by mistake.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from governance_discovery.plan import GovernancePlan, PlanEvent, PlanItem
from governance_discovery.session import DiscoverySession
from governance_discovery.signal import SignalSet

from governance_store.codec import (
    ANSWER_COLUMNS,
    ANSWER_JSONB_COLUMNS,
    PLAN_COLUMNS,
    PLAN_EVENT_COLUMNS,
    PLAN_EVENT_READ_COLUMNS,
    PLAN_ITEM_COLUMNS,
    PLAN_ITEM_JSONB_COLUMNS,
    PLAN_JSONB_COLUMNS,
    SESSION_COLUMNS,
    SESSION_JSONB_COLUMNS,
    answer_to_row,
    plan_event_from_row,
    plan_event_to_row,
    plan_from_row,
    plan_item_from_row,
    plan_item_to_row,
    plan_to_row,
    session_from_row,
    session_to_row,
    signal_set_from_dict,
    signal_set_to_dict,
)
from governance_store.config import (
    TABLE_DISCOVERY_ANSWERS,
    TABLE_DISCOVERY_SESSIONS,
    TABLE_GOVERNANCE_PLAN_EVENTS,
    TABLE_GOVERNANCE_PLAN_ITEMS,
    TABLE_GOVERNANCE_PLANS,
    TABLE_ORGANIZATION_PROFILES,
)
from governance_store.config import dsn as default_dsn

if TYPE_CHECKING:  # import only for type checkers; never required at runtime to import the module
    import psycopg

_MISSING_PG = (
    "PostgresGovernanceStore needs the 'psycopg' package. "
    "Install the optional extra: governance-store[postgres]"
)


def _load_pg() -> tuple[Any, Any, Any]:
    try:
        import psycopg
        from psycopg.rows import dict_row
        from psycopg.types.json import Jsonb
    except ImportError as exc:  # pragma: no cover - exercised only without the extra installed
        raise ImportError(_MISSING_PG) from exc
    return psycopg, Jsonb, dict_row


class AnswerRecord:
    """One row from `discovery_answers`, as read back (a plain, typed view over the raw row)."""

    __slots__ = ("question_id", "sequence", "raw_answer", "resolved_signal_key")

    def __init__(self, question_id: str, sequence: int, raw_answer: Any, resolved_signal_key: str | None):
        self.question_id = question_id
        self.sequence = sequence
        self.raw_answer = raw_answer
        self.resolved_signal_key = resolved_signal_key


class PostgresGovernanceStore:
    def __init__(
        self,
        *,
        dsn: str | None = None,
        connection: psycopg.Connection | None = None,
    ) -> None:
        self._owns_conn = connection is None
        if connection is not None:
            self._conn = connection
        else:
            psycopg, _, _ = _load_pg()
            self._conn = psycopg.connect(dsn or default_dsn(), autocommit=True)

    # --- sessions -------------------------------------------------------------------------

    def save_session(self, session: DiscoverySession) -> None:
        """Upsert the session's current state. Tenant-guarded exactly like
        `PostgresMissionStore.save` (ADR 0040 §5): a cross-tenant overwrite is a no-op the caller
        must treat as an error."""
        psycopg, jsonb, _ = _load_pg()
        row = session_to_row(session)
        params = {
            col: (jsonb(row[col]) if col in SESSION_JSONB_COLUMNS and row[col] is not None else row[col])
            for col in SESSION_COLUMNS
        }
        assignments = ", ".join(f"{col} = EXCLUDED.{col}" for col in SESSION_COLUMNS if col != "id")
        placeholders = ", ".join(f"%({col})s" for col in SESSION_COLUMNS)
        sql = (
            f"INSERT INTO {TABLE_DISCOVERY_SESSIONS} ({', '.join(SESSION_COLUMNS)}) "
            f"VALUES ({placeholders}) "
            f"ON CONFLICT (id) DO UPDATE SET {assignments} "
            f"WHERE {TABLE_DISCOVERY_SESSIONS}.tenant_id = EXCLUDED.tenant_id"
        )
        cur = self._conn.execute(sql, params)
        if cur.rowcount == 0:
            raise ValueError(
                f"refused to overwrite discovery session {session.id}: belongs to a different tenant"
            )

    def get_session(self, session_id: str, tenant_id: str) -> DiscoverySession | None:
        _, _, dict_row = _load_pg()
        sql = (
            f"SELECT {', '.join(SESSION_COLUMNS)} FROM {TABLE_DISCOVERY_SESSIONS} "
            f"WHERE id = %(id)s AND tenant_id = %(tenant_id)s"
        )
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, {"id": session_id, "tenant_id": tenant_id})
            row = cur.fetchone()
        if row is None:
            return None
        answered = self.answered_question_ids(session_id, tenant_id)
        return session_from_row(row, answered_question_ids=answered)

    def find_in_progress_session(self, tenant_id: str) -> DiscoverySession | None:
        """The tenant's most recently updated `in_progress` session, if any — how the interview
        resumes without the client needing to remember a session id (ADR 0066 §Frontend)."""
        _, _, dict_row = _load_pg()
        sql = (
            f"SELECT {', '.join(SESSION_COLUMNS)} FROM {TABLE_DISCOVERY_SESSIONS} "
            f"WHERE tenant_id = %(tenant_id)s AND status = 'in_progress' "
            f"ORDER BY updated_at DESC LIMIT 1"
        )
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, {"tenant_id": tenant_id})
            row = cur.fetchone()
        if row is None:
            return None
        answered = self.answered_question_ids(row["id"], tenant_id)
        return session_from_row(row, answered_question_ids=answered)

    # --- answers (append-only) -------------------------------------------------------------

    def next_sequence(self, session_id: str) -> int:
        with self._conn.cursor() as cur:
            cur.execute(
                f"SELECT COALESCE(MAX(sequence), 0) + 1 FROM {TABLE_DISCOVERY_ANSWERS} "
                f"WHERE session_id = %(session_id)s",
                {"session_id": session_id},
            )
            (next_seq,) = cur.fetchone()
        return int(next_seq)

    def append_answer(self, **fields: Any) -> None:
        """`fields` matches `codec.answer_to_row`'s keyword arguments exactly."""
        psycopg, jsonb, _ = _load_pg()
        row = answer_to_row(**fields)
        params = {
            col: (jsonb(row[col]) if col in ANSWER_JSONB_COLUMNS and row[col] is not None else row[col])
            for col in ANSWER_COLUMNS
        }
        placeholders = ", ".join(f"%({col})s" for col in ANSWER_COLUMNS)
        sql = f"INSERT INTO {TABLE_DISCOVERY_ANSWERS} ({', '.join(ANSWER_COLUMNS)}) VALUES ({placeholders})"
        self._conn.execute(sql, params)

    def answer_history(self, session_id: str, tenant_id: str) -> list[AnswerRecord]:
        """Every answer ever given, in the order given (ascending `sequence`) — the raw material
        for both `answered_question_ids` (latest-per-question_id) and the interview's 'go back'
        breadcrumb (ADR 0066 §Frontend: only questions still in scope are shown)."""
        _, _, dict_row = _load_pg()
        sql = (
            "SELECT question_id, sequence, raw_answer, resolved_signal_key "
            f"FROM {TABLE_DISCOVERY_ANSWERS} "
            "WHERE session_id = %(session_id)s AND tenant_id = %(tenant_id)s "
            "ORDER BY sequence ASC"
        )
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, {"session_id": session_id, "tenant_id": tenant_id})
            rows = cur.fetchall()
        return [
            AnswerRecord(r["question_id"], r["sequence"], r["raw_answer"], r["resolved_signal_key"])
            for r in rows
        ]

    def answered_question_ids(self, session_id: str, tenant_id: str) -> frozenset[str]:
        return frozenset(record.question_id for record in self.answer_history(session_id, tenant_id))

    # --- governance plans (ADR 0066 §3.1: immutable snapshots) -----------------------------

    def create_plan(self, plan: GovernancePlan) -> None:
        """INSERT-only (Phase 3 hardening, ADR 0066 §3.1): a plan is a snapshot at creation and is
        never rewritten. This is the ONLY way a `governance_plans` row is ever created; the only
        legitimate change to an existing row afterward is the single status transition
        `supersede_plan` performs — nothing else may touch a plan's content, and nothing at this
        layer can, because no other write path exists. A duplicate `id` raises the driver's
        integrity error (a real bug in the caller's id generation, not an expected outcome)."""
        psycopg, jsonb, _ = _load_pg()
        row = plan_to_row(plan)
        params = {
            col: (jsonb(row[col]) if col in PLAN_JSONB_COLUMNS and row[col] is not None else row[col])
            for col in PLAN_COLUMNS
        }
        placeholders = ", ".join(f"%({col})s" for col in PLAN_COLUMNS)
        sql = f"INSERT INTO {TABLE_GOVERNANCE_PLANS} ({', '.join(PLAN_COLUMNS)}) VALUES ({placeholders})"
        self._conn.execute(sql, params)

    def supersede_plan(
        self, plan_id: str, tenant_id: str, *, maturity_at_supersession: dict, now: float
    ) -> bool:
        """The one legitimate mutation to an already-created plan (ADR 0066 §3.1): flips
        `active` -> `superseded` and stamps the live maturity it actually reached — never touches
        `executive_summary`/`top_risks`/`maturity_baseline`/any other content column, and the SQL
        itself cannot be made to (they are not in the SET list). `WHERE status = 'active'` makes
        double-supersession impossible: a plan can only ever make this transition once. Returns
        `False` — a plain no-op, not an exception — if the plan is missing, already superseded, or
        belongs to another tenant; the caller decides whether that is an error."""
        psycopg, jsonb, _ = _load_pg()
        sql = (
            f"UPDATE {TABLE_GOVERNANCE_PLANS} SET "
            "status = 'superseded', maturity_at_supersession = %(maturity_at_supersession)s, "
            "updated_at = %(updated_at)s "
            "WHERE id = %(id)s AND tenant_id = %(tenant_id)s AND status = 'active'"
        )
        cur = self._conn.execute(
            sql,
            {
                "id": plan_id,
                "tenant_id": tenant_id,
                "maturity_at_supersession": jsonb(maturity_at_supersession),
                "updated_at": now,
            },
        )
        return cur.rowcount > 0

    def get_plan(self, plan_id: str, tenant_id: str) -> GovernancePlan | None:
        _, _, dict_row = _load_pg()
        sql = (
            f"SELECT {', '.join(PLAN_COLUMNS)} FROM {TABLE_GOVERNANCE_PLANS} "
            f"WHERE id = %(id)s AND tenant_id = %(tenant_id)s"
        )
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, {"id": plan_id, "tenant_id": tenant_id})
            row = cur.fetchone()
        return plan_from_row(row) if row is not None else None

    def get_active_plan(self, tenant_id: str) -> GovernancePlan | None:
        _, _, dict_row = _load_pg()
        sql = (
            f"SELECT {', '.join(PLAN_COLUMNS)} FROM {TABLE_GOVERNANCE_PLANS} "
            f"WHERE tenant_id = %(tenant_id)s AND status = 'active' "
            f"ORDER BY version DESC LIMIT 1"
        )
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, {"tenant_id": tenant_id})
            row = cur.fetchone()
        return plan_from_row(row) if row is not None else None

    def list_plan_versions(self, tenant_id: str) -> list[GovernancePlan]:
        """Every version ever created for a tenant, oldest first — the raw material for a
        'compare versions' view (ADR 0066 §3.1)."""
        _, _, dict_row = _load_pg()
        sql = (
            f"SELECT {', '.join(PLAN_COLUMNS)} FROM {TABLE_GOVERNANCE_PLANS} "
            f"WHERE tenant_id = %(tenant_id)s ORDER BY version ASC"
        )
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, {"tenant_id": tenant_id})
            rows = cur.fetchall()
        return [plan_from_row(row) for row in rows]

    # --- plan items --------------------------------------------------------------------------

    # The only columns `record_item_transition` may write — exactly what `PlanItem.marked_done`/
    # `.reopened`/`.with_evidence` change (ADR 0066 §5.3/§5.4). Restricting the SET list to these,
    # rather than "every column but the id fields", means even a caller that passed a `PlanItem`
    # with some other field mutated (title, rationale, priority, ...) could not make that change
    # stick through this method — content is fixed at creation, full stop.
    _TRANSITION_COLUMNS: tuple[str, ...] = ("status", "completed_at", "evidence_ids", "updated_at")

    def create_plan_item(self, item: PlanItem) -> None:
        """INSERT-only (Phase 3 hardening, ADR 0066 §3.1/§5): a plan item's content is fixed the
        moment `finalize_plan` creates it. A duplicate `id` raises the driver's integrity error —
        `finalize_tool` always mints fresh composite ids per plan version, so a collision here is a
        real bug, never an expected outcome to swallow."""
        psycopg, jsonb, _ = _load_pg()
        row = plan_item_to_row(item)
        params = {
            col: (
                jsonb(row[col]) if col in PLAN_ITEM_JSONB_COLUMNS and row[col] is not None else row[col]
            )
            for col in PLAN_ITEM_COLUMNS
        }
        placeholders = ", ".join(f"%({col})s" for col in PLAN_ITEM_COLUMNS)
        sql = (
            f"INSERT INTO {TABLE_GOVERNANCE_PLAN_ITEMS} ({', '.join(PLAN_ITEM_COLUMNS)}) "
            f"VALUES ({placeholders})"
        )
        self._conn.execute(sql, params)

    def record_item_transition(
        self,
        item: PlanItem,
        *,
        expected_updated_at: float,
        event_id: str,
        event_type: str,
        actor_id: str,
        created_at: float,
    ) -> bool:
        """The ONLY way an existing plan item changes after creation (Phase 3 hardening) — and it
        changes together with its audit event, atomically, or not at all:

        - **Optimistic lock**: the UPDATE is gated `WHERE updated_at = expected_updated_at` (the
          value the caller read the item at). Two concurrent writers racing to complete/reopen/
          attach-evidence on the same item can no longer silently overwrite one another — the
          loser's UPDATE touches 0 rows, this returns `False`, and nothing (not even the event) is
          written; the caller decides how to surface that as a conflict.
        - **One transaction**: item + event commit together or not at all — a crash between them
          can no longer leave a "completed with no event" or "event with no status change" item.
        - **Tenant-safe by construction**: the event is only ever inserted after the item UPDATE
          (scoped `id = ... AND tenant_id = ...`) actually matched a row, so there is no separate
          trust-the-caller step for the event's tenant, unlike a bare `append_plan_event` call.
        """
        psycopg, jsonb, _ = _load_pg()
        row = plan_item_to_row(item)
        item_params: dict[str, Any] = {"id": item.id, "tenant_id": item.tenant_id, "expected_updated_at": expected_updated_at}
        for col in self._TRANSITION_COLUMNS:
            item_params[col] = jsonb(row[col]) if col in PLAN_ITEM_JSONB_COLUMNS and row[col] is not None else row[col]
        assignments = ", ".join(f"{col} = %({col})s" for col in self._TRANSITION_COLUMNS)
        item_sql = (
            f"UPDATE {TABLE_GOVERNANCE_PLAN_ITEMS} SET {assignments} "
            "WHERE id = %(id)s AND tenant_id = %(tenant_id)s AND updated_at = %(expected_updated_at)s"
        )
        event_row = plan_event_to_row(
            event_id=event_id, plan_item_id=item.id, tenant_id=item.tenant_id,
            event_type=event_type, actor_id=actor_id, created_at=created_at,
        )
        event_placeholders = ", ".join(f"%({col})s" for col in PLAN_EVENT_COLUMNS)
        event_sql = (
            f"INSERT INTO {TABLE_GOVERNANCE_PLAN_EVENTS} ({', '.join(PLAN_EVENT_COLUMNS)}) "
            f"VALUES ({event_placeholders})"
        )
        applied = False
        with self._conn.transaction():
            cur = self._conn.execute(item_sql, item_params)
            if cur.rowcount > 0:
                self._conn.execute(event_sql, event_row)
                applied = True
        return applied

    def get_plan_item(self, item_id: str, tenant_id: str) -> PlanItem | None:
        _, _, dict_row = _load_pg()
        sql = (
            f"SELECT {', '.join(PLAN_ITEM_COLUMNS)} FROM {TABLE_GOVERNANCE_PLAN_ITEMS} "
            f"WHERE id = %(id)s AND tenant_id = %(tenant_id)s"
        )
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, {"id": item_id, "tenant_id": tenant_id})
            row = cur.fetchone()
        return plan_item_from_row(row) if row is not None else None

    def list_plan_items(self, plan_id: str, tenant_id: str) -> list[PlanItem]:
        _, _, dict_row = _load_pg()
        sql = (
            f"SELECT {', '.join(PLAN_ITEM_COLUMNS)} FROM {TABLE_GOVERNANCE_PLAN_ITEMS} "
            f"WHERE plan_id = %(plan_id)s AND tenant_id = %(tenant_id)s"
        )
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, {"plan_id": plan_id, "tenant_id": tenant_id})
            rows = cur.fetchall()
        return [plan_item_from_row(row) for row in rows]

    def list_completed_resolutions(self, tenant_id: str) -> list[tuple[str, object, float]]:
        """Every `(signal, value, completed_at)` for items currently `status='done'` with a
        non-null `resolves_signal`, ACROSS every plan version for the tenant — not scoped to one
        `plan_id` (ADR 0066 §5.3: `effective_signals()`'s raw material; a tenant's 'current state'
        reflects everything they've ever completed, regardless of which plan version it came
        from)."""
        _, _, dict_row = _load_pg()
        sql = (
            "SELECT resolves_signal, completed_at FROM "
            f"{TABLE_GOVERNANCE_PLAN_ITEMS} "
            "WHERE tenant_id = %(tenant_id)s AND status = 'done' AND resolves_signal IS NOT NULL"
        )
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, {"tenant_id": tenant_id})
            rows = cur.fetchall()
        return [
            (row["resolves_signal"]["signal"], row["resolves_signal"]["value"], float(row["completed_at"]))
            for row in rows
            if row["completed_at"] is not None
        ]

    # --- plan events (append-only, ADR 0066 §5.3/§5.5) --------------------------------------

    def append_plan_event(self, **fields: Any) -> None:
        """`fields` matches `codec.plan_event_to_row`'s keyword arguments exactly.

        Defensive tenant check (Phase 3 hardening): verifies `plan_item_id` actually belongs to
        the given `tenant_id` before inserting — a bare INSERT would trust the caller's
        `tenant_id` blindly, and a wrong one would write an event under the wrong tenant with
        nothing to catch it. `record_item_transition` is the preferred path for
        mark_done/reopen/attach_evidence — it gets this same guarantee for free from its own
        UPDATE's `WHERE id = ... AND tenant_id = ...`, in the same transaction as the event; this
        method exists for any other caller that appends an event directly."""
        psycopg, jsonb, _ = _load_pg()
        row = plan_event_to_row(**fields)
        owner = self._conn.execute(
            f"SELECT tenant_id FROM {TABLE_GOVERNANCE_PLAN_ITEMS} WHERE id = %(id)s",
            {"id": row["plan_item_id"]},
        ).fetchone()
        if owner is None or owner[0] != row["tenant_id"]:
            raise ValueError(
                f"refused to record an event for plan item {row['plan_item_id']}: "
                "does not belong to the given tenant"
            )
        placeholders = ", ".join(f"%({col})s" for col in PLAN_EVENT_COLUMNS)
        sql = (
            f"INSERT INTO {TABLE_GOVERNANCE_PLAN_EVENTS} ({', '.join(PLAN_EVENT_COLUMNS)}) "
            f"VALUES ({placeholders})"
        )
        self._conn.execute(sql, row)

    def list_plan_events(self, plan_item_id: str, tenant_id: str) -> list[PlanEvent]:
        """The full audit trail for one item, in the order it actually happened — `sequence`, not
        `created_at`, is the ordering key (Phase 3 hardening: two events sharing a timestamp still
        sort deterministically)."""
        _, _, dict_row = _load_pg()
        sql = (
            f"SELECT {', '.join(PLAN_EVENT_READ_COLUMNS)} FROM {TABLE_GOVERNANCE_PLAN_EVENTS} "
            f"WHERE plan_item_id = %(plan_item_id)s AND tenant_id = %(tenant_id)s "
            f"ORDER BY sequence ASC"
        )
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, {"plan_item_id": plan_item_id, "tenant_id": tenant_id})
            rows = cur.fetchall()
        return [plan_event_from_row(row) for row in rows]

    # --- organization profile (the frozen baseline `effective_signals()` builds on, ADR 0066
    # §5.3/§5.7) ------------------------------------------------------------------------------

    def get_organization_baseline(self, tenant_id: str) -> tuple[SignalSet, tuple[str, ...]] | None:
        _, _, dict_row = _load_pg()
        sql = (
            "SELECT signals, active_packs FROM "
            f"{TABLE_ORGANIZATION_PROFILES} WHERE tenant_id = %(tenant_id)s"
        )
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, {"tenant_id": tenant_id})
            row = cur.fetchone()
        if row is None:
            return None
        return signal_set_from_dict(row["signals"]), tuple(row["active_packs"] or ())

    def upsert_organization_baseline(
        self, tenant_id: str, active_packs: tuple[str, ...], signals: SignalSet, now: float
    ) -> None:
        """Called once, when a discovery session concludes (the fix for the gap ADR 0066
        surfaced: nothing previously copied a concluded session's signals here). Overwrites any
        prior baseline — a tenant's baseline reflects their MOST RECENT concluded discovery, not
        an accumulation across sessions."""
        psycopg, jsonb, _ = _load_pg()
        params = {
            "tenant_id": tenant_id,
            "active_packs": jsonb(list(active_packs)),
            "signals": jsonb(signal_set_to_dict(signals)),
            "created_at": now,
            "updated_at": now,
        }
        sql = (
            f"INSERT INTO {TABLE_ORGANIZATION_PROFILES} "
            "(id, tenant_id, active_packs, signals, created_at, updated_at) "
            "VALUES (%(tenant_id)s, %(tenant_id)s, %(active_packs)s, %(signals)s, "
            "%(created_at)s, %(updated_at)s) "
            "ON CONFLICT (tenant_id) DO UPDATE SET "
            "active_packs = EXCLUDED.active_packs, signals = EXCLUDED.signals, "
            "updated_at = EXCLUDED.updated_at"
        )
        self._conn.execute(sql, params)

    # --- lifecycle ---------------------------------------------------------------------------

    def close(self) -> None:
        if self._owns_conn:
            self._conn.close()
