/**
 * Governance coverage — computes control coverage across frameworks from the evidence links
 * (P6). A control is "covered" when at least one evidence artifact is linked to it. This is
 * the cross-cutting relationship that powers governance dashboards. Tenant-scoped. Node-only.
 */

import { ForbiddenError } from "@/lib/errors";
import { can } from "@/lib/auth/permissions";
import type { ActorContext } from "@/lib/auth/actor";
import { FRAMEWORKS } from "@/lib/frameworks/catalog";
import { evidenceRepository } from "@/lib/evidence/repository";

export type ControlStatus = "covered" | "gap";

export interface ControlCoverage {
  id: string;
  code: string;
  title: string;
  description: string;
  evidenceCount: number;
  status: ControlStatus;
}

export interface FrameworkCoverage {
  id: string;
  name: string;
  shortName: string;
  region: string;
  total: number;
  covered: number;
  coveragePct: number;
  controls: ControlCoverage[];
}

export interface CoverageReport {
  frameworks: FrameworkCoverage[];
  overall: {
    totalControls: number;
    coveredControls: number;
    coveragePct: number;
    gaps: number;
    evidenceCount: number;
  };
}

function pct(part: number, total: number): number {
  return total === 0 ? 0 : Math.round((part / total) * 100);
}

export async function computeCoverage(actor: ActorContext): Promise<CoverageReport> {
  if (!can(actor.roles, "read", "framework")) {
    throw new ForbiddenError("You are not permitted to view governance data.");
  }

  const evidence = await evidenceRepository.list(actor.tenantId);
  const counts = new Map<string, number>();
  for (const item of evidence) {
    for (const controlId of item.controlIds) {
      counts.set(controlId, (counts.get(controlId) ?? 0) + 1);
    }
  }

  const frameworks: FrameworkCoverage[] = FRAMEWORKS.map((framework) => {
    const controls: ControlCoverage[] = framework.controls.map((control) => {
      const evidenceCount = counts.get(control.id) ?? 0;
      return {
        id: control.id,
        code: control.code,
        title: control.title,
        description: control.description,
        evidenceCount,
        status: evidenceCount > 0 ? "covered" : "gap",
      };
    });
    const covered = controls.filter((c) => c.status === "covered").length;
    return {
      id: framework.id,
      name: framework.name,
      shortName: framework.shortName,
      region: framework.region,
      total: controls.length,
      covered,
      coveragePct: pct(covered, controls.length),
      controls,
    };
  });

  const totalControls = frameworks.reduce((sum, f) => sum + f.total, 0);
  const coveredControls = frameworks.reduce((sum, f) => sum + f.covered, 0);

  return {
    frameworks,
    overall: {
      totalControls,
      coveredControls,
      coveragePct: pct(coveredControls, totalControls),
      gaps: totalControls - coveredControls,
      evidenceCount: evidence.length,
    },
  };
}

export function findFrameworkCoverage(
  report: CoverageReport,
  frameworkId: string,
): FrameworkCoverage | null {
  return report.frameworks.find((f) => f.id === frameworkId) ?? null;
}
