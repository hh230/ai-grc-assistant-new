"""ADR 0055 — the transaction boundary is the **command**; execution sits **outside** it.

The decision is two independently observable models, and this file has a section for each (ADR 0055
Implementation notes):

1. **The Consistency model.** A command is all-or-nothing: its mission write, its events, and its
   projection commit together, and one that fails half way leaves nothing behind. Delivered by the
   commit *introduce command-scoped durability*.
2. **The Temporal model.** Execution is not wrapped in a transaction: a recorded step is visible to
   another session *before* the mission finishes. This holds exactly when the command's transaction
   does not enclose execution — the constraint "the command owns the transaction, but not progress".

Every assertion reads raw rows through the `observer` session, never through the app. Asking *"what
can another session see?"* is the only honest way to test a transaction boundary.
"""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import Callable
from typing import Any

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mission_engine import StepResult

from tests.production.conftest import AUTH_A, Tables, connect, create_mission

# --- probes ------------------------------------------------------------------------------


class _VisibilityProbe:
    """An executor that, on every step, asks a **separate** session how much of this mission it can
    already see. It executes nothing real — its output is the visibility trace itself."""

    def __init__(self, missions_table: str) -> None:
        self._table = missions_table
        self.steps_visible_elsewhere: list[int] = []

    def execute(self, request: Any) -> StepResult:
        self.steps_visible_elsewhere.append(self._recorded_steps(request.mission_id))
        return StepResult(step_id=request.step_id, ok=True, output="probed")

    def _recorded_steps(self, mission_id: str) -> int:
        """How many step results another session can see. `-1` means the mission row itself is not
        visible — which is what an enclosing, uncommitted transaction would produce."""
        conn = connect(autocommit=True)
        try:
            row = conn.execute(
                f"SELECT step_results FROM {self._table} WHERE id = %s",  # noqa: S608 - test table
                (mission_id,),
            ).fetchone()
            if row is None:
                return -1
            return len(row[0] or [])
        finally:
            conn.close()


def _count(observer: psycopg.Connection, table: str, where: str = "", params: tuple = ()) -> int:
    clause = f" WHERE {where}" if where else ""
    row = observer.execute(f"SELECT count(*) FROM {table}{clause}", params).fetchone()  # noqa: S608
    assert row is not None
    return int(row[0])


# --- property 1: a command is all-or-nothing (fails on arrival) --------------------------


def test_a_mission_and_its_history_are_durable_together(
    client: TestClient,
    observer: psycopg.Connection,
    tables: Tables,
) -> None:
    """A durable mission must have a durable history. State without events means the audit trail
    lies about what happened — in a GRC product that is the failure that matters most.

    **Why this names the outbox.** The Transactional Outbox is frozen architecture (ADR 0043-S4),
    and ADR 0055's decision names the outbox sink explicitly as one of the command's three
    transactional participants. Reading that table is reading the decided contract, not guessing at
    an implementation.

    **What it deliberately does not assert:** *which* events a command emits. That belongs to the
    mission type's plan factory and must stay free to change without touching this test.
    """
    mission_id = create_mission(client)

    missions = _count(observer, tables.missions, "id = %s", (mission_id,))
    events = _count(observer, tables.outbox, "mission_id = %s", (mission_id,))

    assert missions == 1, "the mission was not persisted at all"
    assert events > 0, (
        "the mission is durable but its history is not — no events were captured for it. State and "
        "events must be written in one transaction (ADR 0055; ADR 0043-S4 invariants I1/I2)"
    )


def test_a_failed_command_leaves_nothing_behind(
    client: TestClient,
    observer: psycopg.Connection,
    tables: Tables,
) -> None:
    """The all-or-nothing property, stated as a failure: when one part of a command fails, no part
    of it survives. A mission row here means the command was **partially applied** — the dual write
    ADR 0055 exists to prevent.

    **How the failure is injected** matters, and this is the second thing Commit 3 taught. The
    failure is made to happen *at a participating sink inside the command's transaction* — here, the
    projection: its table is dropped, so the real projection INSERT raises mid-command. An earlier
    version swapped the whole read model for a failing stub, but the command scope builds its own
    projection bound to the transaction, so the stub was never reached — the injection point was
    *below* the property. Dropping the table injects at the real sink, through no test-only hook in
    production code.

    The test still says nothing about *how* atomicity is achieved: a shared unit of work, a
    compensating action, anything that leaves no residue satisfies it equally.
    """
    before = _count(observer, tables.missions)
    assert before == 0, "precondition: this test's throwaway table starts empty"

    # Make the projection sink fail as part of the command's transaction.
    observer.execute(f"DROP TABLE {tables.missions_view}")  # noqa: S608 - test-owned table

    with contextlib.suppress(Exception):
        # However the host surfaces the sink failure (500, or a raised exception through the test
        # client) is its business; the property is what the database is left holding.
        client.post(
            "/v1/missions",
            json={"type": "gap_assessment", "scope": "Technological controls", "document_ids": []},
            headers={**AUTH_A, "Idempotency-Key": uuid.uuid4().hex},
        )

    assert _count(observer, tables.missions) == before, (
        "a mission survived a command whose projection failed — mission write and projection are "
        "not in one transaction (ADR 0055; the dual write the outbox exists to prevent)"
    )


# --- property 2: the Temporal model — execution outside the transaction -------------------


def test_a_recorded_step_is_visible_to_another_session_mid_execution(
    build_app: Callable[..., FastAPI],
    tables: Tables,
) -> None:
    """The guard on ADR 0055's central property. Each step asks a separate session what it can see;
    step *n* must see the *n* steps before it. If execution were ever wrapped in one transaction,
    every probe would read 0 (or -1) and this test would fail — which is its whole purpose.

    **Per-step granularity is the ADR's wording, not this test's preference:** *"each step's state
    and events committed in their own short transaction."* A design that batched several steps per
    transaction would fail here — correctly, because it would be a different decision.
    """
    probe = _VisibilityProbe(tables.missions)
    app = TestClient(build_app(executor=probe))

    mission_id = create_mission(app)
    started = app.post(f"/v1/missions/{mission_id}/run", headers=AUTH_A)
    assert started.status_code == 200, started.text

    trace = probe.steps_visible_elsewhere
    assert len(trace) > 1, "need a multi-step plan to observe progress mid-execution"
    assert trace[0] == 0, (
        f"the first step could not see its own mission (saw {trace[0]}) — execution is running "
        "inside an uncommitted transaction"
    )
    assert trace == list(range(len(trace))), (
        f"steps did not become visible as they completed: {trace}. Execution appears to be wrapped "
        "in a single transaction (the rejected Option A of ADR 0055)"
    )


@pytest.mark.parametrize("mission_type", ["gap_assessment", "risk_assessment"])
def test_execution_progress_is_durable_per_step(
    build_app: Callable[..., FastAPI],
    observer: psycopg.Connection,
    tables: Tables,
    mission_type: str,
) -> None:
    """The same property from the other side: once a mission has run, its steps are durably recorded
    — not buffered in memory and flushed at the end."""
    app = TestClient(build_app())
    mission_id = create_mission(app, mission_type=mission_type)
    assert app.post(f"/v1/missions/{mission_id}/run", headers=AUTH_A).status_code == 200

    row = observer.execute(
        f"SELECT status, step_results FROM {tables.missions} WHERE id = %s",  # noqa: S608
        (mission_id,),
    ).fetchone()

    assert row is not None
    status, step_results = row
    assert status in {"completed", "awaiting_approval"}
    assert len(step_results or []) > 0, "the plan ran but recorded no durable step results"


# --- the launch boundary: a command's response describes the command, not execution --------


def test_run_response_describes_the_command_and_a_query_describes_execution(
    client: TestClient,
) -> None:
    """Migration rule 10 / ADR 0055, over real PostgreSQL. `POST /run` reports the *command* — it
    does not claim the execution it launched has finished. Completion is read afterward through a
    query. Asserted as the **separation**, not a status string, so it survives launch becoming a
    worker or a queue: the response must not say "completed", and a `GET` then shows it did."""
    mission_id = create_mission(client)

    started = client.post(f"/v1/missions/{mission_id}/run", headers=AUTH_A)
    assert started.status_code == 200, started.text
    assert started.json()["status"] != "completed", (
        "the /run response claimed the launched execution finished — the response is coupled to "
        "progress the command does not own (ADR 0055; migration rule 10)"
    )

    detail = client.get(f"/v1/missions/{mission_id}", headers=AUTH_A)
    assert detail.status_code == 200, detail.text
    assert detail.json()["status"] == "completed", (
        "execution did not complete, or the launch did not project its result to the read surfaces"
    )
