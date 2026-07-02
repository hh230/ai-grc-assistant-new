/**
 * Reporting service — aggregates governance coverage (P7), risks (P8), evidence (P6), and
 * policies (P7) into the three report types. Read-only; requires `read` on `report`.
 * Tenant-scoped. Node-only.
 */

import { ForbiddenError } from "@/lib/errors";
import { can } from "@/lib/auth/permissions";
import type { ActorContext } from "@/lib/auth/actor";
import { computeCoverage } from "@/lib/governance/coverage";
import { listRisks } from "@/lib/risk/service";
import { toRiskSummary, type Severity } from "@/lib/risk/types";
import { evidenceRepository } from "@/lib/evidence/repository";
import { policyRepository } from "@/lib/policies/repository";
import { REPORT_META, type Report, type ReportKind } from "./types";

const SEVERITY_ORDER: Severity[] = ["critical", "high", "medium", "low"];

export async function buildReport(actor: ActorContext, kind: ReportKind): Promise<Report> {
  if (!can(actor.roles, "read", "report")) {
    throw new ForbiddenError("You are not permitted to view reports.");
  }
  const meta = REPORT_META[kind];
  const base: Omit<Report, "kpis" | "sections"> = {
    kind,
    title: meta.title,
    subtitle: meta.subtitle,
    tenantName: actor.tenantId,
    generatedAt: new Date().toISOString(),
    generatedBy: actor.userName,
  };

  if (kind === "compliance") return { ...base, ...(await complianceContent(actor)) };
  if (kind === "risk") return { ...base, ...(await riskContent(actor)) };
  return { ...base, ...(await executiveContent(actor)) };
}

async function executiveContent(actor: ActorContext) {
  const coverage = await computeCoverage(actor);
  const risks = (await listRisks(actor)).map(toRiskSummary);
  const policies = await policyRepository.list(actor.tenantId);
  const evidenceCount = (await evidenceRepository.list(actor.tenantId)).length;

  const critical = risks.filter((r) => r.severity === "critical").length;
  const open = risks.filter((r) => r.status === "open" || r.status === "mitigating").length;
  const published = policies.filter((p) => p.status === "published").length;

  const topRisks = [...risks].sort((a, b) => b.inherentScore - a.inherentScore).slice(0, 5);

  return {
    kpis: [
      { label: "Compliance coverage", value: `${coverage.overall.coveragePct}%` },
      { label: "Control gaps", value: String(coverage.overall.gaps) },
      { label: "Open risks", value: String(open) },
      { label: "Critical risks", value: String(critical) },
      { label: "Evidence artifacts", value: String(evidenceCount) },
      { label: "Published policies", value: String(published) },
    ],
    sections: [
      {
        heading: "Framework coverage",
        table: {
          title: "Coverage by framework",
          columns: ["Framework", "Controls", "Covered", "Coverage"],
          rows: coverage.frameworks.map((f) => [
            f.shortName,
            String(f.total),
            String(f.covered),
            `${f.coveragePct}%`,
          ]),
        },
      },
      {
        heading: "Top risks by inherent score",
        table: {
          title: "Highest-scoring risks",
          columns: ["Risk", "Category", "Score", "Severity", "Status"],
          rows: topRisks.map((r) => [
            r.title,
            r.category,
            String(r.inherentScore),
            r.severity,
            r.status,
          ]),
        },
      },
    ],
  };
}

async function complianceContent(actor: ActorContext) {
  const coverage = await computeCoverage(actor);
  const policies = await policyRepository.list(actor.tenantId);

  const gaps = coverage.frameworks.flatMap((f) =>
    f.controls.filter((c) => c.status === "gap").map((c) => [f.shortName, c.code, c.title]),
  );

  return {
    kpis: [
      { label: "Overall coverage", value: `${coverage.overall.coveragePct}%` },
      {
        label: "Controls covered",
        value: `${coverage.overall.coveredControls}/${coverage.overall.totalControls}`,
      },
      { label: "Open gaps", value: String(coverage.overall.gaps) },
      { label: "Policies", value: String(policies.length) },
    ],
    sections: [
      {
        heading: "Coverage by framework",
        table: {
          title: "Framework coverage",
          columns: ["Framework", "Region", "Controls", "Covered", "Coverage"],
          rows: coverage.frameworks.map((f) => [
            f.shortName,
            f.region,
            String(f.total),
            String(f.covered),
            `${f.coveragePct}%`,
          ]),
        },
      },
      {
        heading: "Control gaps",
        narrative:
          gaps.length === 0
            ? "No control gaps — every catalogued control has linked evidence."
            : undefined,
        table: {
          title: "Controls without evidence",
          columns: ["Framework", "Control", "Title"],
          rows: gaps,
        },
      },
      {
        heading: "Policies",
        table: {
          title: "Policy register",
          columns: ["Policy", "Status", "Owner", "Mapped controls"],
          rows: policies.map((p) => [p.title, p.status, p.ownerName, String(p.controlIds.length)]),
        },
      },
    ],
  };
}

async function riskContent(actor: ActorContext) {
  const risks = (await listRisks(actor)).map(toRiskSummary);

  const bySeverity: Record<Severity, number> = { low: 0, medium: 0, high: 0, critical: 0 };
  const byStatus: Record<string, number> = {};
  let scoreSum = 0;
  for (const risk of risks) {
    bySeverity[risk.severity] += 1;
    byStatus[risk.status] = (byStatus[risk.status] ?? 0) + 1;
    scoreSum += risk.inherentScore;
  }
  const avg = risks.length ? Math.round((scoreSum / risks.length) * 10) / 10 : 0;

  return {
    kpis: [
      { label: "Total risks", value: String(risks.length) },
      { label: "Critical", value: String(bySeverity.critical) },
      { label: "High", value: String(bySeverity.high) },
      { label: "Accepted", value: String(byStatus["accepted"] ?? 0) },
      { label: "Average score", value: String(avg) },
    ],
    sections: [
      {
        heading: "Severity distribution",
        table: {
          title: "Risks by severity",
          columns: ["Severity", "Count"],
          rows: SEVERITY_ORDER.map((s) => [s, String(bySeverity[s])]),
        },
      },
      {
        heading: "Risk register",
        table: {
          title: "All risks",
          columns: ["Risk", "Category", "Inherent", "Residual", "Status", "Owner"],
          rows: risks.map((r) => [
            r.title,
            r.category,
            `${r.inherentScore} (${r.severity})`,
            r.residualScore != null ? `${r.residualScore} (${r.residualSeverity})` : "—",
            r.status,
            r.ownerName,
          ]),
        },
      },
    ],
  };
}
