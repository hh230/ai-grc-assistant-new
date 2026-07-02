import { FRAMEWORKS } from "@/lib/frameworks/catalog";
import type { AnalysisFinding, FrameworkCoverage } from "../types";
import { getScoringRule } from "./rules";
import { MATURITY_LEVELS, type MaturityLevel } from "./types";

export type { MaturityLevel };
export { MATURITY_LEVELS };

/** Matches the AI's freeform framework name against the canonical catalog, if possible. */
export function normalizeFrameworkId(name: string): string | null {
  const norm = name.trim().toLowerCase();
  const match = FRAMEWORKS.find(
    (f) =>
      f.shortName.toLowerCase() === norm ||
      f.name.toLowerCase() === norm ||
      f.id.toLowerCase() === norm,
  );
  return match?.id ?? null;
}

function groupBy<T>(items: T[], keyOf: (item: T) => string | null): Map<string | null, T[]> {
  const groups = new Map<string | null, T[]>();
  for (const item of items) {
    const key = keyOf(item);
    const group = groups.get(key);
    if (group) group.push(item);
    else groups.set(key, [item]);
  }
  return groups;
}

/** Overall compliance score (0–100): the average of each resolved framework's own sub-score. */
export function computeComplianceScore(frameworks: FrameworkCoverage[]): number {
  if (frameworks.length === 0) return 0;
  const groups = groupBy(frameworks, (f) => normalizeFrameworkId(f.framework));
  const subScores = [...groups.entries()].map(([frameworkId, group]) =>
    getScoringRule(frameworkId).computeCompliance(group),
  );
  return Math.round(subScores.reduce((a, b) => a + b, 0) / subScores.length);
}

/** Overall risk score (0–100, higher = riskier): average of each resolved framework's sub-score. */
export function computeRiskScore(findings: AnalysisFinding[]): number {
  if (findings.length === 0) return 0;
  const groups = groupBy(findings, (f) => (f.framework ? normalizeFrameworkId(f.framework) : null));
  const subScores = [...groups.entries()].map(([frameworkId, group]) =>
    getScoringRule(frameworkId).computeRisk(group),
  );
  return Math.round(subScores.reduce((a, b) => a + b, 0) / subScores.length);
}

/** 5-band maturity level derived from the compliance score — descriptive label, not a new input. */
export function deriveMaturityLevel(complianceScore: number): MaturityLevel {
  if (complianceScore >= 90) return "Optimized";
  if (complianceScore >= 75) return "Managed";
  if (complianceScore >= 55) return "Defined";
  if (complianceScore >= 30) return "Developing";
  return "Initial";
}
