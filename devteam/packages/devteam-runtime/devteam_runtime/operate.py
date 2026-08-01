"""operate.py — the simplest operator CLI for a supervised run (ADR 0061).

Not a new capability: the minimal glue that OPERATES the existing pieces in ONE process, so no
durable store is needed. It detects a real CI failure, opens the gated fix-it mission (Developer
diagnosis + diff), and prints it for review — stopping at the human approval gate. Only with an
explicit ``--land`` (the human's approval) does it resume the mission through the ApprovalGateway to
land the patch (apply -> commit -> push -> open PR). The opener and the gateway share one in-memory
store in this process, so the mission opened here can be approved here.

Without ``--land`` it is read-only (reads CI logs, opens an in-memory mission, reads local source).
``--land`` performs real, gated, outward-facing git/gh actions on the repo — run it yourself.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from pathlib import Path

from devteam_agents import AnalysisProposer
from devteam_github import GitHubActions, GitHubError
from devteam_tools import SubprocessCommandRunner
from dotenv import load_dotenv
from mission_engine.adapters import InMemoryMissionStore
from mission_engine.lifecycle import MissionStatus

from devteam_runtime.approval import ApprovalGateway
from devteam_runtime.fix_it_runtime import FixItRuntime
from devteam_runtime.github_ci import analyze_run_failure


def _indent(text: str) -> str:
    return "\n".join(f"    {line}" for line in text.splitlines())


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover - live operator entrypoint
    parser = argparse.ArgumentParser(description="Diagnose a CI failure; with --land, approve it.")
    parser.add_argument("--repo", required=True, help="owner/name of the GitHub repo")
    parser.add_argument("--repo-root", default=".", help="local checkout the fix targets")
    parser.add_argument("--run", type=int, default=None, help="run id (default: latest failure)")
    parser.add_argument("--land", action="store_true", help="approve + land (real push/PR)")
    args = parser.parse_args(argv)

    load_dotenv(Path(args.repo_root) / ".env")
    git = SubprocessCommandRunner()
    github = GitHubActions(git, args.repo, token=os.environ.get("GITHUB_TOKEN"))
    store = InMemoryMissionStore()  # shared by the opener + the gateway (one process)

    run_id = args.run
    if run_id is None:
        failure = github.latest_failure()
        if failure is None:
            print(f"{args.repo}: no CI failure in the recent runs.")
            return 0
        run_id = failure.id
        print(f"CI failure: {failure.summary}\n  {failure.html_url}")

    try:
        result = analyze_run_failure(github, run_id, repo_root=args.repo_root)
    except GitHubError as exc:
        print(f"could not read the failure logs: {exc}")
        return 1
    if result is None:
        print(f"run {run_id}: no failing step found.")
        return 0

    step, analysis = result
    print(f"failing step: {step.job_name!r} -> {step.step_name!r}")
    print(
        f"diagnosis: category={analysis.category}, {len(analysis.findings)} finding(s), "
        f"confidence={analysis.confidence:.0%}"
    )
    for finding in analysis.findings[:12]:
        print(f"  {finding.file}:{finding.line}: {finding.message} [{finding.code}]")

    runtime = FixItRuntime(
        propose=AnalysisProposer(analysis, args.repo_root),
        runner=git,
        repo_root=args.repo_root,
        store=store,
    )
    mission = runtime.open_fix_it(analysis.summary)
    proposal = mission.step_results[0].output if mission.step_results else "(no output)"
    print(f"\nmission {mission.id}: {mission.status.value}")
    print("proposal:\n" + _indent(proposal))

    if mission.status is not MissionStatus.AWAITING_APPROVAL:
        # No patch → the mission ended fail-safe (human intervention required); no gate, nothing
        # to approve. This is the owner's rule: no meaningless approval when there is no patch.
        print("\n[no patch] the Developer diagnosed but produced no patch — human intervention "
              "required. The mission ended fail-safe; there is nothing to approve.")
        return 0
    if not args.land:
        print("\n[observe] paused at the approval gate. Re-run with --land to approve + land it.")
        return 0
    print("\n[land] approving — landing the patch (apply, commit, push, open PR)...")
    landed = ApprovalGateway(store, repo_root=args.repo_root, git_runner=git).approve(mission.id)
    print(f"mission {landed.id}: {landed.status.value}")
    print("result:\n" + _indent(landed.step_results[-1].output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
