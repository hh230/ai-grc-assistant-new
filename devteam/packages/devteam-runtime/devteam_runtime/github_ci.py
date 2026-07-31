"""Wiring: a real GitHub CI failure -> real logs -> analysis -> the Developer's diff -> the gate.

Reality-first proof of the engineering workflow (ADR 0061): the GitHubActions connector detects a
real CI failure, finds the failing job/step, and downloads the failing job's REAL log. A
FailureAnalyzer normalizes that log into a tool-agnostic AnalyzedFailure, which the existing
Developer agent reasons over generically (AnalysisProposer — no LLM, no tool knowledge) to propose a
real diff. The mission stops at the human approval gate. Nothing applied/committed/pushed; no retry.

``main`` is the runnable entrypoint (real curl, real GitHub; needs GITHUB_TOKEN for logs). The pure
``open_mission_for_run_failure`` wiring is what the tests exercise with a fake connector.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from pathlib import Path

from devteam_agents import AnalysisProposer
from devteam_analysis import (
    AnalyzedFailure,
    FailureAnalyzer,
    RawFailure,
    analyze_failure,
    default_analyzers,
)
from devteam_github import FailingStep, GitHubActions, GitHubError
from devteam_tools import CommandRunner, SubprocessCommandRunner
from dotenv import load_dotenv
from mission_engine.mission import Mission

from devteam_runtime.fix_it_runtime import FixItRuntime
from devteam_runtime.path_resolver import resolve_paths


def analyze_run_failure(
    github: GitHubActions,
    run_id: int,
    *,
    repo_root: str | Path | None = None,
    analyzers: Sequence[FailureAnalyzer] | None = None,
) -> tuple[FailingStep, AnalyzedFailure] | None:
    """Find the failing step, download its real log, and normalize it via the analyzers. Returns the
    step + AnalyzedFailure (category=unknown if unrecognized), or None if there is no failing step.
    When ``repo_root`` is given, the findings' logical paths are resolved to real repository paths
    (the resolver layer) BEFORE the Developer, so it reads real source. Logs need a token."""
    step = github.find_failing_step(run_id)
    if step is None:
        return None
    log = github.download_job_log(step.job_id)
    analysis = analyze_failure(
        RawFailure(step.step_name, log), analyzers or default_analyzers()
    )
    if analysis is None:
        analysis = AnalyzedFailure(
            category="unknown", summary=f"Unrecognized failure in step {step.step_name!r}."
        )
    if repo_root is not None:
        analysis = resolve_paths(analysis, repo_root)
    return step, analysis


def open_mission_for_run_failure(
    github: GitHubActions,
    run_id: int,
    *,
    repo_root: str | Path,
    git_runner: CommandRunner,
    analyzers: Sequence[FailureAnalyzer] | None = None,
) -> Mission | None:
    """Analyze a run's failure and open the gated fix-it mission whose (generic) Developer proposes
    a real diff from the normalized model. Returns the mission paused at the gate, or None."""
    result = analyze_run_failure(github, run_id, repo_root=repo_root, analyzers=analyzers)
    if result is None:
        return None
    _step, analysis = result
    runtime = FixItRuntime(
        propose=AnalysisProposer(analysis, repo_root), runner=git_runner, repo_root=repo_root
    )
    return runtime.open_fix_it(analysis.summary)


def main(argv: Sequence[str] | None = None) -> int:
    """Reality proof: watch -> detect a CI failure -> download its log -> normalize -> Developer
    proposes a real patch -> stop at the gate. Prints each stage. Nothing is applied."""
    parser = argparse.ArgumentParser(description="Propose a patch for a real CI failure's logs.")
    parser.add_argument("--repo", required=True, help="owner/name of the GitHub repo to watch")
    parser.add_argument("--run", type=int, default=None, help="run id (default: latest failure)")
    parser.add_argument("--repo-root", default=".", help="working tree the patch targets")
    args = parser.parse_args(argv)

    # Local-dev credential injection: load a repo-root .env if present. A no-op in CI/prod, where
    # the token is injected into the environment directly (GitHub/K8s Secrets, Vault, --env-file).
    # The code still reads os.environ, agnostic to how the token got there — not a startup file.
    load_dotenv(Path(args.repo_root) / ".env")
    token = os.environ.get("GITHUB_TOKEN")
    github = GitHubActions(SubprocessCommandRunner(), args.repo, token=token)

    run_id = args.run
    if run_id is None:
        failure = github.latest_failure()
        if failure is None:
            print(f"{args.repo}: no CI failure in the recent runs.")
            return 0
        run_id = failure.id
        print(f"latest CI failure: {failure.summary}\n  {failure.html_url}")

    step = github.find_failing_step(run_id)
    if step is None:
        print(f"run {run_id}: no failing step found.")
        return 0
    print(f"failing job/step: {step.job_name!r} -> {step.step_name!r}")

    try:
        log = github.download_job_log(step.job_id)
    except GitHubError as exc:
        print(f"could not download the real logs: {exc}")
        if not token:
            print("set GITHUB_TOKEN (read-only, actions:read) in the env, then re-run.")
        return 1

    analysis = analyze_failure(RawFailure(step.step_name, log), default_analyzers())
    if analysis is None:
        analysis = AnalyzedFailure(
            category="unknown", summary="No analyzer recognized this failure."
        )
    analysis = resolve_paths(analysis, args.repo_root)  # logical -> real repo paths
    print(
        f"analysis: category={analysis.category}, confidence={analysis.confidence:.0%}, "
        f"{len(analysis.findings)} finding(s) across {len(analysis.affected_files)} file(s)"
    )
    for finding in analysis.findings[:12]:
        print(f"  {finding.file}:{finding.line}: {finding.message} [{finding.code}]")

    runtime = FixItRuntime(
        propose=AnalysisProposer(analysis, args.repo_root),
        runner=SubprocessCommandRunner(),
        repo_root=args.repo_root,
    )
    mission = runtime.open_fix_it(analysis.summary)
    print(f"\nopened mission {mission.id}: status={mission.status.value}")
    print("Developer's proposal:\n" + _indent(mission.step_results[0].output))
    reason = mission.approval.reason if mission.approval is not None else "(none)"
    print(f"approval gate: {reason}")
    return 0


def _indent(text: str) -> str:
    return "\n".join(f"    {line}" for line in text.splitlines())


if __name__ == "__main__":
    raise SystemExit(main())
