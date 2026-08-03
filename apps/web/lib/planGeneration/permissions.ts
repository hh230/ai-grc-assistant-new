/**
 * Who can cross the ADR 0044 approval gate for a Governance Plan — client-safe (no server-only
 * imports), so both the API route/service (server) and the Report's approve button (client) agree
 * on the same rule without duplicating it.
 */

import type { UserRole } from "@/lib/auth/roles";

/** Roles from `apps/web`'s RBAC roster (`lib/auth/roles.ts`) that map to grc-api's hard-coded
 * `"approver"` role check (`ApproveMissionStepCommand.authorize`, `mission_application`). Every
 * other role can read the Report but cannot cross the approval gate. Least-privilege: only the
 * roles whose own `ROLE_META` description covers approvals get it. */
export const APPROVER_ROLES: readonly UserRole[] = ["owner", "admin", "compliance_manager"];

export function canApprovePlanGeneration(roles: readonly UserRole[]): boolean {
  return roles.some((role) => APPROVER_ROLES.includes(role));
}
