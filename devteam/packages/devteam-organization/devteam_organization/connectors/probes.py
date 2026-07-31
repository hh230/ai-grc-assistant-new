"""Real inspectors the jobs use — HTTP, TLS, report files, and worker status.

Every probe is a real measurement of the world, and every probe FAILS SOFT: a network error, a bad
certificate, or a missing report becomes a not-ok result object, never an exception. That lets
a job turn a real failure into evidence (a Mission) while an *absent* source simply yields nothing —
the no-fabrication contract. Each probe is injectable, so jobs are unit-tested with canned results.
"""

from __future__ import annotations

import json
import socket
import ssl
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# --- HTTP (website health + security headers) --------------------------------------------------


@dataclass(frozen=True)
class HttpResult:
    url: str
    ok: bool
    status: int | None
    elapsed_ms: float | None
    headers: dict[str, str] = field(default_factory=dict)
    error: str = ""


HttpProbe = Callable[[str], HttpResult]


def make_http_probe(*, timeout: float = 10.0) -> HttpProbe:
    """A real HTTP GET probe: status, response time, and (lower-cased) response headers. A transport
    error is a not-ok result, not an exception."""

    def probe(url: str) -> HttpResult:
        request = urllib.request.Request(  # noqa: S310 - operator-configured monitoring targets
            url, method="GET", headers={"User-Agent": "devteam-ciso-monitor"}
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                elapsed = (time.perf_counter() - started) * 1000.0
                headers = {k.lower(): v for k, v in response.headers.items()}
                status = int(response.status)
                return HttpResult(url, 200 <= status < 400, status, elapsed, headers)
        except urllib.error.HTTPError as exc:
            elapsed = (time.perf_counter() - started) * 1000.0
            headers = {k.lower(): v for k, v in (exc.headers.items() if exc.headers else [])}
            return HttpResult(url, False, int(exc.code), elapsed, headers, f"HTTP {exc.code}")
        except Exception as exc:
            return HttpResult(url, False, None, None, {}, repr(exc))

    return probe


# --- TLS certificate ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CertResult:
    host: str
    ok: bool
    days_to_expiry: int | None
    hostname_valid: bool
    issuer: str = ""
    error: str = ""


CertProbe = Callable[[str], CertResult]


def make_cert_probe(*, timeout: float = 10.0) -> CertProbe:
    """A real TLS probe: validate the hostname and read days-to-expiry + issuer from the peer
    certificate. A hostname mismatch is ``hostname_valid=False``; any connection error is not-ok."""

    def probe(host: str) -> CertResult:
        hostname, _, port_text = host.partition(":")
        port = int(port_text) if port_text.isdigit() else 443
        context = ssl.create_default_context()
        try:
            with (
                socket.create_connection((hostname, port), timeout=timeout) as sock,
                context.wrap_socket(sock, server_hostname=hostname) as tls,
            ):
                cert = tls.getpeercert()
        except ssl.CertificateError as exc:
            return CertResult(host, False, None, False, "", repr(exc))
        except Exception as exc:
            return CertResult(host, False, None, True, "", repr(exc))
        days = _days_to_expiry(cert)
        error = "" if days is not None else "no notAfter"
        return CertResult(host, days is not None, days, True, _issuer(cert), error)

    return probe


def _issuer(cert: object) -> str:
    """The certificate issuer's org/common name, if present — a real field, never invented."""
    if not isinstance(cert, dict):
        return ""
    issuer = cert.get("issuer")
    if not isinstance(issuer, (list, tuple)):
        return ""
    for rdn in issuer:
        if not isinstance(rdn, (list, tuple)):
            continue
        for pair in rdn:
            if isinstance(pair, (list, tuple)) and len(pair) == 2:
                key, value = pair[0], pair[1]
                if key in ("organizationName", "commonName"):
                    return str(value)
    return ""


def _days_to_expiry(cert: object) -> int | None:
    if not isinstance(cert, dict):
        return None
    not_after = cert.get("notAfter")
    if not isinstance(not_after, str):
        return None
    try:
        expiry = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return (expiry - datetime.now(timezone.utc)).days


# --- report files (dependency / secret / regression / compliance) ------------------------------


def read_json_report(path: str | Path) -> object | None:
    """Read a report the project ALREADY produces. Missing/blank/unreadable ⇒ None (nothing to act
    on — never a fabricated finding)."""
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        data: object = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    return data


# --- worker status (runtime health + supervisor) -----------------------------------------------


@dataclass(frozen=True)
class WorkerStatus:
    label: str
    running: bool
    pid: int | None
    last_exit: int | None


WorkerProbe = Callable[[], Sequence[WorkerStatus]]


def make_launchctl_worker_probe(labels: Sequence[str], *, timeout: float = 10.0) -> WorkerProbe:
    """Report whether each named LaunchAgent is currently running, from ``launchctl list``. A worker
    with no PID is down (launchd could not keep it alive) — a real signal a job escalates."""

    wanted = tuple(labels)

    def probe() -> Sequence[WorkerStatus]:
        try:
            completed = subprocess.run(
                ["launchctl", "list"], capture_output=True, text=True, timeout=timeout, check=False
            )
        except (OSError, subprocess.SubprocessError):
            return tuple(WorkerStatus(label, False, None, None) for label in wanted)
        rows = _parse_launchctl(completed.stdout)
        return tuple(
            rows.get(label, WorkerStatus(label, False, None, None)) for label in wanted
        )

    return probe


def _parse_launchctl(text: str) -> dict[str, WorkerStatus]:
    out: dict[str, WorkerStatus] = {}
    for line in text.splitlines()[1:]:  # skip the "PID\tStatus\tLabel" header
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        pid_text, status_text, label = parts
        pid = int(pid_text) if pid_text.lstrip("-").isdigit() and pid_text != "-" else None
        last_exit = int(status_text) if status_text.lstrip("-").isdigit() else None
        out[label] = WorkerStatus(label, pid is not None, pid, last_exit)
    return out
