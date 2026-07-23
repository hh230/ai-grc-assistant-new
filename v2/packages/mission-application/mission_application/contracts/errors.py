"""Typed Application errors (ADR 0054) — the failure vocabulary commands raise.

Framework-free: a command raises one of these; the HTTP host maps it to a status code, a CLI to an
exit code. Commands never raise `HTTPException` or know about HTTP. Each error names the *use-case*
failure, not a transport concern.
"""

from __future__ import annotations


class ApplicationError(Exception):
    """Base for every Application-layer failure."""


class NotAuthorized(ApplicationError):
    """The principal lacks the role this command requires (e.g. approve without Approver). → 403."""


class MissionNotFound(ApplicationError):
    """No such mission for this tenant — absent, or another tenant's (fail-closed). → 404."""


class IllegalCommand(ApplicationError):
    """Not valid in the mission's current state (e.g. approve when not waiting). → 409."""


class DeliverableNotReady(ApplicationError):
    """The mission has not completed, so its Result is not available yet (S3). → 409."""


class UnsupportedFormat(ApplicationError):
    """An export was requested in a format the service does not offer (S3). → 400."""
