/**
 * Deterministic scoring engine (V2-P2.5). The AI only identifies and classifies (finding
 * severity, framework alignment, recommendation priority); every aggregate score is a pure,
 * reproducible function of that structured output — never a number the model invents.
 * Rules are keyed by framework so a new framework (SAMA, SOC 2, ...) can define its own
 * weighting later as a data addition here, without touching the aggregation logic
 * (CLAUDE.md §13 — frameworks are data, not code).
 */

import type { AnalysisFinding, FrameworkCoverage } from "../types";

export const MATURITY_LEVELS = [
  "Initial",
  "Developing",
  "Defined",
  "Managed",
  "Optimized",
] as const;
export type MaturityLevel = (typeof MATURITY_LEVELS)[number];

export interface ScoringRule {
  /** 0–100 compliance sub-score from every FrameworkCoverage entry resolved to this rule. */
  computeCompliance(frameworks: FrameworkCoverage[]): number;
  /** 0–100 risk sub-score (higher = riskier) from every finding resolved to this rule. */
  computeRisk(findings: AnalysisFinding[]): number;
}
