"""The FastAPI app — thin JSON routes over the three read sources (RuntimeGateway, log_reader,
deployment) plus the two approve/reject actions. No logic here beyond shaping responses; every
runtime decision stays inside the services the gateway calls.

``create_app(config, gateway_factory=...)`` builds the app; the gateway is constructed lazily on
first use so importing the app (and testing it with an injected fake) needs no token or network. The
static single-page UI is served from ``static/``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from devteam_github import GitHubError
from devteam_runtime import ApprovalError
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from devteam_dashboard import (
    agents_view,
    connectors_view,
    deployment,
    executive_view,
    jobs_view,
    lifecycle_view,
    log_reader,
    pipeline_view,
)
from devteam_dashboard.actions_log import ActionsLog
from devteam_dashboard.config import DashboardConfig, load_config
from devteam_dashboard.deployment import WorkerStatus
from devteam_dashboard.runtime_gateway import RuntimeGateway

_STATIC_DIR = Path(__file__).parent / "static"
# The daemon polls on an interval; no poll within this multiple of it → health degrades.
_STALE_POLL_FACTOR = 3.0
_MIN_STALE_SECONDS = 180.0


def create_app(
    config: DashboardConfig | None = None,
    *,
    gateway_factory: Callable[[], RuntimeGateway] | None = None,
) -> FastAPI:
    settings = config or load_config()
    build_gateway = gateway_factory or (lambda: RuntimeGateway.build(settings))
    cache: dict[str, RuntimeGateway] = {}

    def gateway() -> RuntimeGateway:
        if "instance" not in cache:
            cache["instance"] = build_gateway()
        return cache["instance"]

    app = FastAPI(title="Dev Team — Operations Dashboard", docs_url=None, redoc_url=None)
    if _STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(str(_STATIC_DIR / "index.html"))

    @app.get("/api/overview")
    def overview() -> dict[str, object]:
        entries = log_reader.read_log(settings.log_path)
        poll_ts, poll_open = log_reader.last_poll(entries)
        worker = deployment.worker_status(settings.label)
        errors: list[str] = []
        open_pr_count: int | None = None
        try:
            open_pr_count = len(gateway().open_prs())
        except GitHubError as exc:
            errors.append(f"GitHub: {exc}")
        return {
            "workers": [_worker_json(worker)],
            "last_poll": poll_ts,
            "last_poll_open_prs": poll_open,
            "repos": settings.repos,
            "repo": settings.repo,
            "health": _health(worker, poll_ts, settings.poll_seconds),
            "open_pr_count": open_pr_count,
            "errors": errors,
        }

    @app.get("/api/executive")
    def executive() -> dict[str, object]:
        # The command-center overview: a live roll-up of the Mission + Agent Experiences (missions,
        # agents, throughput, fleet decisions, queue health, utilization). Aggregation only.
        return executive_view.read_executive_overview(settings.journal_path)

    @app.get("/api/agents")
    def agents() -> dict[str, object]:
        # The live agent roster, rebuilt from the runtime journal the monitor writes. Read-only and
        # resilient: a missing/partial journal yields the seeded idle roster, never an error.
        return agents_view.read_agents(settings.journal_path)

    @app.get("/api/agents/{agent_key:path}")
    def agent_detail(agent_key: str) -> dict[str, object]:
        # One agent's detail for the Agent Inspector drill-down (its live state + own session
        # timeline). ``:path`` so a "platform:qa" key with its colon is captured whole.
        return agents_view.read_agent(settings.journal_path, agent_key)

    @app.get("/api/jobs")
    def jobs() -> dict[str, object]:
        # The AI Organization Jobs — the recurring departmental responsibilities, read from the
        # snapshot the organization service writes. Read-only; a missing snapshot is not an error.
        return jobs_view.read_jobs(settings.jobs_path)

    @app.get("/api/connectors")
    def connectors() -> dict[str, object]:
        # The AI Organization Connectors — the read-only integration layer, with each connector's
        # health/latency/last-sync and the Owner Jobs that consume it (joined from jobs.json).
        return connectors_view.read_connectors(settings.connectors_path, settings.jobs_path)

    @app.get("/api/lifecycle")
    def lifecycle() -> dict[str, object]:
        # The Mission Lifecycle: every active problem's state + the metrics, read from the snapshot
        # the coordinator writes. Viewer-only — the LifecycleCoordinator owns the state.
        return lifecycle_view.read_lifecycle(settings.lifecycle_path)

    @app.get("/api/pipeline")
    def pipeline() -> dict[str, object]:
        # The observed mission executions (Mission Experience), rebuilt from the runtime journal.
        return pipeline_view.read_pipeline(settings.journal_path)

    @app.get("/api/pipeline/{mission_id}")
    def pipeline_mission(mission_id: str) -> dict[str, object]:
        # One mission's timeline (its ordered sessions + flow). The initial load for the timeline.
        return pipeline_view.read_mission(settings.journal_path, mission_id)

    @app.get("/api/pipeline/{mission_id}/stream")
    async def pipeline_mission_stream(mission_id: str, request: Request) -> StreamingResponse:
        # Live Pipeline: SSE over the SAME read_mission payload — the timeline made live. Pushes a
        # frame only when the mission actually changes; no gateway, no journal parsing (view only).
        stream = pipeline_view.mission_event_stream(
            settings.journal_path, mission_id, is_disconnected=request.is_disconnected
        )
        return StreamingResponse(
            stream,
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/missions")
    def missions() -> dict[str, object]:
        try:
            rows = gateway().open_prs()
        except GitHubError as exc:
            return {"missions": [], "count": 0, "error": f"GitHub: {exc}"}
        rows.sort(key=lambda r: (not r.actionable, r.pr_number))  # actionable first, then PR number
        daemon = log_reader.daemon_prs(log_reader.read_log(settings.log_path))
        out: list[dict[str, object]] = []
        for row in rows:
            seen = daemon.get(row.pr_number)
            out.append(
                {
                    **asdict(row),
                    "daemon_attempt": seen.attempt if seen else None,
                    "daemon_mission_id": seen.mission_id if seen else None,
                    "daemon_status": seen.status if seen else None,
                    "max_attempts": settings.max_attempts,
                }
            )
        return {"missions": out, "count": len(out)}

    @app.get("/api/missions/{pr_number}")
    def mission_details(pr_number: int) -> dict[str, object]:
        return asdict(gateway().materialize(pr_number))

    @app.post("/api/missions/{mission_id}/approve")
    def approve(mission_id: str, pr_number: int | None = None) -> dict[str, object]:
        return _decide("approve", gateway(), mission_id, pr_number)

    @app.post("/api/missions/{mission_id}/reject")
    def reject(mission_id: str, pr_number: int | None = None) -> dict[str, object]:
        return _decide("reject", gateway(), mission_id, pr_number)

    @app.get("/api/logs")
    def logs(tail: int = 300, q: str | None = None, level: str | None = None) -> dict[str, object]:
        entries = log_reader.read_log(settings.log_path, limit=tail, query=q, level=level)
        return {"lines": [asdict(e) for e in entries], "log_path": str(settings.log_path)}

    @app.get("/api/metrics")
    def metrics(window: str = "today") -> dict[str, object]:
        since = ActionsLog.today() if window == "today" else None
        entries = log_reader.read_log(settings.log_path)
        stats = log_reader.compute_metrics(entries, since=since)
        counts = ActionsLog(settings.actions_log_path).counts(since=since)
        worker = deployment.worker_status(settings.label)
        return {
            "window": window,
            "detected": stats.detected,
            "opened_missions": stats.opened_missions,
            "approved": counts.approved,
            "rejected": counts.rejected,
            "declined": stats.declined,
            "average_attempts": stats.average_attempts,
            "green_ci": stats.green_ci,
            "exhausted": stats.exhausted,
            "running_workers": 1 if worker.running else 0,
        }

    @app.get("/api/settings")
    def settings_view() -> dict[str, object]:
        worker = deployment.worker_status(settings.label)
        try:
            gh_ok, gh_msg = gateway().github_ok()
        except Exception as exc:  # noqa: BLE001 - surface any wiring failure as a degraded signal
            gh_ok, gh_msg = False, str(exc)
        return {
            "repos": settings.repos,
            "repo": settings.repo,
            "poll_seconds": settings.poll_seconds,
            "max_attempts": settings.max_attempts,
            "repo_root": str(settings.repo_root),
            "log_path": str(settings.log_path),
            "plist_path": str(settings.plist_path),
            "actions_log_path": str(settings.actions_log_path),
            "worker": _worker_json(worker),
            "github": {"ok": gh_ok, "message": gh_msg},
            "program": settings.launch_agent.program if settings.launch_agent else [],
        }

    return app


def _decide(
    action: str, gateway: RuntimeGateway, mission_id: str, pr_number: int | None
) -> dict[str, object]:
    try:
        result = (
            gateway.approve(mission_id, pr_number=pr_number)
            if action == "approve"
            else gateway.reject(mission_id, pr_number=pr_number)
        )
    except ApprovalError as exc:
        # The mission isn't in the store (stale id, or the process restarted) — re-open Details.
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except GitHubError as exc:
        raise HTTPException(status_code=502, detail=f"GitHub error: {exc}") from exc
    return asdict(result)


def _worker_json(worker: WorkerStatus) -> dict[str, object]:
    return {
        "label": worker.label,
        "present": worker.present,
        "running": worker.running,
        "state": worker.state,
        "pid": worker.pid,
    }


def _health(worker: WorkerStatus, poll_ts: str | None, poll_seconds: float | None) -> str:
    """A blunt health signal for Overview: down if the worker isn't running, degraded if it is but
    hasn't polled recently (or we can't tell), else healthy."""
    if not worker.running:
        return "down"
    age = _seconds_since(poll_ts)
    if age is None:
        return "degraded"
    stale = max((poll_seconds or 60.0) * _STALE_POLL_FACTOR, _MIN_STALE_SECONDS)
    return "healthy" if age <= stale else "degraded"


def _seconds_since(timestamp: str | None) -> float | None:
    if timestamp is None:
        return None
    try:
        moment = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S,%f")
    except ValueError:
        return None
    return max(0.0, (datetime.now() - moment).total_seconds())


app = create_app()
