"""Parse the ContinuousMonitor's plain-text log into structured entries and the operational metrics
the runbook defines (``docs/operations/runbook.md``).

PURE — no runtime imports, no I/O beyond reading the log file the caller names. This is the
dashboard's read-only window onto *what the daemon actually did*: the monitor logs via stdlib
logging with format ``"%(asctime)s %(levelname)s %(name)s: %(message)s"`` (monitor.py) to stderr,
so the LaunchAgent's ``monitor.err.log`` is the live feed. Metrics are counts of the specific
message shapes the monitor emits (``monitor.py`` ``_LOG`` calls); any other line (e.g. the one
``RuntimeWarning`` runpy prepends on start) is kept as a raw entry but ignored by the counters.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# "2026-07-29 00:49:44,106 INFO devteam.monitor: monitoring 0 open PR(s)"
_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3}) "
    r"(?P<level>[A-Z]+) (?P<logger>[\w.]+): (?P<msg>.*)$"
)

# Message shapes the monitor emits (monitor.py). These are the metric signals.
#   "PR 123: opened mission m-abc (attempt 2) — awaiting_approval"  (OPENED outcome)
_OPENED_RE = re.compile(
    r"^PR (?P<pr>\d+): opened mission (?P<mission>\S+) "
    r"\(attempt (?P<attempt>\d+)\) — (?P<status>\w+)$"
)
#   "PR 123: CI is green — chain resolved"                          (GREEN outcome)
_GREEN_RE = re.compile(r"^PR (?P<pr>\d+): CI is green — chain resolved$")
#   "chain pr-123 EXHAUSTED after 3 attempt(s): ..."               (alert)
_EXHAUSTED_RE = re.compile(
    r"^chain (?P<ref>\S+) EXHAUSTED after (?P<attempts>\d+) attempt\(s\): (?P<reason>.*)$"
)
#   "monitoring 3 open PR(s)"                                       (each tick)
_MONITORING_RE = re.compile(r"^monitoring (?P<count>\d+) open PR\(s\)$")

_AWAITING = "awaiting_approval"
_CANCELLED = "cancelled"


@dataclass(frozen=True)
class LogEntry:
    """One log line. ``timestamp``/``level``/``message`` are set when the line matched the monitor's
    logging format; a non-conforming line keeps only ``raw`` (still shown on the Logs page)."""

    raw: str
    timestamp: str | None = None
    level: str | None = None
    logger: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class DaemonPr:
    """The daemon's most recent mission opening for a PR, parsed from the log — the source of the
    'daemon: attempt N' annotation shown next to its own re-derived materialization."""

    pr_number: int
    mission_id: str
    attempt: int
    status: str  # awaiting_approval | cancelled


@dataclass(frozen=True)
class Metrics:
    """The runbook's operational metrics, derived from the log. ``approved``/``rejected`` are NOT in
    the daemon log (the daemon never approves) — the caller fills them from the dashboard's own
    ActionsLog; here they default to 0 so this stays a pure log function."""

    detected: int  # every 'opened mission' line — a failure the daemon acted on
    opened_missions: int  # those that reached awaiting_approval (a patch was produced)
    declined: int  # those that ended '— cancelled' (Developer produced no patch)
    green_ci: int  # 'CI is green — chain resolved'
    exhausted: int  # 'chain ... EXHAUSTED' — needs human intervention
    average_attempts: float
    approved: int = 0
    rejected: int = 0


def parse_line(line: str) -> LogEntry:
    """Structure one log line; a non-conforming line becomes a raw-only entry (never raises)."""
    match = _LINE_RE.match(line)
    if match is None:
        return LogEntry(raw=line)
    return LogEntry(
        raw=line,
        timestamp=match["ts"],
        level=match["level"],
        logger=match["logger"],
        message=match["msg"],
    )


def read_log(
    path: Path | str,
    *,
    limit: int | None = None,
    query: str | None = None,
    level: str | None = None,
) -> list[LogEntry]:
    """Read + parse the monitor log, newest last. Optional case-insensitive ``query`` substring and
    ``level`` filter; ``limit`` keeps only the last N matching lines (the Logs tail). Missing file →
    empty list (the daemon may not have logged yet), never an error."""
    text = _read_text(path)
    if text is None:
        return []
    entries = [parse_line(line) for line in text.splitlines() if line.strip()]
    if level is not None:
        wanted = level.upper()
        entries = [e for e in entries if (e.level or "") == wanted]
    if query:
        needle = query.lower()
        entries = [e for e in entries if needle in e.raw.lower()]
    if limit is not None and limit >= 0:
        entries = entries[-limit:]
    return entries


def compute_metrics(entries: list[LogEntry], *, since: str | None = None) -> Metrics:
    """Count the runbook's metric signals across ``entries``. ``since`` (a ``YYYY-MM-DD`` date
    prefix) windows to that day onward — the Metrics page passes today for 'Detected Today'."""
    detected = opened = declined = green = exhausted = 0
    attempts: list[int] = []
    for entry in _in_window(entries, since):
        message = entry.message
        if message is None:
            continue
        opened_match = _OPENED_RE.match(message)
        if opened_match is not None:
            detected += 1
            attempts.append(int(opened_match["attempt"]))
            if opened_match["status"] == _AWAITING:
                opened += 1
            elif opened_match["status"] == _CANCELLED:
                declined += 1
            continue
        if _GREEN_RE.match(message) is not None:
            green += 1
            continue
        if _EXHAUSTED_RE.match(message) is not None:
            exhausted += 1
    average = round(sum(attempts) / len(attempts), 2) if attempts else 0.0
    return Metrics(
        detected=detected,
        opened_missions=opened,
        declined=declined,
        green_ci=green,
        exhausted=exhausted,
        average_attempts=average,
    )


def daemon_prs(entries: list[LogEntry]) -> dict[int, DaemonPr]:
    """The daemon's LATEST mission opening per PR number (last 'opened mission' line wins) — used to
    annotate the Open Missions rows with the daemon's true attempt count and mission id."""
    latest: dict[int, DaemonPr] = {}
    for entry in entries:
        if entry.message is None:
            continue
        match = _OPENED_RE.match(entry.message)
        if match is None:
            continue
        pr = int(match["pr"])
        latest[pr] = DaemonPr(
            pr_number=pr,
            mission_id=match["mission"],
            attempt=int(match["attempt"]),
            status=match["status"],
        )
    return latest


def last_poll(entries: list[LogEntry]) -> tuple[str | None, int | None]:
    """Timestamp + open-PR count of the most recent 'monitoring N open PR(s)' line — the Overview
    health signal (how long since the daemon last polled). ``(None, None)`` if it never has."""
    for entry in reversed(entries):
        if entry.message is None:
            continue
        match = _MONITORING_RE.match(entry.message)
        if match is not None:
            return entry.timestamp, int(match["count"])
    return None, None


def _in_window(entries: list[LogEntry], since: str | None) -> list[LogEntry]:
    if since is None:
        return entries
    return [e for e in entries if e.timestamp is not None and e.timestamp[:10] >= since]


def _read_text(path: Path | str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return None
    except OSError:
        return None
