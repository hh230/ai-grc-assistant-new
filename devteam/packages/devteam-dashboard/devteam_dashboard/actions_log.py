"""ActionsLog — the dashboard's own record of the approve/reject decisions IT performed.

Not a database and not business logic: an append-only JSONL audit of operator clicks, written next
to the monitor logs (outside the repo). It exists because the daemon log has no approve/reject
signal — the daemon never approves; a human does, via this dashboard (or ``operate.py --land``). So
the Metrics page's Approved/Rejected tiles are sourced from what the dashboard itself did. Losing
this file loses only those two counters, nothing operational.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

_APPROVED = "approved"
_REJECTED = "rejected"


@dataclass(frozen=True)
class ActionRecord:
    """One decision the dashboard carried out. ``at`` is epoch seconds; ``day`` its date."""

    action: str  # approved | rejected
    mission_id: str
    pr_number: int | None
    status: str  # the mission's resulting status (completed | cancelled)
    at: float
    day: str


@dataclass(frozen=True)
class ActionCounts:
    approved: int
    rejected: int


class ActionsLog:
    """Append/read the dashboard's approve|reject audit. All writes are a single appended JSON line;
    a missing/corrupt file reads as empty rather than raising, so the dashboard stays usable."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    def record(
        self, action: str, *, mission_id: str, status: str, pr_number: int | None = None
    ) -> ActionRecord:
        now = time.time()
        record = ActionRecord(
            action=action,
            mission_id=mission_id,
            pr_number=pr_number,
            status=status,
            at=now,
            day=datetime.fromtimestamp(now).date().isoformat(),
        )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_to_json(record)) + "\n")
        return record

    def records(self) -> list[ActionRecord]:
        """Every decision, oldest first. Corrupt/partial lines are skipped, not fatal."""
        out: list[ActionRecord] = []
        for line in self._read_lines():
            parsed = _from_json(line)
            if parsed is not None:
                out.append(parsed)
        return out

    def counts(self, *, since: str | None = None) -> ActionCounts:
        """Approved/Rejected totals; ``since`` (``YYYY-MM-DD``) windows to that day onward."""
        approved = rejected = 0
        for record in self.records():
            if since is not None and record.day < since:
                continue
            if record.action == _APPROVED:
                approved += 1
            elif record.action == _REJECTED:
                rejected += 1
        return ActionCounts(approved=approved, rejected=rejected)

    @staticmethod
    def today() -> str:
        return date.today().isoformat()

    def _read_lines(self) -> list[str]:
        try:
            return self._path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []
        except OSError:
            return []


def _to_json(record: ActionRecord) -> dict[str, object]:
    return {
        "action": record.action,
        "mission_id": record.mission_id,
        "pr_number": record.pr_number,
        "status": record.status,
        "at": record.at,
        "day": record.day,
    }


def _from_json(line: str) -> ActionRecord | None:
    line = line.strip()
    if not line:
        return None
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    action = data.get("action")
    mission_id = data.get("mission_id")
    if action not in (_APPROVED, _REJECTED) or not isinstance(mission_id, str):
        return None
    pr_raw = data.get("pr_number")
    status_raw = data.get("status")
    at_raw = data.get("at")
    day_raw = data.get("day")
    return ActionRecord(
        action=action,
        mission_id=mission_id,
        pr_number=pr_raw if isinstance(pr_raw, int) else None,
        status=status_raw if isinstance(status_raw, str) else "",
        at=float(at_raw) if isinstance(at_raw, (int, float)) else 0.0,
        day=day_raw if isinstance(day_raw, str) else "",
    )
