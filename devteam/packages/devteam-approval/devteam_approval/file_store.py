"""A durable, file-backed ApprovalStore — the shared source of truth across processes.

Persistence only (save / load / list / delete), like ``InMemoryApprovalStore`` — all logic stays in
``ApprovalService``. The API process records decisions here; the daemon reads them here. Each write
is **read-merge-write** (read the whole file, apply this one request, write it back atomically via a
temp file + rename) so two writers — the API granting one request while the daemon opens another —
do not clobber each other's unrelated changes. A cross-process lock / real DB can replace this later
without touching the domain (that is the whole point of the Store being a pure Protocol).
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from pathlib import Path

from devteam_approval.approval import (
    Actor,
    ApprovalDecision,
    ApprovalOutcome,
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalStatus,
)


class FileApprovalStore:
    """A JSON-file realization of the ``ApprovalStore`` protocol."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def save(self, request: ApprovalRequest) -> None:
        requests = {r.id: r for r in self._read()}
        requests[request.id] = request
        self._write(requests.values())

    def load(self, request_id: str) -> ApprovalRequest | None:
        return next((r for r in self._read() if r.id == request_id), None)

    def list(self) -> tuple[ApprovalRequest, ...]:
        return self._read()

    def delete(self, request_id: str) -> None:
        remaining = [r for r in self._read() if r.id != request_id]
        self._write(remaining)

    # --- serialization ---

    def _read(self) -> tuple[ApprovalRequest, ...]:
        if not self._path.exists():
            return ()
        try:
            payload = json.loads(self._path.read_text())
        except (json.JSONDecodeError, OSError):
            return ()
        rows = payload if isinstance(payload, list) else []
        return tuple(_from_dict(row) for row in rows if isinstance(row, dict))

    def _write(self, requests: Iterable[ApprovalRequest]) -> None:
        rows = [_to_dict(r) for r in requests]
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(rows, indent=2))
        os.replace(tmp, self._path)  # atomic on POSIX — readers never see a half-written file


def _to_dict(request: ApprovalRequest) -> dict[str, object]:
    return {
        "id": request.id,
        "target_ref": request.target_ref,
        "resume_token": request.resume_token,
        "status": request.status.value,
        "expires_at": request.expires_at,
        "created_at": request.created_at,
        "policy": {
            "requirement": request.policy.requirement,
            "required_role": request.policy.required_role,
            "reason": request.policy.reason,
        },
        "decisions": [_decision_to_dict(d) for d in request.decisions],
    }


def _decision_to_dict(decision: ApprovalDecision) -> dict[str, object]:
    return {
        "id": decision.id,
        "outcome": decision.outcome.value,
        "actor": {
            "actor_id": decision.actor.actor_id,
            "name": decision.actor.name,
            "role": decision.actor.role,
        },
        "comment": decision.comment,
        "at": decision.at,
    }


def _from_dict(row: dict[str, object]) -> ApprovalRequest:
    policy_row = row.get("policy", {})
    policy_row = policy_row if isinstance(policy_row, dict) else {}
    decisions_row = row.get("decisions", [])
    decisions_row = decisions_row if isinstance(decisions_row, list) else []
    return ApprovalRequest(
        id=str(row.get("id", "")),
        target_ref=str(row.get("target_ref", "")),
        resume_token=str(row.get("resume_token", "")),
        status=ApprovalStatus(str(row.get("status", "pending"))),
        expires_at=float(row.get("expires_at", 0.0)),  # type: ignore[arg-type]
        created_at=float(row.get("created_at", 0.0)),  # type: ignore[arg-type]
        policy=ApprovalPolicy(
            requirement=str(policy_row.get("requirement", "")),
            required_role=str(policy_row.get("required_role", "")),
            reason=str(policy_row.get("reason", "")),
        ),
        decisions=tuple(
            _decision_from_dict(d) for d in decisions_row if isinstance(d, dict)
        ),
    )


def _decision_from_dict(row: dict[str, object]) -> ApprovalDecision:
    actor_row = row.get("actor", {})
    actor_row = actor_row if isinstance(actor_row, dict) else {}
    return ApprovalDecision(
        id=str(row.get("id", "")),
        outcome=ApprovalOutcome(str(row.get("outcome", "granted"))),
        actor=Actor(
            actor_id=str(actor_row.get("actor_id", "")),
            name=str(actor_row.get("name", "")),
            role=str(actor_row.get("role", "")),
        ),
        comment=str(row.get("comment", "")),
        at=float(row.get("at", 0.0)),  # type: ignore[arg-type]
    )
