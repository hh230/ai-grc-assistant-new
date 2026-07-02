/**
 * Risk domain types + scoring. A risk is scored on a 5×5 likelihood/impact matrix
 * (score = likelihood × impact, 1–25) mapped to severity bands. Risk acceptance is a
 * consequential, human-gated action (CLAUDE.md §1 — never auto-accept).
 */

export const RISK_STATUSES = ["open", "mitigating", "accepted", "closed"] as const;
export type RiskStatus = (typeof RISK_STATUSES)[number];

export const RISK_CATEGORIES = [
  "cyber",
  "compliance",
  "privacy",
  "operational",
  "third_party",
  "financial",
] as const;
export type RiskCategory = (typeof RISK_CATEGORIES)[number];

export type Severity = "low" | "medium" | "high" | "critical";

export const LIKELIHOOD_LABELS = [
  "Rare",
  "Unlikely",
  "Possible",
  "Likely",
  "Almost certain",
] as const;
export const IMPACT_LABELS = ["Negligible", "Minor", "Moderate", "Major", "Severe"] as const;

export interface Risk {
  id: string;
  tenantId: string;
  title: string;
  description?: string;
  category: RiskCategory;
  likelihood: number; // 1–5
  impact: number; // 1–5
  status: RiskStatus;
  ownerName: string;
  controlIds: string[];
  mitigationPlan?: string;
  residualLikelihood?: number;
  residualImpact?: number;
  createdByUserId: string;
  createdByName: string;
  createdAt: string;
  updatedAt: string;
  acceptedByName?: string;
  acceptedAt?: string;
}

export function scoreOf(likelihood: number, impact: number): number {
  return Math.max(1, Math.min(5, likelihood)) * Math.max(1, Math.min(5, impact));
}

export function severityOf(score: number): Severity {
  if (score <= 5) return "low";
  if (score <= 10) return "medium";
  if (score <= 15) return "high";
  return "critical";
}

export interface RiskSummary {
  id: string;
  title: string;
  category: RiskCategory;
  likelihood: number;
  impact: number;
  inherentScore: number;
  severity: Severity;
  residualScore: number | null;
  residualSeverity: Severity | null;
  status: RiskStatus;
  ownerName: string;
  controlCount: number;
  updatedAt: string;
}

export function residualScoreOf(risk: Risk): number | null {
  if (risk.residualLikelihood == null || risk.residualImpact == null) return null;
  return scoreOf(risk.residualLikelihood, risk.residualImpact);
}

export function toRiskSummary(risk: Risk): RiskSummary {
  const inherentScore = scoreOf(risk.likelihood, risk.impact);
  const residual = residualScoreOf(risk);
  return {
    id: risk.id,
    title: risk.title,
    category: risk.category,
    likelihood: risk.likelihood,
    impact: risk.impact,
    inherentScore,
    severity: severityOf(inherentScore),
    residualScore: residual,
    residualSeverity: residual == null ? null : severityOf(residual),
    status: risk.status,
    ownerName: risk.ownerName,
    controlCount: risk.controlIds.length,
    updatedAt: risk.updatedAt,
  };
}

export const RISK_TRANSITIONS: Record<RiskStatus, RiskStatus[]> = {
  open: ["mitigating", "accepted", "closed"],
  mitigating: ["accepted", "closed", "open"],
  accepted: ["open", "closed"],
  closed: ["open"],
};

export function canTransitionRisk(from: RiskStatus, to: RiskStatus): boolean {
  return RISK_TRANSITIONS[from].includes(to);
}
