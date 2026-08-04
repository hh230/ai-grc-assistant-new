"""The dashboard — one self-contained HTML file summarising a run.

Deliberately a FILE, not a server. A release gate produces evidence that must outlive the process
that made it: attachable to a CI run, openable from a PR, mailable to whoever asks "what did we
actually check before shipping". A localhost dashboard cannot do any of that.

It renders the Reporter's output rather than re-deriving anything. There is exactly one definition
of "what went wrong" in this harness; a dashboard with its own opinion would drift from the report
and start disagreeing with the gate about the same run.

**It shows what did NOT run as prominently as what failed.** A summary that reads "0 failures"
while browser coverage never executed is the precise lie this whole package exists to prevent, so
unreachable/unavailable findings are surfaced as a banner rather than buried as one more row.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path

from devteam_harness.agents.base import Severity
from devteam_harness.agents.reporter import Report

# Findings that mean "a check did not happen" rather than "a check failed". These must never be
# read as health — see the module docstring.
#
# `route_unreachable` and `page_unreachable` belong here for the same reason as the obvious ones:
# a request that timed out measured NOTHING about that route. The first live dashboard showed
# "did not run: 0" while thirteen routes had timed out, which is precisely the false confidence
# this module exists to prevent.
DID_NOT_RUN_KINDS = frozenset(
    {
        "surface_unreachable",
        "browser_unavailable",
        "login_failed",
        "session_lost",
        "route_unreachable",
        "page_unreachable",
    }
)

_SEVERITY_COLOUR = {
    Severity.CRASH: "#b91c1c",
    Severity.INVARIANT: "#b45309",
    Severity.SUSPICIOUS: "#525252",
}


@dataclass(frozen=True)
class Totals:
    """The headline numbers, and the caveat that qualifies them."""

    findings: int
    classes: int
    crashes: int
    invariants: int
    suspicious: int
    coverage_gaps: int

    @property
    def verdict(self) -> str:
        """Whether this run says the PRODUCT is shippable.

        Severity already encodes "would you block a release on this", so the verdict uses it
        instead of counting findings. A run where all 42 pages rendered correctly is not a
        failure because the dev server restarted underneath it and the harness recovered — that
        happened, and calling it FAIL is the kind of inaccuracy that gets a gate ignored.

        Coverage gaps override everything, including severity: they are graded SUSPICIOUS but they
        mean we did not look, and not looking is never a pass.
        """
        if self.coverage_gaps:
            # Not "PASS with a note" — a run with unmeasured coverage has not passed.
            return "INCOMPLETE"
        return "FAIL" if (self.crashes or self.invariants) else "PASS"


def summarise(report: Report) -> Totals:
    by_severity = {severity: 0 for severity in Severity}
    for finding_class in report.classes:
        by_severity[finding_class.severity] += finding_class.count
    return Totals(
        findings=report.total_findings,
        classes=len(report.classes),
        crashes=by_severity[Severity.CRASH],
        invariants=by_severity[Severity.INVARIANT],
        suspicious=by_severity[Severity.SUSPICIOUS],
        coverage_gaps=sum(
            finding_class.count
            for finding_class in report.classes
            if finding_class.kind in DID_NOT_RUN_KINDS
        ),
    )


def render_html(report: Report, *, title: str = "AI Test Harness") -> str:
    """One standalone page. No external assets — it must open from a CI artifact zip offline."""
    totals = summarise(report)
    parts = [
        "<meta charset='utf-8'>",
        f"<title>{html.escape(title)}</title>",
        _STYLE,
        f"<h1>{html.escape(title)}</h1>",
        _verdict_block(totals),
    ]

    if totals.coverage_gaps:
        parts.append(
            "<div class='gap'><strong>Coverage gap.</strong> Part of this run did not execute. "
            "The counts below describe what was checked, not the whole system — treating this as "
            "a pass would be false confidence.</div>"
        )

    parts.append(_counters_table(report))
    parts.append(_findings_table(report))
    return "\n".join(parts)


def write_html(report: Report, path: Path, *, title: str = "AI Test Harness") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(report, title=title), encoding="utf-8")
    return path


def _verdict_block(totals: Totals) -> str:
    css_class = {"PASS": "pass", "FAIL": "fail", "INCOMPLETE": "incomplete"}[totals.verdict]
    cells = [
        ("findings", totals.findings),
        ("classes", totals.classes),
        ("crashes", totals.crashes),
        ("invariants", totals.invariants),
        ("suspicious", totals.suspicious),
        ("did not run", totals.coverage_gaps),
    ]
    scoreboard = "".join(
        f"<div class='cell'><span class='n'>{value}</span><span class='k'>{label}</span></div>"
        for label, value in cells
    )
    return (
        f"<div class='verdict {css_class}'>{totals.verdict}</div>"
        f"<div class='score'>{scoreboard}</div>"
    )


def _counters_table(report: Report) -> str:
    if not report.stats:
        return ""
    rows = []
    for agent, stats in sorted(report.stats.items()):
        counters = ", ".join(f"{key}={value}" for key, value in sorted(stats.items()))
        rows.append(
            f"<tr><td class='agent'>{html.escape(agent)}</td>"
            f"<td>{html.escape(counters) or '—'}</td></tr>"
        )
    return (
        "<h2>What each agent did</h2><table><thead><tr><th>agent</th><th>counters</th></tr>"
        "</thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def _findings_table(report: Report) -> str:
    if not report.classes:
        return "<h2>Findings</h2><p class='none'>No findings.</p>"

    rows = []
    for finding_class in report.classes:
        colour = _SEVERITY_COLOUR[finding_class.severity]
        seeds = ", ".join(str(seed) for seed in finding_class.seeds[:10])
        if len(finding_class.seeds) > 10:
            seeds += f" (+{len(finding_class.seeds) - 10} more)"
        rows.append(
            "<tr>"
            f"<td><span class='sev' style='background:{colour}'>"
            f"{finding_class.severity.value.upper()}</span></td>"
            f"<td class='kind'>{html.escape(finding_class.kind)}</td>"
            f"<td class='count'>{finding_class.count}</td>"
            f"<td>{html.escape(finding_class.example_detail)}"
            # The reproduce line is the point of the whole report: the first thing anyone does
            # with a bug report is try to see it themselves.
            f"<div class='repro'>{html.escape(finding_class.reproduce)}</div>"
            + (f"<div class='seeds'>seeds: {html.escape(seeds)}</div>" if seeds else "")
            + "</td></tr>"
        )
    return (
        "<h2>Findings</h2><table><thead><tr><th>severity</th><th>kind</th><th>n</th>"
        "<th>example &amp; how to reproduce</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


_STYLE = """<style>
:root { color-scheme: light dark; }
body { font: 14px/1.5 ui-sans-serif, system-ui, sans-serif; margin: 2rem auto; max-width: 60rem;
       padding: 0 1rem; }
h1 { font-size: 1.35rem; margin-bottom: 1rem; }
h2 { font-size: 1rem; margin-top: 2rem; text-transform: uppercase; letter-spacing: .06em;
     opacity: .65; }
.verdict { display: inline-block; font-weight: 700; letter-spacing: .1em; padding: .4rem .9rem;
           border-radius: .4rem; color: #fff; }
.verdict.pass { background: #15803d; }
.verdict.fail { background: #b91c1c; }
.verdict.incomplete { background: #b45309; }
.score { display: flex; flex-wrap: wrap; gap: 1.5rem; margin: 1rem 0 0; }
.cell { display: flex; flex-direction: column; }
.cell .n { font-size: 1.5rem; font-weight: 600; }
.cell .k { font-size: .75rem; text-transform: uppercase; letter-spacing: .06em; opacity: .6; }
.gap { margin: 1.25rem 0; padding: .75rem 1rem; border-left: 4px solid #b45309;
       background: rgba(180,83,9,.09); border-radius: 0 .3rem .3rem 0; }
table { width: 100%; border-collapse: collapse; margin-top: .5rem; }
th { text-align: left; font-size: .72rem; text-transform: uppercase; letter-spacing: .06em;
     opacity: .55; border-bottom: 1px solid currentColor; padding: .4rem .5rem; }
td { padding: .55rem .5rem; border-bottom: 1px solid rgba(128,128,128,.25); vertical-align: top; }
td.agent, td.kind { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
td.count { text-align: right; font-variant-numeric: tabular-nums; }
.sev { color: #fff; font-size: .68rem; font-weight: 700; letter-spacing: .05em;
       padding: .12rem .4rem; border-radius: .25rem; }
.repro, .seeds { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .78rem;
                 margin-top: .35rem; opacity: .75; word-break: break-all; }
.none { opacity: .6; }
@media (max-width: 640px) { .score { gap: 1rem; } body { margin: 1rem auto; } }
</style>"""
