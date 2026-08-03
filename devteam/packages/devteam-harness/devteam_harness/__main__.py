"""CLI — the command a release gate runs, and the command that reproduces a failure.

    python -m devteam_harness --count 1000 --db harness.db
    python -m devteam_harness --seed 1            # reproduce exactly one reported failure
"""

from __future__ import annotations

import argparse
import sys

from devteam_harness.campaign import check_scenario, run_campaign
from devteam_harness.results import ResultStore


def _reproduce(seed: int) -> int:
    """Re-run a single seed and print its transcript — the payoff of seed-based reproduction."""
    checked = check_scenario(seed)
    result = checked.result
    print(f"seed {seed}  ({result.organization.posture.value}, {result.organization.tenant_id})")
    print(f"  concluded={result.concluded}  turns={result.turn_count}")
    if result.error:
        print(f"  error: [{result.error_type}] {result.error}")
    print("  transcript:")
    for turn in result.turns:
        answer = "SKIPPED" if turn.skipped else repr(turn.answer)
        print(f"    {turn.sequence:>3}. {turn.question_id:<34} {turn.value_type:<12} {answer}")
    if checked.violations:
        print(f"  violations ({len(checked.violations)}):")
        for violation in checked.violations:
            print(f"    - {violation.name}: {violation.detail}")
    else:
        print("  violations: none")
    return 0 if checked.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="devteam_harness", description=__doc__)
    parser.add_argument("--count", type=int, default=1000, help="scenarios to run")
    parser.add_argument("--start-seed", type=int, default=0)
    parser.add_argument("--db", default=":memory:", help="SQLite path for results")
    parser.add_argument("--seed", type=int, help="reproduce a single seed and exit")
    parser.add_argument(
        "--fail-on-violation",
        action="store_true",
        help="exit non-zero when any invariant is violated (use for a release gate)",
    )
    parser.add_argument(
        "--team",
        action="store_true",
        help="run the full QA agent team (explorer, breaker, verifier, regression, reporter)",
    )
    args = parser.parse_args(argv)

    if args.seed is not None:
        return _reproduce(args.seed)

    if args.team:
        from devteam_harness.agents import run_team

        outcome = run_team(count=args.count, start_seed=args.start_seed)
        print(outcome.report.render())
        return 1 if (args.fail_on_violation and not outcome.ok) else 0

    store = ResultStore(args.db)
    summary, _ = run_campaign(count=args.count, start_seed=args.start_seed, store=store)

    print(f"scenarios : {summary.scenarios}")
    print(f"passed    : {summary.passed}")
    print(f"failed    : {summary.failed}")
    if summary.violations_by_name:
        print("violations by invariant:")
        for name, total in summary.violations_by_name.items():
            seeds = store.failing_seeds(summary.run_id, name=name)[:5]
            reproduce = " ".join(f"--seed {s}" for s in seeds[:1])
            print(f"  {name:<32} {total:>6}   reproduce: python -m devteam_harness {reproduce}")
    else:
        print("violations: none")

    if args.db != ":memory:":
        print(f"results   : {args.db}")

    return 1 if (args.fail_on_violation and not summary.ok) else 0


if __name__ == "__main__":
    sys.exit(main())
