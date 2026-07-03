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
import type { AppLocale } from "@/i18n/routing";
import { getReportLabels, type ReportLabels } from "./i18n";
import type { Report, ReportKind } from "./types";

const SEVERITY_ORDER: Severity[] = ["critical", "high", "medium", "low"];

export async function buildReport(
  actor: ActorContext,
  kind: ReportKind,
  locale: AppLocale,
): Promise<Report> {
  if (!can(actor.roles, "read", "report")) {
    throw new ForbiddenError("You are not permitted to view reports.");
  }
  const labels = getReportLabels(locale);
  const meta = labels.meta[kind];
  const base: Omit<Report, "kpis" | "sections"> = {
    kind,
    title: meta.title,
    subtitle: meta.subtitle,
    tenantName: actor.tenantId,
    generatedAt: new Date().toISOString(),
    generatedBy: actor.userName,
  };

  if (kind === "compliance") return { ...base, ...(await complianceContent(actor, labels)) };
  if (kind === "risk") return { ...base, ...(await riskContent(actor, labels)) };
  return { ...base, ...(await executiveContent(actor, labels)) };
}

async function executiveContent(actor: ActorContext, l: ReportLabels) {
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
      { label: l.kpis.complianceCoverage, value: `${coverage.overall.coveragePct}%` },
      { label: l.kpis.controlGaps, value: String(coverage.overall.gaps) },
      { label: l.kpis.openRisks, value: String(open) },
      { label: l.kpis.criticalRisks, value: String(critical) },
      { label: l.kpis.evidenceArtifacts, value: String(evidenceCount) },
      { label: l.kpis.publishedPolicies, value: String(published) },
    ],
    sections: [
      {
        heading: l.sections.frameworkCoverage,
        table: {
          title: l.tables.frameworkCoverageTitle,
          columns: [l.columns.framework, l.columns.controls, l.columns.covered, l.columns.coverage],
          rows: coverage.frameworks.map((f) => [
            f.shortName,
            String(f.total),
            String(f.covered),
            `${f.coveragePct}%`,
          ]),
        },
      },
      {
        heading: l.sections.topRisks,
        table: {
          title: l.tables.highestScoringRisks,
          columns: [l.columns.risk, l.columns.category, l.columns.score, l.columns.severity, l.columns.status],
          rows: topRisks.map((r) => [
            r.title,
            l.riskCategory[r.category],
            String(r.inherentScore),
            l.severity[r.severity],
            l.riskStatus[r.status],
          ]),
        },
      },
    ],
  };
}

async function complianceContent(actor: ActorContext, l: ReportLabels) {
  const coverage = await computeCoverage(actor);
  const policies = await policyRepository.list(actor.tenantId);

  const gaps = coverage.frameworks.flatMap((f) =>
    f.controls.filter((c) => c.status === "gap").map((c) => [f.shortName, c.code, c.title]),
  );

  return {
    kpis: [
      { label: l.kpis.overallCoverage, value: `${coverage.overall.coveragePct}%` },
      {
        label: l.kpis.controlsCovered,
        value: `${coverage.overall.coveredControls}/${coverage.overall.totalControls}`,
      },
      { label: l.kpis.openGaps, value: String(coverage.overall.gaps) },
      { label: l.kpis.policies, value: String(policies.length) },
    ],
    sections: [
      {
        heading: l.sections.frameworkCoverage,
        table: {
          title: l.tables.frameworkCoverageTitle,
          columns: [l.columns.framework, l.columns.region, l.columns.controls, l.columns.covered, l.columns.coverage],
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
        heading: l.sections.controlGaps,
        narrative: gaps.length === 0 ? l.tables.noControlGaps : undefined,
        table: {
          title: l.tables.controlsWithoutEvidence,
          columns: [l.columns.framework, l.columns.control, l.columns.title],
          rows: gaps,
        },
      },
      {
        heading: l.sections.policyRegister,
        table: {
          title: l.tables.policyRegisterTitle,
          columns: [l.columns.policy, l.columns.status, l.columns.owner, l.columns.mappedControls],
          rows: policies.map((p) => [p.title, p.status, p.ownerName, String(p.controlIds.length)]),
        },
      },
    ],
  };
}

async function riskContent(actor: ActorContext, l: ReportLabels) {
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
      { label: l.kpis.totalRisks, value: String(risks.length) },
      { label: l.kpis.critical, value: String(bySeverity.critical) },
      { label: l.kpis.high, value: String(bySeverity.high) },
      { label: l.kpis.accepted, value: String(byStatus["accepted"] ?? 0) },
      { label: l.kpis.averageScore, value: String(avg) },
    ],
    sections: [
      {
        heading: l.sections.severityDistribution,
        table: {
          title: l.tables.risksBySeverity,
          columns: [l.columns.severity, l.columns.count],
          rows: SEVERITY_ORDER.map((s) => [l.severity[s], String(bySeverity[s])]),
        },
      },
      {
        heading: l.sections.riskRegister,
        table: {
          title: l.tables.allRisks,
          columns: [
            l.columns.risk,
            l.columns.category,
            l.columns.inherent,
            l.columns.residual,
            l.columns.status,
            l.columns.owner,
          ],
          rows: risks.map((r) => [
            r.title,
            l.riskCategory[r.category],
            `${r.inherentScore} (${l.severity[r.severity]})`,
            r.residualScore != null ? `${r.residualScore} (${l.severity[r.residualSeverity!]})` : "—",
            l.riskStatus[r.status],
            r.ownerName,
          ]),
        },
      },
    ],
  };
}
