import type { Alignment, Severity } from "../types";
import type { ScoringRule } from "./types";

const ALIGNMENT_WEIGHT: Record<Alignment, number> = {
  strong: 100,
  partial: 55,
  gap: 10,
  unknown: 40,
};

const SEVERITY_WEIGHT: Record<Severity, number> = {
  high: 100,
  medium: 60,
  low: 25,
  info: 5,
};

/** Generic rule used for every framework without a bespoke override below. */
const defaultRule: ScoringRule = {
  computeCompliance(frameworks) {
    if (frameworks.length === 0) return 0;
    const total = frameworks.reduce((sum, f) => sum + ALIGNMENT_WEIGHT[f.alignment], 0);
    return Math.round(total / frameworks.length);
  },
  computeRisk(findings) {
    if (findings.length === 0) return 0;
    const total = findings.reduce((sum, f) => sum + SEVERITY_WEIGHT[f.severity], 0);
    return Math.round(total / findings.length);
  },
};

/**
 * Per-framework overrides, keyed by the framework catalog id (`lib/frameworks/catalog.ts`).
 * Empty today — every framework uses `defaultRule`. Add an entry here to give a specific
 * framework its own weighting (e.g. NCA ECC might weight "gap" more harshly); no other file
 * needs to change.
 */
const FRAMEWORK_RULES: Record<string, ScoringRule> = {};

export function getScoringRule(frameworkId: string | null): ScoringRule {
  if (frameworkId && FRAMEWORK_RULES[frameworkId]) return FRAMEWORK_RULES[frameworkId];
  return defaultRule;
}
