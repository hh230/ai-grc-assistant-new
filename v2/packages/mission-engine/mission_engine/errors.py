"""Mission domain errors — raised at the aggregate boundary so illegal use fails loudly
(CLAUDE.md §22: fail loudly in dev, fail safe in prod). They are pure exceptions with no
infrastructure knowledge."""

from __future__ import annotations


class MissionError(Exception):
    """Base of every mission-domain error."""


class IllegalTransition(MissionError):
    """A lifecycle transition the state machine does not permit (ADR 0042 §7). The transition
    table is closed: anything not explicitly legal is rejected here, never silently allowed."""


class TenantMismatch(MissionError):
    """An attempt to touch a mission from a different tenant than it was created for. A mission
    cannot change tenant and cross-tenant access is impossible by construction (ADR 0040 §5)."""


class MissionNotFound(MissionError):
    """No mission with that id exists within the caller's tenant scope. Note the scoping: a
    mission that exists for another tenant is *not found*, never returned."""


class PlanError(MissionError):
    """An invalid plan — e.g. a plan with no steps, or an attempt to re-plan a mission that is
    not in a re-plannable state (ADR 0042 §12.6)."""


class ApprovalError(MissionError):
    """An approval-invariant violation (ADR 0044). Slice 1 raises it for the one-active-request
    invariant: attaching a second approval request while one is still pending (undecided). The
    `approve`/`reject` decision paths that will also use it are Slice 2."""
