"""The Approval Domain — a generic, resumable approval model built ON the frozen Core (S5)."""

from __future__ import annotations

from devteam_approval.approval import (
    Actor,
    ApprovalDecision,
    ApprovalError,
    ApprovalOutcome,
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalStatus,
)
from devteam_approval.file_store import FileApprovalStore
from devteam_approval.service import ApprovalService
from devteam_approval.store import ApprovalStore, InMemoryApprovalStore

__all__ = [
    "Actor",
    "ApprovalDecision",
    "ApprovalError",
    "ApprovalOutcome",
    "ApprovalPolicy",
    "ApprovalRequest",
    "ApprovalService",
    "ApprovalStatus",
    "ApprovalStore",
    "FileApprovalStore",
    "InMemoryApprovalStore",
]
