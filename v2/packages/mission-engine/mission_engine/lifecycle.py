"""The mission lifecycle state machine (ADR 0042 §7).

The **full** set of states is defined here from day one — including `AWAITING_APPROVAL`, the
re-plan path (`RESUMED`), and the terminal/`ARCHIVED` states — even though the first package
only *drives* the happy path `CREATED → PLANNED → EXECUTING → COMPLETED` (ADR 0042 §12.4).
Shipping a reduced three-state machine and growing it later is explicitly rejected: the gate
and re-plan transitions are legal in the table and enforced by the aggregate; they are simply
not exercised until Human Approval and multi-step planning land in later phases.

The transition table is **closed**: a `(src → dst)` pair absent from it is illegal by
construction and rejected at the aggregate boundary (`errors.IllegalTransition`), never
silently allowed. Terminal states permit only archival, which is what makes a completed,
failed, or cancelled mission immutable.
"""

from __future__ import annotations

from enum import Enum


class MissionStatus(str, Enum):
    CREATED = "created"                    # tenant + owner + goal bound (immutable identity)
    PLANNED = "planned"                    # a versioned plan is stored and inspectable
    EXECUTING = "executing"                # steps are dispatched to the ExecutionPort
    AWAITING_APPROVAL = "awaiting_approval"  # paused BEFORE a consequential step (human gate)
    RESUMED = "resumed"                    # approved/edited; may re-plan or re-enter execution
    COMPLETED = "completed"                # outputs + citations + decision trail finalized
    FAILED = "failed"                      # unrecoverable error; fail-safe
    CANCELLED = "cancelled"                # human cancellation; fail-safe
    ARCHIVED = "archived"                  # reconstructable for audit; the only post-terminal state


TERMINAL_STATES: frozenset[MissionStatus] = frozenset(
    {
        MissionStatus.COMPLETED,
        MissionStatus.FAILED,
        MissionStatus.CANCELLED,
        MissionStatus.ARCHIVED,
    }
)

# The legal transition table (ADR 0042 §7). Read each row as "from this state, only these
# states may be reached." Cancellation and failure are reachable from every non-terminal
# active state (fail-safe, §16 of CLAUDE.md); terminal states go only to ARCHIVED.
_LEGAL: dict[MissionStatus, frozenset[MissionStatus]] = {
    MissionStatus.CREATED: frozenset(
        {MissionStatus.PLANNED, MissionStatus.CANCELLED, MissionStatus.FAILED}
    ),
    MissionStatus.PLANNED: frozenset(
        {MissionStatus.EXECUTING, MissionStatus.CANCELLED, MissionStatus.FAILED}
    ),
    MissionStatus.EXECUTING: frozenset(
        {
            MissionStatus.AWAITING_APPROVAL,
            MissionStatus.COMPLETED,
            MissionStatus.FAILED,
            MissionStatus.CANCELLED,
        }
    ),
    MissionStatus.AWAITING_APPROVAL: frozenset(
        {MissionStatus.RESUMED, MissionStatus.CANCELLED, MissionStatus.FAILED}
    ),
    MissionStatus.RESUMED: frozenset(
        {
            MissionStatus.PLANNED,
            MissionStatus.EXECUTING,
            MissionStatus.CANCELLED,
            MissionStatus.FAILED,
        }
    ),
    MissionStatus.COMPLETED: frozenset({MissionStatus.ARCHIVED}),
    MissionStatus.FAILED: frozenset({MissionStatus.ARCHIVED}),
    MissionStatus.CANCELLED: frozenset({MissionStatus.ARCHIVED}),
    MissionStatus.ARCHIVED: frozenset(),
}


def can_transition(src: MissionStatus, dst: MissionStatus) -> bool:
    return dst in _LEGAL.get(src, frozenset())


def is_terminal(status: MissionStatus) -> bool:
    return status in TERMINAL_STATES
