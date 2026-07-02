/**
 * Policy domain types. A policy is an authored governance document that maps to controls and
 * moves through an approval workflow before publication (human gate — CLAUDE.md §1).
 */

export const POLICY_STATUSES = ["draft", "in_review", "published", "archived"] as const;
export type PolicyStatus = (typeof POLICY_STATUSES)[number];

export interface Policy {
  id: string;
  tenantId: string;
  title: string;
  summary?: string;
  body?: string;
  status: PolicyStatus;
  ownerName: string;
  controlIds: string[];
  createdByUserId: string;
  createdByName: string;
  createdAt: string;
  updatedAt: string;
  approvedByName?: string;
  approvedAt?: string;
}

export interface PolicySummary {
  id: string;
  title: string;
  summary?: string;
  status: PolicyStatus;
  ownerName: string;
  controlCount: number;
  updatedAt: string;
}

export function toPolicySummary(policy: Policy): PolicySummary {
  return {
    id: policy.id,
    title: policy.title,
    summary: policy.summary,
    status: policy.status,
    ownerName: policy.ownerName,
    controlCount: policy.controlIds.length,
    updatedAt: policy.updatedAt,
  };
}

/** Allowed status transitions (the workflow graph). */
export const POLICY_TRANSITIONS: Record<PolicyStatus, PolicyStatus[]> = {
  draft: ["in_review", "archived"],
  in_review: ["published", "draft", "archived"],
  published: ["archived", "draft"],
  archived: ["draft"],
};

export function canTransition(from: PolicyStatus, to: PolicyStatus): boolean {
  return POLICY_TRANSITIONS[from].includes(to);
}
